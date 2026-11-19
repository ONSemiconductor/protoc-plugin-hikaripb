# Using the Python generator

`type=py` generates a self-contained Python codec: one module per `.proto` file, with a class for every message and
enum, based on a runtime module that implements the protobuf wire format in pure Python. The generated code requires
only the Python standard library; the `protobuf` package is not used at run time.

## Generate

```sh
mkdir -p out
protoc --experimental_allow_proto3_optional \
    --plugin=protoc-gen-hikaripb=protoc/hikaripb.py \
    --proto_path=examples/proto \
    --hikaripb_out=type=py,prefix=weather_py:out \
    examples/proto/weather.proto
```

`prefix` names the runtime files; the default is `hikaripb`. The remaining options are described in
[Configuration options](configuration.md#generator-options).

| Generated file | Content |
|----------------|---------|
| `<path/basename>_pb.py` | One module per `.proto` file, following its directory layout (`weather.proto` becomes `weather_pb.py`; `a/b.proto` becomes `a/b_pb.py`, imported as `a.b_pb`). Every message, including nested messages, and every enum is a module-level class. |
| `<prefix>_codec.py` | The runtime shared by all modules: the wire codec, the `Message` base class, `MessageList`, `EncodeError`, `DecodeError` and `DecodeErrorCode`. |
| `<prefix>_codec.pxd`, `<prefix>_build_ext.py` | Optional: files for compiling the codec with Cython, see below. |

The modules import the runtime as `import <prefix>_codec`, so the output directory (or the package root of the
subdirectories) must be on `sys.path`.

## Use the messages

```python
from weather_pb import Reading, Report, Unit
from weather_py_codec import DecodeError

report = Report(
    station="roof-1",
    readings=[Reading(sensor_id=1, temperature=215, unit=Unit.UNIT_CELSIUS, humidity=48, label="roof")],
)
report.readings.add(sensor_id=2, temperature=-35, label="shed")   # creates and appends an element
report.note = "calibrated"                                        # a oneof: replaces the other member

data = report.serialize()                                         # bytes

try:
    decoded = Report().deserialize(data)                          # fills and returns the message
except DecodeError as error:
    print(error.code.name, error)

if decoded.readings[0].has_humidity():
    print(decoded.readings[0].humidity)
decoded.print()
```

- **Constructors** accept every field as an optional keyword argument. Enums are `IntEnum` classes. A field whose name
  is a Python keyword or collides with `serialize`, `deserialize`, `init`, `clear` or `print` receives a trailing `_`.
- **Presence.** `optional`, `oneof`, `bytes`, `string` and message fields provide `has_<field>()`. Presence is set by
  assigning a value and cleared by assigning `None`. Plain proto3 scalars read back as their default value and are not
  serialized while they hold it. Assigning one member of a `oneof` clears the other members; unset members read as
  `None`.
- **Repeated fields** are lists. A repeated message field is a type-checked list whose `add(...)` method accepts the
  fields of the element as documented keyword arguments. Repeated scalars are serialized in packed form.
- **`serialize()`** encodes the complete message in a single pass. If a value has the wrong type or is out of range, it
  raises `EncodeError` (a subclass of `ValueError`) that names the field.
- **`deserialize(data, max_depth=100, strict=False)`** replaces the content of the message and returns the message.
  `data` may be `bytes`, `bytearray` or `memoryview`. Malformed input raises `DecodeError`, whose `.code` attribute is
  a `DecodeErrorCode`. Unknown fields are skipped unless `strict=True` is passed, in which case unknown field numbers,
  wire types that do not match the field and multiple set members of a oneof raise an error.
- **Utilities.** Every message supports `clear()`, `init(**fields)`, `==` (which compares the serialized form),
  `repr()`, copying and pickling. `print()` and `str()` produce the same layout as the `print()` functions of the C and
  C++ generators.
- **Docstrings.** The comments of the `.proto` file become the docstrings of the classes, enum values and fields, so
  editors display them on hover. No `.pyi` stub files are generated, because the modules themselves carry type
  annotations.
- **Configuration.** Python messages are dynamically sized, so there is no counterpart to the `<prefix>_config.h` of C
  and C++. The available settings (`strict`, `max_depth`, the Cython build) are described in
  [Configuration options](configuration.md#library-configuration); the operation of the codec is described in
  [Encoding and decoding](../how-it-works.md#python).

The complete program is `examples/py/main.py`.

## Compile the codec with Cython (optional)

```sh
pip install cython setuptools
python weather_py_build_ext.py        # located next to weather_py_codec.py; requires a C compiler
```

This command builds `<prefix>_codec` as a C extension in the same directory. Python prefers an extension module over a
`.py` file of the same name, so every generated module uses the extension from the next import onwards;
`<prefix>_codec.COMPILED` indicates which variant is loaded. The extension is built from the same `<prefix>_codec.py`,
so its behavior is identical, while encoding and decoding are several times faster. If Cython or a C compiler is not
available, the script reports this and the pure Python module remains in use. A compiled `.so` or `.pyd` file must only
be deployed to systems with the same Python version and platform.

## Limitations

- The supported field types are `uint32`, `sint32`, `fixed32`, `sfixed32`, `float`, `bool`, enums, `string`, `bytes`
  and messages; integers are therefore limited to 32 bits. Any other type (`int32`, `int64`, `uint64`, `double`, ...)
  causes the generator to stop with an error, and `deserialize` rejects values wider than 32 bits.
- A `map<K, V>` field is represented as a repeated message of key/value entries, as on the wire, without lookup by key.
  `google.protobuf.Any` is an ordinary message with a `type_url` string field and a `value` bytes field.
- Every message and enum is a module-level class, so their names must be unique within a module. The generator
  verifies this, which is relevant when `single_file` is used.
- If several members of a `oneof` are present on the wire, the last one takes effect, unless `strict=True` is passed
  to `deserialize`.
