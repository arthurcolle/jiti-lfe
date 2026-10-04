(in-package :image-agent/tests)
(in-suite kernel)
(defparameter *unicode-correct-source*
  "(defun reverse-string (string) (with-output-to-string (out) (when (plusp (length string)) (dolist (cluster (reverse (sb-unicode:graphemes string))) (write-string cluster out)))))")
(defun evolution-fixture (&key (budget 100) (cases 1000) artifacts store)
  (multiple-value-bind (spec report)
      (image-agent/experiments:make-reverse-world :cases cases :artifacts artifacts)
    (let* ((world (getf spec :world))
           (session (image-agent:make-session world :interactive t :budget budget :store store
                         :goals (getf spec :goals) :invariants (getf spec :invariants)))
           (controller (image-agent/cli:make-controller session)))
      (values world session controller report))))
(defun sample-on-worker (world session control text &rest options)
  (let ((result nil) (original-goals (image-agent::session-goals session)))
    (unwind-protect
        (progn
          (setf (image-agent::session-goals session)
                (list (cons :sample (lambda ()
                                     (setf result (apply #'image-agent/experiments:check-sample world text options))
                                     (getf result :passed)))))
          (cli-action control :check)
          result)
      (setf (image-agent::session-goals session) original-goals))))
(test unicode-fixed-oracle-and-generated-contract
  (dolist (fixture (image-agent/experiments:reverse-fixtures))
    (is (string= (third fixture) (image-agent/experiments::expected-output (second fixture)))))
  (multiple-value-bind (world session control report) (evolution-fixture)
    (unwind-protect
        (progn
          (is (eq :undefined-function (getf (getf (car report) :counterexample) :problem)))
          (cli-action control :evaluate :source *unicode-correct-source*)
          (is (getf (image-agent/cli:controller-view control) :goals-achieved))
          (is (= 1000 (getf (car report) :cases)))
          (dolist (shape '(:simple :adjustable :displaced))
            (is (getf (sample-on-worker world session control "👩🏽‍💻éשלום" :shape shape) :passed)))
          ;; Deliberately exclude universal involution: boundaries can change on reversal.
          (let ((input (concatenate 'string (string (code-char #x301)) "a")))
            (is (not (string= input (image-agent/experiments::expected-output
                                     (image-agent/experiments::expected-output input)))))))
      (image-agent:close-session session))))
(test unicode-mutation-and-failure-replay
  (let ((root (temp-store)))
    (multiple-value-bind (world session control report) (evolution-fixture :artifacts root)
      (unwind-protect
          (progn
            (cli-action control :evaluate :source "(defun reverse-string (s) (reverse s))")
            (is (eq :fail (getf (car report) :status)))
            (let* ((artifact (getf (car report) :artifact))
                   (record (image-agent::read-record artifact)))
              (is (eq :unicode-reversal (getf record :kind)))
              (is (<= (length (getf record :input)) (length (getf record :original))))
              (is (<= (getf record :shrink-attempts) 100))
              (is (eq :reproduced (image-agent/experiments::replay artifact (make-broadcast-stream))))
              (is (every (lambda (s) (not (search "WORLD-" s))) (getf record :definitions))))
            (cli-action control :evaluate :source "(defun reverse-string (s) (nreverse s))")
            (let ((sample (sample-on-worker world session control "abc")))
              (is (eq :input-mutated (getf sample :problem))))
            (cli-action control :evaluate :source "(progn (defun reverse-string (s) (setf (gethash :x *state*) 99) (reverse s)))")
            (let ((sample (sample-on-worker world session control "abc")))
              (is (getf sample :passed))
              (is (= 0 (gethash :x (image-agent:reference-table world)))))
            (cli-action control :evaluate :source "(defun reverse-string (s) (declare (ignore s)) (error \"failed\"))")
            (is (eq :candidate-signaled (getf (sample-on-worker world session control "abc") :problem))))
        (image-agent:close-session session)))))
(test evolution-prompts-repair-and-reject-false-success
  (multiple-value-bind (world session control report) (evolution-fixture)
    (declare (ignore world))
    (let ((step 0) (requests nil))
      (unwind-protect
          (let* ((chat (image-agent/cli:make-chat control :model "fake" :key "fake-key"
                         :transport (lambda (url key body)
                           (declare (ignore url key))
                           (push (image-agent/cli::parse-json body) requests)
                           (case (incf step)
                             (1 (native-sse (native-call "bad" "evaluate_form" "source" "(defun reverse-string (s) (reverse s))"
                                            "generation" (getf (image-agent/cli:controller-view control) :generation))))
                             (2 (native-sse (native-message "Everything works.")))
                             (3 (native-sse (native-call "good" "evaluate_form" "source" *unicode-correct-source*
                                            "generation" (getf (image-agent/cli:controller-view control) :generation))))
                             (4 (native-sse (native-message "Repaired.")))))))
                 (result (image-agent/experiments:evolve control chat image-agent/experiments::+goal+ :output (make-broadcast-stream))))
            (is (eq :success (getf result :status)))
            (is (= 2 (getf result :rounds)))
            (is (= 1000 (getf (car report) :cases)))
            (let* ((second-round (third (reverse requests)))
                   (prompts (remove-if-not (lambda (message) (equal "user" (gethash "role" message)))
                                            (coerce (gethash "input" second-round) 'list)))
                   (feedback (gethash "content" (car (last prompts)))))
              (is (search "caller has not accepted" feedback))
              (is (search "COUNTEREXAMPLE" feedback))
              (is (not (search "(defun reverse-string" (gethash "content" (first prompts)))))))
        (image-agent:close-session session)))))
(test evolution-round-and-worker-budgets
  (multiple-value-bind (world session control report) (evolution-fixture :budget 10)
    (declare (ignore world report))
    (let ((requests 0))
      (unwind-protect
          (let* ((chat (image-agent/cli:make-chat control :model "fake" :key "fake-key"
                         :transport (lambda (&rest args) (declare (ignore args))
                                      (incf requests) (native-sse (native-message "Done.")))))
                 (result (image-agent/experiments:evolve control chat "Add reverse-string" :output (make-broadcast-stream))))
            (is (eq :failed (getf result :status)))
            (is (= 3 requests))
            (is (eq :round-budget (getf result :reason))))
        (image-agent:close-session session))))
  (multiple-value-bind (world session control report) (evolution-fixture :budget 1)
    (declare (ignore world report))
    (unwind-protect
        (let* ((chat (image-agent/cli:make-chat control :model "fake" :key "fake-key"
                       :transport (lambda (&rest args) (declare (ignore args))
                                    (native-sse (native-call "one" "evaluate_form" "source" "(defun reverse-string (s) (reverse s))"
                                          "generation" (getf (image-agent/cli:controller-view control) :generation))))))
               (result (image-agent/experiments:evolve control chat "Add reverse-string" :output (make-broadcast-stream))))
          (is (eq :failed (getf result :status)))
          (is (eq :exhausted (getf (image-agent/cli:controller-view control) :status))))
      (image-agent:close-session session))))
(test evolution-complete-lifecycle-with-fake-model
  (let ((store (temp-store)))
    (let* ((step 0)
           (result (image-agent/experiments::run-experiment store 424242 1000 (make-broadcast-stream)
                     :chat-factory
                     (lambda (control)
                       (image-agent/cli:make-chat control :model "fake" :key "fake-key"
                         :transport (lambda (&rest args) (declare (ignore args))
                                      (if (= 1 (incf step))
                                          (native-sse (native-call "one" "evaluate_form" "source" *unicode-correct-source*
                                                        "generation" (getf (image-agent/cli:controller-view control) :generation)))
                                          (native-sse (native-message "Defined it.")))))))))
      (is (eq :success (getf result :status)))
      (is (probe-file (merge-pathnames "generated-source.lisp" store)))
      (let ((history (image-agent:list-revisions store)))
        (is (= 4 (length history)))
        (is (equal (getf result :revision) (getf (first history) :rollback-source)))))))
(test experiment-protection-and-bidi-printing
  (multiple-value-bind (world session control report) (evolution-fixture :cases 1)
    (declare (ignore world report))
    (unwind-protect
        (progn
          (cli-action control :evaluate :source "(progn nil (setf image-agent/experiments::+goal+ \"bypass\"))")
          (is (eq :restored (getf (getf (image-agent/cli:controller-view control) :outcome) :commit)))
          (is (search "Add a new function" image-agent/experiments::+goal+)))
      (image-agent:close-session session)))
  (let ((text (image-agent/experiments::escaped-text (image-agent/experiments::code-string #x2066 #x61 #x2069))))
    (is (search "2066" text))
    (is (not (find (code-char #x2066) text)))))
(test unicode-shared-empty-result-is-rejected
  (multiple-value-bind (world session control report) (evolution-fixture)
    (unwind-protect
        (progn
          (cli-action control :evaluate :source "(defun reverse-string (s) (if (zerop (length s)) \"\" (with-output-to-string (out) (dolist (g (reverse (sb-unicode:graphemes s))) (write-string g out)))))")
          (is (eq :result-reused (getf (getf (car report) :counterexample) :problem)))
          (is (not (getf (image-agent/cli:controller-view control) :goals-achieved)))
          (is (not (getf (sample-on-worker world session control "") :passed))))
      (image-agent:close-session session))))
(test failed-live-restart-restores-and-keeps-worker
  (dolist (source '("(progn (setf (gethash :x *state*) 7) (restart-bind ((use (lambda () 8))) (error \"arity\")))"
                    "(progn (setf (gethash :x *state*) 7) (restart-bind ((use (lambda (&rest args) (declare (ignore args)) (error \"restart body failed\")))) (error \"pause\")))"))
    (multiple-value-bind (world session view) (fixture)
      (unwind-protect
          (progn
            (setf view (send session view :action :evaluate :source source))
            (is (eq :paused (getf view :status)))
            (setf view (send session view :action :resume :restart-id (getf (first (getf view :restarts)) :id)
                                        :arguments "(list 1)"))
            (is (eq :idle (getf view :status)))
            (is (eq :restart-failed (getf (getf view :outcome) :reason)))
            (is (= 0 (gethash :x (image-agent:reference-table world))))
            (setf view (send session view :action :evaluate :source "(setf (gethash :x *state*) 4)"))
            (is (= 4 (gethash :x (image-agent:reference-table world)))))
        (image-agent:close-session session)))))
