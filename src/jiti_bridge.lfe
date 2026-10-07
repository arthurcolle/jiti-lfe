;;;; JSON-lines controller. Owns accepted state, provisional repairs and tokens.
(defmodule jiti_bridge (export (main 0)))

(defun text (value)
  (unicode:characters_to_binary (lfe_io:print1 value 15)))

(defun response (controller status value reason goal)
  (let* ((snapshot (map-get controller 'snapshot))
         (reply (map 'status (atom_to_binary status 'utf8)
                     'revision (map-get snapshot 'revision)
                     'state (text (map-get snapshot 'state))
                     'value value 'reason reason 'goal goal)))
    (case (map-get controller 'pending)
      ('none reply)
      (pending (map-set reply 'token (map-get pending 'token))))))

(defun ok (controller value)
  (tuple controller (response controller 'ok value #B() 'false)))

(defun rejected (controller reason)
  (tuple controller (response controller 'rejected #B() (text reason) 'false)))

(defun tool-response (reply value)
  ;; Typed details are nested. They cannot replace revision, goal or repair token.
  (if (andalso (is_map value) (maps:is_key #B("native_tool_result") value))
      (map-set reply 'value #B() 'data (map-get value #B("native_tool_result"))) reply))

(defun publish (controller candidate)
  (let ((previous (map-get controller 'snapshot)))
    (if (andalso (=:= (map-get previous 'state) (map-get candidate 'state))
                 (=:= (map-get previous 'definitions) (map-get candidate 'definitions))
                 (=:= (maps:get 'catalogue previous (map)) (maps:get 'catalogue candidate (map))))
        controller
        (map-set controller 'snapshot
                 (jiti_store:publish (map-get controller 'directory) previous
                   (map-set candidate 'operation-id
                     (map-get (map-get controller 'operation) #B("id"))))))))

(defun attempt (controller source preview base repair)
  (case (jiti_kernel:evaluate base source (map-get controller 'contract)
                             (map-get controller 'timeout))
    ((tuple 'ok _ (map #B("native_tool_result") (map 'error code)) _)
     (let ((next (if repair (map-set controller 'pending 'none) controller)))
       (tuple next (map-set (response next 'rejected #B() code 'false)
                            'data (map 'error code)))))
    ((tuple 'ok candidate value goal)
     (let ((next (cond
                   (repair
                    (map-set controller 'pending
                             (map-set (map-get controller 'pending) 'candidate candidate)))
                   (preview (map-set controller 'pending 'none))
                   ('true (publish (map-set controller 'pending 'none) candidate)))))
       (tuple next (tool-response (response next 'ok (text value) #B() goal) value))))
    ((tuple 'rejected reason)
     ;; A failed repair aborts the whole provisional attempt.
     (let ((next (if repair (map-set controller 'pending 'none) controller)))
       (rejected next reason)))
    ((tuple 'paused reason)
     (if repair
         (let ((next (map-set controller 'pending 'none)))
           (rejected next 'repair_failed_attempt_aborted))
         (let* ((token (map-get controller 'next-token))
                (pending (map 'token token 'source source 'preview preview 'candidate base))
                (next (map-set controller 'pending pending 'next-token (+ token 1))))
           (tuple next (response next 'paused #B() (text reason) 'false)))))))

(defun token-valid (controller request)
  (case (map-get controller 'pending)
    ('none 'false)
    (pending (=:= (maps:get #B("token") request 'none) (map-get pending 'token)))))

(defun source (request)
  (let ((value (maps:get #B("source") request 'undefined)))
    (case (is_binary value)
      ('true
       (let ((decoded (unicode:characters_to_list value)))
         (case (is_list decoded)
           ('true decoded) ('false (error 'invalid_source)))))
      ('false (error 'source_required)))))

(defun visible-snapshot (controller)
  (case (map-get controller 'pending)
    ('none (map-get controller 'snapshot))
    (pending (map-get pending 'candidate))))

(defun inspection (controller details)
  (tuple controller (maps:merge (response controller 'ok #B() #B() 'false) details)))

(defun plan-list-inspection (controller request)
  (let* ((offset (maps:get #B("offset") request 0))
         ('true (andalso (is_integer offset) (>= offset 0)))
         (state (map-get (visible-snapshot controller) 'state))
         (plans (lists:keysort 1 (lists:filtermap
           (lambda (entry)
             (case entry
               ((tuple (tuple 'hierarchical-plan id) p) (when (is_binary id) (is_map p))
                (tuple 'true (tuple id p)))
               (_ 'false))) (maps:to_list state))))
         (count (length plans))
         (page (if (>= offset count) () (lists:sublist (lists:nthtail offset plans) 50))))
    (inspection controller
      (map 'plans (lists:map (lambda (entry)
        (let (((tuple id p) entry))
          (map 'id id 'title (map-get p 'title) 'version (map-get p 'version)
               'node_count (map_size (map-get p 'nodes)) 'started (map-get p 'started)))) page)
           'plan_count count 'next_offset (if (< (+ offset (length page)) count)
                                             (+ offset (length page)) 'null)))))

(defun plan-inspection (controller request)
  (let* ((id (maps:get #B("id") request #B()))
         ('true (andalso (is_binary id) (> (byte_size id) 0) (=< (byte_size id) 128)))
         (printed (lfe_io:print1 id 200))
         (source (lists:flatten (list "(map 'plan (jiti_plan:inspect " printed
                    ") 'frontier (jiti_plan:ready " printed "))")))
         (snapshot (visible-snapshot controller)))
    (case (jiti_kernel:evaluate snapshot source (map 'safety () 'goals ()) 1000)
      ((tuple 'ok candidate value _) (when (=:= snapshot candidate))
       (let ((p (map-get value 'plan)) (frontier (map-get value 'frontier)))
         (inspection controller
           (map 'plan_id id 'plan_version (map-get p 'version) 'ready (map-get frontier 'ready)
                'nodes (lists:map
                  (lambda (n)
                    (let ((job (map-get n 'job)))
                      (map 'id (map-get n 'id) 'title (map-get n 'title)
                           'priority (map-get n 'priority)
                           'parent (if (=:= (map-get n 'parent) 'none) 'null (map-get n 'parent))
                           'kind (atom_to_binary (map-get n 'kind) 'utf8)
                           'status (atom_to_binary (map-get n 'status) 'utf8)
                           'dependencies (map-get n 'deps)
                           'job_status (if (=:= job 'none) 'null
                                         (atom_to_binary (map-get job 'status) 'utf8))
                           'job_id (if (=:= job 'none) 'null (map-get job 'id))
                           'started_at (if (=:= job 'none) 'null (maps:get 'started_at job 'null))
                           'finished_at (if (=:= job 'none) 'null (maps:get 'finished_at job 'null))
                           'check_present (/= (map-get n 'check) #B())
                           'result (if (=:= job 'none) 'null (maps:get 'result job 'null)))))
                  (maps:values (map-get p 'nodes)))))))
      (_ (rejected controller 'plan_inspection_rejected)))))

(defun handle (controller request)
  (case (maps:get #B("op") request #B())
    (#B("open") (rejected controller 'already_open))
    (#B("quit") (ok controller #B()))
    (#B("status")
     (case (map-get controller 'pending)
       ('none (ok controller #B()))
       (_ (tuple controller (response controller 'paused #B() #B("awaiting_explicit_retry") 'false)))))
    (#B("history")
     (ok controller (text (jiti_store:history (map-get controller 'directory)
                                            (map-get controller 'snapshot)))))
    (#B("functions")
     (let ((offset (maps:get #B("offset") request 0)))
       (if (andalso (is_integer offset) (>= offset 0))
           (inspection controller (jiti_catalogue:page (visible-snapshot controller) offset))
           (rejected controller 'invalid_catalogue_offset))))
    (#B("describe")
     (let ((name (maps:get #B("name") request #B()))
           (arity (maps:get #B("arity") request -1)))
       (if (andalso (is_binary name) (is_integer arity) (>= arity 0))
           (inspection controller (jiti_catalogue:describe (visible-snapshot controller) name arity))
           (rejected controller 'invalid_function_request))))
    (#B("operations")
     (let* ((records (map-get controller 'operations))
            (page (lists:sublist records 25)))
       (inspection controller (map 'operations page 'operation_count (length records)
                                    'operations_truncated (> (length records) 25)))))
    (#B("plan_status")
     (try (plan-inspection controller request)
       (catch ((tuple _ _ _) (rejected controller 'invalid_plan_inspection)))))
    (#B("plan_list")
     (try (plan-list-inspection controller request)
       (catch ((tuple _ _ _) (rejected controller 'invalid_plan_listing)))))
    (#B("tool_inspect")
     (try
       (inspection controller (map 'data (jiti_toolkit:inspect (visible-snapshot controller)
         (map-get request #B("action")) (map-get request #B("arguments")))))
       (catch ((tuple _ reason _)
         (rejected controller (if (is_atom reason) reason 'invalid_tool_inspection))))))
    (op (when (orelse (=:= op #B("workspace_list")) (=:= op #B("workspace_read"))
                     (=:= op #B("workspace_stat"))))
        (case (jiti_workspace:inspect op request)
          ((tuple 'ok details) (inspection controller details))
          ((tuple 'error reason) (rejected controller reason))))
    (#B("abort")
     (if (token-valid controller request)
         (ok (map-set controller 'pending 'none) #B())
         (rejected controller 'stale_token)))
    (#B("retry")
     (if (token-valid controller request)
         (let ((pending (map-get controller 'pending)))
           (attempt controller (map-get pending 'source) (map-get pending 'preview)
                    (map-get pending 'candidate) 'false))
         (rejected controller 'stale_token)))
    (#B("repair")
     (if (token-valid controller request)
         (attempt controller (source request) 'false
                  (map-get (map-get controller 'pending) 'candidate) 'true)
         (rejected controller 'stale_token)))
    (#B("rollback")
     (if (/= (map-get controller 'pending) 'none)
         (rejected controller 'pending_attempt)
         (let* ((revision (maps:get #B("revision") request 'none))
                (history (jiti_store:history (map-get controller 'directory)
                                            (map-get controller 'snapshot))))
           (if (lists:member revision history)
               (let ((candidate (if (=:= revision 0) (jiti_store:new)
                                    (jiti_store:load-revision (map-get controller 'directory) revision))))
                 (case (jiti_kernel:checks candidate
                         (map-get (map-get controller 'contract) 'safety)
                         (map-get (map-get controller 'contract) 'goals)
                         (map-get controller 'timeout))
                   ((tuple 'checks 'true goal)
                    (let ((next (publish controller candidate)))
                      (tuple next (response next 'ok #B() #B() goal))))
                   (_ (rejected controller 'rollback_safety_failed))))
               (rejected controller 'unknown_revision)))))
    (op
     (if (lists:member op '(#B("execute") #B("develop") #B("preview")))
         (if (=:= (map-get controller 'pending) 'none)
             (attempt controller (source request) (=:= op #B("preview"))
                      (map-get controller 'snapshot) 'false)
             (rejected controller 'pending_attempt))
         (rejected controller 'unknown_operation)))))

(defun tracked (controller request)
  (let ((op (maps:get #B("op") request #B())))
    (orelse
      (andalso (=:= (map-get controller 'pending) 'none)
               (lists:member op '(#B("execute") #B("develop") #B("preview") #B("rollback"))))
      (andalso (lists:member op '(#B("repair") #B("retry") #B("abort")))
               (token-valid controller request)))))

(defun track-result (controller request reply)
  (let* ((record (map-get controller 'operation))
         (pending (/= (map-get controller 'pending) 'none))
         (status (cond
                   (pending #B("paused"))
                   ((=:= (map-get request #B("op")) #B("abort")) #B("aborted"))
                   ((/= (map-get reply 'status) #B("ok")) #B("rejected"))
                   ((map-get record #B("preview")) #B("previewed"))
                   ((> (map-get reply 'revision) (map-get record #B("base_revision"))) #B("committed"))
                   ('true #B("completed"))))
         (updated (jiti_operations:update (map-get controller 'directory) record request status reply))
         (next (map-set controller 'operation (if pending updated 'none)
                                   'operations (jiti_operations:recent (map-get controller 'operations) updated))))
    (tuple next (map-set reply 'operation_id (map-get updated #B("id"))))))

(defun abandon (controller)
  (case (map-get controller 'operation)
    ('none controller)
    (_
     (let* ((request (map #B("op") #B("abort")))
            (cleared (map-set controller 'pending 'none))
            ((tuple next _) (track-result cleared request
                               (response cleared 'ok #B() #B() 'false))))
       next))))

(defun dispatch (controller request)
  (case (tracked controller request)
    ('true
     (let* ((running (if (=:= (map-get controller 'operation) 'none)
                        (map-set controller 'operation
                          (jiti_operations:begin (map-get controller 'directory) request
                            (map-get (map-get controller 'snapshot) 'revision)))
                        controller))
            ((tuple next reply) (handle running request)))
       (track-result next request reply)))
    ('false
     (if (=:= (maps:get #B("op") request #B()) #B("quit"))
         (handle (abandon controller) request)
         (handle controller request)))))

(defun strings (request key)
  (let ((values (maps:get key request ())))
    (case (andalso (is_list values) (lists:all (fun erlang:is_binary 1) values))
      ('true (lists:map (fun unicode:characters_to_list 1) values))
      ('false (error 'invalid_checks)))))

(defun open (request)
  (let* ((directory (unicode:characters_to_list (map-get request #B("store"))))
         (timeout (maps:get #B("timeout_ms") request 1000))
         ('true (andalso (is_integer timeout) (> timeout 0)))
         (snapshot (jiti_store:open directory))
         (contract (map 'safety (strings request #B("safety"))
                        'goals (strings request #B("goals"))))
         (controller (map 'directory directory 'snapshot snapshot
                          'timeout timeout 'contract contract 'pending 'none
                          'operation 'none 'operations (jiti_operations:recover directory snapshot)
                          'next-token (erlang:system_time 'microsecond))))
    (jiti_processes:configure (binary:encode_hex (crypto:hash 'sha256 (unicode:characters_to_binary directory))))
    (case (jiti_kernel:checks snapshot (map-get contract 'safety)
                             (map-get contract 'goals) timeout)
      ((tuple 'checks 'true goal)
       (tuple controller (response controller 'ok #B() #B() goal)))
      (_ (error 'recovered_state_unsafe)))))

(defun emit (reply)
  (io:put_chars (list (json:encode reply) #B(10))))

(defun read-request ()
  (case (io:get_line "")
    ('eof 'eof)
    (line (json:decode (unicode:characters_to_binary line)))))

(defun loop (controller)
  (let ((outcome
          (try
            (let ((request (read-request)))
              (case request
                ('eof (abandon controller) 'stop)
                (_
                 (let (((tuple next reply) (dispatch controller request)))
                   (emit reply)
                   (if (=:= (maps:get #B("op") request #B()) #B("quit"))
                       'stop (tuple 'continue next))))))
            (catch
              ;; Publication failure may be uncertain. Close the connection.
              ((tuple _ _ _)
               (emit (response controller 'error #B() #B("controller_failed_reopen_store") 'false))
               'stop)))))
    ;; Tail call outside TRY: long sessions do not retain request stack frames.
    (case outcome
      ((tuple 'continue next) (loop next))
      ('stop 'ok))))

(defun main ()
  ;; Supervisor failures must not forge or corrupt JSON-lines responses.
  ;; logger_std_h cannot change its output type after installation. Runtime
  ;; crash reports must not enter the JSON-lines response stream.
  (logger:remove_handler 'default)
  (logger:add_handler 'default 'logger_std_h (map 'config (map 'type 'standard_error)))
  (jiti_runtime:start_link)
  (try
    (let* ((request (read-request))
           ('true (=:= (maps:get #B("op") request #B()) #B("open")))
           ((tuple controller reply) (open request)))
      (emit reply)
      (loop controller))
    (catch
      ((tuple _ _ _)
       (emit (map 'status #B("error") 'revision 0 'state #B() 'value #B()
                  'reason #B("open_failed_store_or_contract_invalid") 'goal 'false)))))
  (erlang:halt 0))
