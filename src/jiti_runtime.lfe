;;;; Session runtime ownership is separate from durable managed planning data.
(defmodule jiti_runtime
  (behaviour supervisor)
  (export (start_link 0) (init 1)))
(defun start_link () (supervisor:start_link (tuple 'local 'jiti_runtime) 'jiti_runtime ()))
(defun init (_)
  (tuple 'ok (tuple (map 'strategy 'one_for_one 'intensity 3 'period 10)
    (list (map 'id 'jiti_processes 'start (tuple 'jiti_processes 'start_link ())
               'restart 'permanent 'shutdown 2000 'type 'worker 'modules '(jiti_processes))))))
