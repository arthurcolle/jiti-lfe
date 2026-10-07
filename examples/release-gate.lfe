(progn
  ;; Fixed synthetic receipts; durations below are fixture data, not benchmarks.
  (defun release-receipt-valid (row)
    (andalso (is_map row) (is_binary (maps:get 'id row 'undefined))
      (is_integer (maps:get 'duration_ms row 'undefined))
      (>= (maps:get 'duration_ms row) 0)))
  (defun release-p95 (receipts)
    "Nearest-rank p95 of a nonempty fixture set, using integer arithmetic."
    (let* ((sorted (lists:sort (lists:map
             (lambda (row) (map-get row 'duration_ms)) receipts)))
           (rank (div (+ (* 95 (length sorted)) 99) 100)))
      (lists:nth rank sorted)))
  (defun release-version ()
    (map-get (jiti_plan:inspect #B("release")) 'version))
  (defun release-result (id)
    (map-get (map-get (map-get (jiti_plan:inspect #B("release")) 'nodes) id) 'job))
  (defun release-run (id)
    (jiti_plan:launch #B("release") id (release-version)))
  (defun release-verify (id)
    (jiti_plan:verify #B("release") id (release-version)))
  (defun release-await (remaining)
    "Observe only already-started jobs; timeout never admits replacement work."
    (jiti_plan:reconcile #B("release"))
    (let ((running (lists:any (lambda (node) (=:= (map-get node 'status) 'running))
      (maps:values (map-get (jiti_plan:inspect #B("release")) 'nodes)))))
      (cond ((not running) 'observed)
            ((=< remaining 0) (error 'release_example_timeout))
            ('true (timer:sleep 10) (release-await (- remaining 1))))))

  (state-put 'release-receipts (lists:map (lambda (duration)
    (map 'id (integer_to_binary duration) 'duration_ms duration))
    '(20 30 90 40 75 60 50 65 80 100)))
  (jiti_plan:create #B("release") #B("Verify a candidate before admitting its release task"))
  (jiti_plan:add #B("release") #B("shape") 'none #B("Receipt schema and rejection case")
    'task () 10
    #B("(=:= (map-get (release-result #B(\"shape\")) 'result) #B(\"#(ok true)\"))")
    (map 'adapter 'lfe 'timeout_ms 1000
      'source #B("(andalso (lists:all (fun release-receipt-valid 1) (state-get 'release-receipts)) (not (release-receipt-valid (map 'id #B(\"bad\") 'duration_ms -1))))")))
  (jiti_plan:add #B("release") #B("latency") 'none #B("Fixture p95 acceptance")
    'task () 10
    #B("(=:= (map-get (release-result #B(\"latency\")) 'result) #B(\"#(ok 100)\"))")
    (map 'adapter 'lfe 'timeout_ms 1000
      'source #B("(release-p95 (state-get 'release-receipts))")))
  (jiti_plan:add #B("release") #B("admit") 'none #B("Release decision")
    'task (list #B("shape") #B("latency")) 1
    #B("(=:= (map-get (release-result #B(\"admit\")) 'result) #B(\"#(ok release_ready)\"))")
    (map 'adapter 'lfe 'timeout_ms 1000 'source #B("'release_ready")))
  (release-run #B("shape"))
  (release-run #B("latency"))
  (release-await 100)
  ;; Successful worker exits alone must leave the dependent task inadmissible.
  (case (=:= (map-get (jiti_plan:ready #B("release")) 'ready) ())
    ('true 'ok) (_ (error 'release_admitted_before_verification)))
  (release-verify #B("shape"))
  (release-verify #B("latency"))
  (case (=:= (map-get (jiti_plan:ready #B("release")) 'ready) (list #B("admit")))
    ('true 'ok) (_ (error 'release_frontier_wrong)))
  (release-run #B("admit"))
  (release-await 100)
  (release-verify #B("admit"))
  (case (lists:all (lambda (node) (=:= (map-get node 'status) 'done))
    (maps:values (map-get (jiti_plan:inspect #B("release")) 'nodes)))
    ('true (state-put 'release-report (map 'decision 'ready
      'fixture_p95_ms (release-p95 (state-get 'release-receipts)) 'verified_tasks 3)))
    (_ (error 'release_example_failed))))
