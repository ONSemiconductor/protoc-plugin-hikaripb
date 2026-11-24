# Tests

This folder holds the tests of the plugin and of the code that it generates: the behaviour of the C, C++ and Python
output, their agreement on the wire, the documentation generator, the options, and the static analysis, sanitizer, stack
and coverage runs of the generated C and C++ code. `test/Makefile` drives all of them; the root `Makefile` forwards
`test`, `run`, `stack`, `coverage` and `clean` to it.

## Requirements

- Linux, or WSL on Windows (see [Windows](#windows)).
- `make`, `pkg-config`, GCC and G++ (C11, C++17) and the [Criterion](https://github.com/Snaipe/Criterion) test library
  (`libcriterion-dev`).
- `protoc` with `--experimental_allow_proto3_optional`.
- Python 3.10 or later with `protoc/requirements.txt` and `test/py/requirements.txt`. Cython and setuptools are
  optional: with them, the Python tests also run against the compiled codec.
- Optional, each skipped with a note when it is missing:
  - `sphinx` and `myst-parser` for the Sphinx builds of `test/sphinx`;
  - `clang-tidy`, and `cppcheck` with its MISRA addon (`misra.py`), for `make analyze`;
  - `lcov` for `make coverage`.

## Running

Run the commands in `test/` (or `make -C test ...` from the root):

| Command | What it does |
|---------|--------------|
| `make test` | Generates the code of `proto/`, builds and runs every suite (see [What `make test` runs](#what-make-test-runs)). |
| `make codegen` | Only generates the code, into `build/test/generated/`. |
| `make test_config`, `make test_sphinx` | One of the suites that need no generated code. |
| `make analyze` | The static analysis of the generated C and C++ code. |
| `make sanitize` | Every suite with AddressSanitizer and UndefinedBehaviorSanitizer, in `build/test_sanitize/`. |
| `make stack` | The worst-case stack use of the C runtime. |
| `make coverage` | A coverage report of the suites, see [Coverage](#coverage). |
| `make clean` | Removes `build/test/`. |

Run `make clean` after a change of a template: the object files do not depend on the generated headers, so a stale
object can survive a rebuild.

The variables `PROTOC`, `CC`, `CXX` and `PYTHON` select the tools, `PLUGIN` the plugin (default:
`protoc/hikaripb.py`), `CYTHON_PYTHON` and `SPHINX_PYTHON` the interpreters of the compiled codec and of the Sphinx
builds, for example `make test PLUGIN=$HOME/hikari-plugin.sh`.

### Windows

The plugin is a Python script, which `protoc` cannot start on native Windows: run the tests in WSL.

```sh
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/c/<path of the repository>/test && make test"
```

With `git config core.autocrlf true`, the files are checked out with CRLF line endings: the shebang of
`protoc/hikaripb.py` becomes `python3\r`, and `sh` fails on the scripts of `tools/`. Check the repository out with
`core.autocrlf input`, or start the plugin through a wrapper with LF line endings and convert the scripts:

```sh
printf '#!/bin/sh\nexec python3 /mnt/c/<path of the repository>/protoc/hikaripb.py "$@"\n' > ~/hikari-plugin.sh
chmod +x ~/hikari-plugin.sh
sed -i 's/\r$//' tools/*.sh
make test PLUGIN=$HOME/hikari-plugin.sh
```

## Layout

| Folder | Contents |
|--------|----------|
| `proto/` | The schemas that the C, C++ and Python tests share: scalars, repeated fields, oneofs, nested types, deep nesting, callbacks, a message without fields, and a schema in a sub-folder (`shared/`). |
| `c/` | The Criterion tests of the C output (encode, decode, errors, depth, callbacks, nested types, empty messages, `single_file`), the transport functions of the tests (`test_io.c`) and their configuration `sample_config.h`. `alt/sample_config.h` switches every option on, for `make analyze`. |
| `cpp/` | The same tests for the C++ output, with `hikaripb_config.h`. `alt/` switches every option on, `defaults/` keeps the defaults of the library; both are for `make analyze`. |
| `py/` | The `unittest` tests of the Python output: API, encode, decode, errors, depth, nested types, empty messages, the generator options, and a randomised cross-check against protoc's own Python runtime (`test_wire.py`). `check_interop.py` decodes the messages of the C and C++ tests. |
| `config/` | `unittest` tests that run `protoc` on schemas of their own and build small C and C++ programs: the options and the configuration file, names and `ignore`, comments, the settings (`COMPRESS_ENUMS`, `DEC_VARINT_UNROLL` and the performance hooks, `ENABLE_FLOAT`, `ENABLE_REPEATED_BYTES`, the standard types), field numbers above 255, message identifiers, the struct layout, `bool`, `fixed32` and `float` values, `print()` and the debug output of the decoders (`DEBUG` with `PRINT_ENABLE`, and the error of the C output when only one of `PRINT` and `PRINTLN` is defined). |
| `sphinx/` | The tests of the documentation generator: comment conversion, pages, navigation and Sphinx builds, with schemas and Markdown pages of their own. |
| `tools/` | The scripts of the Makefile: `suite_run.sh` (runs Criterion binaries, prints a summary), `static_analysis.sh` with `clang_tidy_checks_c.txt`, `clang_tidy_checks_cpp.txt` and the folder `misra/` (`misra_deviations.txt` and `misra_deviations.sh`), `stack_build.sh`, `stack_run.sh` and `stack_usage.py`, and `suite_coverage.sh`. |

The generated code, the objects and the binaries go to `build/test/` of the repository root.

## What `make test` runs

1. The C, C++ and Python generators run on `proto/`, once with an output per `.proto` file and once with
   `single_file=all`; protoc's `--python_out` output is generated as the reference implementation of the wire format.
2. **Interoperability.** The C and C++ encoders write the test messages into `build/test/interop/`, `check_interop.py`
   decodes them with the Python output and encodes them again, and the C and C++ decoders read the Python messages.
3. The C and C++ suites of errors (malformed input), depth, callbacks, nested types, empty messages and `single_file`.
4. The Python suite, against the pure Python codec and, when Cython is installed, against the compiled one.
5. The `config` and `sphinx` suites.

A Criterion suite prints `=== Suite Summary: Tested: ... | Failing: 0 | Crashing: 0 ...`, a Python suite
`Ran ... tests ... OK`. The first failing suite stops the run.

## Static analysis

`make analyze` checks every generated source of the C and C++ output with each configuration: `c/` and `c/alt/` for C,
`cpp/`, `cpp/alt/` and `cpp/defaults/` for C++.

1. GCC with strict warnings as errors; the flags are in `tools/static_analysis.sh`.
2. clang-tidy with the checks of `tools/clang_tidy_checks_c.txt` or `tools/clang_tidy_checks_cpp.txt`, as errors.
3. C only: the MISRA C:2012 addon of cppcheck, with `c/alt/` (which defines `PB_OFFSETOF` as `offsetof`). Each
   finding (file and rule) must match a line of `tools/misra/misra_deviations.txt`, which gives the rule and a file
   pattern; any other finding fails the run. A new deviation needs a line there and an entry in
   `docs/content/c/misra.md`.

`CLANG_TIDY`, `CPPCHECK` and `CPPCHECK_ADDONS` (the folder of `misra.py`) select the tools, `ANALYSIS_DIR` the folder of
the reports (default `/tmp/hikaripb_analysis`, with the MISRA findings in `misra.txt` and `misra_findings.txt`):

```sh
make analyze CPPCHECK=/usr/bin/cppcheck CPPCHECK_ADDONS=/usr/lib/x86_64-linux-gnu/cppcheck/addons
```

## Sanitizers and stack

`make sanitize` builds every suite with `-fsanitize=address,undefined -fno-sanitize-recover=undefined` in
`build/test_sanitize/` and runs it; any finding aborts the test.

`make stack` compiles the C runtime with `-O1 -fno-inline -fstack-usage` and reports the worst-case stack use of
`sample_decode` and `sample_encode_varint_u32` from the static call graph (`tools/stack_usage.py`).

## Coverage

`make coverage` rebuilds the suites with gcov, runs them and writes an HTML report with lcov to
`build/test/coverage/html/index.html`. The report excludes `*/generated/*`, so it covers the test programs only. For the
generated runtime and messages, run the instrumented suites and filter the generated folder, for example with gcovr:

```sh
make clean && make coverage=1 run
gcovr -r .. --object-directory ../build/test --filter '.*/build/test/generated/(c|cpp)/' --html-details coverage.html
```

The programs of the `config` suite are built without instrumentation, so the paths that only they exercise (the
`DEC_VARINT_UNROLL` levels, the settings) are not counted. The coverage of the plugin itself is measured with
coverage.py, through a `PLUGIN` wrapper that runs `python -m coverage run --parallel-mode protoc/hikaripb.py "$@"`.

## Adding a test

- A behaviour of the generated C or C++ code with the shared schemas: a Criterion test in `c/` and its mirror in
  `cpp/`, and in `py/` if the Python output has it too.
- A behaviour that needs a schema or a setting of its own: a test in `config/`; `test_enums.py` is a short example,
  with the helpers of `test_tags.py` (the transport, a hex decoder, the wire format).
- A new option of the plugin: a test in `config/test_config.py`. A test checks that every option is in
  `docs/content/options.md` or in the configuration page of its generator.
- The documentation generator: a test in `sphinx/`.
