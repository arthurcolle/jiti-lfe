(in-package :image-agent/tests)
(in-suite kernel)
(defun revision-count (session) (length (image-agent:list-revisions (image-agent:session-store session))))
(defun result-text (controller &optional (index 0))
  (getf (nth index (getf (getf (image-agent/cli:controller-view controller) :outcome) :values)) :text))
(test composition-revisions-preview-and-catalogue
  (multiple-value-bind (world session control) (interactive-fixture)
    (unwind-protect
        (progn
          (cli-action control :develop :source "(defun uppercase-string (s) \"Uppercase without mutating input.\" (string-upcase s))")
          (cli-action control :develop :source *unicode-correct-source*)
          (is (= 3 (revision-count session)))
          (cli-action control :execute :source "(reverse-string (uppercase-string \"Hello 👩🏽‍💻é\"))")
          (is (equal "\"É👩🏽‍💻 OLLEH\"" (result-text control)))
          (cli-action control :operations)
          (let* ((record (first (getf (getf (image-agent/cli:controller-view control) :outcome) :operation-records)))
                 (outcome (getf record :outcome)))
            (is (eq :accepted (getf record :status)))
            (is (equal "\"É👩🏽‍💻 OLLEH\"" (getf (first (getf outcome :values)) :text)))
            (is (equal (getf record :base-revision) (getf record :revision)))
            (is (eq :accepted (getf outcome :commit))))
          (is (= 3 (revision-count session)))
          (cli-action control :develop :source "(defun uppercase-string (s) \"Uppercase without mutating input.\" (string-upcase s))")
          (is (= 3 (revision-count session)))
          (cli-action control :execute :source "(progn (setf (gethash :x *state*) 10) (setf (gethash :x *state*) 0))")
          (is (= 3 (revision-count session)))
          (cli-action control :execute :source "(incf (gethash :x *state*))" :preview t)
          (is (equal "1" (result-text control)))
          (is (= 0 (gethash :x (image-agent:reference-table world))))
          (is (= 3 (revision-count session)))
          (cli-action control :execute :source "(incf (gethash :x *state*))")
          (is (= 1 (gethash :x (image-agent:reference-table world))))
          (is (= 4 (revision-count session)))
          (cli-action control :develop :source "(defun shout-backwards (s) (reverse-string (uppercase-string s)))")
          (is (= 5 (revision-count session)))
          (cli-action control :describe :name "uppercase-string")
          (is (search "Uppercase without mutating input" (getf (getf (getf (image-agent/cli:controller-view control) :outcome) :function) :text)))
          (cli-action control :inspect)
          (is (= 3 (length (getf (getf (image-agent/cli:controller-view control) :outcome) :catalogue))))
          (cli-action control :execute :source "(values (shout-backwards \"Hi\") 42 nil)")
          (is (equal "\"IH\"" (result-text control)))
          (is (equal "42" (result-text control 1)))
          (is (equal "NIL" (result-text control 2)))
          (cli-action control :execute :source "(make-string 5000 :initial-element #\\a)")
          (is (= 4096 (length (result-text control))))
          (is (getf (first (getf (getf (image-agent/cli:controller-view control) :outcome) :values)) :truncated)))
      (image-agent:close-session session))))
(test preview-live-repair-and-chain-atomicity
  (multiple-value-bind (world session control) (interactive-fixture)
    (unwind-protect
        (progn
          (cli-action control :execute :preview t :source "(progn (setf (gethash :x *state*) 7) (restart-case (error \"pause\") (use () (helper))))")
          (let ((operation (getf (image-agent/cli:controller-view control) :operation-id)))
            (cli-action control :develop :source "(defun helper () 42)")
            (is (equal operation (getf (image-agent/cli:controller-view control) :operation-id)))
            (cli-action control :resume :restart-id (getf (first (getf (image-agent/cli:controller-view control) :restarts)) :id) :arguments "nil")
            (is (equal "42" (result-text control)))
            (is (= 0 (gethash :x (image-agent:reference-table world))))
            (is (not (fboundp (find-symbol "HELPER" (image-agent:world-package world)))))
            (is (= 1 (revision-count session))))
          (cli-action control :execute :source "(progn (incf (gethash :x *state*)) (error \"second call failed\"))")
          (cli-action control :abort)
          (is (= 0 (gethash :x (image-agent:reference-table world))))
          (is (= 1 (revision-count session)))
          (cli-action control :execute :source "(progn (incf (gethash :x *state*)) (restart-case (error \"continue\") (use () (incf (gethash :x *state*)))))")
          (cli-action control :resume :restart-id (getf (first (getf (image-agent/cli:controller-view control) :restarts)) :id) :arguments "nil")
          (is (= 2 (gethash :x (image-agent:reference-table world))))
          (is (= 2 (revision-count session)))
          (cli-action control :execute :source "(setf (gethash :x *state*) -1)")
          (is (= 2 (gethash :x (image-agent:reference-table world))))
          (is (= 2 (revision-count session))))
      (image-agent:close-session session))))
(test managed-case-changes-and-unsupported-mutations
  (multiple-value-bind (world session control) (interactive-fixture)
    (unwind-protect
        (progn
          (cli-action control :execute :source "(setf (gethash :text *state*) \"hello\")")
          (cli-action control :execute :source "(nstring-upcase (gethash :text *state*))" :preview t)
          (is (equal "hello" (gethash :text (image-agent:reference-table world))))
          (is (= 2 (revision-count session)))
          (cli-action control :execute :source "(nstring-upcase (gethash :text *state*))")
          (is (= 3 (revision-count session)))
          (cli-action control :execute :source "(setf (gethash :bad *state*) (make-hash-table))")
          (is (eq :state-capture-failed (getf (getf (image-agent/cli:controller-view control) :outcome) :reason)))
          (is (not (gethash :bad (image-agent:reference-table world))))
          (cli-action control :execute :source "(let ((x (list 1))) (setf (cdr x) x (gethash :bad *state*) x))")
          (is (eq :idle (getf (image-agent/cli:controller-view control) :status)))
          (is (not (gethash :bad (image-agent:reference-table world))))
          (cli-action control :execute :source "(setf (symbol-function 'unrecorded) (lambda () 1))")
          (is (not (fboundp (find-symbol "UNRECORDED" (image-agent:world-package world)))))
          (is (= 3 (revision-count session))))
      (image-agent:close-session session))))
(test operation-recovery-does-not-reexecute
  (let ((store (temp-store)))
    (multiple-value-bind (world session control) (interactive-fixture 100 store)
      (declare (ignore world))
      (unwind-protect
          (progn
            (cli-action control :develop :source "(defun twice (x) \"Double X.\" (* 2 x))")
            (cli-action control :execute :source "(incf (gethash :x *state*))")
            (cli-action control :execute :source "(incf (gethash :x *state*))" :preview t)
            (image-agent:close-session session)
            (let* ((fresh (image-agent:make-reference-world))
                   (recovered (image-agent:recover-session fresh store :interactive t))
                   (c (image-agent/cli:make-controller recovered)))
              (unwind-protect
                  (progn
                    (is (= 1 (gethash :x (image-agent:reference-table fresh))))
                    (cli-action c :describe :name "twice")
                    (is (search "Double X" (getf (getf (getf (image-agent/cli:controller-view c) :outcome) :function) :text)))
                    (cli-action c :operations)
                    (is (= 3 (length (getf (getf (image-agent/cli:controller-view c) :outcome) :operations))))
                    (cli-action c :execute :source "(twice 3)")
                    (is (equal "6" (result-text c)))
                    (is (= 3 (revision-count recovered))))
                (image-agent:close-session recovered))))
        (image-agent:close-session session)))))
(test managed-function-removal-lifecycle
  (multiple-value-bind (world session control) (interactive-fixture)
    (let ((package (image-agent:world-package world)))
      (unwind-protect
          (progn
            (cli-action control :develop :source "(progn (defun f (x) \"Increment X.\" (+ x 1)) (defun caller (x) (f x)))")
            (let ((cached (symbol-function (find-symbol "F" package)))
                  (count (revision-count session)))
              (cli-action control :execute :preview t :source "(fmakunbound 'f)")
              (is (fboundp (find-symbol "F" package)))
              (is (= count (revision-count session)))
              (cli-action control :develop :source "(fmakunbound 'f)")
              (is (eq :accepted (getf (getf (image-agent/cli:controller-view control) :outcome) :commit)))
              (is (not (fboundp (find-symbol "F" package))))
              (is (null (documentation (find-symbol "F" package) 'function)))
              (is (fboundp (find-symbol "CALLER" package)))
              (is (= 4 (funcall cached 3)))
              (is (= (1+ count) (revision-count session)))
              (cli-action control :describe :name "f")
              (is (not (getf (getf (image-agent/cli:controller-view control) :outcome) :found)))
              (cli-action control :inspect)
              (is (not (find "F" (getf (getf (image-agent/cli:controller-view control) :outcome) :catalogue-infos)
                             :key (lambda (entry) (getf entry :name)) :test #'equal)))
              (cli-action control :develop :source "(fmakunbound 'f)")
              (is (= (1+ count) (revision-count session)))
              (cli-action control :rollback :revision "previous")
              (is (fboundp (find-symbol "F" package)))
              (is (equal "Increment X." (documentation (find-symbol "F" package) 'function))))
            (cli-action control :execute :preview t :source "(defun preview-only () \"Ephemeral.\" 1)")
            (is (not (fboundp (find-symbol "PREVIEW-ONLY" package))))
            (is (null (documentation (find-symbol "PREVIEW-ONLY" package) 'function)))
            (cli-action control :develop :source "(progn (defun temp () 1) (fmakunbound 'temp))")
            (is (not (fboundp (find-symbol "TEMP" package))))
            (cli-action control :develop :source "(progn (fmakunbound 'f) (defun f (x) (* x 2)))")
            (cli-action control :execute :source "(caller 3)")
            (is (equal "6" (result-text control)))
            (cli-action control :develop :source "(progn (defun f (x) x) (progn (fmakunbound 'f)))")
            (is (not (fboundp (find-symbol "F" package))))
            (cli-action control :execute :source "(restart-case (caller 3) (use () (caller 3)))")
            (is (eq :paused (getf (image-agent/cli:controller-view control) :status)))
            (cli-action control :develop :source "(defun f (x) (+ x 9))")
            (let ((restart (find "USE" (getf (image-agent/cli:controller-view control) :restarts)
                                 :key (lambda (entry) (getf entry :name)) :test #'equal)))
              (cli-action control :resume :restart-id (getf restart :id) :arguments "nil"))
            (is (equal "12" (result-text control))))
        (image-agent:close-session session)))))

(test removal-restoration-and-in-flight-frames
  (multiple-value-bind (world session control) (interactive-fixture)
    (let ((package (image-agent:world-package world)))
      (unwind-protect
          (progn
            (cli-action control :develop :source "(defun f () \"Retain me.\" 1)")
            (let ((count (revision-count session)))
              (setf (image-agent::session-invariants session)
                    (list (cons :keep-f (lambda () (fboundp (find-symbol "F" package))))))
              (cli-action control :develop :source "(fmakunbound 'f)")
              (is (eq :unsafe (getf (getf (image-agent/cli:controller-view control) :outcome) :reason)))
              (is (fboundp (find-symbol "F" package)))
              (is (equal "Retain me." (documentation (find-symbol "F" package) 'function)))
              (is (= count (revision-count session)))
              (setf (image-agent::session-invariants session) nil)
              (cli-action control :develop :source "(progn (fmakunbound 'f) (error \"pause\"))")
              (is (eq :paused (getf (image-agent/cli:controller-view control) :status)))
              (cli-action control :abort)
              (is (fboundp (find-symbol "F" package)))
              (is (= count (revision-count session))))
            (cli-action control :develop :source "(defun active () (restart-case (error \"paused frame\") (use () 42)))")
            (cli-action control :execute :source "(active)")
            (is (eq :paused (getf (image-agent/cli:controller-view control) :status)))
            (cli-action control :develop :source "(fmakunbound 'active)")
            (let ((restart (find "USE" (getf (image-agent/cli:controller-view control) :restarts)
                                 :key (lambda (entry) (getf entry :name)) :test #'equal)))
              (cli-action control :resume :restart-id (getf restart :id) :arguments "nil"))
            (is (equal "42" (result-text control)))
            (is (not (fboundp (find-symbol "ACTIVE" package)))))
        (image-agent:close-session session)))))

(test removal-validation-before-effects
  (multiple-value-bind (world session control) (interactive-fixture)
    (let* ((foreign (make-package (string (gensym "FOREIGN-")) :use '(:cl)))
           (foreign-name (intern "KEEP" foreign)))
      (unwind-protect
          (progn
            (setf (symbol-function foreign-name) (lambda () 99))
            (cli-action control :develop :source "(defun f () 1)")
            (dolist (source (list "(progn (setf (gethash :x *state*) 77) (fmakunbound 'cl:car))"
                                 "(fmakunbound (progn (setf (gethash :x *state*) 77) 'f))"
                                 "(let () (fmakunbound 'f))" "(funcall #'fmakunbound 'f)"
                                 "(progn (fmakunbound 'f) (fmakunbound 'image-agent:run))"
                                 (format nil "(fmakunbound '~a::keep)" (package-name foreign))))
              (let ((before (revision-count session)))
                (cli-action control :develop :source source)
                (is (eq :rejected (getf (getf (image-agent/cli:controller-view control) :outcome) :reason)))
                (is (fboundp (find-symbol "F" (image-agent:world-package world))))
                (is (= 0 (gethash :x (image-agent:reference-table world))))
                (is (= before (revision-count session)))
                (is (= 99 (funcall foreign-name)))))
            (let ((validator (image-agent:world-validate-form world)))
              (setf (image-agent:world-validate-form world) (lambda (form) (declare (ignore form)) (error "policy")))
              (cli-action control :execute :source "(setf (gethash :x *state*) 88)")
              (is (= 0 (gethash :x (image-agent:reference-table world))))
              (setf (image-agent:world-validate-form world) validator)))
        (image-agent:close-session session)
        (delete-package foreign)))))

(test removal-fresh-recovery-and-rollback
  (let ((store (temp-store)))
    (multiple-value-bind (world session control) (interactive-fixture 100 store)
      (declare (ignore world))
      (unwind-protect
          (progn
            (cli-action control :develop :source "(defun f () \"Recover me.\" 7)")
            (cli-action control :develop :source "(fmakunbound 'f)")
            (image-agent:close-session session)
            (is (= 0 (uiop:wait-process
                      (uiop:launch-program
                       (list (namestring (truename "/proc/self/exe")) "--noinform" "--script"
                             "tests/execution-child.lisp" (namestring store) "(not (fboundp 'f))" "T")
                       :output *standard-output* :error-output *error-output*))))
            (let* ((fresh (let* ((w (image-agent:make-reference-world))
                                 (form (image-agent:parse-one-form "(defun f () \"Bootstrap definition.\" 99)"
                                                                  (image-agent:world-package w))))
                            (image-agent:validate-form form)
                            (funcall (image-agent:world-validate-form w) form)
                            (eval form) (funcall (image-agent:world-record-form w) form)
                            w))
                   (recovered (image-agent:recover-session fresh store :interactive t))
                   (c (image-agent/cli:make-controller recovered)))
              (unwind-protect
                  (progn
                    (is (not (fboundp (find-symbol "F" (image-agent:world-package fresh)))))
                    (is (null (documentation (find-symbol "F" (image-agent:world-package fresh)) 'function)))
                    (cli-action c :describe :name "f")
                    (is (not (getf (getf (image-agent/cli:controller-view c) :outcome) :found)))
                    (cli-action c :rollback :revision "previous")
                    (cli-action c :execute :source "(f)")
                    (is (equal "7" (result-text c)))
                    (cli-action c :describe :name "f")
                    (is (equal "Recover me." (getf (getf (getf (image-agent/cli:controller-view c) :outcome) :function-info) :documentation))))
                (image-agent:close-session recovered))))
        (image-agent:close-session session)))))

(defun composition-history-p (commands)
  "Independent model: final data and function offset determine change-sensitive revisions."
  (let* ((store (temp-store)) (world (image-agent:make-reference-world :initial '((:x . 0))))
         (session (image-agent:make-session world :interactive t :store store :budget 500))
         (control (image-agent/cli:make-controller session))
         (expected '(0 nil)) (states (list expected)))
    (labels ((accept (next)
               (unless (equal next expected) (setf states (append states (list next))))
               (setf expected next)))
      (unwind-protect
          (handler-case
              (progn
                (loop for (op n) in commands do
                  (let ((value (abs n)))
                    (case op
                      (:develop
                       (cli-action control :develop :source (format nil "(defun f (x) (+ x ~d))" value))
                       (accept (list (first expected) value)))
                      (:delete
                       (cli-action control :develop :source "(fmakunbound 'f)")
                       (accept (list (first expected) nil)))
                      (:delete-preview
                       (cli-action control :execute :preview t :source "(fmakunbound 'f)"))
                      (:execute
                       (cli-action control :execute :source (format nil "(identity (setf (gethash :x *state*) ~d))" value))
                       (accept (list value (second expected))))
                      (:preview
                       (cli-action control :execute :preview t :source (format nil "(progn (defun f (x) (+ x ~d)) (setf (gethash :x *state*) ~d))" value value)))
                      (:pure (cli-action control :execute :source (format nil "(values (+ ~d 1) ~d)" value value)))
                      (:unsafe
                       ;; No safety predicates in this oracle fixture: use unreadable state rejection.
                       (cli-action control :execute :source "(setf (gethash :bad *state*) (make-hash-table))"))
                      (:abort
                       (cli-action control :execute :source "(progn (setf (gethash :x *state*) 999) (error \"abort\"))")
                       (cli-action control :abort))
                      (:resume
                       (let ((preview (oddp n)))
                         (cli-action control :execute :preview preview :source (format nil "(progn (setf (gethash :x *state*) ~d) (restart-case (error \"repair\") (use () nil)))" value))
                         (cli-action control :develop :source (format nil "(defun f (x) (+ x ~d))" value))
                         (cli-action control :resume :restart-id (getf (first (getf (image-agent/cli:controller-view control) :restarts)) :id) :arguments "nil")
                         (unless preview (accept (list value value)))))
                      (:stale (image-agent/cli::controller-action control (image-agent/cli::object "generation" -1) :execute :source "(setf (gethash :x *state*) 999)"))
                      (:rollback
                       (let* ((target (mod value (length states))) (next (nth target states)))
                         (cli-action control :rollback :revision (princ-to-string (1+ target)))
                         (setf expected next states (append states (list next)))))
                      (:recover
                       (image-agent:close-session session)
                       (setf world (image-agent:make-reference-world)
                             session (image-agent:recover-session world store :interactive t :budget 500)
                             control (image-agent/cli:make-controller session)))))
                  (unless (and (eq :idle (getf (image-agent/cli:controller-view control) :status))
                               (= (first expected) (gethash :x (image-agent:reference-table world)))
                               (equal (and (second expected) (+ 3 (second expected))) (function-value world))
                               (= (length states) (revision-count session)))
                    (setf *failure-context* (list :op op :value n :expected expected :states states
                                                 :view (image-agent/cli:controller-view control)))
                    (return-from composition-history-p nil)))
                t)
            (error (c) (setf *failure-context* (list :error (image-agent::bounded c))) nil))
        (image-agent:close-session session)))))
(test generated-composition-transactions
  (dotimes (i (min 100 *trials*))
    (let* ((gen (check-it:generator (list (check-it:tuple (or :develop :delete :delete-preview :execute :preview :pure :unsafe :abort :resume :stale :rollback :recover)
                                                        (integer -20 20)) :min-length 1 :max-length 20)))
           (commands (check-it:generate gen)))
      (if (composition-history-p commands) (pass)
          (let ((small commands) (attempts 0))
            (catch 'limit
              (check-it:shrink commands (lambda (candidate)
                                         (when (> (incf attempts) 100) (throw 'limit nil))
                                         (let ((ok (composition-history-p candidate)))
                                           (unless ok (setf small candidate)) ok))))
            (save-counterexample small :original commands :kind :composition-history
                                 :context (list :shrink-attempts attempts :failure *failure-context*))
            (fail "Composition history failed: ~s" small))))))
(test execution-failure-boundaries-and-preview-exhaustion
  (multiple-value-bind (world session control) (interactive-fixture)
    (unwind-protect
        (let ((original (image-agent:world-managed-state world)))
          (setf (image-agent:world-managed-state world)
                (lambda () (when (= 7 (gethash :x (image-agent:reference-table world))) (error "capture failed"))
                           (funcall original)))
          (cli-action control :execute :source "(setf (gethash :x *state*) 7)")
          (is (= 0 (gethash :x (image-agent:reference-table world))))
          (is (eq :state-capture-failed (getf (getf (image-agent/cli:controller-view control) :outcome) :reason)))
          (is (= 1 (revision-count session)))
          (let ((old image-agent:*store-boundary-hook*))
            (unwind-protect
                (progn
                  (setf image-agent:*store-boundary-hook* (lambda (point) (when (eq point :before-export) (error "publish failed"))))
                  (cli-action control :execute :source "(setf (gethash :x *state*) 8)")
                  (is (= 0 (gethash :x (image-agent:reference-table world))))
                  (is (= 1 (revision-count session))))
              (setf image-agent:*store-boundary-hook* old))))
      (image-agent:close-session session)))
  (multiple-value-bind (world session control) (interactive-fixture 1)
    (unwind-protect
        (progn
          (cli-action control :execute :preview t :source "(progn (setf (gethash :x *state*) 7) (error \"pause\"))")
          (is (eq :exhausted (getf (image-agent/cli:controller-view control) :status)))
          (is (= 0 (gethash :x (image-agent:reference-table world))))
          (is (= 1 (revision-count session))))
      (image-agent:close-session session)))
  (multiple-value-bind (world session control) (interactive-fixture)
    (unwind-protect
        (progn
          (setf (image-agent:world-restore world) (lambda (snap) (declare (ignore snap)) (error "restore failed")))
          (cli-action control :execute :preview t :source "(setf (gethash :x *state*) 7)")
          (is (eq :faulted (getf (image-agent/cli:controller-view control) :status))))
      (image-agent:close-session session))))
(test generic-fresh-process-composition
  (multiple-value-bind (world session control) (interactive-fixture)
    (declare (ignore world))
    (unwind-protect
        (progn
          (cli-action control :develop :source "(progn (defun twice (x) (* x 2)) (defun composed (x) (twice (twice x))))")
          (image-agent:close-session session)
          (is (= 0 (uiop:wait-process
                    (uiop:launch-program (list (namestring (truename "/proc/self/exe")) "--noinform" "--script"
                                              "tests/execution-child.lisp" (namestring (image-agent:session-store session))
                                              "(composed 3)" "12") :output nil :error-output nil)))))
      (image-agent:close-session session))))
(defun composition-live-test ()
  ;; Domain functionality lives only in this test, and the real model supplies definitions.
  (let ((store (temp-store)))
    (multiple-value-bind (spec report) (image-agent/experiments:make-reverse-world :artifacts store)
      (declare (ignore report))
      (let* ((world (getf spec :world))
             (session (image-agent:make-session world :interactive t :store store :budget 150
                       :goals (getf spec :goals) :invariants (getf spec :invariants)))
             (control (image-agent/cli:make-controller session))
             (chat (image-agent/cli:make-chat control :on-tool (lambda (name result)
                       (format t "Composition tool ~a: ~a~%" name (gethash "outcome" result)) (finish-output)))))
        (unwind-protect
            (progn
              (format t "Live composition workspace: ~a~%" store) (finish-output)
              (image-agent/cli:chat-turn chat "Add a managed function uppercase-string that returns an uppercased copy of its string argument. Preserve the existing program. Use develop_form; do not add other functions.")
              (cli-action control :execute :source "(uppercase-string \"Hello 👩🏽‍💻é\")")
              (unless (equal "\"HELLO 👩🏽‍💻É\"" (result-text control)) (error "Live uppercase failed"))
              (unless (eq :success (getf (image-agent/experiments:evolve control chat
                                      image-agent/experiments::+goal+) :status))
                (error "Live Unicode development failed"))
              (let ((before (image-agent::current-revision store)) (count (revision-count session))
                    (frontier (getf (first (image-agent::session-operations session)) :id)))
                (image-agent/cli:chat-turn chat "Execute uppercase-string on \"Hello 👩🏽‍💻é\", then reverse-string on that result, in one nested expression. Use execute_form with preview=false. Return its actual result. Do not define or redefine anything.")
                (unless (and (loop for record in (image-agent::session-operations session)
                                   until (equal frontier (getf record :id))
                                   thereis (and (eq :execute (getf record :intent))
                                                (eq :accepted (getf record :status))
                                                (equal "\"É👩🏽‍💻 OLLEH\""
                                                  (getf (first (getf (getf record :outcome) :values)) :text))))
                             (equal before (image-agent::current-revision store)))
                  (error "Live transient composition changed revision or returned wrong result"))
                (image-agent/cli:chat-turn chat "Save the composition as shout-backwards: call uppercase-string, then reverse-string, reusing both existing functions. Define only shout-backwards using develop_form.")
                (cli-action control :execute :source "(shout-backwards \"Hello 👩🏽‍💻é\")")
                (unless (and (equal "\"É👩🏽‍💻 OLLEH\"" (result-text control)) (= (1+ count) (revision-count session)))
                  (error "Live saved composition failed")))
              (image-agent:close-session session)
              (unless (= 0 (uiop:wait-process
                            (uiop:launch-program (list (namestring (truename "/proc/self/exe")) "--noinform" "--script"
                                       "tests/execution-child.lisp" (namestring store)
                                       "(shout-backwards \"Hello 👩🏽‍💻é\")" "\"É👩🏽‍💻 OLLEH\"")
                                       :output *standard-output* :error-output *error-output*)))
                (error "Fresh process live composition failed"))
              (format t "Underclass composition: incremental development, transient execution, saved composition, and fresh recovery PASS.~%"))
          (image-agent:close-session session))))))
(test execute-json-booleans-and-transport-timeout
  (is (not (getf (image-agent:parse-action "{\"action\":\"execute\",\"source\":\"nil\",\"preview\":false}") :preview)))
  (is (getf (image-agent:parse-action "{\"action\":\"execute\",\"source\":\"nil\",\"preview\":true}") :preview))
  (dolist (text '("{\"action\":\"execute\",\"source\":\"nil\",\"preview\":null}"
                  "{\"action\":\"execute\",\"source\":\"nil\"}"
                  "{\"action\":\"evaluate\",\"source\":\"nil\"}"))
    (signals error (image-agent:parse-action text)))
  (signals image-agent:configuration-error
    (image-agent::guarded-transport (lambda () (error 'sb-ext:timeout :seconds 0.01))))
  (multiple-value-bind (world session control) (interactive-fixture)
    (declare (ignore world))
    (unwind-protect
        (let ((before (revision-count session))
              (chat (image-agent/cli:make-chat control :model "fake" :key "never-log"
                      :transport (lambda (url key body) (declare (ignore url key body))
                                   (error 'sb-ext:timeout :seconds 0.01)))))
          (is (search "request failed" (image-agent/cli:chat-turn chat "Execute existing functionality")))
          (is (= before (revision-count session)))
          (is (eq :idle (getf (image-agent/cli:controller-view control) :status))))
      (image-agent:close-session session))))
(test catalogue-paging-and-query-bounds
  (multiple-value-bind (world session control) (interactive-fixture)
    (unwind-protect
        (progn
          (setf (image-agent:world-catalogue world)
                (lambda () (loop for i below 65 collect (list :name (format nil "FUNCTION-~d" i)
                                                              :arguments '(x) :documentation "Example" :source "(defun example (x) x)"))))
          (let ((result (image-agent/cli:dispatch-tool (image-agent/cli:controller-tools control) "inspect_world"
                              (image-agent/cli::object "offset" 0))))
            (is (= 50 (length (gethash "catalogue" (gethash "result" result)))))
            (is (= 50 (gethash "next_offset" (gethash "result" result)))))
          (cli-action control :inspect :offset 50)
          (is (= 15 (length (getf (getf (image-agent/cli:controller-view control) :outcome) :catalogue))))
          (is (not (getf (getf (image-agent/cli:controller-view control) :outcome) :next-offset)))
          (signals error (image-agent/cli:dispatch-tool (image-agent/cli:controller-tools control) "inspect_world"
                              (image-agent/cli::object "offset" -1)))
          (is (= 1 (revision-count session))))
      (image-agent:close-session session))))
(test multiple-values-have-a-total-output-budget
  (multiple-value-bind (world session control) (interactive-fixture)
    (declare (ignore world))
    (unwind-protect
        (progn
          (cli-action control :execute :source (format nil "(values ~{~a ~})"
                               (make-list 10 :initial-element "(make-string 4000 :initial-element #\\a)")))
          (let* ((result (getf (image-agent/cli:controller-view control) :outcome)) (values (getf result :values)))
            (is (= 10 (getf result :value-count)))
            (is (getf result :values-truncated))
            (is (<= (reduce #'+ values :key (lambda (v) (length (getf v :text))) :initial-value 0) 12000))
            (is (= 1 (revision-count session)))))
      (image-agent:close-session session))))

(defun removal-live-test ()
  (let* ((store (temp-store))
         (world (image-agent:make-reference-world :initial '((:x . 0))))
         (session (image-agent:make-session world :interactive t :store store :budget 50))
         (control (image-agent/cli:make-controller session))
         (chat (image-agent/cli:make-chat control)))
    (unwind-protect
        (progn
          (image-agent/cli:chat-turn chat "Add two managed functions in one develop_form: removal-probe takes x and returns (+ x 1); removal-caller takes x and calls removal-probe. Do not add anything else.")
          (cli-action control :execute :source "(removal-caller 3)")
          (unless (equal "4" (result-text control)) (error "Live removal fixture was not added"))
          (let ((before (revision-count session)))
            (image-agent/cli:chat-turn chat "Remove only removal-probe from the accepted application. Keep removal-caller unchanged, even though it references removal-probe. Use develop_form and verify the actual catalogue; do not roll back or redefine either function.")
            (unless (and (not (fboundp (find-symbol "REMOVAL-PROBE" (image-agent:world-package world))))
                         (fboundp (find-symbol "REMOVAL-CALLER" (image-agent:world-package world)))
                         (= (1+ before) (revision-count session)))
              (error "Live removal did not preserve caller or publish exactly one revision")))
          (image-agent:close-session session)
          (unless (= 0 (uiop:wait-process
                        (uiop:launch-program
                         (list (namestring (truename "/proc/self/exe")) "--noinform" "--script"
                               "tests/execution-child.lisp" (namestring store)
                               "(list (fboundp 'removal-probe) (not (null (fboundp 'removal-caller))))" "(NIL T)")
                         :output *standard-output* :error-output *error-output*)))
            (error "Live removal fresh recovery failed"))
          (let* ((fresh (image-agent:make-reference-world))
                 (recovered (image-agent:recover-session fresh store :interactive t))
                 (c (image-agent/cli:make-controller recovered)))
            (unwind-protect
                (progn
                  (cli-action c :rollback :revision "previous")
                  (cli-action c :execute :source "(removal-caller 3)")
                  (unless (equal "4" (result-text c)) (error "Live removal rollback failed")))
              (image-agent:close-session recovered)))
          (format t "Underclass removal: accepted deletion, caller preservation, fresh recovery, and rollback PASS.~%"))
      (image-agent:close-session session))))

(test native-removal-tool-roundtrip
  (multiple-value-bind (world session control) (interactive-fixture)
    (let ((step 0))
      (unwind-protect
          (progn
            (cli-action control :develop :source "(defun removable () 5)")
            (let ((chat (image-agent/cli:make-chat control :model "fake" :key "not-a-real-key"
                         :transport
                         (lambda (url key body)
                           (declare (ignore url key))
                           (let ((request (image-agent/cli::parse-json body)))
                             (is (search "fmakunbound" (gethash "instructions" request)))
                             (is (search "never cascade" (gethash "instructions" request))))
                           (incf step)
                           (if (= step 1)
                               (native-sse (native-call "remove-one" "develop_form"
                                            "source" "(fmakunbound 'removable)"
                                            "generation" (getf (image-agent/cli:controller-view control) :generation)))
                               (native-sse (native-message "Removed it.")))))))
              (is (equal "Removed it." (image-agent/cli:chat-turn chat "Remove removable")))
              (is (not (fboundp (find-symbol "REMOVABLE" (image-agent:world-package world)))))
              (is (= 3 (revision-count session)))
              (is (= 2 step))))
        (image-agent:close-session session)))))
