# Jiti-LFE examples

These examples were built for this fork. They execute LFE against synthetic
local fixtures and retain executable acceptance checks. They need no model
credential, remote actor service or external account.

```sh
make examples
```

The runner uses isolated temporary stores and reopens every example in a fresh
process. It removes only its own temporary directory. Your active application
and `.jiti/default` store are not used.

## Invoice audit

[invoice-audit.lfe](invoice-audit.lfe) defines `invoice-line-valid/1` and
`invoice-audit/1`. Maps use binary keys, matching JSON object fields accepted by
the chat tools. Prices use integer cents. The five-row fixture has three valid
unique IDs, one duplicate ID and one negative quantity. Expected accepted value
is 32,400 cents; duplicate A-101 and invalid A-103 are reported separately.
The program also checks empty input and rejection of a fractional price.

Load into your own fresh store, then call the saved function:

```sh
python3 scripts/repl.py --store .jiti/invoice-example \
  --eval "$(cat examples/invoice-audit.lfe)"
python3 scripts/repl.py --store .jiti/invoice-example \
  --eval '(invoice-audit (state-get '\''invoice-input))'
```

The input and report remain inspectable managed data. This calculates a fixture
total; it does not collect payments or establish revenue.

## Release gate

[release-gate.lfe](release-gate.lfe) creates a fixed three-task dependency plan.
Two independent jobs check receipt shape and nearest-rank p95. The shape check
includes a malformed negative-duration case; the p95 fixture's expected answer
is 100 ms. Both jobs are explicitly launched before waiting. Their successful
exits leave the release task inadmissible until separate stored checks pass.

```sh
python3 scripts/repl.py --store .jiti/release-example --timeout-ms 5000 \
  --eval "$(cat examples/release-gate.lfe)"
python3 scripts/repl.py --store .jiti/release-example
```

Then inspect `/plan release` and `(state-get 'release-report)`. After reopening,
the three verified outcomes remain recorded while the current job manager has
no replacement jobs. Use a fresh store to rerun the program; the plan ID is
immutable. This is a fixed local workflow, not an autonomous alliance or public
deployment. Fixture duration values are not measured execution latency.

## Reservation repair

[reservation-repair.lfe](reservation-repair.lfe) defines a reservation function
that changes stock before calling an intentionally missing pricing function.
Load the setup and open its store:

```sh
python3 scripts/repl.py --store .jiti/reservation-example \
  --eval "$(cat examples/reservation-repair.lfe)"
python3 scripts/repl.py --store .jiti/reservation-example
```

```text
(reserve-items 4)
/status
/repair (defun reservation-price (quantity) (* quantity 1500))
/retry
(state-get 'stock)
(state-get 'reservation-cents)
/preview (reserve-items 2)
(state-get 'stock)
(state-get 'reservation-cents)
```

The initial failure discards the provisional stock edit. Retry evaluates the
whole action with the repaired definition: stock becomes 16 and price 6,000
cents. Preview returns a hypothetical reservation but leaves those accepted
values unchanged. Reopening recovers the function and accepted state. This is
LFE whole-action retry, distinct from the original SBCL kernel's live restarts.

## Dynamic dispatch

[dynamic-dispatch.lfe](dynamic-dispatch.lfe) registers integer, number and tagged
map pricing methods, composes the selected implementation with a partially bound
fee, maps over heterogeneous inputs and folds the total: 925 cents. Change
`price-int/1` and the saved pipeline uses its replacement immediately. Method
registrations and named descriptors recover with the managed image.

```sh
python3 scripts/repl.py --store .jiti/dispatch-example \
  --eval "$(cat examples/dynamic-dispatch.lfe)"
```

Verification is [scripts/run-lfe-examples.sh](../scripts/run-lfe-examples.sh).
Each program or its recovery check exits unsuccessfully if its fixed contract
fails. No additional Python example implementation is added.
