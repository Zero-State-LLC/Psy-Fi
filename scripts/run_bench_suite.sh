#!/usr/bin/env bash
# Run every CPU-only FieldLoop workload plus the baseline model runs and store the results.
# Usage: scripts/run_bench_suite.sh [extra psyfi-bench run flags]
# Results land in bench_results/ (gitignored). Nothing here is Ultra GPU evidence.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
run() { echo "== psyfi-bench run $*"; "$PY" -m psyfi_bench run "$@" --quiet ${EXTRA[@]+"${EXTRA[@]}"} || echo "   exit $? (partial or failed; see result)"; }
EXTRA=("$@")
run field-compute.scaling
run field-compute.steps
run field-compute.sustained
run field-compute.presets
run field-compute.accelerator
run render.soft.g4
for p in oracle constant random heuristic; do run interpretation.fieldread.smoke --provider "$p"; done
for p in oracle constant random heuristic; do run interpretation.fieldread --provider "$p"; done
run fieldloop.signature --provider heuristic
run fieldloop.signature --provider oracle
echo "== stored results"
"$PY" -m psyfi_bench results | "$PY" -c "import json,sys; [print(e['run_id'], e['manifest_id'], e['status'], e['measurement_class']) for e in json.load(sys.stdin)]"
