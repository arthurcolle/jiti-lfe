;;;; Local trusted managed snapshots. The Python launcher holds the writer lock.
(defmodule jiti_store
  (export (new 0) (open 1) (publish 3) (load-revision 2) (history 2)))

(defun new ()
  (map 'revision 0 'parent 'none 'state (map) 'definitions (map) 'catalogue (map)))

(defun path (directory revision)
  (filename:join directory (++ (integer_to_list revision) ".term")))

(defun open (directory)
  (case (file:read_file (filename:join directory "CURRENT"))
    ((tuple 'error 'enoent) (new))
    ((tuple 'ok bytes)
     (load-revision directory (binary_to_integer (string:trim bytes))))
    (_ (error 'store_read_failed))))

(defun load-revision (directory revision)
  (let* (((tuple 'ok bytes) (file:read_file (path directory revision)))
         ((tuple 'jiti_lfe 1 digest payload) (binary_to_term bytes '(safe)))
         ('true (=:= digest (crypto:hash 'sha256 payload)))
         ;; Trusted local input must recreate user atoms on a fresh VM.
         ((tuple otp snapshot) (binary_to_term payload))
         ('true (=:= otp (erlang:system_info 'otp_release)))
         ('true (=:= revision (map-get snapshot 'revision)))
         ('true (is_map (map-get snapshot 'state)))
         ('true (is_map (map-get snapshot 'definitions))))
    snapshot))

(defun write-synced (filename bytes)
  (let (((tuple 'ok fd) (file:open filename '(write binary raw exclusive))))
    (try
      (progn
        (case (file:change_mode filename 384)
          ('ok 'ok) (_ (error 'store_permissions_failed)))
        (case (file:write fd bytes)
          ('ok 'ok) (_ (error 'store_write_failed)))
        (case (file:sync fd)
          ('ok 'ok) (_ (error 'store_sync_failed))))
      (after (file:close fd)))))

(defun publish (directory previous candidate)
  (let* ((next (unused-revision directory (+ (map-get previous 'revision) 1)))
         (snapshot (map-set candidate 'revision next
                            'parent (map-get previous 'revision)))
         (payload (term_to_binary (tuple (erlang:system_info 'otp_release) snapshot)))
         (bytes (term_to_binary (tuple 'jiti_lfe 1 (crypto:hash 'sha256 payload) payload)))
         (pointer (filename:join directory "CURRENT"))
         (temporary (++ pointer "." (integer_to_list (erlang:unique_integer '(positive))) ".tmp")))
    (write-synced (path directory next) bytes)
    (write-synced temporary (integer_to_binary next))
    (case (file:rename temporary pointer)
      ('ok snapshot) (_ (error 'store_publish_failed)))))

(defun unused-revision (directory revision)
  (case (file:read_file_info (path directory revision))
    ((tuple 'error 'enoent) revision)
    ((tuple 'ok _) (unused-revision directory (+ revision 1)))
    (_ (error 'store_read_failed))))

(defun history (directory snapshot)
  (case (map-get snapshot 'parent)
    ('none (list (map-get snapshot 'revision)))
    (0 (list (map-get snapshot 'revision) 0))
    (parent
     (cons (map-get snapshot 'revision)
           (history directory (load-revision directory parent))))))
