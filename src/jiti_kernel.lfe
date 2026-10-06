;;;; Experimental LFE evaluator. Only the controller owns accepted snapshots.
;;;; Exceptions unwind: repair retries explicit actions, never a live stack.
(defmodule jiti_kernel
  (export (evaluate 4) (checks 4) (state-get 1) (state-put 2)
          (state-delete 1) (forget 2) (durable 1) (background 2)
          (invoke 2) (define 4) (eval-source 1)))

(defun state-get (key)
  (maps:get key (map-get (get 'jiti_candidate) 'state) 'undefined))

(defun state-put (key value)
  (case (andalso (durable key) (durable value))
    ('false (error 'non_durable_state))
    ('true
     (let* ((candidate (get 'jiti_candidate))
            (state (map-set (map-get candidate 'state) key value)))
       (put 'jiti_candidate (map-set candidate 'state state))
       value))))

(defun state-delete (key)
  (let ((candidate (get 'jiti_candidate)))
    (put 'jiti_candidate (map-set candidate 'state
                         (maps:remove key (map-get candidate 'state))))
    'ok))

(defun forget (name arity)
  (let ((candidate (get 'jiti_candidate)))
    (put 'jiti_candidate (map-set candidate 'definitions
                         (maps:remove (tuple name arity) (map-get candidate 'definitions))
                         'catalogue (maps:remove (tuple name arity)
                                      (maps:get 'catalogue candidate (map)))))
    'ok))

(defun durable (value)
  (cond
    ((orelse (is_atom value) (is_number value) (is_binary value)) 'true)
    ((is_list value) (lists:all (fun durable 1) value))
    ((is_tuple value) (durable (tuple_to_list value)))
    ((is_map value) (durable (maps:to_list value)))
    ('true 'false)))

(defun environment (candidate)
  (let* ((base (lfe_env:new))
         (helpers (list
                    (tuple 'state-get 1 '(lambda (key) (jiti_kernel:state-get key)))
                    (tuple 'state-put 2 '(lambda (key value) (jiti_kernel:state-put key value)))
                    (tuple 'state-delete 1 '(lambda (key) (jiti_kernel:state-delete key)))
                    (tuple 'forget 2 '(lambda (name arity) (jiti_kernel:forget name arity)))))
         (env (lists:foldl
                (lambda (binding acc)
                  (let (((tuple name arity definition) binding))
                    (lfe_eval:add_dynamic_func name arity definition acc)))
                base helpers))
         (bindings (lists:map
                     (lambda (entry)
                       (let (((tuple (tuple name arity) definition) entry))
                         (tuple name arity definition)))
                     (maps:to_list (map-get candidate 'definitions)))))
    (lfe_eval:make_letrec_env bindings env)))

(defun arity
  (((cons 'lambda (cons arguments _))) (length arguments))
  (((cons 'match-lambda (cons (cons arguments _) _))) (length arguments)))

(defun validate-definition (name definition env)
  (case (is_atom name)
    ('false (error 'invalid_function_name)) ('true 'ok))
  (case (lfe_lint:expr (lfe_macro:expand_expr_all definition env))
    ((tuple 'ok _ _) 'ok)
    ((tuple 'error errors _)
     ;; Forward references and recursion are resolved when the function runs.
     ;; Reader, pattern and unbound-variable errors cannot become accepted code.
     (case (lists:all
             (lambda (entry)
               (case entry
                 ((tuple _ 'lfe_lint (tuple 'undefined_function _)) 'true)
                 (_ 'false))) errors)
       ('true 'ok) ('false (error 'invalid_definition))))))

(defun eval-form (form)
  (let* ((env (environment (get 'jiti_candidate)))
         (expanded (case (lfe_macro:expand_expr form env)
                     ((tuple 'yes value) value) ('no form))))
    (case expanded
      ((list 'define-function name meta definition)
       (validate-definition name definition env)
       (let* ((count (arity definition))
              (candidate (get 'jiti_candidate)))
         (case (lists:member name '(state-get state-put state-delete forget))
           ('true (error 'reserved_function)) ('false 'ok))
         (put 'jiti_candidate (map-set candidate 'definitions
                              (map-set (map-get candidate 'definitions)
                                       (tuple name count) definition)
                              'catalogue (map-set (maps:get 'catalogue candidate (map))
                                            (tuple name count) (jiti_catalogue:metadata form meta))))
         name))
      ((cons 'progn forms) (eval-forms forms 'ok))
      (_ (lfe_eval:expr expanded env)))))

(defun eval-forms
  ((() value) value)
  (((cons form rest) _) (eval-forms rest (eval-form form))))

;; Typed entry points execute inside the same provisional worker and environment.
;; Unknown lookups never intern caller-provided names. Definition names are code.
(defun invoke (name arguments)
  (let* ((candidate (get 'jiti_candidate))
         (matches (lists:filter
           (lambda (key)
             (let (((tuple symbol count) key))
               (andalso (=:= (atom_to_binary symbol 'utf8) name)
                        (=:= count (length arguments)))))
           (maps:keys (map-get candidate 'definitions)))))
    (case matches
      ((list (tuple symbol _))
       (lfe_eval:expr (cons symbol (lists:map (lambda (value) (list 'quote value)) arguments))
                      (environment candidate)))
      (_ (error 'function_not_found)))))

(defun define (name arguments body documentation)
  (case (andalso (is_binary name) (> (byte_size name) 0) (=< (byte_size name) 128)
                 (is_list arguments) (=< (length arguments) 16)
                 (=:= (length arguments) (length (lists:usort arguments)))
                 (lists:all (lambda (arg) (andalso (is_binary arg) (> (byte_size arg) 0)
                                                   (=< (byte_size arg) 128))) arguments))
    ('true 'ok) (_ (error 'invalid_function_request)))
  (let* ((symbol (binary_to_atom name 'utf8))
         (args (lists:map (lambda (arg) (binary_to_atom arg 'utf8)) arguments))
         (forms (parse (unicode:characters_to_list body)))
         (docs (if (=:= documentation #B()) ()
                    (list (unicode:characters_to_list documentation)))))
    (eval-form (++ (list 'defun symbol args) docs forms))))

(defun eval-source (source)
  (eval-forms (parse (unicode:characters_to_list source)) 'ok))

(defun parse (source)
  (case (lfe_io:read_string source)
    ((tuple 'ok ()) (error 'empty_source))
    ((tuple 'ok forms) forms)
    (_ (error 'invalid_source))))

(defun run-checks (sources candidate)
  (lists:all
    (lambda (source)
      (put 'jiti_candidate candidate)
      (try
        (let* ((value (eval-forms (parse source) 'ok))
               (after-check (get 'jiti_candidate)))
          (andalso (=:= value 'true) (=:= after-check candidate)))
        (catch ((tuple _ _ _) 'false))))
    sources))

(defun worker (snapshot source safety goals)
  (put 'jiti_candidate snapshot)
  (try
    (let* ((value (eval-forms (parse source) 'ok))
           (candidate (get 'jiti_candidate))
           (safe (run-checks safety candidate))
           (goal (andalso (/= goals ()) (run-checks goals candidate))))
      (if safe
          (tuple 'ok candidate value goal)
          (tuple 'rejected 'safety_failed)))
    (catch
      ((tuple class reason _) (tuple 'paused (tuple class reason))))))

(defun bounded (task timeout)
  (let* ((parent (self))
         (tag (make_ref))
         (sink (spawn (lambda () (io-sink))))
         ((tuple pid monitor)
          (spawn_monitor (lambda ()
                           (group_leader sink (self))
                           (! parent (tuple tag (funcall task)))))))
    (try
      (receive
        ((tuple tag result)
         (erlang:demonitor monitor '(flush))
         result)
        ((tuple 'DOWN monitor 'process pid _)
         (tuple 'paused 'worker_failed))
        (after timeout
          (exit pid 'kill)
          (receive ((tuple 'DOWN monitor 'process pid _) 'ok))
          (receive ((tuple tag _) 'ok) (after 0 'ok))
          (tuple 'paused 'timeout)))
      (after (progn (unlink sink) (exit sink 'kill))))))

;; Cooperative terminal output is discarded so it cannot forge JSON replies.
;; Arbitrary explicit file/port I/O remains outside managed rollback.
(defun io-sink ()
  (receive
    ((tuple 'io_request from reply-as _)
     (! from (tuple 'io_reply reply-as 'ok))
     (io-sink))))

(defun background (snapshot source)
  (let ((sink (spawn_link (lambda () (io-sink)))))
    (group_leader sink (self))
    (try
      (case (worker snapshot source () ())
        ((tuple 'ok candidate value _) (when (=:= candidate snapshot))
         (if (durable value) (tuple 'ok value) (tuple 'error 'non_durable_background_result)))
        ((tuple 'ok _ _ _) (tuple 'error 'background_managed_mutation))
        (_ (tuple 'error 'background_evaluation_failed)))
      (after (progn (unlink sink) (exit sink 'kill))))))

(defun evaluate (snapshot source contract timeout)
  (bounded (lambda ()
             (worker snapshot source (map-get contract 'safety)
                     (map-get contract 'goals))) timeout))

(defun checks (snapshot safety goals timeout)
  (bounded (lambda ()
             (put 'jiti_candidate snapshot)
             (tuple 'checks (run-checks safety snapshot)
                    (andalso (/= goals ()) (run-checks goals snapshot)))) timeout))
