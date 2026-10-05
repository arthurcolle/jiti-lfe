;;; A real model grows the empty expense application. No implementation is supplied.
;;; Invoke through chat_capture.py for local configuration and the 600s watchdog.
(require :asdf)
(push (truename "./") asdf:*central-registry*)
(asdf:load-system "image-agent/cli")
(load "examples/expense-tracker.lisp")

(defun live-object (&rest pairs) (apply #'image-agent::json-object pairs))
(defun live-write-json (path value)
  (with-open-file (stream path :direction :output :if-exists :supersede :if-does-not-exist :create)
    (write-string (image-agent::json-text value) stream) (terpri stream)))
(defun live-call (controller action &rest fields)
  (setf (image-agent/cli:controller-view controller)
        (image-agent:session-step (image-agent/cli:controller-session controller)
          (append (list :action action :generation (getf (image-agent/cli:controller-view controller) :generation)) fields))))
(defun live-text (view)
  (getf (first (getf (getf view :outcome) :values)) :text))
(defun live-read-value (view)
  (when (and (eq :idle (getf view :status)) (live-text view))
    (let ((*read-eval* nil)) (read-from-string (live-text view)))))
(defun live-check-pass (view name)
  (eq :pass (getf (find name (getf view :goals) :key (lambda (check) (getf check :name))) :status)))
(defun live-transcript-event (event)
  (format t "~&[~a] ~a~%" (gethash "id" event) (gethash "title" event))
  (when (gethash "prompt" event) (format t "User: ~a~%" (gethash "prompt" event)))
  (when (gethash "reply" event) (format t "Model: ~a~%" (gethash "reply" event)))
  (when (gethash "result_text" event) (format t "Verified execution: ~a~%" (gethash "result_text" event)))
  (finish-output))

(defun capture-live-chat (output)
  (when (probe-file output) (error "Output directory must be fresh"))
  (ensure-directories-exist (merge-pathnames "live-capture.json" output))
  (let* ((spec (make-cli-world)) (world (getf spec :world))
         (table (image-agent:reference-table world))
         (session (image-agent:make-session world :interactive t :budget 180
                    :store (merge-pathnames "store/" output)
                    :goals (getf spec :goals) :invariants (getf spec :invariants)))
         (controller (image-agent/cli:make-controller session))
         (events nil) (tool-events nil) (chat nil) (repair-count 0)
         (started (get-universal-time)) (passed nil))
    (labels ((document ()
               (live-object "schema_version" 1 "scenario" "expense-tracker"
                            "meta" (live-object "mode" "live-model"
                                                "model" (image-agent::environment "OPENAI_MODEL")
                                                "started_universal_time" started
                                                "process_id" (sb-posix:getpid)
                                                "passed" (if passed 'yason:true 'yason:false))
                            "provenance" "Actual model conversation and registered tool execution; model-created function source retained."
                            "events" (coerce (reverse events) 'vector)))
             (persist () (live-write-json (merge-pathnames "live-capture.json" output) (document)))
             (remember (event)
               (push event events) (live-transcript-event event) (persist))
             (sources ()
               (mapcar (lambda (entry) (getf entry :source))
                       (funcall (image-agent:world-catalogue world))))
             (abort-pause ()
               (when (eq :paused (getf (image-agent/cli:controller-view controller) :status))
                 (live-call controller :abort)))
             (exact-ledger-p (expected)
               (let ((actual (gethash :expenses table)))
                 (and (= (length actual) (length expected))
                      (every (lambda (entry)
                               (let ((matching (find (getf entry :category) actual
                                                     :key (lambda (item) (getf item :category)))))
                                 (and matching (eql (getf matching :amount) (getf entry :amount))))) expected))))
             (turn (id title prompt source expected verify)
               (loop for attempt from 0 do
                 (setf tool-events nil)
                 (format t "~&Requesting live model turn: ~a (attempt ~d)~%" id (1+ attempt))
                 (finish-output)
                 (let* ((actual-prompt
                          (if (zerop attempt) prompt
                              (format nil "The caller's verification for ~a did not pass. Inspect current functions and data, then repair only the missing or incorrect behavior from my previous request. Avoid duplicate expenses; preserve existing correct entries. Required caller verification: ~a. Execute the requested operation and run check_world."
                                      title expected)))
                        (reply (image-agent/cli:chat-turn chat actual-prompt)))
                   (abort-pause)
                   (let* ((view (if source (live-call controller :execute :source source)
                                    (live-call controller :check)))
                          (ok (handler-case (funcall verify view) (error () nil)))
                          (event (live-object "id" (if ok id (format nil "~a_attempt_~d" id (1+ attempt)))
                                              "title" title "prompt" actual-prompt "reply" reply
                                              "action" "chat" "source" source
                                              "tool_calls" (coerce (reverse tool-events) 'vector)
                                              "managed_sources" (coerce (sources) 'vector)
                                              "view" (image-agent/cli::view-json view)
                                              "result_text" (live-text view)
                                              "verified" (if ok 'yason:true 'yason:false))))
                     (remember event)
                     (when ok (return))
                     (abort-pause)
                     (when (>= repair-count 2) (error "Bounded live verification failed"))
                     (incf repair-count))))))
      (unwind-protect
           (progn
             (setf chat (image-agent/cli:make-chat controller :tool-limit 16
                          :on-tool
                          (lambda (name result)
                            (let* ((history (image-agent/cli::chat-history chat))
                                   (call (find-if (lambda (item)
                                                    (equal "function_call" (gethash "type" item)))
                                                  (reverse history))))
                              (push (live-object "name" name
                                                 "arguments" (and call (gethash "arguments" call))
                                                 "result" result) tool-events)
                              (format t "~&tool ~a: ~a~%" name (gethash "status" result))
                              (finish-output)))))
             (let ((view (live-call controller :inspect)))
               (unless (and (zerop (getf (getf view :outcome) :catalogue-count))
                            (null (gethash :expenses table))) (error "Live application must start empty"))
               (remember (live-object "id" "empty_catalogue" "title" "An empty application before the first prompt"
                                      "action" "inspect" "view" (image-agent/cli::view-json view)
                                      "result_text" nil
                                      "verification_text" "Caller verified zero managed functions and an empty ledger."
                                      "verified" 'yason:true)))
             (turn "record_expense" "Chat creates the first function"
                   "Let me record expenses. This application starts with an empty *state* hash table entry :expenses and no functions. Its caller-owned data contract is a list of entries, each a property list with :amount as positive integer cents and :category as a keyword. Add a managed function add-expense taking amount and category. It records an entry in (gethash :expenses *state*). Then record one coffee expense of 450 cents using :coffee. Keep all data in that managed ledger. Define only add-expense in this turn. Do not change caller checks or access external resources. Use registered tools and show the actual result."
                   "(gethash :expenses *state*)" "Exactly one expense: 450 cents, category :coffee; can-record-expenses passes."
                   (lambda (view) (and (eq :idle (getf view :status))
                                       (exact-ledger-p '((:amount 450 :category :coffee)))
                                       (live-check-pass view :can-record-expenses))))
             (turn "spending_total" "Chat adds total spending"
                   "Add a function total-expenses with no arguments that returns the ledger's total amount in integer cents. Keep add-expense. Record groceries 3200 cents in :groceries and transport 1800 cents in :transport, each exactly once, alongside the existing coffee expense. Execute total-expenses and tell me its actual result. Define no other functions this turn."
                   "(total-expenses)" "Three entries coffee450/groceries3200/transport1800; total-expenses returns5450."
                   (lambda (view) (and (eql 5450 (live-read-value view))
                                       (exact-ledger-p '((:amount 450 :category :coffee)
                                                         (:amount 3200 :category :groceries)
                                                         (:amount 1800 :category :transport))))))
             (turn "category_totals" "Chat adds spending by category"
                   "Break my spending down by category. Add spending-by-category with no arguments. Return an association list of category . total-cents pairs, sorted by category name. Reuse the current ledger and leave existing functions and entries intact. Execute the function and show its actual result."
                   "(spending-by-category)" "((:coffee . 450) (:groceries . 3200) (:transport . 1800)); correct-totals passes."
                   (lambda (view) (and (equal '((:coffee . 450) (:groceries . 3200) (:transport . 1800))
                                             (live-read-value view))
                                       (live-check-pass view :correct-totals))))
             (turn "budget_report" "Chat composes the existing functions"
                   "Combine those capabilities into a reusable budget-report function taking budget-cents. It must call the existing total-expenses and spending-by-category functions, returning a property list with :spent, :remaining, and :by-category. Run it for a 6000-cent budget. Preserve all existing entries and functions. Run the caller checks and show the actual report."
                   "(budget-report 6000)" "Report has :spent5450, :remaining550, and exact category totals; all caller-owned goals pass."
                   (lambda (view)
                     (let ((value (live-read-value view)))
                       (and (eql 5450 (getf value :spent)) (eql 550 (getf value :remaining))
                            (equal '((:coffee . 450) (:groceries . 3200) (:transport . 1800))
                                   (getf value :by-category))
                            (every (lambda (check) (eq :pass (getf check :status))) (getf view :goals))))))
             (let ((view (live-call controller :check)))
               (remember (live-object "id" "caller_checks" "title" "Caller goals and safety checks pass"
                                      "action" "check" "view" (image-agent/cli::view-json view)
                                      "result_text" nil "verified" 'yason:true)))
             (with-open-file (stream (merge-pathnames "generated-source.lisp" output) :direction :output :if-exists :error)
               (format stream ";;; Actual managed definitions generated by the model in this capture.~%")
               (dolist (source (sources)) (format stream "~a~%~%" source)))
             (setf passed t) (persist)
             (format t "~&PASS: actual live model growth and caller verification (~d repair prompts).~%" repair-count))
        (persist)
        (image-agent:close-session session)))))

(handler-case
    (let ((args (cdr sb-ext:*posix-argv*)))
      (unless (= (length args) 1) (error "One fresh output directory required"))
      (capture-live-chat (uiop:ensure-directory-pathname (first args))))
  (error ()
    ;; Avoid dumping transport details or credential-bearing configuration.
    (format *error-output* "Live capture did not complete. Accepted state and recorded events remain in the fresh output directory.~%")
    (sb-ext:exit :code 1)))
