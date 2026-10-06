;;;; Inspect interpreted definitions without evaluating user code or interning input.
(defmodule jiti_catalogue
  (export (metadata 2) (page 2) (describe 3)))

(defun printed (value)
  (unicode:characters_to_binary (lfe_io:prettyprint1 value -1 0 120)))

(defun metadata (form meta)
  (map 'source (printed form)
       'documentation
       (unicode:characters_to_binary (lists:append
         (lists:map (lambda (item)
                      (case item ((list 'doc text) text) (_ ()))) meta)))))

(defun limited (text limit)
  ;; Slice decoded characters so output never contains a partial UTF-8 sequence.
  (let ((chars (unicode:characters_to_list text)))
    (tuple (unicode:characters_to_binary (lists:sublist chars limit))
           (> (length chars) limit))))

(defun entry (snapshot key include-source)
  (let* (((tuple name arity) key)
         (definition (map-get (map-get snapshot 'definitions) key))
         (meta (maps:get key (maps:get 'catalogue snapshot (map))
                 (map 'source (printed (list 'define-function name () definition))
                      'documentation #B())))
         ((tuple doc doc-truncated) (limited (map-get meta 'documentation) 512))
         ((tuple args args-truncated) (limited
                           (printed (case definition
                                      ((cons 'lambda (cons arguments _)) arguments)
                                      ((cons 'match-lambda (cons (cons arguments _) _)) arguments))) 512))
         (summary (map 'name (atom_to_binary name 'utf8) 'arity arity
                       'arguments args 'documentation doc
                       'arguments_truncated args-truncated
                       'documentation_truncated doc-truncated)))
    (if include-source
        (let (((tuple source truncated) (limited (map-get meta 'source) 4096)))
          (map-set summary 'source source 'source_truncated truncated))
        summary)))

(defun ordered (snapshot)
  (lists:sort
    (lambda (a b)
      (let (((tuple an aa) a) ((tuple bn ba) b))
        (< (tuple (atom_to_binary an 'utf8) aa) (tuple (atom_to_binary bn 'utf8) ba))))
    (maps:keys (map-get snapshot 'definitions))))

(defun page (snapshot offset)
  (case (andalso (is_integer offset) (>= offset 0))
    ('false (error 'invalid_catalogue_offset)) ('true 'ok))
  (let* ((keys (ordered snapshot))
         (count (length keys))
         (start (min count offset))
         (page (lists:sublist (lists:nthtail start keys) 50))
         (next (+ start (length page))))
    (map 'functions (lists:map (lambda (key) (entry snapshot key 'false)) page)
         'function_count count 'next_offset (if (< next count) next 'null))))

(defun calls
  (((list 'quote _) _ _) 'false)
  (((cons head tail) name arity)
   (orelse (andalso (=:= head name) (is_list tail) (=:= (length tail) arity))
           (calls head name arity) (calls tail name arity)))
  ((_ _ _) 'false))

(defun describe (snapshot name arity)
  (case (andalso (is_binary name) (is_integer arity) (>= arity 0))
    ('false (error 'invalid_function_request)) ('true 'ok))
  (case (lists:filter
          (lambda (key)
            (let (((tuple key-name key-arity) key))
              (andalso (=:= (atom_to_binary key-name 'utf8) name) (=:= key-arity arity))))
          (ordered snapshot))
    (() (map 'found 'false 'function 'null 'callers ()))
    ((list key)
     (let* (((tuple target _) key)
            (callers (lists:filter
                       (lambda (caller)
                         (calls (map-get (map-get snapshot 'definitions) caller) target arity))
                       (ordered snapshot))))
       (map 'found 'true 'function (entry snapshot key 'true)
            'callers (lists:map (lambda (caller) (entry snapshot caller 'false)) callers))))))
