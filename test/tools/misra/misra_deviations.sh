#!/bin/sh
# Compare the MISRA findings with the deviation list.
#
#   misra_deviations.sh <findings> <deviations>
#
# <findings> has a line "<file> <rule>" for every finding, <deviations> a line "<rule> <file pattern> <reason>" for every
# rule that the generated code deviates from in the files that match the pattern (a shell pattern for the base name of the
# file; lines that start with # are comments). The exit status is 1 when there is a finding that no deviation covers.

findings=$1
deviations=$2
status=0

while read -r file rule; do
    [ -n "$file" ] || continue
    base=$(basename "$file")
    covered=0
    while read -r deviation_rule pattern _; do
        case "$deviation_rule" in
            '' | '#'*) continue ;;
        esac
        if [ "$deviation_rule" = "$rule" ]; then
            # the pattern is unquoted on purpose: it is a shell pattern
            case "$base" in
                $pattern) covered=1 ;;
            esac
        fi
        [ "$covered" -eq 1 ] && break
    done < "$deviations"
    if [ "$covered" -eq 0 ]; then
        echo "MISRA finding that no deviation covers: $rule in $file"
        status=1
    fi
done < "$findings"

exit $status
