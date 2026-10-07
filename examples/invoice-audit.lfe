(progn
  ;; Synthetic invoices, integer cents, no payment service or model calls.
  (defun invoice-line-valid (row)
    "Require an ID, positive integer quantity and nonnegative integer unit price."
    (andalso (is_map row)
      (is_binary (maps:get #B("id") row 'undefined))
      (> (byte_size (maps:get #B("id") row)) 0)
      (is_integer (maps:get #B("qty") row 'undefined))
      (> (maps:get #B("qty") row) 0)
      (is_integer (maps:get #B("unit_cents") row 'undefined))
      (>= (maps:get #B("unit_cents") row) 0)))

  (defun invoice-audit (rows)
    "Accept each valid line ID once; report rejected and duplicate IDs separately."
    (let ((report (lists:foldl
      (lambda (row report)
        (let ((id (if (is_map row) (maps:get #B("id") row 'unknown) 'unknown)))
          (cond
            ((not (invoice-line-valid row))
             (map-set report #B("invalid") (cons id (map-get report #B("invalid")))))
            ((lists:member id (map-get report #B("seen")))
             (map-set report #B("duplicates") (cons id (map-get report #B("duplicates")))))
            ('true
             (map-set report
               #B("seen") (cons id (map-get report #B("seen")))
               #B("accepted_lines") (+ 1 (map-get report #B("accepted_lines")))
               #B("total_cents") (+ (map-get report #B("total_cents"))
                 (* (map-get row #B("qty")) (map-get row #B("unit_cents")))))))))
      (map #B("seen") () #B("accepted_lines") 0 #B("total_cents") 0 #B("duplicates") () #B("invalid") ()) rows)))
      (maps:without (list #B("seen")) report)))

  (state-put 'invoice-input (list
    (map #B("id") #B("A-101") #B("qty") 2 #B("unit_cents") 12000)
    (map #B("id") #B("A-102") #B("qty") 3 #B("unit_cents") 2500)
    (map #B("id") #B("A-101") #B("qty") 1 #B("unit_cents") 12000)
    (map #B("id") #B("A-103") #B("qty") -1 #B("unit_cents") 100)
    (map #B("id") #B("A-104") #B("qty") 1 #B("unit_cents") 900)))
  (state-put 'invoice-report (invoice-audit (state-get 'invoice-input)))
  (case (andalso
    (=:= (jiti_kernel:invoke #B("invoice-audit")
      (list (json:decode (iolist_to_binary (json:encode (state-get 'invoice-input))))))
      (state-get 'invoice-report))
    (=:= (map-get (invoice-audit ()) #B("total_cents")) 0)
    (not (invoice-line-valid (map #B("id") #B("bad") #B("qty") 1 #B("unit_cents") 2.5)))
    (=:= (map-get (state-get 'invoice-report) #B("total_cents")) 32400)
    (=:= (map-get (state-get 'invoice-report) #B("accepted_lines")) 3)
    (=:= (map-get (state-get 'invoice-report) #B("duplicates")) (list #B("A-101")))
    (=:= (map-get (state-get 'invoice-report) #B("invalid")) (list #B("A-103"))))
    ('true (state-get 'invoice-report))
    (_ (error 'invoice_example_failed))))
