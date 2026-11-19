# protoc

This directory contains the sources of `protoc-gen-hikaripb`, the `protoc` plugin of HikariPb. Its usage and all
options are described in the documentation in [docs/content](../docs/content), which is published on GitHub Pages
(see the main [README](../README.md)).

| Path | Content |
|------|---------|
| `hikaripb.py` | The entry point started by `protoc`. `hikaripb.py --help` lists every option. On native Windows, `protoc` starts `protoc-gen-hikaripb.bat`, which runs this script. |
| `config.py` | The options: `OPTIONS` declares each option once, and `ConfigManager` reads the parameter of `--hikaripb_out` and the file named by `config_file`. A new option requires one entry there and a row in [docs/content/options.md](../docs/content/options.md) if every generator reads it, otherwise in the `configuration.md` of each generator that reads it ([docs/content/c](../docs/content/c), ...). |
| `names.py` | `namespace_override` and `ignore`, which every generator applies. |
| `common.py` | The base classes for reading a `.proto` file, the `clang-format` integration and the shared runtime files. |
| `c/`, `cpp/`, `python/` | The code generators. Each contains a `parser.py`, `templates/` (rendered per message or enum) and `files/` (the runtime, rendered once). |
| `sphinxdocs/` | The documentation generator: `parser.py` writes the pages, and `comments.py` converts the comments. |
| `requirements.txt` | The packages required by the plugin (`protobuf`, `jinja2`). |
