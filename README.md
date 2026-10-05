# Live image repair

A generic cooperative SBCL kernel for developing and executing a running Lisp application through chat. Application functionality is supplied by your prompts and world adapter, not built into the kernel. A worker retains a failed call's live restarts while an external controller evaluates repair forms or resumes the call. Accepted registered code and data can survive process restarts.

Grow an expense tracker from an empty application catalogue:

```sh
devenv shell -- image-repl --program examples/expense-tracker.lisp --store .image-agent/workspaces/expenses/
```

The [launch production package](launch/README.md) contains ten video scripts, a reproducible capture/render pipeline, and the original “Say the Word” music brief. The expense adapter supplies caller-owned checks; chat supplies its functions. Saved recordings distinguish actual model-generated code from deterministic demonstrations of repair and rollback.

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

Interactive terminals use a scrolling, coloured interface with editable multiline input, syntax highlighting, function listings, and live restart panels. Enter submits chat or a complete Lisp form; incomplete Lisp continues on another line. Alt+Enter (or Esc then Enter) always inserts a newline. Left/right edit text; up/down move between rows and recall whole submissions at the buffer edges. Ctrl+C clears the current draft without aborting a paused call; Ctrl+D exits when the buffer is empty. Pasting never submits automatically.

Input history is saved per workspace in `input-history.txt` with permissions `0600`, including submitted chat prompts and commands. Delete that file to clear it. Model replies and conversation context remain in memory. Use `--no-emoji` to disable decorative emoji, `NO_COLOR=1` to disable colours, or `--plain` for the line interface. Pipes and `TERM=dumb` select the plain interface automatically. Unicode input is preserved; glyph appearance depends on your terminal and font. The rich display escapes control sequences and directional formatting controls from application output.

The demo has a `*state*` table with `:x` initially zero and a `(counter)` function. Type natural language to OpenAI, or use commands:

```text
chat> Add uppercase-string that returns an uppercased copy of a string.
chat> Add Unicode-aware reverse-string, preserving original grapheme clusters.
chat> Uppercase "Hello 👋", then reverse it. Execute using existing functions.
chat> Save that composition as shout-backwards.
chat> /functions
chat> /describe shout-backwards
chat> /execute (shout-backwards "Hello 👋")
chat> /preview (incf (gethash :x *state*))
chat> /operations
chat> /history
chat> /context
chat> /compact
chat> Roll back to revision 1.
chat> /mode lisp
lisp> (counter)
lisp> /mode chat
chat> /model
chat> /model gpt-6-astra
chat> /quit
```

Restart the same command to recover accepted state. The default demo workspace is `.image-agent/workspaces/demo/`; `/status` shows the revision, observation generation, checks, and restart menu. `/rollback previous` restores the current revision's parent and creates a new revision, preserving history. `/develop FORM` adds or redefines functionality; `/execute FORM` calls it; `/preview FORM` returns values and restores managed state; `/chat TEXT` sends chat from either mode. Forms may span lines. `/abort` unwinds a paused attempt; EOF and `/quit` close the worker and restore provisional changes. `/help` lists commands. Bare forms in Lisp mode execute normally, including supported definitions.

Remove an accepted function by asking in chat, or use `/develop (fmakunbound 'function-name)`. Removal creates a revision and updates the catalogue; removing an already absent local function creates no revision. Callers remain in the application. The model can point out visible references, but computed calls cannot be exhaustively identified. If a caller later reaches the missing function, its condition can be repaired through the live restart workflow. Caller-owned safety checks may reject removal. Use `/preview (fmakunbound 'function-name)` to try it without retaining the change, or `/rollback previous` to restore an accepted deletion. Requested caller repairs and deletion can share one `PROGN` transaction.

Compose functions with ordinary Lisp, for example `(reverse-string (uppercase-string "Hello 👋"))`. No pipeline language or wrapper definition is required. Save a named composition only when you want another reusable building block. The catalogue comes from current managed definitions and survives process recovery.

Every development or execution attempt gets an operation ID and a diagnostic journal record. Pure calls, identical definitions, and final-state no-ops create no revision. Successful managed code or data changes create one revision; explicit rollback always publishes a new revision. Observation generations advance independently for worker coordination. `/operations` shows recent attempts, including failures and previews, rather than application versions. Unfinished operations are marked interrupted on recovery and never replayed.

Ordinary execution retains safe managed changes. Preview restores the same checkpoint after successful execution or failure, including repairs made while paused. It cannot undo unmanaged external effects such as sending a network request. Results are bounded printable values with truncation flags, not live object references.

The CLI loads local Underclass settings automatically. Environment variables override local configuration, and `--model` overrides model selection. Manual Lisp works without API credentials. Chat has a default limit of 20 tool calls per prompt; the worker has a 1,000-action session budget. Set `--tool-limit` and `--budget` at startup. On budget exhaustion, quit and reopen the workspace to recover. Model switching affects future requests and resets conversation context. Transport failures preserve local world state and any live pause. Conversation context and model replies are not persisted; the terminal stores submitted input history as described above.

Conversation memory compacts automatically before a request reaches the configured threshold, including between completed tool exchanges during one prompt. The same prompt then continues. `/compact` compacts manually; `/context` shows usage, window, threshold, backend, and compaction count; `/context clear` explicitly forgets conversation memory. These commands preserve the live worker and paused restarts and spend no worker actions. Compaction does not reset the per-prompt tool budget.

The default working window is 65,536 tokens, with compaction at 70% and 8,192 tokens reserved for output and reasoning. Set `--context-tokens N` and optionally `--compact-threshold N` (both in tokens). This is a configured working budget, not automatic discovery of a model's maximum context. Request estimates include instructions, tool schemas, history, and Unicode UTF-8 bytes. Near the threshold, the controller uses `/responses/input_tokens` if supported; otherwise it uses an estimate calibrated against reported input usage. `/context` and the toolbar label local estimates; `/context` also reports the last measured request count and method.

Compaction prefers `/responses/compact` and passes its returned context forward intact. Gateways without that endpoint use an ordinary, tool-free Responses request to summarize goals, constraints, decisions, verified progress, and unfinished work. The summary fallback retains the latest prompt verbatim and two recent complete tool exchanges. Summaries are fallible; current worker state and actual tool results take precedence. If compaction fails or cannot free enough space, conversation memory and the live world remain available for retry. Compaction adds model latency and usage, and conversation memory remains session-only.

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

OpenAI discovers registered tools for application inspection, function descriptions, development, execution, caller checks, operation history, revision listing, rollback, restart resumption, and attempt abortion. Catalogue pages contain up to 50 summaries; `inspect_world` starts at offset 0 and returns `next_offset`. `/functions [OFFSET]` provides the same paging in the terminal. Full source is available through `/describe NAME`. The controller validates arguments and routes world operations through the owning worker. Observation generations are stale-command guards; accepted revision numbers identify persistent history. Rollback restores managed code/data, not historical call stacks.

```sh
devenv shell test
devenv shell test-stress
devenv shell test-replay /tmp/image-agent-counterexample-424242.sexp
devenv shell test-live
```

`test` is deterministic and offline. `test-live` reads this machine's Underclass profile from Codex configuration unless environment variables override it. Other installations must provide `OPENAI_MODEL` and `OPENAI_API_KEY` or `OPENAI_API_KEY_FILE`, optionally `OPENAI_BASE_URL`. Credentials are not logged. `test-live` also asks the real model to add and compose functionality, then checks execution and fresh recovery. Tests have an external watchdog (180 seconds offline, 600 seconds live); adjust `TEST_TIMEOUT` for stress runs.

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
           session (list :action :execute :source "(setf (gethash :x *state*) 7)"
                         :generation (getf view :generation))))
    (image-agent:close-session session)))
```

`session-step` accepts `:develop` or `:execute` with `:source`, and execution accepts optional `:preview t`. Inspection actions are `:inspect`, `:describe :name NAME`, and `:operations`. `session-step` returns `:idle`, `:paused`, `:success`, `:exhausted`, `:aborted`, or `:faulted`. Include the returned generation in every action. Paused views include temporary restart IDs; resume using `:action :resume :restart-id ID :arguments "(list ...)"`. `run` drives this protocol using an injected proposer. All attempts, including malformed actions and failed proposer requests, spend budget.

A world supplies an evaluation package, bounded observation, checkpoint/restore, required `:managed-state` and `:catalogue` callbacks, and optional durable export/import, form-validation, and definition-recording callbacks. `:validate-form` receives the parsed, kernel-validated form before evaluation and must not mutate the world; signaling an error rejects the attempt. It defaults to no additional validation. Apply the same callback when initializing your own program outside worker execution. `:managed-state` returns a deterministic acyclic readable tree of managed code and data; the kernel captures its case-sensitive readable representation to compare final state. Keep this distinct from live checkpoints. `:catalogue` returns a list of entries with `:name` (string), `:arguments` (Lisp lambda list), `:documentation` (string or NIL), and `:source` (string). The reference adapter manages readable table values and direct named DEFUNs and literal local FMAKUNBOUND edits, rejecting unrecorded function changes rather than losing them during recovery. Other adapters can manage methods, classes, or other resources by supplying complete hooks. An outer form and repairs made while it is paused share one provisional checkpoint. Failed repair evaluation aborts that entire attempt. Checkpoints precede reading, compilation, and evaluation. False goals permit accepted intermediate revisions; false or signaled safety invariants reject them. Noninteractive sessions require nonempty goals; interactive sessions may omit them. Autonomous evolution always requires executable goals.

`make-property-check` returns a named check usable among goals or invariants. Provide a generator function taking a size, an assertion taking a sample, seed, case budget, and optional shrink function. Each sample and shrink test restores its world checkpoint. Results include seed, completed case count and counterexample. Model-created tests cannot replace the caller's acceptance contract.

Persistence publishes immutable world artifacts and a manifest, then flushes an atomic `CURRENT` pointer. `recover-session` imports the current revision and includes prior diagnostic history; it does not replay actions or restore old stacks. A torn diagnostic journal cannot change accepted state; recovery archives it before appending new records. Revisions currently require the same SBCL version.

The reference adapter covers an equal-tested table of readable, acyclic scalar/list/vector/string values and direct named `defun` and `(fmakunbound 'local-name)` forms, including edits nested in `progn`. Computed targets, removal inside other control forms, and indirect FMAKUNBOUND references are rejected by this adapter's conservative validation. It preserves table identity and restores function cells. Definitions performed indirectly, macros, methods, classes, external I/O, background threads, closures captured from arbitrary frames, and other resources need a world adapter with appropriate coverage. Accepted definitions must be reconstructible from their exported source. Safety checks and observations must cooperate with the owning thread and avoid deadlocking on locks held by a paused call.

Package locks and recursive syntax checks protect against mistakes, not arbitrary hostile Lisp. Computed calls, macro expansion, FFI, and resource exhaustion are outside that guarantee. Active frames and cached function objects retain their existing bodies; hot replacement relies on non-inline global dispatch. Hard crash/hang isolation belongs to an external process supervisor.

Architectural decisions live in [docs/adr](docs/adr/). [AGENTS.md](AGENTS.md) invokes the repository's [ADR maintenance skill](skills/maintain-adrs/SKILL.md).
