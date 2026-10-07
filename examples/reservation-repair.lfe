(progn
  ;; The pricing function is intentionally absent until the explicit repair.
  (defun reserve-items (quantity)
    "Reserve stock and calculate cents as one managed action."
    (let ((available (state-get 'stock)))
      (case (andalso (is_integer quantity) (> quantity 0) (=< quantity available))
        ('true 'ok) (_ (error 'invalid_reservation)))
      (state-put 'stock (- available quantity))
      (state-put 'reservation-cents (reservation-price quantity))
      (map 'remaining (state-get 'stock) 'cents (state-get 'reservation-cents))))
  (state-put 'stock 20)
  (state-put 'reservation-cents 0)
  (map 'stock (state-get 'stock) 'pricing 'not_defined_yet))
