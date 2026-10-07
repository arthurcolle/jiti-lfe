;;;; Runtime multimethods, partial application and a durable hot-swappable pipeline.
(defun price-int (value) (* value 100))
(defun price-number (value) (round (* value 100)))
(defun price-line (row) (* (map-get row #B("qty")) (map-get row #B("unit_cents"))))
(defun add-fee (fee cents) (+ fee cents))
(defun sum-cents (total cents) (+ total cents))

;; Erlang functions are first-class targets too; no wrapper definition needed.
(state-put 'absolute-values (map-call (tuple 'remote 'erlang 'abs) '(-3 4 -5)))

(method-put 'price '(number) 'price-number)
(method-put 'price '(integer) 'price-int)
(method-put 'price (list (tuple 'map-tag #B("line"))) 'price-line)
(state-put 'pricing-pipeline
  (compose (list (tuple 'dispatch 'price) (partial 'add-fee '(25)))))
(state-put 'pricing-input
  (list 3 2.5 (map #B("type") #B("line") #B("qty") 2 #B("unit_cents") 150)))
(state-put 'pricing-output
  (map-call (state-get 'pricing-pipeline) (state-get 'pricing-input)))
(case (=:= (state-get 'pricing-output) '(325 275 325))
  ('true (fold-call 'sum-cents 0 (state-get 'pricing-output)))
  (_ (error 'pricing_dispatch_failed)))
