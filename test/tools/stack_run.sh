#!/bin/sh
# Report worst-case stack usage for a set of root functions.
# Usage: stack_run.sh <stack_usage.py> <build_dir> <args...> -- <root_func> [<root_func> ...]
set -eu

if [ "$#" -lt 4 ]; then
	echo "Usage: $0 <stack_script> <build_dir> <script_args> <root_func> [<root_func> ...]" >&2
	exit 1
fi

STACK_SCRIPT="$1"
BUILD_DIR="$2"
SCRIPT_ARGS="$3"
shift 3

for root in "$@"; do
	echo ""
	echo "=== Stack usage for ${root} ==="
	eval "python3 \"${STACK_SCRIPT}\" \"${BUILD_DIR}\" ${SCRIPT_ARGS} \"${root}\""
done
