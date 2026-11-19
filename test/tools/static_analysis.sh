#!/bin/sh
# Static analysis of the generated C or C++ code: strict compiler warnings (-Werror), clang-tidy and, for C, the
# MISRA C:2012 addon of cppcheck. Every tool that is not installed is skipped with a note; any finding fails the run.
#
#   static_analysis.sh c   <generated dir> <config dir>...
#   static_analysis.sh cpp <generated dir> <config dir>...
#
# Every config dir holds the <prefix>_config.h that the generated code includes (the library compiles with each one:
# the settings change the code that is compiled). Environment: CC, CXX, CLANG_TIDY, CPPCHECK (default: the tool
# found in the PATH), CPPCHECK_ADDONS (the directory of misra.py), ANALYSIS_DIR (the folder for the reports).

set -u

LANG_KIND=$1
GEN_DIR=$2
shift 2
CONFIG_DIRS="$*"

SELF_DIR=$(cd "$(dirname "$0")" && pwd)
CC=${CC:-gcc}
CXX=${CXX:-g++}
CLANG_TIDY=${CLANG_TIDY:-clang-tidy}
CPPCHECK=${CPPCHECK:-cppcheck}
ANALYSIS_DIR=${ANALYSIS_DIR:-/tmp/hikaripb_analysis}
FAILED=0

mkdir -p "$ANALYSIS_DIR"

have() {
    command -v "$1" >/dev/null 2>&1
}

fail() {
    echo "FAIL: $*"
    FAILED=1
}

# The warnings that the coding standards ask for. -Wcast-align is left out: the descriptor tables address the fields of a
# message by their offset, which needs the casts of the deviations in docs (the decoder reads a field at an aligned
# offset of an aligned struct).
C_WARNINGS="-std=c11 -Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion -Wshadow -Wcast-qual -Wstrict-prototypes \
-Wmissing-prototypes -Wmissing-declarations -Wundef -Wswitch-default -Wredundant-decls -Wdouble-promotion -Wformat=2 \
-Wnull-dereference -Wvla -Wfloat-equal -Wold-style-definition -Wjump-misses-init -Wlogical-op -Wunused \
-Wnested-externs -Werror"
CXX_WARNINGS="-std=c++17 -Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion -Wshadow -Wold-style-cast -Wcast-qual \
-Wzero-as-null-pointer-constant -Wnon-virtual-dtor -Woverloaded-virtual -Wundef -Wswitch-default \
-Wdouble-promotion -Wformat=2 -Wnull-dereference -Wextra-semi -Wfloat-equal -Wlogical-op -Wunused \
-Wsuggest-override -Werror"

# every translation unit of the generated code: the sources of C, a unit that includes every header of C++
sources() {
    if [ "$LANG_KIND" = "c" ]; then
        find "$GEN_DIR" -name '*.c' | sort
    else
        unit="$ANALYSIS_DIR/all_headers.cc"
        : > "$unit"
        find "$GEN_DIR" -name '*.pb.h' | sort | while read -r header; do
            echo "#include \"${header#"$GEN_DIR"/}\"" >> "$unit"
        done
        echo "$unit"
        find "$GEN_DIR" -name '*.cc' | sort
    fi
}

compile_all() {
    config=$1
    for source in $(sources); do
        if [ "$LANG_KIND" = "c" ]; then
            $CC -fsyntax-only $C_WARNINGS -isystem "$config" -I"$GEN_DIR" "$source" || fail "$CC $source ($config)"
        else
            $CXX -fsyntax-only $CXX_WARNINGS -isystem "$config" -I"$GEN_DIR" "$source" || fail "$CXX $source ($config)"
        fi
    done
}

for config in $CONFIG_DIRS; do
    echo "== compiler warnings: $LANG_KIND with the configuration $config"
    compile_all "$config"
done

# clang-tidy: the checks that map to the rules of MISRA C:2012 / MISRA C++ and CERT, over the same translation units
TIDY_CHECKS=$(tr -d '\r\n' < "$SELF_DIR/clang_tidy_checks_$LANG_KIND.txt")
if have "$CLANG_TIDY"; then
    for config in $CONFIG_DIRS; do
        echo "== clang-tidy: $LANG_KIND with the configuration $config"
        for source in $(sources); do
            if [ "$LANG_KIND" = "c" ]; then
                std="-std=c11"
            else
                std="-std=c++17"
            fi
            $CLANG_TIDY -quiet -checks="$TIDY_CHECKS" -warnings-as-errors='*' --header-filter="$GEN_DIR/.*" \
                "$source" -- $std -isystem "$config" -I"$GEN_DIR" > "$ANALYSIS_DIR/tidy.txt" 2>&1 ||
                { cat "$ANALYSIS_DIR/tidy.txt"; fail "clang-tidy $source ($config)"; }
        done
    done
else
    echo "== clang-tidy is not installed, skipped"
fi

# MISRA C:2012 with the addon of cppcheck: its findings must be the ones of the deviation list, nothing else. A checker
# is configured for a standard: MISRA_CONFIG_DIRS names the configurations that define PB_OFFSETOF as offsetof (cppcheck does
# not know the GCC built-in that the default of the library uses), by default all of them.
if [ "$LANG_KIND" = "c" ]; then
    ADDONS=${CPPCHECK_ADDONS:-}
    if have "$CPPCHECK" && [ -n "$ADDONS" ] && [ -f "$ADDONS/misra.py" ] && have python3; then
        for config in ${MISRA_CONFIG_DIRS:-$CONFIG_DIRS}; do
            echo "== MISRA C:2012 (cppcheck): the configuration $config"
            : > "$ANALYSIS_DIR/misra.txt"
            for source in $(sources); do
                $CPPCHECK -q --std=c11 --dump --max-configs=1 --suppress=missingIncludeSystem -I"$config" -I"$GEN_DIR" \
                    "$source" > /dev/null 2>&1
                python3 "$ADDONS/misra.py" "$source.dump" 2>&1 | grep -E 'misra-c2012-[0-9]+\.[0-9]+' >> "$ANALYSIS_DIR/misra.txt"
                rm -f "$source.dump" "$source".*.dump
            done
            # a finding is "[file:line] ... [misra-c2012-X.Y]", the deviation list holds the rule and a file pattern; only the
            # findings in the generated code count, the configuration is the code of the user
            sed -E 's/^\[([^:]+):([0-9]+)\].*\[(misra-c2012-[0-9]+\.[0-9]+)\]$/\1 \3/' "$ANALYSIS_DIR/misra.txt" |
                grep "^$GEN_DIR/" | sort -u > "$ANALYSIS_DIR/misra_findings.txt"
            sh "$SELF_DIR/misra/misra_deviations.sh" "$ANALYSIS_DIR/misra_findings.txt" "$SELF_DIR/misra/misra_deviations.txt" ||
                fail "MISRA C:2012 findings that are not in tools/misra/misra_deviations.txt ($config)"
        done
    else
        echo "== cppcheck with its MISRA addon is not available (set CPPCHECK and CPPCHECK_ADDONS), skipped"
    fi
fi

if [ "$FAILED" -ne 0 ]; then
    echo "static analysis of the $LANG_KIND code: FAILED"
    exit 1
fi
echo "static analysis of the $LANG_KIND code: passed"
