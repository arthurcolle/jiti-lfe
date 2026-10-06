.PHONY: all build test repl test-kernel check-adrs

all: build

build:
	bash scripts/build-lfe.sh

test: build
	python3 tests/lfe_scenarios.py
	python3 tests/lfe_diagnostics.py
	python3 tests/lfe_native_plans.py
	python3 tests/lfe_toolkit.py
	python3 tests/lfe_tool_limit_test.py
	python3 tests/lfe_display_test.py
	python3 tests/test_lfe_chat_compaction.py
	python3 tests/test_lfe_context_v2.py
	python3 tests/lfe_planning.py
	python3 tests/lfe_farm_rollouts.py
	python3 scripts/check-adrs.py

repl: build
	python3 scripts/repl.py --lfe

test-kernel:
	devenv shell test

check-adrs:
	python3 scripts/check-adrs.py
