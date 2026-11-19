#!/usr/bin/env python3
"""
stack_usage.py - compute worst-case stack depth for one or more call-tree roots.

Usage:
    python3 test/tools/stack_usage.py [options] <build_dir> <root_func> [root_func ...]

Options:
    -v, --verbose                     Print the full call path for each root.
    --indirect-edge caller:callee     Inject a synthetic call edge (may be
                                      repeated).  Use this to account for calls
                                      made through function pointers that the
                                      static disassembler cannot see.
    --max-recursion N                 Allow each function to be re-entered up to
                                      N extra times on a single path.  Use this
                                      when the code contains bounded mutual
                                      recursion (e.g. a message decoder that
                                      recurses once per nesting level).
                                      Default: 0 (no re-entry).
    --top N                           Print the N worst-case stack traces for
                                      each root function.  Default: 1.

GCC must have been invoked with -fstack-usage so that .su files exist next to
the .o files.  objdump is used to build the call graph from the object files.
"""

import os
import re
import sys
import subprocess
from bisect import bisect_right
from collections import defaultdict


def get_objdump_cmd(obj_path):
    """Return the objdump command prefix (binary + arch flags) for obj_path.

    The system objdump only handles native objects.  For cross-compiled targets
    (e.g. ARM) the matching cross-objdump binary must be used instead.
    """
    try:
        result = subprocess.run(
            ["file", obj_path],
            capture_output=True, text=True, check=True,
        )
        file_output = result.stdout.lower()

        if "80386" in file_output or "intel 80386" in file_output:
            return ["objdump", "-m", "i386"]
        elif "x86-64" in file_output or "x86_64" in file_output:
            return ["objdump"]
        elif "aarch64" in file_output or "arm64" in file_output:
            return ["aarch64-linux-gnu-objdump"]
        elif "arm" in file_output:
            return ["arm-none-eabi-objdump"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    # Default: native objdump, let it auto-detect
    return ["objdump"]


def normalize_function_name(name):
    """Normalize function names by removing numeric suffixes added by the compiler.
    E.g., 'foo.isra.0' -> 'foo.isra', 'bar.constprop.0' -> 'bar.constprop'."""
    # Strip trailing .digits (e.g., .0, .1, etc.)
    return re.sub(r'\.\d+$', '', name)


def find_files(root, ext):
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(ext):
                yield os.path.join(dirpath, name)


def parse_su_files(build_dir):
    """Return {function_name: (frame_bytes, qualifier_string, source_location)}."""
    usage = {}
    su_line = re.compile(r"^(.+?):([0-9]+):[0-9]+:([^\s]+)\s+(\d+)\s*(.*)$")
    for su_path in find_files(build_dir, ".su"):
        with open(su_path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                # GCC format: path:line:col:fname <ws> bytes <ws> qualifier
                m = su_line.match(line)
                if not m:
                    continue
                src_file = m.group(1)
                src_line = m.group(2)
                fname = normalize_function_name(m.group(3))
                size = int(m.group(4))
                qualifier = m.group(5).strip() if m.group(5).strip() else "static"
                location = f"{src_file}:{src_line}"
                # Keep the worst-case entry when a name appears in multiple TUs.
                if fname not in usage or size > usage[fname][0]:
                    usage[fname] = (size, qualifier, location)
    return usage


def parse_function_ranges(obj_path):
    """Return [(start_addr, func_name)] sorted by address for one object file."""
    try:
        cmd = get_objdump_cmd(obj_path) + ["-d", obj_path]
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    ranges = []
    seen_addrs = set()
    label_re = re.compile(r"^([0-9a-f]+)\s+<([^>]+)>:")
    for line in result.stdout.splitlines():
        m = label_re.match(line.strip())
        if m:
            addr = int(m.group(1), 16)
            func_name = normalize_function_name(m.group(2))
            # Skip compiler-internal thunks (e.g. __x86.get_pc_thunk.*).
            # They live in their own .text.* subsections, each starting at
            # address 0, which collides with real functions in .text and
            # causes owner_function() to map relocation offsets incorrectly.
            if func_name.startswith("__"):
                continue
            # When two symbols share the same address (different sections),
            # keep only the first one seen — that is the real .text function.
            if addr in seen_addrs:
                continue
            seen_addrs.add(addr)
            ranges.append((addr, func_name))
    ranges.sort(key=lambda t: t[0])
    return ranges


def owner_function(offset_hex, func_ranges):
    """Map a relocation/instruction offset to its containing function name."""
    if not func_ranges:
        return None
    starts = [start for start, _ in func_ranges]
    offset = int(offset_hex, 16)
    idx = bisect_right(starts, offset) - 1
    if idx < 0:
        return None
    return func_ranges[idx][1]


def parse_relocation_calls(obj_path, func_ranges):
    """Return {caller: set(external_callees)} inferred from .text relocations."""
    graph = defaultdict(set)
    try:
        cmd = get_objdump_cmd(obj_path) + ["-r", obj_path]
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return graph

    in_text = False
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if line.startswith("RELOCATION RECORDS FOR [.text]:"):
            in_text = True
            continue
        if in_text and line.startswith("RELOCATION RECORDS FOR [") and ".text" not in line:
            break
        if not in_text:
            continue
        if not line or line.startswith("OFFSET"):
            continue

        parts = line.split()
        if len(parts) < 3:
            continue

        offset_hex = parts[0]
        rel_type = parts[1]
        value = parts[2]

        # Accept relocation types that represent direct function calls:
        #   PLT32 / PC32  — x86 (external / internal)
        #   THM_CALL      — ARM Thumb BL/BLX
        #   ARM_CALL      — ARM BL/BLX
        #   ARM_PC24      — ARM B/BL (older toolchains)
        call_types = ("PLT32", "PC32", "THM_CALL", "ARM_CALL", "ARM_PC24")
        if not any(t in rel_type for t in call_types):
            continue

        callee = value.split("-")[0]
        # Skip compiler-internal and runtime-support symbols (__aeabi_*, __x86.*,
        # etc.) — they are ABI helpers, not application stack contributors.
        if callee.startswith("__"):
            continue
        caller = owner_function(offset_hex, func_ranges)
        if caller:
            caller = normalize_function_name(caller)
            callee = normalize_function_name(callee)
        if caller and callee and callee != caller and not callee.startswith("."):
            graph[caller].add(callee)

    return graph


def parse_call_graph(build_dir):
    """Return {caller: set(callees)} built from object-file disassembly."""
    graph = defaultdict(set)
    for obj_path in find_files(build_dir, ".o"):
        func_ranges = parse_function_ranges(obj_path)

        # Add external call edges based on relocations in .text.
        rel_graph = parse_relocation_calls(obj_path, func_ranges)
        for caller, callees in rel_graph.items():
            graph[caller].update(callees)

        # Add direct internal call edges from disassembly labels.
        try:
            cmd = get_objdump_cmd(obj_path) + ["-d", obj_path]
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

        current_func = None
        for line in result.stdout.splitlines():
            # Function label: "0000000000000000 <func_name>:"
            m = re.match(r"^[0-9a-f]+\s+<([^>@+]+)>:", line.strip())
            if m:
                current_func = normalize_function_name(m.group(1))
                continue
            if current_func is None:
                continue
            # Direct call instruction with a resolved target label.
            # x86:  call / callq  addr <name>
            # ARM:  bl / blx      addr <name>
            m = re.search(
                r"\b(?:call[q]?|blx?)\s+[0-9a-f]+\s+<([^>@+]+?)(?:@[^>]+)?(?:\+0x[0-9a-f]+)?>",
                line.strip(),
            )
            if m:
                callee = normalize_function_name(m.group(1))
                # Skip compiler/runtime helpers (e.g. __aeabi_*, __x86.*)
                if callee.startswith("__"):
                    continue
                if callee != current_func:
                    graph[current_func].add(callee)
    return graph


def _top_stacks(func, usage, graph, stack, visit_counts, max_recursion, n):
    """
    Depth-first search returning up to *n* (total_bytes, path) pairs,
    sorted worst-first.  Each pair represents a distinct leaf-to-root path.
    *visit_counts* maps function names to how many times they have been entered
    on the current path.  A function may be re-entered at most *max_recursion*
    extra times; when that limit is reached it is treated as a leaf.
    """
    own = usage.get(func, (0, "static"))[0]
    new_stack = stack + [(func, own)]

    child_counts = dict(visit_counts)
    child_counts[func] = child_counts.get(func, 0) + 1

    callees = {c for c in graph.get(func, set())
               if child_counts.get(c, 0) <= max_recursion}

    if not callees:
        total = sum(sz for _, sz in new_stack)
        return [(total, new_stack)]

    all_results = []
    for c in callees:
        all_results.extend(
            _top_stacks(c, usage, graph, new_stack, child_counts, max_recursion, n)
        )

    all_results.sort(key=lambda t: t[0], reverse=True)
    return all_results[:n]


def top_n_cases(root, usage, graph, max_recursion=0, n=1):
    """Return up to *n* (total_bytes, path) pairs sorted worst-first."""
    return _top_stacks(root, usage, graph, [], {}, max_recursion, n)


def worst_case(root, usage, graph, max_recursion=0):
    """Return (total_bytes, call_path_list) for the worst-case call chain."""
    results = top_n_cases(root, usage, graph, max_recursion, n=1)
    return results[0] if results else (0, [])


def main():
    args = sys.argv[1:]

    verbose = False
    indirect_edges = []
    max_recursion = 0
    top = 1
    filtered = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-v", "--verbose"):
            verbose = True
        elif arg == "--indirect-edge":
            i += 1
            if i >= len(args):
                print("--indirect-edge requires a caller:callee argument", file=sys.stderr)
                sys.exit(1)
            indirect_edges.append(args[i])
        elif arg.startswith("--indirect-edge="):
            indirect_edges.append(arg.split("=", 1)[1])
        elif arg == "--max-recursion":
            i += 1
            if i >= len(args):
                print("--max-recursion requires an integer argument", file=sys.stderr)
                sys.exit(1)
            max_recursion = int(args[i])
        elif arg.startswith("--max-recursion="):
            max_recursion = int(arg.split("=", 1)[1])
        elif arg == "--top":
            i += 1
            if i >= len(args):
                print("--top requires an integer argument", file=sys.stderr)
                sys.exit(1)
            top = int(args[i])
        elif arg.startswith("--top="):
            top = int(arg.split("=", 1)[1])
        else:
            filtered.append(arg)
        i += 1

    if len(filtered) < 2:
        print(f"Usage: {sys.argv[0]} [options] <build_dir> <root_func> [root_func ...]")
        sys.exit(1)

    build_dir = filtered[0]
    roots = filtered[1:]

    usage = parse_su_files(build_dir)
    graph = parse_call_graph(build_dir)

    # Inject synthetic edges for calls made through function pointers.
    for edge in indirect_edges:
        parts = edge.split(":", 1)
        if len(parts) != 2:
            print(f"Invalid --indirect-edge format (expected caller:callee): {edge}", file=sys.stderr)
            sys.exit(1)
        caller, callee = parts
        graph[caller].add(callee)

    if not usage:
        print("No .su files found.  Rebuild with -fstack-usage first.")
        sys.exit(1)

    ordinals = ["worst", "2nd", "3rd"] + [f"{n}th" for n in range(4, 20)]
    col_w = max(len(r) for r in roots)
    for root in roots:
        results = top_n_cases(root, usage, graph, max_recursion, top)

        for rank, (total, path) in enumerate(results):
            qualifiers = {usage[f][1] for f, _ in path if f in usage}
            note = ""
            if any("dynamic" in q for q in qualifiers):
                note = "  [!] dynamic frame in path – size is a lower bound"

            rank_label = f"  [{ordinals[rank]}]" if top > 1 else ""
            print(f"  {root:<{col_w}}  {total:>6} bytes{rank_label}{note}")
            if verbose:
                for fname, sz in path:
                    q = usage.get(fname, (0, "?", None))[1]
                    loc = usage.get(fname, (0, "?", None))[2]
                    loc_str = f"  [{loc}]" if loc else ""
                    print(f"      {fname}  +{sz}  ({q}){loc_str}")
                if rank < len(results) - 1:
                    print()


if __name__ == "__main__":
    main()
