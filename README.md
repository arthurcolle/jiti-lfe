# Live image repair

A cooperative SBCL kernel for incrementally changing a running Lisp world. A worker retains a failed call's live restarts while an external controller evaluates repair forms or resumes the call. Accepted registered code and data can survive process restarts.

Run a live evolution experiment:

```sh
devenv shell -- experiment-reverse
```

The Lisp process starts with no `reverse-string`, builds a prompt from its goal, and asks OpenAI to add the function through registered tools. Caller-owned tests verify 21 fixed Unicode examples and 1,000 generated cases. Lisp automatically prompts again on failure, bounded by three rounds, 20 tools per round, 100 worker actions, and a 600-second external watchdog. No reversal implementation is supplied to the live proposer.

Success requires a freshly allocated output string on each invocation, unchanged input, and reversal of the **original logical grapheme clusters**. Emoji sequences and combining accents retain their internal code points. RTL/LTR rendering still follows Unicode bidi rules; directional controls are preserved as input units rather than rebalanced for display. Cluster boundaries can change after reversal, so universal double-reversal identity is deliberately not asserted. Generated expectations use the pinned SBCL UAX #29 segmentation; fixed examples have independent expected outputs. Unicode behavior follows that runtime, rather than promising a different Unicode release.

The experiment prints actual outputs, expected outputs, and code points. It then launches a fresh SBCL process to execute the recovered function, rolls back to remove it, and restores the successful implementation into a new revision. Each run uses a fresh `.image-agent/experiments/reverse-TIME-PID/` workspace; `--store FRESH-DIRECTORY` selects another location, and `--seed INTEGER` changes the generated cases. Existing experiment stores are preserved and rejected for a new run.

Artifacts include `experiment.txt`, the kernel journal and immutable revisions, `generated-source.lisp` containing the actual model-created definitions, and minimized failures under `counterexamples/`. To reproduce a failure offline:

```sh
devenv shell -- experiment-reverse --replay .image-agent/experiments/reverse-TIME-PID/counterexamples/failure-1.sexp
```

A reproduced failure exits with status 1; a passing replay exits with status 0. Replay evaluates the recorded managed definitions, so use trusted local artifacts. Credentials are resolved through the same local Underclass/environment configuration as the REPL and never written into experiment artifacts.

Start the loaded-program CLI:

```sh
devenv shell -- image-repl
```

The demo has a `*state*` table with `:x` initially zero and a `(counter)` function. Type natural language to OpenAI, or use commands:

```text
chat> Set :x in *state* to 7.
chat> /history
chat> Roll back to revision 1.
chat> /mode lisp
lisp> (counter)
lisp> /mode chat
chat> /model
chat> /model gpt-6-astra
chat> /quit
```

Restart the same command to recover accepted state. The default demo workspace is `.image-agent/workspaces/demo/`; `/status` shows the revision, observation generation, checks, and restart menu. `/rollback previous` restores the current revision's parent and creates a new revision, preserving history. `/eval FORM` submits Lisp from either mode; `/chat TEXT` sends chat from either mode. Forms may span lines. `/abort` unwinds a paused attempt; EOF and `/quit` close the worker and restore provisional changes. `/help` lists commands.

The CLI loads local Underclass settings automatically. Environment variables override local configuration, and `--model` overrides model selection. Manual Lisp works without API credentials. Chat has a default limit of 20 tool calls per prompt; the worker has a 1,000-action session budget. Set `--tool-limit` and `--budget` at startup. On budget exhaustion, quit and reopen the workspace to recover. Model switching affects future requests and resets conversation context. Transport failures preserve local world state and any live pause. Conversation text is not persisted.

Load your own managed application using `devenv shell -- image-repl --program app.lisp --store ./my-workspace/`. The file defines a factory in `CL-USER`:

```lisp
(in-package :cl-user)
(defun make-cli-world ()
  (let ((world (image-agent:make-reference-world :initial '((:x . 42)))))
    (list :id "my-app" :world world
          :goals (list (cons :target
                        (lambda () (= 7 (gethash :x (image-agent:reference-table world))))))
          :invariants (list (cons :nonnegative
                             (lambda () (>= (gethash :x (image-agent:reference-table world)) 0)))))))
```

`:id` must be stable and use letters, digits, hyphens, or underscores. Goals and invariants are optional for interactive use. The workspace checks adapter identity and allows only one CLI process at a time. Application resources beyond the reference adapter need your own snapshot/restore and export/import hooks. Interactive sessions stay available after goals pass.

OpenAI discovers registered tools for observation, evaluation, caller checks, revision listing, rollback, restart resumption, and attempt abortion. The controller validates arguments and routes world operations through the owning worker. Observation generations are stale-command guards; accepted revision numbers identify persistent history. Rollback restores managed code/data, not historical call stacks.

```sh
devenv shell test
devenv shell test-stress
devenv shell test-replay /tmp/image-agent-counterexample-424242.sexp
devenv shell test-live
```

`test` is deterministic and offline. `test-live` reads this machine's Underclass profile from Codex configuration unless environment variables override it. Other installations must provide `OPENAI_MODEL` and `OPENAI_API_KEY` or `OPENAI_API_KEY_FILE`, optionally `OPENAI_BASE_URL`. Credentials are not logged. Tests have an external watchdog; adjust `TEST_TIMEOUT` for stress runs.

Load `image-agent` for the core, `image-agent/store` for persistence and the reference world, and `image-agent/openai` for the Responses proposer. HTTP/JSON and test libraries are outside the core.

```lisp
(let* ((world (image-agent:make-reference-world :initial '((:x . 0))))
       (session (image-agent:make-session
                  world :goal "Set :x to 7"
                  :goals (list (cons :seven
                             (lambda () (= 7 (gethash :x (image-agent:reference-table world))))))
                  :budget 10 :store #p"/tmp/my-image-revisions/")))
  (unwind-protect
       (let ((view (image-agent:session-step session)))
         (image-agent:session-step
           session (list :action :evaluate :source "(setf (gethash :x *state*) 7)"
                         :generation (getf view :generation))))
    (image-agent:close-session session)))
```

`session-step` returns `:idle`, `:paused`, `:success`, `:exhausted`, `:aborted`, or `:faulted`. Include the returned generation in every action. Paused views include temporary restart IDs; resume using `:action :resume :restart-id ID :arguments "(list ...)"`. `run` drives this protocol using an injected proposer. All attempts, including malformed actions and failed proposer requests, spend budget.

A world supplies an evaluation package, bounded observation, checkpoint/restore, and optional durable export/import and definition-recording callbacks. An outer form and repairs made while it is paused share one provisional checkpoint. Failed repair evaluation aborts that entire attempt. Checkpoints precede reading, compilation, and evaluation. False goals permit accepted intermediate revisions; false or signaled safety invariants reject them. Noninteractive sessions require nonempty goals; interactive sessions may omit them. Autonomous evolution always requires executable goals.

`make-property-check` returns a named check usable among goals or invariants. Provide a generator function taking a size, an assertion taking a sample, seed, case budget, and optional shrink function. Each sample and shrink test restores its world checkpoint. Results include seed, completed case count and counterexample. Model-created tests cannot replace the caller's acceptance contract.

Persistence publishes immutable world artifacts and a manifest, then flushes an atomic `CURRENT` pointer. `recover-session` imports the current revision and includes prior diagnostic history; it does not replay actions or restore old stacks. A torn diagnostic journal cannot change accepted state; recovery archives it before appending new records. Revisions currently require the same SBCL version.

The reference adapter covers an equal-tested table of readable, acyclic scalar/list values and direct named `defun` forms, including definitions nested in `progn`. It preserves table identity and restores function cells. Definitions performed indirectly, macros, methods, classes, external I/O, background threads, closures captured from arbitrary frames, and other resources need a world adapter with appropriate coverage. Accepted definitions must be reconstructible from their exported source. Safety checks and observations must cooperate with the owning thread and avoid deadlocking on locks held by a paused call.

Package locks and recursive syntax checks protect against mistakes, not arbitrary hostile Lisp. Computed calls, macro expansion, FFI, and resource exhaustion are outside that guarantee. Active frames and cached function objects retain their existing bodies; hot replacement relies on non-inline global dispatch. Hard crash/hang isolation belongs to an external process supervisor.

Architectural decisions live in [docs/adr](docs/adr/). [AGENTS.md](AGENTS.md) invokes the repository's [ADR maintenance skill](skills/maintain-adrs/SKILL.md).
