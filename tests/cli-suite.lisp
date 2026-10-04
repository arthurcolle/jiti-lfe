(in-package :image-agent/tests)
(in-suite kernel)
(defun interactive-fixture (&optional (budget 1000))
  (let* ((w (image-agent:make-reference-world :initial '((:x . 0))))
         (s (image-agent:make-session w :interactive t :store (temp-store) :budget budget
                 :goals (list (cons :zero (lambda () (= 0 (gethash :x (image-agent:reference-table w))))))
                 :invariants (list (cons :safe (lambda () (>= (gethash :x (image-agent:reference-table w)) 0))))))
         (c (image-agent/cli:make-controller s)))
    (values w s c)))
(defun cli-action (c action &rest args)
  (apply #'image-agent/cli::controller-action c
         (image-agent/cli::object "generation" (getf (image-agent/cli:controller-view c) :generation)) action args))
(test interactive-goals-and-rollback
  (multiple-value-bind (w s c) (interactive-fixture)
    (unwind-protect
        (progn
          (is (eq :idle (getf (image-agent/cli:controller-view c) :status)))
          (is (getf (image-agent/cli:controller-view c) :goals-achieved))
          (is (raises-error-p (lambda () (image-agent:rollback-revision s "previous"))))
          (cli-action c :evaluate :source "(progn (setf (gethash :x *state*) 8) (defun f (x) (+ x 8)))")
          (let ((prior (getf (image-agent/cli:controller-view c) :revision)))
            (cli-action c :rollback :revision "1")
            (is (= 0 (gethash :x (image-agent:reference-table w))))
            (is (null (function-value w)))
            (let ((history (image-agent:list-revisions (image-agent:session-store s))))
              (is (= 3 (getf (first history) :sequence)))
              (is (equal prior (getf (first history) :parent)))
              (is (equal (getf (third history) :id) (getf (first history) :rollback-source)))))
          (cli-action c :evaluate :source "(setf (gethash :x *state*) 4)")
          (is (= 4 (gethash :x (image-agent:reference-table w))))
          (cli-action c :abort)
          (is (eq :idle (getf (image-agent/cli:controller-view c) :status))))
      (image-agent:close-session s))))
(test paused-rollback-unwinds-and-invalidates
  (multiple-value-bind (w s c) (interactive-fixture)
    (unwind-protect
        (progn
          (cli-action c :evaluate :source "(progn (setf (gethash :x *state*) 3) (defun f (x) (+ x 3)))")
          (cli-action c :evaluate :source "(unwind-protect (progn (setf (gethash :x *state*) 99) (restart-case (error \"paused\") (use () 42))) (setf (gethash :x *state*) 888))")
          (let* ((old (copy-list (image-agent/cli:controller-view c)))
                 (restart (getf (first (getf old :restarts)) :id)))
            (is (eq :paused (getf old :status)))
            (cli-action c :check)
            (is (eq :paused (getf (image-agent/cli:controller-view c) :status)))
            (cli-action c :rollback :revision "1")
            ;; Unwind cleanup ran before checkpoint restoration/import, not afterwards.
            (is (= 0 (gethash :x (image-agent:reference-table w))))
            (is (null (function-value w)))
            (is (null (getf (image-agent/cli:controller-view c) :restarts)))
            (image-agent/cli::controller-action c (image-agent/cli::object "generation" (getf old :generation))
                                              :resume :restart-id restart :arguments "nil")
            (is (eq :stale-observation (getf (image-agent/cli:controller-view c) :rejected)))
            (is (= 0 (gethash :x (image-agent:reference-table w))))))
      (image-agent:close-session s))))
(test rollback-failures-and-publication
  (dolist (point '(:before-export :after-export :artifacts-flushed :before-pointer :pointer-renamed :published))
    (multiple-value-bind (w s c) (interactive-fixture)
      (unwind-protect
          (progn
            (cli-action c :evaluate :source "(progn (setf (gethash :x *state*) 8) (defun f (x) (+ x 8)))")
            (let ((old image-agent:*store-boundary-hook*))
              (unwind-protect
                  (progn (setf image-agent:*store-boundary-hook* (lambda (p) (when (eq p point) (error "publication fault"))))
                         (cli-action c :rollback :revision "1"))
                (setf image-agent:*store-boundary-hook* old)))
            (if (member point '(:pointer-renamed :published))
                (is (eq :faulted (getf (image-agent/cli:controller-view c) :status)))
                (is (= 8 (gethash :x (image-agent:reference-table w)))))
            (let ((fresh (image-agent:make-reference-world)))
              (image-agent:load-revision fresh (image-agent:session-store s))
              (is (= (if (member point '(:pointer-renamed :published)) 0 8)
                     (gethash :x (image-agent:reference-table fresh))))))
        (image-agent:close-session s))))
  (multiple-value-bind (w s c) (interactive-fixture)
    (unwind-protect
        (progn
          (cli-action c :evaluate :source "(setf (gethash :x *state*) 9)")
          (let ((original (image-agent:world-import w)))
            (setf (image-agent:world-import w)
                  (lambda (dir) (declare (ignore dir)) (setf (gethash :x (image-agent:reference-table w)) 77) (error "bad import")))
            (cli-action c :rollback :revision "1")
            (is (= 9 (gethash :x (image-agent:reference-table w))))
            (setf (image-agent:world-import w) original))
          (setf (image-agent::session-invariants s)
                (list (cons :positive (lambda () (> (gethash :x (image-agent:reference-table w)) 0)))))
          (cli-action c :rollback :revision "1")
          (is (= 9 (gethash :x (image-agent:reference-table w))))
          (cli-action c :rollback :revision "../../CURRENT")
          (is (= 2 (length (image-agent:list-revisions (image-agent:session-store s))))))
      (image-agent:close-session s))))
(defun native-sse (&rest output)
  (format nil "data: ~a~%~%"
          (image-agent/cli::json
            (image-agent/cli::object "type" "response.completed" "response"
              (image-agent/cli::object "id" "response-test" "status" "completed" "output" (coerce output 'vector))))))
(defun native-call (id name &rest pairs)
  (image-agent/cli::object "type" "function_call" "id" (concatenate 'string "fc_" id)
                          "call_id" id "name" name "arguments" (image-agent/cli::json (apply #'image-agent/cli::object pairs))))
(defun native-message (text)
  (image-agent/cli::object "type" "message" "role" "assistant" "content"
                          (vector (image-agent/cli::object "type" "output_text" "text" text))))
(test native-tool-roundtrip-and-reasoning
  (multiple-value-bind (w s c) (interactive-fixture)
    (let ((requests nil) (step 0))
      (unwind-protect
          (let ((chat (image-agent/cli:make-chat c :model "fake" :key "not-a-real-key"
                        :transport (lambda (url key body)
                          (declare (ignore url key))
                          (let ((request (image-agent/cli::parse-json body)))
                            (push request requests)
                            (is (eq 'yason:false (gethash "parallel_tool_calls" request)))
                            (is (= 7 (length (gethash "tools" request)))))
                          (incf step)
                          (case step
                            (1 (native-sse (image-agent/cli::object "type" "reasoning" "id" "rs_test" "summary" #())
                                 (native-call "one" "evaluate_form" "source" "(setf (gethash :x *state*) 7)"
                                              "generation" (getf (image-agent/cli:controller-view c) :generation))))
                            (2 (native-sse (native-message "Changed it.")))
                            (3 (native-sse (native-call "two" "rollback_revision" "revision" "1"
                                              "generation" (getf (image-agent/cli:controller-view c) :generation))))
                            (4 (native-sse (native-message "Restored it."))))))))
            (is (equal "Changed it." (image-agent/cli:chat-turn chat "Set :x to 7")))
            (is (= 7 (gethash :x (image-agent:reference-table w))))
            (let ((input (gethash "input" (first requests))))
              (is (find "reasoning" input :key (lambda (item) (gethash "type" item)) :test #'equal))
              (let ((result (find "function_call_output" input :key (lambda (item) (gethash "type" item)) :test #'equal)))
                (is (equal "one" (gethash "call_id" result)))
                (is (search "accepted" (string-downcase (gethash "output" result))))))
            (is (equal "Restored it." (image-agent/cli:chat-turn chat "Roll back to revision 1")))
            (is (= 0 (gethash :x (image-agent:reference-table w))))
            (is (= 3 (length (image-agent:list-revisions (image-agent:session-store s))))))
        (image-agent:close-session s)))))
(test native-malformed-and-bounded
  (multiple-value-bind (w s c) (interactive-fixture)
    (unwind-protect
        (progn
          (dolist (response (list
                    "data: {\"type\":\"response.function_call_arguments.delta\",\"delta\":\"partial\"}\n\n"
                    (native-sse (native-call "one" "evaluate_form" "source" "(setf (gethash :x *state*) 99)" "generation" 1)
                                (native-call "two" "abort_attempt" "generation" 1))))
            (let ((chat (image-agent/cli:make-chat c :model "fake" :key "secret"
                          :transport (lambda (&rest args) (declare (ignore args)) response))))
              (image-agent/cli:chat-turn chat "Don't change anything")
              (is (= 0 (gethash :x (image-agent:reference-table w))))))
          (let* ((step 0) (chat (image-agent/cli:make-chat c :model "fake" :key "secret" :tool-limit 2
                                :transport (lambda (&rest args) (declare (ignore args))
                                  (native-sse (native-call (format nil "call-~d" (incf step)) "observe_world"))))))
            (is (search "2 calls" (image-agent/cli:chat-turn chat "Inspect")))
            (is (= 2 step))
            (is (equal "function_call_output" (gethash "type" (car (last (image-agent/cli::chat-history chat)))))))
          (let ((tools (image-agent/cli:controller-tools c)))
            (is (raises-error-p (lambda () (image-agent/cli:dispatch-tool tools "unknown" (image-agent/cli::object)))))
            (is (raises-error-p (lambda () (image-agent/cli:dispatch-tool tools "evaluate_form"
                                            (image-agent/cli::object "source" "nil" "generation" "1")))))
            (is (raises-error-p (lambda () (image-agent/cli:dispatch-tool tools "observe_world"
                                            (image-agent/cli::object "extra" 1)))))))
      (image-agent:close-session s))))
(test scripted-terminal-and-adapter-identity
  (multiple-value-bind (w s c) (interactive-fixture)
    (unwind-protect
        (let* ((input (format nil "/model fake~%/mode lisp~%(progn~% (setf (gethash :x *state*) 12))~%/history~%/rollback 1~%/chat hello~%/abort~%/quit~%"))
               (output (with-output-to-string (out)
                         (with-input-from-string (in input)
                           (image-agent/cli::repl c :input in :output out
                             :chat-factory (lambda (controller model)
                                             (is (equal "fake" model))
                                             (image-agent/cli:make-chat controller :model model :key "secret"
                                               :transport (lambda (&rest args) (declare (ignore args))
                                                            (native-sse (native-message "Hello!"))))))))))
          (is (search "Program loaded" output))
          (is (search "Hello!" output))
          (is (search "ROLLED-BACK" output))
          (is (= 0 (gethash :x (image-agent:reference-table w)))))
      (image-agent:close-session s)))
  (let ((store (temp-store)))
    (image-agent/cli::ensure-workspace store "one")
    (image-agent/cli::ensure-workspace store "one")
    (is (raises-error-p (lambda () (image-agent/cli::ensure-workspace store "two"))))))
(defun rollback-history-p (commands)
  "Independent oracle: append-only (data, function-offset) states, indexed from one."
  (multiple-value-bind (w s c) (interactive-fixture 500)
    (let ((states (list (list 0 nil))) (expected (list 0 nil)))
      (unwind-protect
          (handler-case
              (progn
                (loop for (op n) in commands do
                  (case op
                    (:edit
                     (let ((value (abs n)))
                       (cli-action c :evaluate :source (format nil "(progn (setf (gethash :x *state*) ~d) (defun f (x) (+ x ~d)))" value value))
                       (setf expected (list value value) states (append states (list expected)))))
                    ((:rollback :paused-rollback)
                     (let* ((target (1+ (mod (abs n) (length states)))) (old-state (nth (1- target) states)))
                       (when (eq op :paused-rollback)
                         (cli-action c :evaluate :source "(progn (setf (gethash :x *state*) 999) (defun f (x) (+ x 999)) (restart-case (error \"pause\") (use () nil)))"))
                       (cli-action c :rollback :revision (princ-to-string target))
                       (setf expected old-state states (append states (list expected)))))
                    (:stale
                     (image-agent/cli::controller-action c (image-agent/cli::object "generation" -1) :rollback :revision "1"))
                    (:invalid (cli-action c :rollback :revision "not-a-revision"))
                    (:abort
                     (cli-action c :evaluate :source "(progn (setf (gethash :x *state*) 999) (defun f (x) (+ x 999)) (error \"pause\"))")
                     (cli-action c :abort))
                    (:resume
                     (let ((value (abs n)))
                       (cli-action c :evaluate :source (format nil "(progn (defun f (x) (+ x ~d)) (restart-case (error \"resume\") (use () (setf (gethash :x *state*) ~d))))" value value))
                       (cli-action c :resume :restart-id (getf (first (getf (image-agent/cli:controller-view c) :restarts)) :id) :arguments "nil")
                       (setf expected (list value value) states (append states (list expected))))))
                  (unless (and (= (first expected) (gethash :x (image-agent:reference-table w)))
                               (equal (and (second expected) (+ 3 (second expected))) (function-value w))
                               (= (length states) (length (image-agent:list-revisions (image-agent:session-store s))))
                               (= (length states) (getf (first (image-agent:list-revisions (image-agent:session-store s))) :sequence))
                               (eq :idle (getf (image-agent/cli:controller-view c) :status)))
                    (setf *failure-context* (list :operation op :value n :expected expected :states states
                                                 :view (image-agent/cli:controller-view c)))
                    (return-from rollback-history-p nil)))
                t)
            (error () nil))
        (image-agent:close-session s)))))
(test generated-rollback-histories
  (dotimes (i *trials*)
    (let* ((gen (check-it:generator (list (check-it:tuple (or :edit :rollback :paused-rollback :stale :invalid :abort :resume)
                                                       (integer -20 20)) :min-length 1 :max-length 30)))
           (commands (check-it:generate gen)))
      (if (rollback-history-p commands) (pass)
          (let ((small commands) (attempts 0))
            (catch 'limit
              (check-it:shrink commands (lambda (candidate)
                                         (when (> (incf attempts) 100) (throw 'limit nil))
                                         (if (not (valid-rollback-history-p candidate)) t
                                             (let ((ok (rollback-history-p candidate)))
                                               (unless ok (setf small candidate)) ok)))))
            (save-counterexample small :original commands :kind :rollback-history
                                       :context (list :shrink-attempts attempts :failure *failure-context*))
            (fail "Rollback history failed: ~s" small))))))
(test rollback-recovery-and-legacy-numbers
  (multiple-value-bind (w s c) (interactive-fixture)
    (declare (ignore w))
    (unwind-protect
        (progn
          (cli-action c :evaluate :source "(progn (setf (gethash :x *state*) 3) (defun f (x) (+ x 3)))")
          (cli-action c :evaluate :source "(progn (setf (gethash :x *state*) 8) (defun f (x) (+ x 8)))")
          ;; Simulate manifests written by the previous implementation.
          (dolist (record (image-agent:list-revisions (image-agent:session-store s)))
            (let* ((path (merge-pathnames (format nil "~a/manifest.sexp" (getf record :id))
                                         (image-agent::directory-path (image-agent:session-store s))))
                   (manifest (image-agent::read-record path)))
              (remf manifest :sequence)
              (with-open-file (out path :direction :output :if-exists :supersede)
                (write manifest :stream out))))
          (is (equal '(3 2 1) (mapcar (lambda (r) (getf r :sequence)) (image-agent:list-revisions (image-agent:session-store s)))))
          (cli-action c :rollback :revision "2")
          (image-agent:close-session s)
          (let ((process (uiop:launch-program (list (namestring (truename "/proc/self/exe")) "--noinform" "--script"
                                                    "tests/crash-child.lisp" "recover" (namestring (image-agent:session-store s)) "none" "3")
                                               :output nil :error-output nil)))
            (is (= 0 (uiop:wait-process process))))
          (is (= 4 (getf (first (image-agent:list-revisions (image-agent:session-store s))) :sequence))))
      (image-agent:close-session s))))
(defun cli-live-test ()
  (multiple-value-bind (w s c) (interactive-fixture)
    (unwind-protect
        (let ((chat (image-agent/cli:make-chat c :on-tool
                       (lambda (name result)
                         (format t "Live tool ~a: status=~a error=~a~%" name
                                 (and (hash-table-p result) (gethash "status" result))
                                 (and (hash-table-p result) (gethash "error" result)))
                         (finish-output)))))
          (let ((answer (image-agent/cli:chat-turn chat "Use your registered tools to set :x in *state* to 7. Stop once accepted.")))
            (unless (= 7 (gethash :x (image-agent:reference-table w)))
              (error "Live tool mutation failed: ~a" answer)))
          (let ((before (getf (image-agent/cli:controller-view c) :revision)))
            (image-agent/cli:chat-turn chat "Roll back to accepted revision number 1, using rollback_revision. Stop once restored.")
            (unless (and (= 0 (gethash :x (image-agent:reference-table w)))
                         (not (equal before (getf (image-agent/cli:controller-view c) :revision)))
                         (getf (first (image-agent:list-revisions (image-agent:session-store s))) :rollback-source))
              (error "Live rollback failed")))
          (format t "Underclass native tools: mutation and history-preserving rollback succeeded~%"))
      (image-agent:close-session s))))
(test underclass-completed-item-fallback
  (let* ((call (native-call "proxy" "evaluate_form" "source" "nil" "generation" 1))
         (events (format nil "data: ~a~%~%data: ~a~%~%"
                   (image-agent/cli::json (image-agent/cli::object "type" "response.output_item.done" "item" call))
                   (image-agent/cli::json (image-agent/cli::object "type" "response.completed" "response"
                                           (image-agent/cli::object "status" "completed" "output" #())))))
         (response (image-agent/cli::completed-response events)))
    (is (= 1 (length (gethash "output" response))))
    (is (equal "proxy" (gethash "call_id" (aref (gethash "output" response) 0))))
    (is (raises-error-p (lambda () (image-agent/cli::completed-response
                     (format nil "data: ~a~%~%" (image-agent/cli::json
                       (image-agent/cli::object "type" "response.output_item.done" "item" call))))))))
  (let* ((events (format nil "data: {\"type\":\"response.output_text.delta\",\"delta\":\"Hello\"}~%~%~a" (native-sse)))
         (response (image-agent/cli::completed-response events)))
    (is (equal "Hello" (image-agent/cli::response-text (gethash "output" response))))))
(test interactive-last-action-budget
  (multiple-value-bind (w s c) (interactive-fixture 2)
    (unwind-protect
        (progn
          (cli-action c :evaluate :source "(setf (gethash :x *state*) 7)")
          (cli-action c :rollback :revision "1")
          (is (eq :exhausted (getf (image-agent/cli:controller-view c) :status)))
          (is (= 0 (gethash :x (image-agent:reference-table w))))
          (is (= 3 (length (image-agent:list-revisions (image-agent:session-store s)))))
          (is (raises-error-p (lambda () (cli-action c :evaluate :source "nil")))))
      (image-agent:close-session s))))
(test transport-and-context-preserve-paused-world
  (multiple-value-bind (w s c) (interactive-fixture)
    (unwind-protect
        (progn
          (cli-action c :evaluate :source "(progn (setf (gethash :x *state*) 9) (restart-case (error \"pause\") (use () nil)))")
          (let* ((view (image-agent/cli:controller-view c))
                 (chat (image-agent/cli:make-chat c :model "fake" :key "never-print-this"
                         :transport (lambda (&rest args) (declare (ignore args)) (error "never-print-this")))))
            (is (search "request failed" (image-agent/cli:chat-turn chat "repair")))
            (is (eq view (image-agent/cli:controller-view c)))
            (is (= 9 (gethash :x (image-agent:reference-table w))))
            (setf (image-agent/cli::chat-history chat)
                  (list (image-agent/cli::message "user" (make-string 20000 :initial-element #\x))))
            (setf (image-agent/cli::chat-context-limit chat) 16384
                  (image-agent/cli::chat-transport chat)
                  (lambda (url key body)
                    (declare (ignore url key))
                    (let ((request (image-agent/cli::parse-json body)))
                      (is (= 1 (length (gethash "input" request))))
                      (is (search "paused" (gethash "instructions" request))))
                    (native-sse (native-message "Still paused."))))
            (is (equal "Still paused." (image-agent/cli:chat-turn chat "inspect")))
            (is (eq view (image-agent/cli:controller-view c))))
          (cli-action c :abort)
          (is (= 0 (gethash :x (image-agent:reference-table w)))))
      (image-agent:close-session s))))
(test protected-cli-and-repeated-call-ids
  (multiple-value-bind (w s c) (interactive-fixture)
    (unwind-protect
        (progn
          (cli-action c :evaluate :source "(progn nil (setf image-agent/cli::chat-tool-limit 999))")
          (is (eq :restored (getf (getf (image-agent/cli:controller-view c) :outcome) :commit)))
          (let ((chat (image-agent/cli:make-chat c :model "fake" :key "secret" :tool-limit 5
                        :transport (lambda (&rest args) (declare (ignore args))
                          (native-sse (native-call "repeated" "evaluate_form" "source" "(incf (gethash :x *state*))"
                                                  "generation" (getf (image-agent/cli:controller-view c) :generation)))))))
            (is (search "Invalid tool-call" (image-agent/cli:chat-turn chat "increment once")))
            (is (= 1 (gethash :x (image-agent:reference-table w))))
            (is (search "Invalid tool-call" (image-agent/cli:chat-turn chat "do something else")))
            (is (= 1 (gethash :x (image-agent:reference-table w))))))
      (image-agent:close-session s))))
(defun native-property-p (number)
  (let* ((source (format nil "(list ~s ~d)" "λ🍋" number))
         (call (native-call "generated" "evaluate_form" "source" source "generation" number))
         (response (image-agent/cli::completed-response (native-sse call)))
         (args (image-agent/cli::parse-json (gethash "arguments" (aref (gethash "output" response) 0))))
         (tool (image-agent/cli:make-tool :name "evaluate_form" :description "fixture"
                 :schema (image-agent/cli::schema "source" "string" "generation" "integer")
                 :handler (lambda (a) (gethash "source" a)))))
    (and (equal source (image-agent/cli:dispatch-tool (list tool) "evaluate_form" args))
         (raises-error-p (lambda () (image-agent/cli::completed-response
              (format nil "data: ~a~%~%" (image-agent/cli::json
                (image-agent/cli::object "type" "response.output_item.done" "item" call))))))
         (progn (setf (gethash "extra" args) number)
                (raises-error-p (lambda () (image-agent/cli:dispatch-tool (list tool) "evaluate_form" args)))))))
(test generated-native-call-parsing
  (dotimes (i *pure-trials*) (exercise-property :native-calls (random 10000))))
(defun valid-rollback-history-p (commands)
  (ignore-errors
    (and (listp commands)
         (every (lambda (command)
                  (and (listp command) (= 2 (length command))
                       (member (first command) '(:edit :rollback :paused-rollback :stale :invalid :abort :resume))
                       (integerp (second command)))) commands))))
(test tool-result-and-callback-failures-retain-pairs
  (multiple-value-bind (w s c) (interactive-fixture)
    (declare (ignore w))
    (unwind-protect
        (let ((step 0))
          (setf (image-agent/cli::tool-handler (first (image-agent/cli:controller-tools c)))
                (lambda (args) (declare (ignore args)) #'identity))
          (let ((chat (image-agent/cli:make-chat c :model "fake" :key "secret"
                        :on-tool (lambda (&rest args) (declare (ignore args)) (error "callback failed"))
                        :transport (lambda (&rest args) (declare (ignore args))
                                     (if (= 1 (incf step))
                                         (native-sse (native-call "bad-result" "observe_world"))
                                         (native-sse (native-message "Handled the tool error.")))))))
            (is (equal "Handled the tool error." (image-agent/cli:chat-turn chat "inspect")))
            (let ((output (find "function_call_output" (image-agent/cli::chat-history chat)
                                :key (lambda (item) (gethash "type" item)) :test #'equal)))
              (is (equal "bad-result" (gethash "call_id" output)))
              (is (search "could not be encoded" (gethash "output" output))))))
      (image-agent:close-session s))))
