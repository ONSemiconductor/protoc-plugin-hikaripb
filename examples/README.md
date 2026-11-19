# Examples

This directory contains a small schema and one usage example per generator. The three code examples build the same
`weather.Report`, encode it, decode it and print it; the printed reports are identical. The schema also serves as the
input of the documentation generator.

| Folder | Content |
|--------|---------|
| [proto/weather.proto](proto/weather.proto) | The schema, with an enum, an optional field, a repeated message, a oneof and strings. Its comments become the comments of the C/C++ headers, the docstrings of the Python modules and the text of the documentation. |
| [c](c) | `type=c`: [main.c](c/main.c), which implements the memory-based I/O functions required by the runtime and writes the report both with the functions and with the macros of the header, and [weather_c_config.h](c/weather_c_config.h) with the handwritten settings. |
| [cpp](cpp) | `type=cpp`: [main.cc](cpp/main.cc), and [weather_cpp_config.h](cpp/weather_cpp_config.h) with the settings and the two stream classes. |
| [py](py) | `type=py`: [main.py](py/main.py). |

## Prepare and run

```sh
examples/build.sh          # Linux / macOS / WSL, also: make examples
examples\build.bat         # Windows
```

The script generates the bindings into `build/examples/generated/{c,cpp,py}`, builds the C and C++ examples into
`build/examples/bin` (`CC` and `CXX` select the compilers) and generates the Sphinx sources of the schema
documentation into `build/examples/generated/sphinx`. If `sphinx-build` and `myst-parser` are installed, the script
also builds the documentation into `build/examples/docs`. It requires `protoc` and the packages listed in
[protoc/requirements.txt](../protoc/requirements.txt).

```sh
build/examples/bin/weather_c
build/examples/bin/weather_cpp
python3 examples/py/main.py          # Windows: python examples\py\main.py
```

Each generator runs with its own prefix (`weather_c`, `weather_cpp`, `weather_py`, `weather_docs`), so the runtime
files of the C and C++ output, which would otherwise have the same names, can share one include path.

The C and C++ encoders reserve two bytes for every length prefix and fill in the length afterwards, and the C and C++
examples explicitly write the default value of `unit`, which Python omits. Their messages are therefore longer (57
bytes compared with 47). Both are valid encodings of the same message.

## VS Code

[.vscode/settings.json](../.vscode/settings.json) adds the generated directories to `python.analysis.extraPaths` and
`C_Cpp.default.includePath`, so that imports and includes of the generated code resolve once the examples have been
prepared, and the comments of the schema are displayed on hover. The "Prepare examples" and "Run ... example" tasks and
the "Python: weather example" launch configuration run the examples.
