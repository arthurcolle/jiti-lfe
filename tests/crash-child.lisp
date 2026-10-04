(require :asdf)
(push (truename "./") asdf:*central-registry*)
(asdf:load-system "image-agent/store")
(let* ((args (cdr sb-ext:*posix-argv*)) (mode (first args)) (store (second args))
       (point (third args)) (value (and (fourth args) (parse-integer (fourth args))))
       (world (image-agent:make-reference-world)))
  (cond
    ((equal mode "recover")
     (image-agent:load-revision world store)
     (unless (and (= value (gethash :x (image-agent:reference-table world)))
                  (= (+ 3 value)
                     (funcall (symbol-function (find-symbol "F" (image-agent:world-package world))) 3)))
       (error "Fresh process recovered mixed code/data")))
    (t
     (let* ((s (image-agent:make-session world :store store
                                       :goals (list (cons :never (constantly nil)))))
            (v (image-agent:session-step s)))
       (setf v (image-agent:session-step s (list :action :evaluate :generation (getf v :generation)
                           :source "(progn (setf (gethash :x *state*) 1) (defun f (x) (+ x 1)))")))
       (setf image-agent:*store-boundary-hook*
             (lambda (boundary)
               (when (equal point (string-downcase (symbol-name boundary)))
                 (sb-posix:kill (sb-posix:getpid) sb-posix:sigkill))))
       (image-agent:session-step s
         (list :action :evaluate :generation (getf v :generation)
               :source (format nil "(progn (setf (gethash :x *state*) ~d) (defun f (x) (+ x ~d)))" value value)))
       (error "Crash boundary not exercised")))))
