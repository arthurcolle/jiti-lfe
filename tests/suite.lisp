(defpackage :image-agent/tests (:use :cl :fiveam))
(in-package :image-agent/tests)
(def-suite kernel)
(in-suite kernel)
(defvar *seed* 424242)
(defvar *trials* 200)
(defvar *pure-trials* 1000)
(defvar *crash-trials* 20)
(defvar *mutate-definitions* nil)
(defvar *failure-context* nil)
(defvar *coverage* (make-hash-table))
(defun cover (name) (incf (gethash name *coverage* 0)))
(defun temp-store ()
  (let ((dir (pathname (format nil "/tmp/image-agent-test-~d-~a/" (get-universal-time) (gensym)))))
    (ensure-directories-exist dir) dir))
(defun source (world text)
  ;; Source normally uses the explicitly bound world package; no package names needed.
  (declare (ignore world)) text)
(defun send (s view &rest action)
  (image-agent:session-step s (append action (list :generation (getf view :generation)))))
(defun fixture (&optional (goal (constantly nil)) (budget 40) store)
  (let* ((w (image-agent:make-reference-world :initial '((:x . 0))))
         (s (image-agent:make-session w :goals (list (cons :done goal))
                                      :invariants (list (cons :nonnegative
                                        (lambda () (>= (gethash :x (image-agent:reference-table w)) 0))))
                                      :budget budget :store store)))
    (values w s (image-agent:session-step s))))
(defun function-value (w)
  (let ((sym (find-symbol "F" (image-agent:world-package w))))
    (and sym (fboundp sym) (funcall (symbol-function sym) 3))))
(test basic-acceptance-and-safety
  (multiple-value-bind (w s view) (fixture)
    (unwind-protect
        (progn
          (setf view (send s view :action :develop :source "(progn (setf (gethash :x *state*) 4) (defun f (x) (+ x 7)))"))
          (is (eq :idle (getf view :status)))
          (is (= 4 (gethash :x (image-agent:reference-table w))))
          (is (= 10 (function-value w)))
          (setf view (send s view :action :develop :source "(progn (defun f (x) (+ x 100)) (setf (gethash :x *state*) -1))"))
          (is (= 4 (gethash :x (image-agent:reference-table w))))
          (is (= 10 (function-value w))))
      (image-agent:close-session s))))
(test live-repair-and-old-frame
  (multiple-value-bind (w s v) (fixture)
    (unwind-protect
        (progn
          (setf v (send s v :action :develop :source "(progn (declaim (notinline helper)) (defun helper () (error \"broken\")) (defun task () (list :old (restart-case (helper) (retry () (helper))) :old-exit)))"))
          (setf v (send s v :action :develop :source "(setf (gethash :result *state*) (task))"))
          (is (eq :paused (getf v :status))) (cover :pause)
          (setf v (send s v :action :develop :source "(progn (defun helper () 42) (defun task () :new))"))
          (let ((r (find "RETRY" (getf v :restarts) :key (lambda (r) (getf r :name)) :test #'equal)))
            (setf v (send s v :action :resume :restart-id (getf r :id) :arguments "nil")))
          (is (equal '(:old 42 :old-exit) (gethash :result (image-agent:reference-table w))))
          (is (eq :new (funcall (symbol-function (find-symbol "TASK" (image-agent:world-package w))))))
          (cover :repair))
      (image-agent:close-session s))))
(test abort-restores-repair
  (multiple-value-bind (w s v) (fixture)
    (unwind-protect
        (progn
          (setf v (send s v :action :develop :source "(defun f (x) (+ x 1))"))
          (setf v (send s v :action :develop :source "(progn (setf (gethash :x *state*) 7) (error \"pause\"))"))
          (setf v (send s v :action :develop :source "(defun f (x) (+ x 99))"))
          (setf v (send s v :action :abort))
          (is (= 0 (gethash :x (image-agent:reference-table w))))
          (is (= 4 (function-value w))) (cover :rollback))
      (image-agent:close-session s))))
(test duplicate-unnamed-and-stale-restarts
  (multiple-value-bind (w s v) (fixture)
    (unwind-protect
        (progn
          (setf v (send s v :action :develop :source "(restart-case (restart-case (error \"choose\") (same () (setf (gethash :x *state*) 11))) (same () (setf (gethash :x *state*) 22)) (nil () 3))"))
          (let* ((menu (getf v :restarts)) (old (getf (first menu) :id)))
            (is (= 2 (count "SAME" menu :key (lambda (r) (getf r :name)) :test #'equal)))
            (is (some (lambda (r) (null (getf r :name))) menu))
            (setf v (send s v :action :resume :restart-id "unknown" :arguments "nil"))
            (is (eq :paused (getf v :status)))
            (setf v (send s v :action :resume :restart-id old :arguments "nil"))
            (is (eq :paused (getf v :status)))
            (let ((outer (second (remove-if-not (lambda (r) (equal "SAME" (getf r :name))) (getf v :restarts)))))
              (setf v (send s v :action :resume :restart-id (getf outer :id) :arguments "nil")))
            (is (= 22 (gethash :x (image-agent:reference-table w)))) (cover :stale)))
      (image-agent:close-session s))))
(test budget-and-check-errors
  (let* ((w (image-agent:make-reference-world))
         (s (image-agent:make-session w :goals (list (cons :broken (lambda () (error "check failed")))) :budget 1)))
    (unwind-protect
        (let* ((v (image-agent:session-step s))
               (last (send s v :action :develop :source "nil")))
          (is (eq :exhausted (getf last :status))) (cover :exhausted))
      (image-agent:close-session s))))
(test budget-during-pause
  (multiple-value-bind (w s v) (fixture (constantly nil) 1)
    (unwind-protect
        (progn
          (setf v (send s v :action :develop :source "(progn (setf (gethash :x *state*) 9) (error \"stop\"))"))
          (is (eq :exhausted (getf v :status)))
          (is (= 0 (gethash :x (image-agent:reference-table w)))))
      (image-agent:close-session s))))
(defun generated-history (commands)
  "Independent oracle: integers represent data and named F behavior, not Lisp forms."
  (multiple-value-bind (w s v) (fixture (constantly nil) 200)
    (let ((expected 0) (offset nil) (remaining 200))
      (unwind-protect
          (loop for (op n) in commands do
            (decf remaining (case op ((:fail :fail-define :resume) 2) (:repair 3) (:stale 3) (otherwise 1)))
            (case op
              (:set (setf v (send s v :action :develop :source
                                  (format nil "(setf (gethash :x *state*) ~d)" n)))
                    (when (>= n 0) (setf expected n)))
              (:define (setf v (send s v :action :develop :source
                                     (format nil "(defun f (x) (+ x ~d))" (if *mutate-definitions* (1+ n) n))))
                       (setf offset n))
              (:fail (setf v (send s v :action :develop :source
                                   (format nil "(progn (setf (gethash :x *state*) ~d) (error \"generated\"))" (abs n))))
                     (unless (eq :paused (getf v :status)) (return-from generated-history nil))
                     (setf v (send s v :action :abort)))
              (:fail-define
               (setf v (send s v :action :develop :source
                    (format nil "(progn (defun f (x) (+ x ~d)) (error \"failed definition\"))" n)))
               (setf v (send s v :action :abort)))
              (:repair
               (setf v (send s v :action :develop :source
                    (format nil "(progn (setf (gethash :x *state*) ~d) (restart-case (error \"repair\") (retry () (f 3))))" (abs n))))
               (setf v (send s v :action :develop :source (format nil "(defun f (x) (+ x ~d))" n)))
               (if (minusp n)
                   (setf v (send s v :action :abort))
                   (progn
                     (setf v (send s v :action :resume :restart-id (getf (first (getf v :restarts)) :id) :arguments "nil"))
                     (setf offset n expected n))))
              (:stale
               (setf v (send s v :action :develop :source "(restart-case (error \"stale\") (use () nil))"))
               (setf v (send s v :action :resume :restart-id "expired" :arguments "nil"))
               (unless (eq :paused (getf v :status)) (return-from generated-history nil))
               (setf v (send s v :action :abort)))
              (:invalid (setf v (send s v :action :claimed-success)))
              (:resume (setf v (send s v :action :develop :source
                                     "(restart-case (error \"resume\") (use (x) (setf (gethash :x *state*) x)))"))
                       (let ((restart (first (getf v :restarts))))
                         (setf v (send s v :action :resume :restart-id (getf restart :id)
                                       :arguments (format nil "(list ~d)" (abs n)))))
                       (setf expected (abs n))))
            (cover op)
            (unless (and (eq :idle (getf v :status))
                         (= remaining (getf v :remaining))
                         (= expected (gethash :x (image-agent:reference-table w)))
                         (if offset (= (+ 3 offset) (function-value w)) (null (function-value w))))
              (setf *failure-context* (list :expected-data expected :expected-offset offset
                                          :expected-budget remaining :view v))
              (return-from generated-history nil)))
        (image-agent:close-session s)))
    t))
(defun valid-history-p (commands)
  (and (listp commands) (every (lambda (cmd)
    (and (listp cmd) (= (length cmd) 2) (integerp (second cmd))
         (member (first cmd) '(:set :define :fail :fail-define :resume :repair :stale :invalid)))) commands)))
(defun shrink-history (commands)
  (let ((attempts 0) (small commands))
    (catch 'limit
      (check-it:shrink commands
        (lambda (candidate)
          (when (> (incf attempts) 100) (throw 'limit small))
          (if (not (valid-history-p candidate)) t
              (handler-case
                  (let ((pass (generated-history candidate)))
                    (unless pass (setf small candidate)) pass)
                ;; Do not replace a semantic mismatch with a different infrastructure failure.
                (error () t))))))))
(defun save-counterexample (commands &key original (kind :history) property context)
  (let ((file (format nil "/tmp/image-agent-counterexample-~d.sexp" *seed*)))
    (with-open-file (s file :direction :output :if-exists :supersede)
      (let ((*print-readably* t))
        (write (list :version 1 :generator-version 1 :seed *seed* :fixture '((:x . 0))
                     :kind kind :property property :failure-class (or property :model-mismatch)
                     :original (or original commands) :trace commands
                     :context (or context *failure-context*)
                     :sbcl (lisp-implementation-version)
                     :dependencies (uiop:read-file-string "devenv.lock")) :stream s)))
    (format t "Replay: devenv shell test-replay ~a~%" file)))
(defun raises-error-p (thunk)
  (handler-case (progn (funcall thunk) nil) (error () t)))
(defun pure-property-passes-p (name input)
  (handler-case
      (ecase name
        (:native-calls (native-property-p input))
        (:protection
         (let ((package (make-package (format nil "PARSE-~a" (gensym)) :use '(:cl))))
           (unwind-protect
               (let ((bad "(setf image-agent::session-budget 999)"))
                 (dotimes (depth input) (setf bad (format nil "(progn nil ~a)" bad)))
                 (and (raises-error-p (lambda () (image-agent:validate-form (image-agent:parse-one-form bad package))))
                      (raises-error-p (lambda () (image-agent:parse-one-form "#. (error \"read\")" package)))
                      (raises-error-p (lambda () (image-agent:parse-one-form "nil nil" package)))))
             (delete-package package))))
        (:response
         (let* ((form (format nil "(+ ~d 1)" input))
                (text (image-agent::json-text (image-agent::json-object "action" "develop" "source" form))))
           (and (equal form (getf (image-agent:parse-sse (sse text)) :source))
                (raises-error-p (lambda () (image-agent:parse-sse (sse text nil)))))))
        (:chunks
         (destructuring-bind (number lengths) input
           (let* ((form (format nil "(list ~s ~d)" "λ🍋" number))
                  (text (sse (image-agent::json-text (image-agent::json-object "action" "develop" "source" form))))
                  (bytes (babel:string-to-octets text :encoding :utf-8))
                  (position 0)
                  (parts (loop for size in lengths while (< position (length bytes))
                               for end = (min (length bytes) (+ position size))
                               collect (prog1 (subseq bytes position end) (setf position end))))
                  (parts (append parts (when (< position (length bytes)) (list (subseq bytes position)))))
                  (stream (make-instance 'chunked-input :chunks parts)))
             (unwind-protect
                 (equal form (getf (image-agent:parse-sse (image-agent::read-response-stream stream)) :source))
               (close stream))))))
    (error () nil)))
(defun valid-pure-input-p (name input)
  (case name
    ((:response :protection :native-calls) (and (integerp input) (<= 0 input 10000)))
    (:chunks (and (listp input) (= (length input) 2) (integerp (first input))
                  (listp (second input))
                  (every (lambda (x) (and (integerp x) (plusp x))) (second input))))))
(defun exercise-property (name input)
  (if (pure-property-passes-p name input) (pass)
      (let ((small input) (attempts 0))
        (catch 'limit
          (check-it:shrink input
            (lambda (candidate)
              (when (> (incf attempts) 100) (throw 'limit nil))
              (if (not (valid-pure-input-p name candidate)) t
                  (let ((ok (pure-property-passes-p name candidate)))
                    (unless ok (setf small candidate)) ok)))))
        (save-counterexample small :original input :kind :pure :property name
                                   :context (list :shrink-attempts attempts))
        (fail "Property ~a failed: ~s" name small))))
(test stateful-generated-histories
  (dotimes (i *trials*)
    (let* ((gen (check-it:generator (list (check-it:tuple (or :set :define :fail :fail-define :resume :repair :stale :invalid) (integer -20 20)) :min-length 1 :max-length 40)))
           (commands (check-it:generate gen)))
      (if (generated-history commands) (pass)
        (let ((small (shrink-history commands)))
          (save-counterexample small :original commands) (fail "Generated history failed: ~s" small))))))
(test generated-protected-forms
  (dotimes (i *pure-trials*) (exercise-property :protection (random 8))))
(defun sse (text &optional (complete t))
  (format nil "data: ~a~%~%~a"
          (image-agent::json-text (image-agent::json-object "type" "response.output_text.delta" "delta" text))
          (if complete (format nil "data: {\"type\":\"response.completed\",\"response\":{\"status\":\"completed\"}}~%~%") "")))
(test generated-response-parsing
  (dotimes (i *pure-trials*) (exercise-property :response (random 10000)))
  (dolist (text '("" "prose" "{\"action\":\"done\"}" "{\"action\":\"develop\",\"source\":\"nil\",\"extra\":1}"))
    (signals error (image-agent:parse-action text))))
(test injected-transport
  (let ((proposer (image-agent:make-openai-proposer :model "test" :key "secret"
                    :transport (lambda (url key body)
                                 (is (search "/responses" url))
                                 (is (equal "secret" key))
                                 (let ((request (yason:parse body)))
                                   (is (gethash "stream" request))
                                   (is (listp (gethash "input" request))))
                                 (sse "{\"action\":\"develop\",\"source\":\"nil\"}")))))
    (is (eq :develop (getf (funcall proposer '(:goal "test")) :action)))))
(test durable-code-and-data
  (let ((store (temp-store)))
    (multiple-value-bind (w s v) (fixture (constantly nil) 10 store)
      (unwind-protect
          (progn
            (setf v (send s v :action :develop :source "(progn (setf (gethash :x *state*) 8) (defun f (x) (+ x 17)))"))
            (image-agent:close-session s)
            (let* ((fresh (image-agent:make-reference-world))
                   (recovered (image-agent:recover-session fresh store :goals (list (cons :done (constantly nil))))))
              (unwind-protect
                  (progn (image-agent:session-step recovered)
                         (is (= 8 (gethash :x (image-agent:reference-table fresh))))
                         (is (= 20 (function-value fresh))) (cover :recovery))
                (image-agent:close-session recovered))))
        (image-agent:close-session s)))))
(test publication-faults
  (dolist (point '(:before-export :after-export :artifacts-flushed :before-pointer :pointer-renamed :published))
    (let ((store (temp-store)))
      (multiple-value-bind (w s v) (fixture (constantly nil) 10 store)
        (let ((old image-agent:*store-boundary-hook*))
          (unwind-protect
              (progn
                (setf image-agent:*store-boundary-hook* (lambda (p) (when (eq p point) (error "fault"))))
                (setf v (send s v :action :develop :source "(setf (gethash :x *state*) 9)"))
                (setf image-agent:*store-boundary-hook* old)
                (let ((fresh (image-agent:make-reference-world)))
                  (image-agent:load-revision fresh store)
                  (is (= (if (member point '(:pointer-renamed :published)) 9 0)
                         (gethash :x (image-agent:reference-table fresh))))))
            (setf image-agent:*store-boundary-hook* old)
            (image-agent:close-session s)))))))
(defun main (mode seed)
  (let ((*seed* seed) (*random-state* (sb-ext:seed-random-state seed))
        (*trials* (if (equal mode "stress") 2000 200))
        (*pure-trials* (if (equal mode "stress") 10000 1000))
        (check-it:*list-size* 40)
        (*crash-trials* (if (equal mode "stress") 200 20)))
    (cond ((equal mode "live") (live-test) (cli-live-test) (composition-live-test) (removal-live-test) (context-live-test))
          ((equal mode "replay")
           (let* ((file (third sb-ext:*posix-argv*)) (record (image-agent::read-record file)))
             (unless (if (eq (getf record :kind) :context-history)
                         (context-history-p (getf record :trace))
                         (if (eq (getf record :kind) :pure)
                         (pure-property-passes-p (getf record :property) (getf record :trace))
                         (if (eq (getf record :kind) :rollback-history)
                             (rollback-history-p (getf record :trace))
                             (if (eq (getf record :kind) :composition-history)
                                 (composition-history-p (getf record :trace))
                                 (generated-history (getf record :trace))))))
               (error "Replay failed"))))
          (t (unless (run! 'kernel) (sb-ext:exit :code 1))
             (dolist (category '(:pause :repair :rollback :stale :exhausted :fail :define :set :resume :recovery :process-recovery))
               (unless (plusp (gethash category *coverage* 0)) (error "Missing coverage: ~a" category)))
             (format t "Coverage: ~s~%" (loop for k being the hash-keys of *coverage* using (hash-value v) collect (cons k v)))))))
(defun live-test ()
  (let* ((w (image-agent:make-reference-world))
         (s (image-agent:make-session w :goal "Set :x in *state* to 7."
               :goals (list (cons :seven (lambda () (= 7 (gethash :x (image-agent:reference-table w) 0))))) :budget 5))
         (result (image-agent:run s (image-agent:make-openai-proposer))))
    (unless (eq :success (getf result :status)) (error "Live repair failed: ~s" result))
    (format t "Underclass live image mutation: success~%")))
(test property-feedback-and-isolation
  (let* ((w (image-agent:make-reference-world :initial '((:x . 0))))
         (property (image-agent:make-property-check w :nonnegative
           :generator (lambda (size) (declare (ignore size)) -7)
           :assertion (lambda (x) (setf (gethash :x (image-agent:reference-table w)) 99) (>= x 0))
           :shrink #'check-it:shrink :cases 30 :shrink-limit 20))
         (result (funcall (cdr property))))
    (is (eq :fail (getf result :status)))
    (is (= 0 (gethash :x (image-agent:reference-table w))))
    (is (< (abs (getf result :counterexample)) 7))
    (let ((s (image-agent:make-session w :goals (list property) :budget 1)))
      (unwind-protect
          (let ((v (image-agent:session-step s)))
            (is (eq :idle (getf v :status)))
            (is (getf (first (getf v :goals)) :counterexample)))
        (image-agent:close-session s)))))
(test generated-process-recovery
  (dotimes (i *crash-trials*)
    (let* ((point (nth (mod i 6) '("before-export" "after-export" "artifacts-flushed"
                                  "before-pointer" "pointer-renamed" "published")))
           (n (+ 2 (random 100))) (store (temp-store)))
      (let* ((child (uiop:launch-program
                      (list (first sb-ext:*posix-argv*) "--noinform" "--script" "tests/crash-child.lisp"
                            "crash" (namestring store) point (princ-to-string n))
                      :output :stream :error-output :output))
             (exit (uiop:wait-process child)))
        (is (not (zerop exit)))
        (uiop:close-streams child))
      (let ((expected (if (member point '("pointer-renamed" "published") :test #'equal) n 1)))
        (multiple-value-bind (out err exit)
            (uiop:run-program
              (list (first sb-ext:*posix-argv*) "--noinform" "--script" "tests/crash-child.lisp"
                    "recover" (namestring store) "none" (princ-to-string expected))
              :output :string :error-output :string :ignore-error-status t)
          (declare (ignore out)) (is (= 0 exit) "Recovery failed: ~a" err)))
      (cover :process-recovery))))
(defclass chunked-input (sb-gray:fundamental-binary-input-stream)
  ((chunks :initarg :chunks :accessor chunks) (offset :initform 0 :accessor offset)))
(defmethod stream-element-type ((stream chunked-input)) '(unsigned-byte 8))
(defmethod sb-gray:stream-read-byte ((stream chunked-input))
  (loop while (chunks stream) do
    (let ((chunk (first (chunks stream))))
      (if (< (offset stream) (length chunk))
          (return-from sb-gray:stream-read-byte (prog1 (aref chunk (offset stream)) (incf (offset stream))))
          (progn (pop (chunks stream)) (setf (offset stream) 0)))))
  :eof)
(test generated-byte-chunk-boundaries
  (dotimes (i *pure-trials*)
    (exercise-property :chunks (list (random 100) (loop repeat 100 collect (1+ (random 13)))))))
(test interrupted-journal-does-not-replay
  (let ((store (temp-store)))
    (multiple-value-bind (w s v) (fixture (constantly nil) 10 store)
      (unwind-protect
          (progn
            (setf v (send s v :action :develop :source "(setf (gethash :x *state*) 3)"))
            (image-agent:close-session s)
            (with-open-file (stream (merge-pathnames "events.sexp" store) :direction :output :if-exists :append)
              (write-string "(:event :action :proposal (" stream))
            (let ((fresh (image-agent:make-reference-world)))
              (image-agent:load-revision fresh store)
              (is (= 3 (gethash :x (image-agent:reference-table fresh))))
              (is (plusp (length (image-agent::journal-history store))))))
        (image-agent:close-session s)))))
(test malformed-and-property-check-errors
  (signals error (image-agent:parse-action "{\"action\":\"abort\"} prose"))
  (signals error (image-agent:parse-one-form "#1=(progn . #1#) nil" (find-package :cl-user)))
  (signals error (image-agent:validate-form (image-agent:parse-one-form "#1=(progn . #1#)" (find-package :cl-user))))
  (let* ((w (image-agent:make-reference-world))
         (property (image-agent:make-property-check w :broken :generator (lambda (size) size)
                       :assertion (lambda (x) (declare (ignore x)) (error "property read failure")))))
    (is (eq :error (getf (funcall (cdr property)) :status)))))
(test restore-error-and-owner-exclusivity
  (let* ((w (image-agent:make-reference-world :initial '((:x . 0))))
         (original (image-agent:world-restore w))
         (s (image-agent:make-session w :goals (list (cons :never (constantly nil)))))
         (v (image-agent:session-step s)))
    (unwind-protect
        (progn
          (signals error (image-agent:make-session w :goals (list (cons :never (constantly nil)))))
          (setf (image-agent:world-restore w) (lambda (snap) (declare (ignore snap)) (error "restore failed")))
          (setf v (send s v :action :develop :source "(progn (setf (gethash :x *state*) 99) (error \"pause\"))"))
          (setf v (send s v :action :abort))
          (is (eq :faulted (getf v :status))))
      (setf (image-agent:world-restore w) original) (image-agent:close-session s))))
(test last-action-can-succeed
  (let* ((w (image-agent:make-reference-world :initial '((:x . 0))))
         (s (image-agent:make-session w :budget 1 :goals (list (cons :done
                  (lambda () (= 1 (gethash :x (image-agent:reference-table w))))))))
         (v (image-agent:session-step s)))
    (unwind-protect
        (is (eq :success (getf (send s v :action :develop :source "(setf (gethash :x *state*) 1)") :status)))
      (image-agent:close-session s))))
(test oracle-detects-mutation-and-shrinks
  ;; Deliberately wrong emitted function checks that the oracle is independent.
  (let* ((*mutate-definitions* t)
         (trace '((:set 12) (:define 9) (:set 4)))
         (small (shrink-history trace)))
    (is (not (generated-history trace)))
    (is (valid-history-p small))
    (is (not (generated-history small)))
    (is (< (length small) (length trace)))
    (is (eq :define (first (first small))))))
(test infrastructure-failure-is-terminal
  (let* ((w (image-agent:make-reference-world))
         (s nil))
    (setf (image-agent:world-observe w) (lambda () (error "observation failed")))
    (setf s (image-agent:make-session w :goals (list (cons :never (constantly nil)))))
    (unwind-protect
        (is (eq :faulted (getf (image-agent:session-step s) :status)))
      (image-agent:close-session s)))
  (let* ((store (temp-store)) (w (image-agent:make-reference-world)) (s nil))
    (ensure-directories-exist (merge-pathnames "events.sexp/" store))
    (setf s (image-agent:make-session w :store store :goals (list (cons :never (constantly nil)))))
    (unwind-protect
        (is (eq :faulted (getf (image-agent:session-step s) :status)))
      (image-agent:close-session s))))
(test recovery-archives-torn-journal
  (let ((store (temp-store)))
    (multiple-value-bind (w s v) (fixture (constantly nil) 10 store)
      (declare (ignore w v))
      (image-agent:close-session s))
    (with-open-file (stream (merge-pathnames "events.sexp" store) :direction :output :if-exists :append)
      (write-string "(:event :incomplete" stream))
    (let* ((fresh (image-agent:make-reference-world))
           (s (image-agent:recover-session fresh store :goals (list (cons :never (constantly nil)))))
           (v (image-agent:session-step s)))
      (unwind-protect
          (progn
            (setf v (send s v :action :develop :source "(setf (gethash :x *state*) 5)"))
            (is (= 5 (gethash :x (image-agent:reference-table fresh))))
            (is (not (nth-value 1 (image-agent::journal-history store))))
            (is (not (null (directory (merge-pathnames "events-torn-*.sexp" store))))))
        (image-agent:close-session s)))))
(test recorder-failure-restores-without-model-repair
  (multiple-value-bind (w s v) (fixture)
    (unwind-protect
        (progn
          (setf (image-agent:world-record-form w) (lambda (form) (declare (ignore form)) (error "recorder failed")))
          (setf v (send s v :action :develop :source "(setf (gethash :x *state*) 99)"))
          (is (eq :faulted (getf v :status)))
          (is (= 0 (gethash :x (image-agent:reference-table w)))))
      (image-agent:close-session s))))
(test missing-live-configuration-is-explicit
  (signals image-agent:configuration-error (image-agent:make-openai-proposer :model nil :key "test"))
  (signals image-agent:configuration-error (image-agent:make-openai-proposer :model "test" :key nil)))
(test generalized-boolean-goals
  (dolist (value '((1) (a . b) #(1) :true))
    (let* ((w (image-agent:make-reference-world))
           (s (image-agent:make-session w :goals (list (cons :truth (lambda () value))))))
      (unwind-protect
          (is (eq :success (getf (image-agent:session-step s) :status)))
        (image-agent:close-session s)))))
