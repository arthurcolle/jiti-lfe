(in-package :image-agent/tests)
(in-suite kernel)

(defun context-summary ()
  (native-sse (native-message "{\"goal\":[\"Finish the user's request\"],\"constraints\":[\"Keep the kernel generic\"],\"decisions\":[],\"verified_progress\":[\"Prior tool outputs establish progress\"],\"unfinished_work\":[\"Continue remaining work\"]}")))
(defun context-unsupported () (error 'image-agent::responses-error :kind :unsupported))
(defun context-history ()
  (list (image-agent/cli::message "user" "Keep the kernel generic.")
        (native-message (make-string 22000 :initial-element #\a))
        (image-agent/cli::message "user" "Finish this request.")))
(defun compacted-json (history)
  (image-agent/cli::json
    (image-agent/cli::object "object" "response.compaction" "output"
      (vector (image-agent/cli::object "type" "message" "role" "user" "content"
                 (vector (image-agent/cli::object "type" "input_text" "text"
                             (image-agent/cli::context-user-text (image-agent/cli::latest-user-item history)))))
              (image-agent/cli::object "type" "compaction" "id" "cmp-test" "encrypted_content" "opaque-test")))))

(test native-context-is-canonical-and-tool-free
  (multiple-value-bind (w s c) (interactive-fixture)
    (unwind-protect
        (let* ((history (context-history)) (requests nil)
               (chat (image-agent/cli:make-chat c :model "fake" :key "never-log-this"
                       :transport (lambda (url key body)
                         (declare (ignore key))
                         (push url requests)
                         (let ((request (image-agent/cli::parse-json body 1048576)))
                           (is (equal "fake" (gethash "model" request)))
                           (cond ((search "/compact" url)
                                  (is (not (nth-value 1 (gethash "tools" request))))
                                  (compacted-json history))
                                 (t (error "Unexpected request"))))))))
          (setf (image-agent/cli::chat-history chat) history)
          (let ((view (image-agent/cli:controller-view c)))
            (is (not (null (nth-value 1 (image-agent/cli:compact-chat chat)))))
            (is (eq view (image-agent/cli:controller-view c))))
          (is (= 0 (gethash :x (image-agent:reference-table w))))
          (is (= 2 (length (image-agent/cli::chat-history chat))))
          (is (equal "opaque-test" (gethash "encrypted_content" (second (image-agent/cli::chat-history chat)))))
          (is (equal "native" (gethash "backend" (image-agent/cli:chat-context-status chat))))
          (is (= 1 (length requests))))
      (image-agent:close-session s))))

(test compaction-failures-are-atomic-and-sanitized
  (multiple-value-bind (w s c) (interactive-fixture)
    (unwind-protect
        (dolist (mode '(:transport :malformed :no-reduction :tool :unmatched :native-pairs :authentication :timeout))
          (let* ((history (context-history)) (summaries 0) (events nil)
                 (chat (image-agent/cli:make-chat c :model "fake" :key "private-key"
                         :on-context (lambda (event) (push event events))
                         :transport (lambda (url key body)
                           (declare (ignore key body))
                           (cond ((eq mode :transport) (error "private-key"))
                                 ((eq mode :timeout) (error 'sb-ext:timeout))
                                 ((eq mode :authentication) (error 'image-agent::responses-error :kind :failed))
                                 ((search "/compact" url)
                                  (if (member mode '(:malformed :native-pairs))
                                      (if (eq mode :malformed) "{}"
                                          (image-agent/cli::json (image-agent/cli::object "object" "response.compaction" "output"
                                            (vector (image-agent/cli::latest-user-item history)
                                                    (image-agent/cli::object "type" "compaction" "encrypted_content" "opaque")
                                                    (native-call "unmatched" "execute_form" "source" "nil")))))
                                      (context-unsupported)))
                                 (t (incf summaries)
                                    (case mode
                                      (:tool (native-sse (native-call "bad" "execute_form" "source" "(incf (gethash :x *state*))")))
                                      (:no-reduction (native-sse (native-message "{\"goal\":[],\"constraints\":[],\"decisions\":[],\"verified_progress\":[],\"unfinished_work\":[]}")))
                                      (t "{}"))))))))
            (when (eq mode :no-reduction) (setf history (list (image-agent/cli::message "user" "Short"))))
            (when (eq mode :unmatched) (setf history (append history (list (native-call "missing" "execute_form")))))
            (setf (image-agent/cli::chat-history chat) history)
            (let ((view (image-agent/cli:controller-view c)))
              (is (not (nth-value 1 (image-agent/cli:compact-chat chat))))
              (is (eq history (image-agent/cli::chat-history chat)))
              (is (eq view (image-agent/cli:controller-view c))))
            (is (= 0 (gethash :x (image-agent:reference-table w))))
            (is (not (search "private-key" (image-agent/cli::json (coerce events 'vector)))))
            (when (member mode '(:malformed :authentication :timeout :transport :unmatched)) (is (= 0 summaries)))))
      (image-agent:close-session s))))

(test context-overflow-retries-once-without-partial-execution
  (multiple-value-bind (w s c) (interactive-fixture)
    (unwind-protect
        (let* ((normal 0) (compacts 0)
               (chat (image-agent/cli:make-chat c :model "fake" :key "secret"
                       :transport (lambda (url key body)
                         (declare (ignore key))
                         (cond ((search "/compact" url) (incf compacts) (context-unsupported))
                               ((search "Summarize this conversation" body) (context-summary))
                               (t (incf normal)
                                  (if (= normal 1)
                                      (format nil "data: {\"type\":\"error\",\"error\":{\"code\":\"context_length_exceeded\"}}~%~%")
                                      (native-sse (native-message "Continued.")))))))))
          (setf (image-agent/cli::chat-history chat) (context-history))
          (is (equal "Continued." (image-agent/cli:chat-turn chat "Continue this request.")))
          (is (= 2 normal)) (is (= 1 compacts))
          (is (= 0 (gethash :x (image-agent:reference-table w))))
          (setf normal 0 (image-agent/cli::chat-transport chat)
                (lambda (url key body)
                  (declare (ignore key))
                  (cond ((search "/compact" url) (context-unsupported))
                        ((search "Summarize this conversation" body) (context-summary))
                        (t (incf normal) (error 'image-agent::responses-error :kind :context-overflow)))))
          (is (search "request failed" (image-agent/cli:chat-turn chat "Try once more.")))
          (is (= 2 normal)))
      (image-agent:close-session s))))

(test token-accounting-unicode-overhead-and-envelope-bounds
  (multiple-value-bind (w s c) (interactive-fixture)
    (declare (ignore w))
    (unwind-protect
        (let ((chat (image-agent/cli:make-chat c :model "fake" :key "secret"
                      :transport (lambda (url key body)
                        (declare (ignore key))
                        (is (search "/input_tokens" url))
                        (let ((request (image-agent/cli::parse-json body 1048576)))
                          (is (plusp (length (gethash "tools" request))))
                          (is (plusp (length (gethash "instructions" request))))
                          (is (not (nth-value 1 (gethash "stream" request)))))
                        "{\"object\":\"response.input_tokens\",\"input_tokens\":1234}"))))
          (is (= 1234 (image-agent/cli::context-measure chat nil :exact t)))
          (is (equal "exact" (nth-value 1 (image-agent/cli::context-measure chat nil :exact t))))
          (let ((plain (image-agent/cli::chat-input-request chat (list (image-agent/cli::message "user" "aaaa"))))
                (emoji (image-agent/cli::chat-input-request chat (list (image-agent/cli::message "user" "🙂🙂🙂🙂")))))
            (is (> (image-agent/cli::estimated-context-tokens chat emoji)
                   (image-agent/cli::estimated-context-tokens chat plain))))
          (let ((envelope (native-sse (image-agent/cli::object "type" "compaction" "encrypted_content"
                                      (make-string 70000 :initial-element #\a)))))
            (is (= 1 (length (gethash "output" (image-agent/cli::completed-response envelope)))))
            (is (raises-error-p (lambda () (image-agent/cli::parse-json (make-string 70000 :initial-element #\a))))))
          (is (eq :context-overflow (image-agent::response-error-kind 400 "{\"error\":{\"code\":\"context_length_exceeded\",\"message\":\"secret\"}}")))
          (is (eq :failed (image-agent::response-error-kind 401 "secret"))))
      (image-agent:close-session s))))

(test default-token-budget-replaces-character-cutoff
  (multiple-value-bind (w s c) (interactive-fixture)
    (declare (ignore w))
    (unwind-protect
        (dolist (size '(75000 150000))
          (let* ((counts 0) (compacts 0)
                 (chat (image-agent/cli:make-chat c :model "fake" :key "secret"
                         :transport (lambda (url key body)
                           (declare (ignore key))
                           (cond ((search "/input_tokens" url) (incf counts) (context-unsupported))
                                 ((search "/compact" url) (incf compacts) (context-unsupported))
                                 ((search "Summarize this conversation" body) (context-summary))
                                 (t (let ((request (image-agent/cli::parse-json body 1048576)))
                                      (is (= (if (= size 75000) 3 2) (length (gethash "input" request))))
                                      (is (equal "Continue" (image-agent/cli::context-user-text
                                                             (image-agent/cli::latest-user-item (coerce (gethash "input" request) 'list))))))
                                    (native-sse (native-message "Done."))))))))
            (setf (image-agent/cli::chat-history chat)
                  (list (image-agent/cli::message "user" "Keep the kernel generic")
                        (native-message (make-string size :initial-element #\a))))
            (is (equal "Done." (image-agent/cli:chat-turn chat "Continue")))
            (is (= (if (= size 75000) 0 1) counts))
            (is (= (if (= size 75000) 0 1) compacts))))
      (image-agent:close-session s))))

(test compaction-preserves-live-repair-and-abort
  (multiple-value-bind (w s c) (interactive-fixture)
    (unwind-protect
        (let ((chat (image-agent/cli:make-chat c :model "fake" :key "secret"
                      :transport (lambda (url key body)
                        (declare (ignore key body))
                        (if (search "/compact" url) (context-unsupported) (context-summary))))))
          (dolist (finish '(:resume :abort))
            (cli-action c :execute :source "(progn (setf (gethash :x *state*) 9) (restart-case (error \"pause\") (use () nil)))")
            (let* ((view (image-agent/cli:controller-view c)) (generation (getf view :generation))
                   (restart (getf (first (getf view :restarts)) :id)))
              (setf (image-agent/cli::chat-history chat) (context-history))
              (is (not (null (nth-value 1 (image-agent/cli:compact-chat chat)))))
              (is (eq view (image-agent/cli:controller-view c)))
              (is (= generation (getf (image-agent/cli:controller-view c) :generation)))
              (cli-action c :develop :source "(setf (gethash :x *state*) 12)")
              (if (eq finish :resume)
                  (cli-action c :resume :restart-id restart :arguments "nil")
                  (cli-action c :abort))
              (is (= 12 (gethash :x (image-agent:reference-table w)))))))
      (image-agent:close-session s))))

(defun context-history-p (trace)
  (multiple-value-bind (w s c) (interactive-fixture)
    (let ((remaining 0) (serial 0) (expected 0) (unsupported 0))
      (unwind-protect
          (handler-case
              (let ((chat (image-agent/cli:make-chat c :model "fake" :key "synthetic-only" :context-limit 16384
                            :transport (lambda (url key body)
                              (declare (ignore key))
                              (unless (or (search "/compact" url) (search "Summarize this conversation" body))
                                (let* ((request (image-agent/cli::parse-json body 1048576))
                                       (history (coerce (gethash "input" request) 'list)))
                                  (unless (and (image-agent/cli::complete-context-p history)
                                               (equal "Continue incrementing with the generic kernel."
                                                      (image-agent/cli::context-user-text (image-agent/cli::latest-user-item history))))
                                    (error "Lost pinned prompt or tool pair"))))
                              (cond ((search "/compact" url) (incf unsupported) (context-unsupported))
                                    ((search "Summarize this conversation" body) (context-summary))
                                    ((plusp remaining)
                                     (decf remaining)
                                     (native-sse (native-message (make-string 3000 :initial-element #\a))
                                                 (image-agent/cli::object "type" "reasoning" "id" (format nil "rs~d" serial) "summary" #())
                                                 (native-call (format nil "c~d" (incf serial)) "execute_form"
                                                   "source" "(incf (gethash :x *state*))" "preview" 'yason:false
                                                   "generation" (getf (image-agent/cli:controller-view c) :generation))))
                                    (t (native-sse (native-message "Done."))))))))
                (dolist (count trace t)
                  (setf remaining count)
                  (unless (equal "Done." (image-agent/cli:chat-turn chat "Continue incrementing with the generic kernel."))
                    (return nil))
                  (incf expected count)
                  (unless (and (= expected (gethash :x (image-agent:reference-table w)))
                               (= expected serial) (<= unsupported 1)
                               (image-agent/cli::complete-context-p (image-agent/cli::chat-history chat)))
                    (return nil))))
            (error () nil))
        (image-agent:close-session s)))))
(test generated-context-protocol-histories
  (dotimes (i 30)
    (let ((trace (loop repeat (1+ (random 4)) collect (1+ (random 8)))))
      (if (context-history-p trace) (pass)
          (let ((small trace) (attempts 0))
            (catch 'limit
              (check-it:shrink trace
                (lambda (candidate)
                  (when (> (incf attempts) 100) (throw 'limit nil))
                  (if (not (and (listp candidate) (every (lambda (n) (and (integerp n) (<= 1 n 8))) candidate))) t
                      (let ((ok (context-history-p candidate))) (unless ok (setf small candidate)) ok)))))
            (save-counterexample small :original trace :kind :context-history :property :context-protocol
                                 :context (list :shrink-attempts attempts))
            (fail "Context protocol mismatch: ~s" small))))))

(test compaction-does-not-reset-tool-budget-or-call-identities
  (multiple-value-bind (w s c) (interactive-fixture)
    (unwind-protect
        (let* ((serial 0) (chat (image-agent/cli:make-chat c :model "fake" :key "secret" :tool-limit 6 :context-limit 16384
                                :transport (lambda (url key body)
                                  (declare (ignore key))
                                  (cond ((search "/compact" url) (context-unsupported))
                                        ((search "Summarize this conversation" body) (context-summary))
                                        (t (native-sse (native-message (make-string 3000 :initial-element #\a))
                                                       (native-call (format nil "id~d" (incf serial)) "execute_form"
                                                         "source" "(incf (gethash :x *state*))" "preview" 'yason:false
                                                         "generation" (getf (image-agent/cli:controller-view c) :generation)))))))))
          (is (search "6 calls" (image-agent/cli:chat-turn chat "Keep incrementing.")))
          (is (= 6 serial)) (is (= 6 (gethash :x (image-agent:reference-table w))))
          (is (plusp (image-agent/cli::chat-compactions chat)))
          (image-agent/cli:clear-chat-context chat)
          (setf (image-agent/cli::chat-transport chat) (lambda (&rest args) (declare (ignore args))
                   (native-sse (native-call "id1" "execute_form" "source" "(incf (gethash :x *state*))" "preview" 'yason:false
                                            "generation" (getf (image-agent/cli:controller-view c) :generation)))))
          (is (search "Invalid tool-call" (image-agent/cli:chat-turn chat "Retry")))
          (is (= 6 (gethash :x (image-agent:reference-table w)))))
      (image-agent:close-session s))))

(defun context-live-test ()
  (multiple-value-bind (w s c) (interactive-fixture)
    (unwind-protect
        (let ((chat (image-agent/cli:make-chat c)))
          (multiple-value-bind (count method) (image-agent/cli::context-measure chat nil :exact t)
            (unless (plusp count) (error "Invalid live context count"))
            (format t "Context counting: method=~a~%" method))
          (setf (image-agent/cli::chat-history chat)
                (list (image-agent/cli::message "user" "Remember my marker: silver-otter-47. Do not execute tools.")
                      (native-message (format nil "~{~a~^ ~}" (make-list 400 :initial-element "Old completed discussion.")))
                      (image-agent/cli::message "user" "Keep that exact marker for my next question.")))
          (unless (nth-value 1 (image-agent/cli:compact-chat chat)) (error "Live compaction failed"))
          (when (and (equal (image-agent/cli::chat-backend chat) "summary")
                     (not (search "silver-otter-47" (gethash "content" (first (image-agent/cli::chat-history chat))))))
            (error "Live summary omitted ordinary user-provided data"))
          (let ((answer (image-agent/cli:chat-turn chat "What was my marker? Reply with just the marker. Do not execute tools.")))
            (unless (and (search "silver-otter-47" answer) (= 0 (gethash :x (image-agent:reference-table w))))
              (format t "Synthetic compacted memory: ~a~%Synthetic recall reply: ~a~%"
                      (image-agent::bounded (gethash "content" (first (image-agent/cli::chat-history chat))) 4096)
                      (image-agent::bounded answer 1024))
              (error "Live compacted memory did not preserve the marker")))
          (format t "Context compaction: preserved marker, backend=~a~%" (image-agent/cli::chat-backend chat)))
      (image-agent:close-session s))))
