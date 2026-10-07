;;;; Bounded source inspection. This convenience API is not an evaluator sandbox.
(defmodule jiti_workspace (export (inspect 2) (source 2)))

(defun root () "/Users/arthurcolle/Dsco")

(defun source-type (path)
  (lists:member (filename:extension path)
    '(".md" ".c" ".h" ".erl" ".hrl" ".lfe" ".lisp" ".py" ".rs"
      ".go" ".ts" ".js" ".nix" ".sh")))

(defun safe-path (relative)
  (case (is_binary relative)
    ('false (error 'invalid_workspace_path)) ('true 'ok))
  (let* ((chars (unicode:characters_to_list relative))
         ('true (is_list chars))
         ('true (=:= (filename:pathtype chars) 'relative))
         (parts (if (=:= chars ()) () (filename:split chars))))
    (lists:foldl
      (lambda (part parent)
        (case (orelse (=:= part "..") (=:= part ".")
                      (=:= (hd part) 46) (lists:member 0 part))
          ('true (error 'hidden_or_traversal_path)) ('false 'ok))
        (let ((path (filename:join parent part)))
          (case (file:read_link path)
            ((tuple 'ok _) (error 'workspace_symlink))
            ((tuple 'error 'einval) path)
            ((tuple 'error 'enoent) (error 'workspace_path_not_found))
            (_ (error 'workspace_path_unavailable)))))
      (root) parts)))

(defun offset (request)
  (let ((n (maps:get #B("offset") request 0)))
    (case (andalso (is_integer n) (>= n 0) (=< n 100000000))
      ('true n) ('false (error 'invalid_workspace_offset)))))

(defun listing (request)
  (let* ((relative (maps:get #B("path") request #B()))
         (path (safe-path relative))
         ((tuple 'ok names) (file:list_dir path))
         (visible (lists:sort (lists:filter (lambda (s) (/= (hd s) 46)) names)))
         (start (min (length visible) (offset request)))
         (page (lists:sublist (lists:nthtail start visible) 80))
         (next (+ start (length page))))
    (map 'workspace_path relative 'entries
         (lists:map (lambda (s)
                      (let* ((child (filename:join path s))
                             (link (case (file:read_link child) ((tuple 'ok _) 'true) (_ 'false))))
                        (map 'name (unicode:characters_to_binary s)
                             'directory (andalso (not link) (filelib:is_dir child))
                             'symlink link 'source (andalso (not link) (source-type child))))) page)
         'entry_count (length visible)
         'next_offset (if (< next (length visible)) next 'null))))

(defun metadata (request)
  (let* ((relative (maps:get #B("path") request #B()))
         (path (safe-path relative))
         ((tuple 'ok info) (file:read_file_info path))
         (kind (element 3 info)))
    (case (orelse (=:= kind 'directory) (andalso (=:= kind 'regular) (source-type path)))
      ('true 'ok) (_ (error 'workspace_source_type_required)))
    (map 'workspace_path relative 'file_bytes (element 2 info)
         'kind (atom_to_binary kind 'utf8)
         'modified_seconds (- (calendar:datetime_to_gregorian_seconds (element 6 info))
                              (calendar:datetime_to_gregorian_seconds '#(#(1970 1 1) #(0 0 0))))
         'inode (element 12 info))))

(defun reading (request)
  (let* ((relative (maps:get #B("path") request #B()))
         (path (safe-path relative))
         ('true (source-type path))
         ('true (filelib:is_regular path))
         (start (offset request))
         (limit (maps:get #B("byte_limit") request 12000))
         ('true (andalso (is_integer limit) (> limit 0) (=< limit 12000)))
         ((tuple 'ok fd) (file:open path '(read binary raw))))
    (try
      (let* (((tuple 'ok _) (file:position fd start))
             (chunk (case (file:read fd limit)
                      ('eof #B()) ((tuple 'ok b) b) (_ (error 'workspace_read_failed))))
             ;; Binary slices may split UTF-8. Explicit Latin-1 conversion keeps
             ;; JSON valid and flags encoding; source code is normally ASCII.
             (decoded (unicode:characters_to_binary chunk 'utf8 'utf8))
             (utf8 (is_binary decoded))
             (content (if utf8 decoded (unicode:characters_to_binary chunk 'latin1 'utf8))))
        (map 'workspace_path relative 'offset start 'bytes (byte_size chunk)
             'content content 'encoding (if utf8 #B("utf-8") #B("latin-1-fallback"))
             'next_offset (if (=:= (byte_size chunk) limit) (+ start limit) 'null)))
      (after (file:close fd)))))

;; Native project scans read exact bounded bytes. A consistency rejection still
;; returns the bytes consumed so the caller cannot replenish its scan allowance.
(defun source (relative allowance)
  (try
    (let* ((before (metadata (map #B("path") relative)))
           (size (map-get before 'file_bytes)))
      (case (andalso (=:= (map-get before 'kind) #B("regular"))
                     (=< size 262144) (=< size allowance))
        ('false (tuple 'error 'workspace_file_byte_limit 0))
        ('true
         (let* ((path (safe-path relative)) ((tuple 'ok fd) (file:open path '(read binary raw))))
           (try
             (let* ((raw (case (file:read fd size)
                          ('eof #B()) ((tuple 'ok bytes) bytes) (_ (error 'workspace_read_failed))))
                    (used (byte_size raw))
                    (after (try (metadata (map #B("path") relative))
                             (catch ((tuple _ _ _) 'unavailable)))))
               (if (andalso (=:= before after) (=:= size used))
                 (tuple 'ok (maps:merge before
                   (map 'bytes used 'raw raw 'sha256 (string:lowercase
                     (binary:encode_hex (crypto:hash 'sha256 raw))))))
                 (tuple 'error 'workspace_file_changed used)))
             (after (file:close fd)))))))
    (catch ((tuple _ reason _)
      (tuple 'error (if (is_atom reason) reason 'workspace_inspection_rejected) 0)))))

(defun inspect (op request)
  (try
    (tuple 'ok (case op (#B("workspace_list") (listing request))
                       (#B("workspace_stat") (metadata request))
                       (#B("workspace_read") (reading request))))
    (catch ((tuple _ reason _)
      (tuple 'error (if (lists:member reason '(workspace_path_not_found workspace_symlink
                       hidden_or_traversal_path workspace_source_type_required))
                        reason 'workspace_inspection_rejected))))))
