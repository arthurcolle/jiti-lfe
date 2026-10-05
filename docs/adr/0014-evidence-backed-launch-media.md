# 0014: Render launch media from saved execution evidence

Status: Accepted
Date: 2026-10-05

## Context

Launch and explainer videos demonstrate incremental application construction, live repair, and durable managed state. Reconstructing terminal replies in an editor could misrepresent what ran. Repeating model requests every time captions or layout change adds cost and makes the result difficult to reproduce.

## Decision

Separate capture and media generation from rendering. Save real kernel results and model conversations as evidence with explicit provenance, then bind video scenes to evidence IDs in a versioned editorial manifest. The offline renderer requires referenced evidence, labels scripted execution and model output separately, and retains its exact inputs beside the rendered files. Narration and music are saved assets; rendering never invokes a model.

## Rationale

A single live-generation-and-render operation would couple editorial iteration to nondeterministic model behavior. Handwritten terminal simulations would obscure whether claims were verified. Saved evidence allows repeatable layouts and comparison with the actual application results while preserving the difference between a deterministic demonstration and a model-created implementation.

## Consequences

The expense example uses the existing world-adapter interface and caller-owned checks. Deterministic capture proves repair, preview, rollback, and fresh-process recovery; model capture records incremental function creation separately. Generated media and local capture stores are ignored by Git, while scripts, prompts, and the editorial manifest are tracked. Missing evidence rejects rendering. Credentials and signed media URLs are excluded from exported metadata. Provider-generated audio can vary between generations; rerenders use its retained files.

Related: [caller-governed evolution](0008-caller-governed-evolution.md), [development and execution](0010-development-and-execution.md).

Implementation: [capture](../../scripts/launch/expense_capture.lisp), [renderer](../../scripts/launch/render.py), [production package](../../launch/README.md).
Verification: [capture scenarios](../../tests/launch_capture_scenarios.py), [renderer checks](../../scripts/launch/test_render.py).
