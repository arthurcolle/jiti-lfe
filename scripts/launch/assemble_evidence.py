#!/usr/bin/env python3
"""Combine recorded model chat and scripted kernel events without mixing provenance."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

SECRET = re.compile(r"(?:sk-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9_.-]{20,})")


def read_capture(path: Path) -> dict:
    text = path.read_text()
    if SECRET.search(text):
        raise ValueError("Possible credential in capture; refusing to export")
    return json.loads(text)


def event_lines(event: dict, mode: str) -> list[str]:
    view = event.get("view", {})
    result = view.get("result", {})
    lines = []
    if mode == "live-model" and event.get("prompt"):
        # Exact first sentence, explicitly labelled an excerpt. The full prompt remains in JSON.
        first_sentence = re.split(r"(?<=[.!?])\s+", event["prompt"], maxsplit=1)[0]
        lines.append("User (excerpt): " + first_sentence)
    if mode == "scripted-kernel" and event.get("prompt"):
        lines.append("Scripted intent: " + event["prompt"])
    if event.get("result_text"):
        lines.append("Result:")
        lines.extend(event["result_text"].splitlines())
    if event["id"] == "empty_catalogue":
        lines.append("Catalogue count: " + str(result.get("catalogue_count", 0)))
    if view.get("condition"):
        lines.append("Condition: " + view["condition"])
    if event.get("source"):
        lines.append("Lisp: " + event["source"])
    lines.append("Worker status: " + str(view.get("status", "unknown")))
    if result.get("commit"):
        lines.append("Commit: " + result["commit"])
    if result.get("reason"):
        lines.append("Reason: " + result["reason"])
    if view.get("operation_id"):
        lines.append("Operation: " + view["operation_id"])
    if view.get("revision"):
        lines.append("Revision: " + view["revision"])
    if event.get("process_id"):
        lines.append("Fresh process ID: " + str(event["process_id"]))
    if event["id"] == "caller_checks":
        for field, label in [("goal_checks", "Goal"), ("safety_checks", "Safety")]:
            for check in view.get(field, []):
                lines.append(f"{label} {check['name']}: {check['status']}")
    if event["id"] == "paused_call":
        for restart in view.get("restarts", []):
            lines.append(f"Live restart: {restart['name']} ({restart['id']})")
    if mode == "live-model" and event.get("tool_calls"):
        # Display actual source from this turn, not an illustrative replacement.
        for tool in event["tool_calls"]:
            if tool["name"] == "develop_form":
                source = json.loads(tool["arguments"]).get("source", "")
                lines.append("Model-generated source (excerpt):")
                rows = source.splitlines()
                lines.extend(rows[:14])
                if len(rows) > 14:
                    lines.append("[Continues in the saved source artifact]")
                break
    return lines


def assemble(scripted: Path | None, live: Path | None) -> dict:
    if not scripted and not live:
        raise ValueError("Supply at least one saved capture")
    inputs = []
    if scripted:
        inputs.append((scripted, "scripted-kernel", "Scripted kernel verification · author-supplied Lisp"))
    if live:
        inputs.append((live, "live-model", "Live model conversation · model-generated Lisp"))
    sections, sources = {}, []
    for path, mode, provenance in inputs:
        capture = read_capture(path)
        if mode == "live-model" and capture.get("meta", {}).get("passed") is not True:
            raise ValueError("The live model capture has not passed caller verification")
        sources.append({"path": str(path), "mode": mode, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        for event in capture["events"]:
            if mode == "live-model" and event.get("verified") is not True:
                continue
            sections[event["id"]] = {
                "lines": event_lines(event, mode),
                "mode": mode,
                "provenance": provenance,
                "source_capture": str(path),
                "event_id": event["id"],
            }
            definitions = {
                "record_expense": "define_expense",
                "spending_total": "define_total",
                "category_totals": "define_categories",
                "budget_report": "define_report",
            }
            if mode == "live-model" and event["id"] in definitions:
                for index, tool in enumerate(event.get("tool_calls", [])):
                    if tool["name"] != "develop_form":
                        continue
                    source = json.loads(tool["arguments"])["source"]
                    tool_view = tool["result"]
                    result_values = tool_view.get("result", {}).get("values", [])
                    definition_event = {
                        "id": definitions[event["id"]],
                        "prompt": event.get("prompt"),
                        "source": source,
                        "view": tool_view,
                        "result_text": "\n".join(value["text"] for value in result_values),
                    }
                    sections[definition_event["id"]] = {
                        "lines": event_lines(definition_event, mode),
                        "mode": mode,
                        "provenance": provenance,
                        "source_capture": str(path),
                        "event_id": event["id"],
                        "tool_call_index": index,
                    }
                    break
    return {
        "schema_version": 1,
        "meta": {
            "mode": "mixed" if live and scripted else "live-model" if live else "scripted-kernel",
            "description": "Literal excerpts from saved kernel and model events; each section identifies its provenance.",
            "sources": sources,
        },
        "sections": sections,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scripted", type=Path)
    parser.add_argument("--live", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = assemble(args.scripted, args.live)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {len(evidence['sections'])} evidence sections to {args.output}")


if __name__ == "__main__":
    main()
