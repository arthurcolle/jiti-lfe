;;;; Local agents.erl status bridge developed in the Jiti terminal.
;;;; Launch with distribution bound to loopback; use the existing cookie.
;;;; RPC and distribution are external effects, outside managed rollback.
(state-put 'agents-node 'agents_jiti@127.0.0.1)
(state-put 'agents-id #B("jiti-bridge-agent"))

(defun agents-status ()
  (let ((distribution-result
         (case (erlang:node)
           ('nonode@nohost
            (net_kernel:start (list (erlang:list_to_atom (++ "jiti_lfe_" (os:getpid) "@127.0.0.1")) 'longnames)))
           (_ (tuple 'ok 'already_started)))))
    (case distribution-result
      ((tuple 'ok _)
       (let ((remote-node (state-get 'agents-node)) (agent-id (state-get 'agents-id)))
         (case (net_kernel:connect_node remote-node)
           ('true
            (case (rpc:call remote-node 'agent_registry 'get_agent (list agent-id) 5000)
              ((tuple 'ok pid)
               (case (rpc:call remote-node 'agent_instance 'get_state (list pid) 5000)
                 ((tuple 'ok remote-state)
                  (when (is_map remote-state))
                  (maps:with '(id name type model autonomous_mode metrics) remote-state))
                 (remote-state
                  (when (is_map remote-state))
                  (maps:with '(id name type model autonomous_mode metrics) remote-state))
                 ((tuple 'badrpc reason) (tuple 'error (tuple 'state_rpc_failed reason)))
                 (_ (tuple 'error 'unexpected_state_response))))
              ((tuple 'badrpc reason) (tuple 'error (tuple 'registry_rpc_failed reason)))
              (_ (tuple 'error 'agent_lookup_failed))))
           (_ (tuple 'error 'connection_failed)))))
      ((tuple 'error reason) (tuple 'error (tuple 'distribution_start_failed reason)))
      (_ (tuple 'error 'unexpected_distribution_start_response)))))
