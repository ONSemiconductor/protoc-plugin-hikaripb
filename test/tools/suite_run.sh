#!/bin/sh
# Run test binaries and print a Suite Summary line (criterion --verbose synthesis).
# Usage: suite_run.sh <bin1> [<bin2>...]
set -eu

if [ "$#" -lt 1 ]; then
	echo "Usage: $0 <bin> [<bin>...]" >&2
	exit 1
fi

echo "=== Running tests ==="

tested=0
passing=0
failing=0
crashing=0
failed_bins=0

for bin in "$@"; do
	echo "Running $bin..."
	set +e
	output=$("$bin" --verbose 2>&1)
	status=$?
	set -e
	printf '%s\n' "$output"
	summary_line=$(printf '%s\n' "$output" | grep '\[====\] Synthesis:' | tail -n1)
	if [ -n "$summary_line" ]; then
		tested_count=$(printf '%s\n' "$summary_line" | sed -n 's/.*Tested: \([0-9][0-9]*\).*/\1/p')
		pass=$(printf '%s\n' "$summary_line" | sed -n 's/.*Passing: \([0-9][0-9]*\).*/\1/p')
		fail=$(printf '%s\n' "$summary_line" | sed -n 's/.*Failing: \([0-9][0-9]*\).*/\1/p')
		crash=$(printf '%s\n' "$summary_line" | sed -n 's/.*Crashing: \([0-9][0-9]*\).*/\1/p')
		tested=$((tested + ${tested_count:-0}))
		passing=$((passing + ${pass:-0}))
		failing=$((failing + ${fail:-0}))
		crashing=$((crashing + ${crash:-0}))
	fi
	if [ "$status" -ne 0 ]; then
		failed_bins=$((failed_bins + 1))
	fi
done

echo "=== Suite Summary: Tested: $tested | Passing: $passing | Failing: $failing | Crashing: $crashing | Failed Binaries: $failed_bins"
if [ "$failing" -ne 0 ] || [ "$crashing" -ne 0 ] || [ "$failed_bins" -ne 0 ]; then
	exit 1
fi
