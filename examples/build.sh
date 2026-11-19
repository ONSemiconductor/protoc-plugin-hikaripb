#!/bin/sh
# Prepare the examples: generate the C, C++ and Python bindings and the Sphinx documentation of
# examples/proto/weather.proto into build/examples/generated, build the C and C++ examples into build/examples/bin
# and the documentation into build/examples/docs.
#
# Usage: examples/build.sh
#
# Requires protoc and the Python packages in protoc/requirements.txt (see scripts/generate.sh). The examples are only
# built when a compiler is found (CC / CXX, default cc / c++); the Python example needs no build. The documentation
# is only built when sphinx-build and the Python package myst_parser are installed.
set -eu

EXAMPLES_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${EXAMPLES_DIR}/.." && pwd)"
SCRIPT_DIR="${ROOT_DIR}/scripts"
OUT_DIR="${ROOT_DIR}/build/examples"
GEN_DIR="${OUT_DIR}/generated"
BIN_DIR="${OUT_DIR}/bin"
PROTO_FILE="${EXAMPLES_DIR}/proto/weather.proto"

CC="${CC:-cc}"
CXX="${CXX:-c++}"

rm -rf "${OUT_DIR}"

# One prefix per backend keeps the runtime files of the C and C++ output apart, so both directories can be on
# one include path (see .vscode/settings.json).
sh "${SCRIPT_DIR}/generate.sh" "${PROTO_FILE}" "${GEN_DIR}/c" weather_c c
sh "${SCRIPT_DIR}/generate.sh" "${PROTO_FILE}" "${GEN_DIR}/cpp" weather_cpp cpp
sh "${SCRIPT_DIR}/generate.sh" "${PROTO_FILE}" "${GEN_DIR}/py" weather_py py
sh "${SCRIPT_DIR}/generate.sh" "${PROTO_FILE}" "${GEN_DIR}/sphinx" weather_docs sphinxdocs "title=Weather+station+protocol"

mkdir -p "${BIN_DIR}"

# -Wno-unused-parameter: the generated inline setters only use their handle parameter in debug assertions.
if command -v "${CC}" >/dev/null 2>&1; then
	echo "Building the C example -> ${BIN_DIR}/weather_c"
	"${CC}" -std=c11 -Wall -Wextra -Wno-unused-parameter -g \
		-I"${EXAMPLES_DIR}/c" -I"${GEN_DIR}/c" \
		"${EXAMPLES_DIR}/c/main.c" "${GEN_DIR}"/c/*.c -o "${BIN_DIR}/weather_c"
else
	echo "No C compiler found (${CC}), the C example is not built."
fi

if command -v "${CXX}" >/dev/null 2>&1; then
	echo "Building the C++ example -> ${BIN_DIR}/weather_cpp"
	"${CXX}" -std=c++17 -Wall -Wextra -Wno-unused-parameter -g \
		-I"${EXAMPLES_DIR}/cpp" -I"${GEN_DIR}/cpp" \
		"${EXAMPLES_DIR}/cpp/main.cc" "${GEN_DIR}"/cpp/*.cc -o "${BIN_DIR}/weather_cpp"
else
	echo "No C++ compiler found (${CXX}), the C++ example is not built."
fi

if command -v sphinx-build >/dev/null 2>&1 && "${PYTHON:-python3}" -c "import myst_parser" >/dev/null 2>&1; then
	echo "Building the documentation -> ${OUT_DIR}/docs"
	sphinx-build -q -b html "${GEN_DIR}/sphinx" "${OUT_DIR}/docs"
else
	echo "sphinx-build or myst_parser not found, the documentation is not built."
fi

echo "Examples are ready:"
echo "  ${BIN_DIR}/weather_c"
echo "  ${BIN_DIR}/weather_cpp"
echo "  python3 ${EXAMPLES_DIR}/py/main.py"
echo "  ${GEN_DIR}/sphinx (Sphinx sources of the documentation)"
