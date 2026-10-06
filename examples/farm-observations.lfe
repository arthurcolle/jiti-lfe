(defun farm-observations ()
  "Read retained empirical farm observations; no evaluation, routing change or promotion."
  (state-get 'farm-rollout-observations))
