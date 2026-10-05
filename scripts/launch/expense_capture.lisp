;;; Reproducible captures of real kernel behavior using author-supplied Lisp.
;;; This is deliberately labelled as a scripted session, not an LLM conversation.
;;; devenv shell -- sbcl --noinform --script scripts/launch/expense_capture.lisp OUTPUT_DIR
(require :asdf)
(push (truename "./") asdf:*central-registry*)
(asdf:load-system "image-agent/cli")
(load "examples/expense-tracker.lisp")

(defun launch-object (&rest pairs) (apply #'image-agent::json-object pairs))
(defun launch-json-file (path value)
  (with-open-file (stream path :direction :output :if-exists :error :if-does-not-exist :create)
    (write-string (image-agent::json-text value) stream)
    (terpri stream)))
(defun launch-value (view)
  (getf (first (getf (getf view :outcome) :values)) :text))
(defun launch-value-equal (expected view)
  (let ((*read-eval* nil))
    (equal expected (read-from-string (launch-value view)))))
(defun launch-assert (value message)
  (unless value (error "Launch verification failed: ~a" message)))
(defun launch-action (session view action &rest fields)
  (image-agent:session-step session
    (append (list :action action :generation (getf view :generation)) fields)))
(defun launch-session (spec store &optional recover)
  (apply (if recover #'image-agent:recover-session #'image-agent:make-session)
         (getf spec :world)
         (append (if recover (list store) (list :store store))
                 (list :interactive t :budget 200
                       :goals (getf spec :goals) :invariants (getf spec :invariants)))))
(defun launch-recover (output)
  (let* ((spec (make-cli-world)) (store (merge-pathnames "store/" output))
         (session (launch-session spec store t))
         (revision (image-agent::current-revision store)))
    (unwind-protect
         (let* ((initial (image-agent:session-step session))
                (view (launch-action session initial :execute :source "(budget-report 6000)")))
           (launch-assert (launch-value-equal
                           '(:spent 5450 :remaining 550 :by-category
                             ((:coffee . 450) (:groceries . 3200) (:transport . 1800))) view)
                          "fresh process recovers functions and expense data")
           (launch-assert (equal revision (image-agent::current-revision store))
                          "fresh pure execution creates no revision")
           (launch-json-file (merge-pathnames "recovery.json" output)
             (launch-object "id" "fresh_recovery" "title" "Functions and data survive a process restart"
                            "prompt" "Restart the process and use the recovered budget report."
                            "action" "execute" "source" "(budget-report 6000)"
                            "process_id" (sb-posix:getpid)
                            "view" (image-agent/cli::view-json view)
                            "result_text" (launch-value view)))
           (format t "Fresh process ~d: ~a~%" (sb-posix:getpid) (launch-value view)))
      (image-agent:close-session session))))

(defparameter *launch-add-source*
  "(defun add-expense (amount category)
  \"Record a positive integer amount in cents and a keyword category.\"
  (let ((entry (list :amount amount :category category)))
    (setf (gethash :expenses *state*)
          (append (gethash :expenses *state*) (list entry)))
    entry))")
(defparameter *launch-total-source*
  "(defun total-expenses ()
  \"Return total spending in integer cents.\"
  (loop for entry in (gethash :expenses *state*)
        sum (getf entry :amount)))")
(defparameter *launch-categories-source*
  "(defun spending-by-category ()
  \"Return category/cent pairs sorted by category name.\"
  (let ((totals nil))
    (dolist (entry (gethash :expenses *state*))
      (let* ((category (getf entry :category))
             (pair (assoc category totals)))
        (if pair (incf (cdr pair) (getf entry :amount))
            (push (cons category (getf entry :amount)) totals))))
    (sort totals #'string< :key (lambda (pair) (symbol-name (car pair))))))")
(defparameter *launch-report-source*
  "(defun budget-report (budget-cents)
  \"Compose existing totals into a budget report.\"
  (let ((spent (total-expenses)))
    (list :spent spent :remaining (- budget-cents spent)
          :by-category (spending-by-category))))")
(defun launch-render-source (marker)
  (format nil "(defun render-budget-report ()
  (let ((outer-frame-marker ~s))
    (incf (gethash :report-entry-count *state* 0))
    (list :frame outer-frame-marker
          :entries (gethash :report-entry-count *state*)
          :categories
          (loop for (category . amount) in (spending-by-category)
                collect (list (restart-case (category-label category)
                                (retry-category () (category-label category)))
                              amount))
          :budget (budget-report 6000))))" marker))

(defun launch-capture (output)
  (when (probe-file output) (error "Output directory must be fresh: ~a" output))
  (ensure-directories-exist (merge-pathnames "capture.json" output))
  (let* ((spec (make-cli-world)) (world (getf spec :world))
         (table (image-agent:reference-table world))
         (store (merge-pathnames "store/" output))
         (session (launch-session spec store))
         (view (image-agent:session-step session)) (events nil)
         (checks nil))
    (labels ((verify (condition description)
               (launch-assert condition description)
               (push description checks))
             (record (id title prompt action &rest arguments)
               (setf view (apply #'launch-action session view action arguments))
               (launch-assert (member (getf view :status) '(:idle :paused))
                              (format nil "~a reaches a usable worker boundary" id))
               (let ((event (launch-object "id" id "title" title "prompt" prompt
                                          "action" (string-downcase (symbol-name action))
                                          "source" (getf arguments :source)
                                          "view" (image-agent/cli::view-json view)
                                          "result_text" (when (member action '(:develop :execute :resume))
                                                          (launch-value view)))))
                 (push event events)
                 (format t "~&[~a] ~a~%~a~%" id title
                         (or (launch-value view) (getf view :condition) (getf view :status))))
               view)
             (revision-count () (length (image-agent:list-revisions store))))
      (unwind-protect
           (progn
             (record "empty_catalogue" "An empty application" "Start with no expense functions." :inspect)
             (verify (zerop (getf (getf view :outcome) :catalogue-count)) "empty function catalogue")
             (verify (null (gethash :expenses table)) "empty expense ledger")
             (record "define_expense" "Teach the first function" "Let me record an expense with an amount in cents and a category." :develop :source *launch-add-source*)
             (record "record_expense" "Use it immediately" "Record coffee for $4.50, groceries for $32, and transport for $18."
                     :execute :source "(list (add-expense 450 :coffee) (add-expense 3200 :groceries) (add-expense 1800 :transport))")
             (verify (= 3 (length (gethash :expenses table))) "three real expense entries")
             (record "define_total" "Add another capability" "Add up my spending." :develop :source *launch-total-source*)
             (record "spending_total" "Total spending: $54.50" "Calculate total spending." :execute :source "(total-expenses)")
             (verify (equal "5450" (launch-value view)) "spending total is 5450 cents")
             (record "define_categories" "Group spending by category" "Break spending down by category." :develop :source *launch-categories-source*)
             (record "category_totals" "Reuse the ledger" "Show the category totals." :execute :source "(spending-by-category)")
             (verify (equal "((:COFFEE . 450) (:GROCERIES . 3200) (:TRANSPORT . 1800))" (launch-value view)) "exact category totals")
             (record "define_report" "Compose existing functions" "Combine the total and categories into a report for a $60 budget." :develop :source *launch-report-source*)
             (record "budget_report" "$54.50 spent. $5.50 remaining." "Run the budget report." :execute :source "(budget-report 6000)")
             (verify (launch-value-equal '(:spent 5450 :remaining 550 :by-category
                                          ((:coffee . 450) (:groceries . 3200) (:transport . 1800))) view)
                     "composed budget report returns exact values")
             (record "caller_checks" "Caller-owned acceptance checks" "Run the acceptance goals and safety checks." :check)
             (verify (every (lambda (check) (eq :pass (getf check :status))) (getf view :goals)) "all caller-owned goals pass")
             (let ((before (revision-count)))
               (record "preview_restore" "Preview returns a result and restores state" "Preview adding $5 of coffee." :execute :preview t :source "(progn (add-expense 500 :coffee) (total-expenses))")
               (verify (and (equal "5950" (launch-value view))
                            (eq :preview (getf (getf view :outcome) :reason))
                            (= 3 (length (gethash :expenses table)))
                            (= before (revision-count))) "preview returns 5950 and restores ledger without a revision")
               (record "safety_rejection" "Invalid changes are restored" "Try to record a negative expense." :execute :source "(add-expense -100 :coffee)")
               (verify (and (eq :unsafe (getf (getf view :outcome) :reason))
                            (= 3 (length (gethash :expenses table)))
                            (= before (revision-count))) "negative amount fails safety and leaves accepted state intact"))
             (record "accepted_change" "Accept a change" "Add $5 of coffee for real." :execute :source "(add-expense 500 :coffee)")
             (let ((before (revision-count)))
               (record "rollback_history" "Undo while preserving history" "Undo that accepted expense change." :rollback :revision "previous")
               (verify (and (= 3 (length (gethash :expenses table)))
                            (= (1+ before) (revision-count))
                            (getf (first (image-agent:list-revisions store)) :rollback-source))
                       "rollback restores ledger and publishes a new revision"))
             (record "prepare_repair" "A report with an unsupported category" "Add a formatter that currently knows coffee and groceries."
                     :develop :source
                     (format nil "(progn (defun category-label (category) (case category (:coffee \"Coffee\") (:groceries \"Groceries\") (otherwise (error \"Unsupported category: ~~a\" category)))) ~a)"
                             (launch-render-source "v1-active-frame")))
             (record "paused_call" "The worker retains a paused call" "Render the report; transport triggers a repairable condition." :execute :source "(render-budget-report)")
             (verify (and (eq :paused (getf view :status))
                          (= 1 (gethash :report-entry-count table))) "report entered once and paused in an active restart")
             (let* ((operation-id (getf view :operation-id))
                    (restart (find "RETRY-CATEGORY" (getf view :restarts) :key (lambda (entry) (getf entry :name)) :test #'equal)))
               (verify restart "retry-category restart exists")
               (record "repair_definitions" "Replace functions while the call is paused" "Teach transport formatting and update future report calls."
                       :develop :source
                       (format nil "(progn (defun category-label (category) (string-capitalize (symbol-name category))) ~a)"
                               (launch-render-source "v2-new-frame")))
               (verify (equal operation-id (getf view :operation-id)) "repair shares the paused operation identity")
               ;; Restart IDs are observation-scoped; fetch the refreshed menu after repair.
               (setf restart (find "RETRY-CATEGORY" (getf view :restarts)
                                   :key (lambda (entry) (getf entry :name)) :test #'equal))
               (record "repair_resume" "The existing call continues" "Resume its retry-category restart." :resume :restart-id (getf restart :id) :arguments "nil")
               (verify (and (equal operation-id (getf (getf view :outcome) :operation-id))
                            (search "v1-active-frame" (launch-value view))
                            (search "\"Transport\"" (launch-value view))
                            (= 1 (gethash :report-entry-count table)))
                       "resumed call retains original frame, uses repaired helper, and does not re-enter")
               (record "subsequent_call" "Future calls use the new function" "Render the next report." :execute :source "(render-budget-report)")
               (verify (and (search "v2-new-frame" (launch-value view))
                            (= 2 (gethash :report-entry-count table))) "next call enters the replacement function")))
        (image-agent:close-session session))
      ;; A separate process proves durable recovery, rather than a second in-image world.
      (let ((child-output
              (uiop:run-program
               (list (namestring (truename "/proc/self/exe")) "--noinform" "--script"
                     "scripts/launch/expense_capture.lisp" "--recover" (namestring output))
               :output :string :error-output *error-output*)))
        (write-string child-output)
        (with-open-file (stream (merge-pathnames "recovery.json" output))
          (let* ((yason:*parse-json-booleans-as-symbols* t)
                 (yason:*parse-json-arrays-as-vectors* t)
                 (recovery (yason:parse stream)))
            (verify (/= (gethash "process_id" recovery) (sb-posix:getpid)) "recovery ran in a distinct operating-system process")
            (push recovery events))))
      (let ((ordered-events (nreverse events)))
        (launch-json-file (merge-pathnames "capture.json" output)
          (launch-object "schema_version" 1 "scenario" "expense-tracker"
                         "provenance" "Deterministic scripted kernel session with author-supplied code; not a model conversation."
                         "process_id" (sb-posix:getpid)
                         "events" (coerce ordered-events 'vector)
                         "verification" (coerce (nreverse checks) 'vector)))
        (with-open-file (stream (merge-pathnames "transcript.txt" output) :direction :output :if-exists :error)
          (format stream "JITI — REAL KERNEL, SCRIPTED INPUT~%Author-supplied code; this transcript is not a model conversation.~%~%")
          (dolist (event ordered-events)
            (format stream "[~a] ~a~%Intent: ~a~%" (gethash "id" event) (gethash "title" event) (gethash "prompt" event))
            (when (gethash "source" event) (format stream "Lisp: ~a~%" (gethash "source" event)))
            (let ((json-view (gethash "view" event)))
              (format stream "Status: ~a  Revision: ~a  Operation: ~a~%" (gethash "status" json-view) (gethash "revision" json-view) (gethash "operation_id" json-view)))
            (when (gethash "result_text" event) (format stream "Result: ~a~%" (gethash "result_text" event)))
            (terpri stream))))
      (format t "~&PASS: ~d assertions; capture written to ~a~%" (length checks) output))))

(let ((arguments (cdr sb-ext:*posix-argv*)))
  (cond ((and (= (length arguments) 2) (equal (first arguments) "--recover"))
         (launch-recover (uiop:ensure-directory-pathname (second arguments))))
        ((= (length arguments) 1)
         (launch-capture (uiop:ensure-directory-pathname (first arguments))))
        (t (error "Usage: expense_capture.lisp FRESH_OUTPUT_DIRECTORY"))))
