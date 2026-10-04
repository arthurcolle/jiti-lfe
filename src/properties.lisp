(in-package :image-agent)
(defun make-property-check (world name &key generator assertion (seed 424242)
                                          (cases 100) (size 20) shrink (shrink-limit 100))
  "Return a named predicate for GOALS or INVARIANTS. GENERATOR takes SIZE;
ASSERTION takes its sample. Each sample and shrink replay has isolated world state."
  (unless (and (functionp generator) (functionp assertion) (plusp cases)
               (integerp cases) (integerp shrink-limit) (>= shrink-limit 0))
    (error 'configuration-error :message "Property needs generator/assertion and positive case count"))
  (cons name
        (lambda ()
          (let ((*random-state* (sb-ext:seed-random-state seed))
                (checks 0) (failure nil) (status :pass) (small nil) (shrink-count 0))
            (labels ((sample-test (sample)
                       (let ((checkpoint (funcall (world-snapshot world))))
                         (unwind-protect (funcall assertion sample)
                           (funcall (world-restore world) checkpoint)))))
              (loop repeat cases do
                (let ((checkpoint (funcall (world-snapshot world))))
                  (unwind-protect
                       (handler-case
                           (let ((sample (funcall generator size)))
                             (incf checks)
                             (unless (sample-test sample)
                               (setf failure sample status :fail) (return)))
                         (error (c) (setf status :error failure (bounded c)) (return)))
                    (funcall (world-restore world) checkpoint))))
              (setf small failure)
              (when (and shrink (eq status :fail))
                (handler-case
                    (setf small
                          (catch 'shrink-limit
                            (funcall shrink failure
                              (lambda (candidate)
                                (when (>= (incf shrink-count) shrink-limit)
                                  (throw 'shrink-limit small))
                                ;; A failing assertion must remain a false value, not an exception.
                                (handler-case
                                    (let ((passes (sample-test candidate)))
                                      (unless passes (setf small candidate)) passes)
                                  (error () t))))))
                  (error () nil)))
              (list :property-result t :status status :seed seed :cases checks
                    :size size :counterexample small :shrink-attempts shrink-count))))))
