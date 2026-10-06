;; Opt-in bounded numeric AST evolution. Execute each form separately in the REPL.
;; propose publishes only a durable receipt; promote must be the next publication.
;; Read-only inspect/evaluation and restarting the Bridge are safe between them.
(defun estimate (x) x)
(jiti_evolution:generate 'estimate 1 1 1 1)
(jiti_evolution:propose #B("estimate-v1") 'estimate 1 '((lambda (x) (+ x 1))) '(((0) 1) ((2) 3)) '(((7) 8) ((-3) -2)) '(((0) -10 10) ((9) -20 20)) (map 'seed 1 'population 4 'generations 1 'timeout_ms 200))
(jiti_evolution:inspect #B("estimate-v1"))
(jiti_evolution:promote #B("estimate-v1"))
(estimate 7)
;; Result: 8. Use the existing controller rollback operation to restore revisions.
;; Use 'generate instead of the quoted candidate list to run deterministic mutation.
;; AST DSL: lambda, 1..4 distinct atom arguments, integer constants, binary + - *.
;; Bounds: depth 8, 63 nodes, 32 candidates/generation, 8 generations, 64 attempts.
;; Fixtures: 1..32 unique rows/split; train and heldout inputs must be disjoint.
;; Training/heldout rows: ((integer-arguments ...) expected-integer).
;; Safety rows: ((integer-arguments ...) inclusive-min inclusive-max), nonempty.
;; Strictly lower summed absolute error on BOTH splits; ties never promote.
;; These are finite tests, not a proof outside the supplied numeric domain.
;; Receipts are managed trusted-local data, not signatures or authorization tokens.
