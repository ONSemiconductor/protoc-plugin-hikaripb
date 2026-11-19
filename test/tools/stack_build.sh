#!/bin/sh
# Compile every generated + support .c file with -fstack-usage so stack_usage.py
# can build a static call graph and report worst-case stack depth.
# Usage: stack_build.sh <cc> <build_dir> <cflags> <include_flags> <src_dir> [<src_dir> ...]
set -eu

if [ "$#" -lt 5 ]; then
	echo "Usage: $0 <cc> <build_dir> <cflags> <include_flags> <src_dir> [<src_dir> ...]" >&2
	exit 1
fi

CC="$1"
BUILD_DIR="$2"
CFLAGS="$3"
INCLUDE_FLAGS="$4"
shift 4

rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

find "$@" -name '*.c' > "${BUILD_DIR}/sources.txt"

while IFS= read -r src; do
	obj="${BUILD_DIR}/$(basename "${src}" .c).o"
	eval "${CC} ${INCLUDE_FLAGS} ${CFLAGS} -c \"${src}\" -o \"${obj}\""
done < "${BUILD_DIR}/sources.txt"
