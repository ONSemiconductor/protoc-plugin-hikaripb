# Configuration options of the Python generator

The Python generator is configured at two levels. The options of `--hikaripb_out` determine what `protoc` generates;
the arguments of `deserialize()` and a few constants of the runtime module determine how the generated code behaves at
run time. The syntax of the options, on the command line and in a configuration file, is described in
[Generator options](../options.md). The operation of the codec is described in
[Encoding and decoding](../how-it-works.md#python).

## Generator options

`type=py` selects this generator, and `config_file` names a [configuration file](../options.md#configuration-file). The
generator also reads the following options:

| Option | Default | Description |
|--------|---------|-------------|
| `prefix` | `hikaripb` | Names the runtime files: `<prefix>_codec.py`, `<prefix>_codec.pxd` and `<prefix>_build_ext.py`. The modules of the `.proto` files are not prefixed. |
| `single_file` | *(off)* | Generates `<name>_pb.py` for all `.proto` files instead of one `<path/basename>_pb.py` per file. See [single_file](../options.md#single_file). |
| `ignore` | *(none)* | Messages and enums to exclude: the class of the message or enum is omitted. See [ignore](../options.md#ignore). |
| `namespace_override` | *(none)* | Replaces the leading part that the packages of all modules have in common; the packages follow the directories of the `.proto` files. For example, with `acme` and the files `weather.proto` and `server/net_core.proto`, which have no directory in common, the modules become `acme/weather_pb.py` and `acme/server/net_core_pb.py`, imported as `acme.weather_pb` and `acme.server.net_core_pb`. The runtime files remain in the output directory. See [namespace_override](../options.md#namespace_override). |

The other options of the plugin have no effect on `type=py`.

## Library configuration

The Python library requires no configuration header: there is nothing to size, and the messages are dynamically sized.
The following settings are available:

| Setting | Default | Description |
|---------|---------|-------------|
| `deserialize(data, strict=...)` | `False` | With `True`, unknown fields, wire types that do not match the field and multiple members of a oneof raise `DecodeError` instead of being skipped or resolved in favor of the last member. Use it for untrusted input or when the schema must match exactly. |
| `deserialize(data, max_depth=...)` | `100` | The maximum nesting depth. Lower it to limit the effect of hostile input, or raise it for schemas that nest more than 100 levels deep. |
| Compilation of the codec with `<prefix>_build_ext.py` | pure Python | Compiles the codec into a C extension with identical behavior that encodes and decodes several times faster, see [Compile the codec with Cython](overview.md#compile-the-codec-with-cython-optional). `<prefix>_codec.COMPILED` indicates which variant is loaded. |
| `INDENT_SIZE`, `CHARS_PER_LINE` in `<prefix>_codec` | `2`, `16` | The layout of `print()`: the number of spaces per indentation level and the number of bytes per line of a bytes field, as in the C and C++ libraries. |
