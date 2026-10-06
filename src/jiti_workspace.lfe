;;;; Bounded source inspection. This convenience API is not an evaluator sandbox.
(defmodule jiti_workspace (export (inspect 2)))

(defun root () "/Users/arthurcolle/Dsco")

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
                      (map 'name (unicode:characters_to_binary s)
                           'directory (filelib:is_dir (filename:join path s)))) page)
         'entry_count (length visible)
         'next_offset (if (< next (length visible)) next 'null))))

(defun reading (request)
  (let* ((relative (maps:get #B("path") request #B()))
         (path (safe-path relative))
         ('true (lists:member (filename:extension path)
                  '(".md" ".c" ".h" ".erl" ".hrl" ".lfe" ".lisp" ".py" ".rs"
                    ".go" ".ts" ".js" ".nix" ".sh")))
         ('true (filelib:is_regular path))
         (start (offset request))
         ((tuple 'ok fd) (file:open path '(read binary raw))))
    (try
      (let* (((tuple 'ok _) (file:position fd start))
             (chunk (case (file:read fd 12000)
                      ('eof #B()) ((tuple 'ok b) b) (_ (error 'workspace_read_failed))))
             ;; Binary slices may split UTF-8. Explicit Latin-1 conversion keeps
             ;; JSON valid and flags encoding; source code is normally ASCII.
             (decoded (unicode:characters_to_binary chunk 'utf8 'utf8))
             (utf8 (is_binary decoded))
             (content (if utf8 decoded (unicode:characters_to_binary chunk 'latin1 'utf8))))
        (map 'workspace_path relative 'offset start 'bytes (byte_size chunk)
             'content content 'encoding (if utf8 #B("utf-8") #B("latin-1-fallback"))
             'next_offset (if (=:= (byte_size chunk) 12000) (+ start 12000) 'null)))
      (after (file:close fd)))))

(defun inspect (op request)
  (try
    (tuple 'ok (case op (#B("workspace_list") (listing request))
                       (#B("workspace_read") (reading request))))
    (catch ((tuple _ _ _) (tuple 'error 'workspace_inspection_rejected)))))
