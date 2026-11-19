<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/content/img/hikaripb-logo-dark.svg">
    <img src="docs/content/img/hikaripb-logo.svg" alt="HikariPb" width="320">
  </picture>
</h1>

HikariPb is a lightweight implementation of Protocol Buffers (proto3) that generates encoders, decoders and protocol
documentation from the `.proto` files of a protocol. The generation is performed by `protoc-gen-hikaripb`, a `protoc`
plugin that is invoked through `--hikaripb_out` and provides four generators:

- **C**: a compact encoder and decoder runtime without dynamic memory allocation.
- **C++**: a self-contained native C++17 codec.
- **Python**: message classes based on a pure Python runtime, which can optionally be compiled with
  [Cython](https://cython.org).
- **Documentation**: [Sphinx](https://www.sphinx-doc.org) pages generated from the comments of the `.proto` files.

## Documentation

The documentation is published on the GitHub Pages site of this repository, and `make docs` builds it into
`build/site`. It describes the generator options and, for each generator, its usage and configuration options. The
sources are in [docs/content](docs/content).

## Quick start

Requirements: `protoc` with support for `--experimental_allow_proto3_optional`, and Python 3.10 or later.

```sh
pip install -r protoc/requirements.txt
mkdir -p out
protoc --experimental_allow_proto3_optional \
    --plugin=protoc-gen-hikaripb=protoc/hikaripb.py \
    --proto_path=examples/proto \
    --hikaripb_out=type=py,prefix=weather_py:out \
    examples/proto/weather.proto
```

`type=` selects the generator: `c`, `cpp`, `py` or `sphinxdocs`. On native Windows, use
`protoc\protoc-gen-hikaripb.bat` as the plugin. The `examples/` directory contains a usage example for each generator,
see [examples/README.md](examples/README.md).

## Repository

| Folder | Content |
| --- | --- |
| `protoc/` | The plugin and its generators. |
| `examples/` | A small `.proto` and one usage example per generator. |
| `scripts/` | Helper scripts. |
| `test/` | The tests and the checks of the generated code, see [test/README.md](test/README.md). |
| `docs/` | The documentation. |

## License

The plugin is free software under the GNU General Public License v3.0 or later ([LICENSE](LICENSE)). The templates,
the examples and everything the plugin generates are under the BSD 3-Clause license
([LICENSE-BSD-3-Clause](LICENSE-BSD-3-Clause)), so the generated code can be used in any project.
