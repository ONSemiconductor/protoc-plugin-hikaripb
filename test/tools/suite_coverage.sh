#!/bin/sh
# Capture gcov data and generate an HTML coverage report.
# Usage: suite_coverage.sh <gcov_dir> <lcov_info> <html_dir> <obj_dir> [-- <excl1>...]
set -eu

if [ "$#" -lt 4 ]; then
	echo "Usage: $0 <gcov_dir> <lcov_info> <html_dir> <obj_dir> [-- <excl1>...]" >&2
	exit 1
fi

GCOV_DIR="$1"
LCOV_INFO="$2"
HTML_DIR="$3"
OBJ_DIR="$4"
shift 4

if [ "$#" -gt 0 ] && [ "$1" = "--" ]; then
	shift
fi

if ! command -v lcov >/dev/null 2>&1; then
	echo "lcov not found. Install with: sudo apt-get install lcov"
	echo "Coverage data is in: $OBJ_DIR"
	exit 0
fi

mkdir -p "$GCOV_DIR"

lcov --directory "$OBJ_DIR" --capture --output-file "$LCOV_INFO" --quiet --ignore-errors mismatch,unused

for excl in "$@"; do
	lcov --remove "$LCOV_INFO" "$excl" --output-file "$LCOV_INFO" --quiet --ignore-errors unused
done

genhtml "$LCOV_INFO" --output-directory "$HTML_DIR" --quiet
echo "Coverage report generated at $HTML_DIR/index.html"
