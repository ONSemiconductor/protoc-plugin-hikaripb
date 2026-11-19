#!/bin/sh
# Generate C, C++ and/or Python bindings from a .proto file using protoc/hikaripb.py.
#
# Usage:
#   generate.sh <proto_file> <out_dir> [prefix] [type] [options]
#
#   proto_file  Path to the .proto file to compile.
#   out_dir     Directory that will receive the generated files.
#   prefix      Prefix used for the generated runtime symbols, the C++
#               namespace, the Python runtime modules and the labels of the
#               Sphinx documentation (default: hikaripb).
#   type        c | cpp | py | both | sphinxdocs (default: both). "both" means
#               c+py; pass "cpp" explicitly for the self-contained native C++ codec
#               (unrelated to the c backend - requires a hand-written
#               <prefix>_config.h, see test/cpp/hikaripb_config.h). "sphinxdocs"
#               writes Sphinx documentation (MyST Markdown) instead of code.
#   options     Extra --hikaripb_out options appended to every backend, comma
#               separated, e.g. "single_file=protocol" (see docs/content/options.md).
#
# Requires `protoc` (with support for `--experimental_allow_proto3_optional`)
# and the Python packages in protoc/requirements.txt (protobuf, jinja2) to be
# importable by the `python3` on PATH.
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PLUGIN="${ROOT_DIR}/protoc/hikaripb.py"

if [ "$#" -lt 2 ]; then
	echo "Usage: $0 <proto_file> <out_dir> [prefix] [type: c|cpp|py|both|sphinxdocs] [options]" >&2
	exit 1
fi

PROTO_FILE="$1"
OUT_DIR="$2"
PREFIX="${3:-hikaripb}"
TYPE="${4:-both}"
EXTRA="${5:+,$5}"

PROTOC="${PROTOC:-protoc}"
PYTHON="${PYTHON:-python3}"

PROTO_DIR="$(cd "$(dirname "${PROTO_FILE}")" && pwd)"
PROTO_BASENAME="$(basename "${PROTO_FILE}")"

mkdir -p "${OUT_DIR}"

if [ "${TYPE}" = "c" ] || [ "${TYPE}" = "both" ]; then
	echo "Generating C bindings -> ${OUT_DIR}"
	"${PROTOC}" --experimental_allow_proto3_optional \
		--plugin=protoc-gen-hikaripb="${PLUGIN}" \
		--proto_path="${PROTO_DIR}" \
		--hikaripb_out="type=c,prefix=${PREFIX}${EXTRA}:${OUT_DIR}" \
		"${PROTO_DIR}/${PROTO_BASENAME}"
fi

if [ "${TYPE}" = "py" ] || [ "${TYPE}" = "both" ]; then
	echo "Generating Python bindings -> ${OUT_DIR}"
	"${PROTOC}" --experimental_allow_proto3_optional \
		--plugin=protoc-gen-hikaripb="${PLUGIN}" \
		--proto_path="${PROTO_DIR}" \
		--hikaripb_out="type=py,prefix=${PREFIX}${EXTRA}:${OUT_DIR}" \
		"${PROTO_DIR}/${PROTO_BASENAME}"
fi

if [ "${TYPE}" = "cpp" ]; then
	echo "Generating C++ bindings (self-contained hikaripb:: codec) -> ${OUT_DIR}"
	"${PROTOC}" --experimental_allow_proto3_optional \
		--plugin=protoc-gen-hikaripb="${PLUGIN}" \
		--proto_path="${PROTO_DIR}" \
		--hikaripb_out="type=cpp,prefix=${PREFIX}${EXTRA}:${OUT_DIR}" \
		"${PROTO_DIR}/${PROTO_BASENAME}"
fi

if [ "${TYPE}" = "sphinxdocs" ]; then
	echo "Generating Sphinx documentation -> ${OUT_DIR}"
	"${PROTOC}" --experimental_allow_proto3_optional \
		--plugin=protoc-gen-hikaripb="${PLUGIN}" \
		--proto_path="${PROTO_DIR}" \
		--hikaripb_out="type=sphinxdocs,prefix=${PREFIX}${EXTRA}:${OUT_DIR}" \
		"${PROTO_DIR}/${PROTO_BASENAME}"
fi

echo "Done."
