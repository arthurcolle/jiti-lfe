;;;; Durable diagnostics, separate from accepted snapshots. Never replay actions.
(defmodule jiti_operations
  (export (begin 3) (update 5) (recover 2) (recent 2)))

(defun directory (store) (filename:join store "operations"))

(defun path (store id)
  (case (re:run id #B("^operation-[0-9]+-[0-9]+-[0-9]+$") '(#(capture none)))
    ('match (filename:join (directory store) (++ (binary_to_list id) ".json")))
    (_ (error 'invalid_operation_id))))

(defun persist (store record)
  (let* ((target (path store (map-get record #B("id"))))
         (temporary (++ target "." (integer_to_list (erlang:unique_integer '(positive))) ".tmp"))
         (bytes (json:encode record)))
    (case (filelib:ensure_dir target)
      ('ok 'ok) (_ (error 'operation_directory_failed)))
    (case (file:change_mode (directory store) 448)
      ('ok 'ok) (_ (error 'operation_permissions_failed)))
    (let (((tuple 'ok fd) (file:open temporary '(write binary raw exclusive))))
      (try
        (let* (('ok (file:change_mode temporary 384))
               ('ok (file:write fd bytes))
               ('ok (file:sync fd)))
          'ok)
        (after (file:close fd))))
    (case (file:rename temporary target)
      ('ok record) (_ (error 'operation_publish_failed)))))

(defun source-info (request)
  ;; No source, managed values, condition text, or credentials enter diagnostics.
  (let ((source (maps:get #B("source") request #B())))
    (if (is_binary source)
        (map #B("source_sha256") (binary:encode_hex (crypto:hash 'sha256 source))
             #B("source_bytes") (byte_size source))
        (map #B("source_sha256") 'null #B("source_bytes") 0))))

(defun begin (store request revision)
  (let* ((now (erlang:system_time 'microsecond))
         (id (iolist_to_binary (list "operation-" (integer_to_list now) "-"
                                    (os:getpid) "-"
                                    (integer_to_list (erlang:unique_integer '(positive))))))
         (op (map-get request #B("op")))
         (record (maps:merge
                   (map #B("version") 1 #B("id") id #B("started_at") now
                        #B("updated_at") now #B("intent") op #B("last_action") op
                        #B("preview") (=:= op #B("preview"))
                        #B("base_revision") revision #B("revision") revision
                        #B("status") #B("running") #B("outcome") #B("pending")
                        #B("goal") 'false #B("steps") 0 #B("recovered") 'false)
                   (source-info request))))
    ;; A start must never overwrite an existing operation identity.
    (case (file:read_file_info (path store id))
      ((tuple 'error 'enoent) (persist store record))
      (_ (error 'operation_id_collision)))))

(defun update (store record request status reply)
  (persist store
    (map-set record #B("updated_at") (erlang:system_time 'microsecond)
                    #B("last_action") (map-get request #B("op"))
                    #B("status") status
                    #B("outcome") (map-get reply 'status)
                    #B("revision") (map-get reply 'revision)
                    #B("goal") (map-get reply 'goal)
                    #B("steps") (+ 1 (map-get record #B("steps"))))))

(defun recent (records record)
  (lists:sublist
    (cons record (lists:filter
                   (lambda (entry) (/= (map-get entry #B("id")) (map-get record #B("id"))))
                   records)) 100))

(defun read-record (filename)
  (let* (((tuple 'ok bytes) (file:read_file filename))
         ('true (=< (byte_size bytes) 16384))
         (record (json:decode bytes))
         (id (map-get record #B("id")))
         ('true (is_binary id))
         ('true (=:= (filename:basename filename) (++ (binary_to_list id) ".json")))
         (1 (map-get record #B("version")))
         ('true (is_integer (map-get record #B("started_at"))))
         ('true (lists:member (map-get record #B("status"))
                   '(#B("running") #B("paused") #B("committed") #B("completed")
                     #B("previewed") #B("rejected") #B("aborted") #B("interrupted")))))
    record))

(defun publications (store snapshot)
  (lists:foldl
    (lambda (revision acc)
      (let* ((entry (if (=:= revision (map-get snapshot 'revision)) snapshot
                       (jiti_store:load-revision store revision)))
             (id (maps:get 'operation-id entry 'none)))
        (if (=:= id 'none) acc (map-set acc id revision))))
    (map) (lists:filter (lambda (revision) (/= revision 0))
                       (jiti_store:history store snapshot))))

(defun recover (store snapshot)
  (let* ((records (lists:map (fun read-record 1)
                   (filelib:wildcard (filename:join (directory store) "*.json"))))
         (ordered (lists:sort
                    (lambda (a b)
                      (> (tuple (map-get a #B("started_at")) (map-get a #B("id")))
                         (tuple (map-get b #B("started_at")) (map-get b #B("id"))))) records))
         (accepted (publications store snapshot)))
    ;; Reconcile every unfinished file, even when it falls outside the retained
    ;; inspection window. The retention bound must not hide unfinished recovery.
    (lists:sublist
      (lists:map
        (lambda (record)
          (case (map-get record #B("status"))
            ((binary "running") (recover-one store record accepted))
            ((binary "paused") (recover-one store record accepted))
            (_ record))) ordered) 100)))

(defun recover-one (store record accepted)
  (let* ((revision (maps:get (map-get record #B("id")) accepted 'none))
         (published (/= revision 'none)))
    (persist store
      (map-set record #B("updated_at") (erlang:system_time 'microsecond)
                      #B("status") (if published #B("committed") #B("interrupted"))
                      #B("outcome") (if published #B("published_before_disconnect") #B("unknown"))
                      #B("revision") (if published revision (map-get record #B("revision")))
                      #B("goal") 'null #B("recovered") 'true))))
