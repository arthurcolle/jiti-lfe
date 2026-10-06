# Bounded goal-oriented action planning

`src/jiti_goap.lfe` is a standalone LFE module; `examples/goap.lfe` contains the same definitions for managed hot loading. Neither executes actions nor writes managed state.

API: `(goap-action id pre effects cost)`, `(goap-plan world goal actions max-expansions max-cost)`, `(goap-replan observed-world goal actions max-expansions max-cost)`, `(goap-step world action)`. Facts, goals, preconditions and effects are maps. Conditions use exact partial-map matching; absent facts do not equal false. Effects overwrite facts. Costs must be positive integers and action IDs unique. Limits: 64 actions, 10000 expansions.

Uniform-cost search minimizes model cost. ID-sorted expansion and cost/path frontier ordering are deterministic; equal-cost duplicate states retain first discovery. Results distinguish satisfied, planned, unreachable, cost-limit, expansion-limit and invalid-input. A planned result includes action IDs, cost, predicted-world and expanded count. A cost-limit result does not establish global unreachability.

After each explicit real action, observe the actual world, check the goal independently, and call goap-replan when necessary. Predictions are not execution receipts or safety certification. Resources and negative conditions can be modeled as facts, but there is no concurrency, probabilistic effect model or automatic durable-plan dispatch.

Regression entry point: `(goap-self-test)` in managed LFE or `(jiti_goap:goap-self-test)` after compilation. It checks cost choice, preconditions, effects, changed observations, already-satisfied and unreachable goals, cycles, deterministic ties, input validation and search limits.

Standalone verification with the local LFE toolchain:

```sh
mkdir -p _build/goap-test
export PATH="$PWD/_build/deps/lfe/bin:$PATH"
_build/deps/lfe/bin/lfec -pa _build/deps/lfe/ebin -o _build/goap-test src/jiti_goap.lfe
erl -noshell -pa _build/goap-test -eval 'true=apply(jiti_goap,list_to_atom("goap-self-test"),[]),halt().'
```
