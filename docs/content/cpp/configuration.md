# Configuration options of the C++ generator

The C++ generator is configured at two levels. The options of `--hikaripb_out` determine what `protoc` generates; the
macros in `<prefix>_config.h` determine how the generated code behaves and which resources it uses at run time. The
syntax of the options, on the command line and in a configuration file, is described in
[Generator options](../options.md). [Encoding and decoding](../how-it-works.md) explains how the encoder and the
decoder work, which is the basis for most of the settings.

## Generator options

`type=cpp` selects this generator, and `config_file` names a [configuration file](../options.md#configuration-file).
The generator also reads the following options:

| Option | Default | Description |
|--------|---------|-------------|
| `prefix` | `hikaripb` | Names the runtime: the namespace (`hikaripb::Encoder`), the macros (`HIKARIPB_*`) and the runtime files (`<prefix>_defines.h`, ...). The headers of the `.proto` files are not prefixed. |
| `single_file` | *(off)* | Generates `<name>.pb.h` for all `.proto` files, with one namespace block per `.proto` file, instead of one `<basename>.pb.h` per file. See [single_file](../options.md#single_file). |
| `ignore` | *(none)* | Messages and enums to exclude. For a message, the struct, its functions and its entry in the bindings are omitted; for an enum, the enum itself. See [ignore](../options.md#ignore). |
| `namespace_override` | *(none)* | Replaces the leading part of the namespaces of the messages: with `acme`, `namespace esb::gpio` becomes `namespace acme::gpio`. See [namespace_override](../options.md#namespace_override). |
| `include_path` | *(empty)* | Prefix of the `#include` paths of the generated headers (`<prefix>_encode.h`, `<prefix>_decode.h`, `<prefix>_bindings.h`, the per-file `.pb.h`, `<prefix>_config_default.h`). |
| `config_path` | value of `include_path` | Prefix of the path in `#include "<prefix>_config.h"`. |
| `doc_parent_group` | *(empty)* | Doxygen group to which the group of the generated runtime belongs (`@ingroup`). |
| `doc_group_id` | `hikaripb` | ID of the Doxygen group of the generated runtime. |
| `doc_group_title` | value of `doc_group_id` | Title of that group. |
| `doc_protocol_parent_group` | value of `doc_parent_group` | Doxygen group to which the groups of the `.proto` files belong. |
| `doc_protocol_group_id` | `hikaripb_protocol` | ID of the Doxygen group that contains the groups of the `.proto` files. |
| `doc_protocol_group_title` | `Protocol` | Title of that group. |
| `doc_protocol_root_header` | *(empty)* | The generated header that opens the top-level group of the protocol. If empty, the header of the first `.proto` file in name order opens it. Ignored with `single_file`, where the merged header opens the group. |

The `doc_*` options only set the names of the Doxygen groups in the comments of the generated code and have no other
effect.

## Library configuration

`<prefix>_config.h` is written by the user and placed on the include path, see
[Write `<prefix>_config.h`](overview.md#write-prefix_configh). Because it is included first, a macro defined there
overrides the default in the generated `<prefix>_config_default.h`, which lists every setting. The names below use the
default prefix `hikaripb`; with another prefix, they begin accordingly, for example with `WEATHER_CPP_`.

### Required definitions

| Definition | Description |
|------------|-------------|
| `<package>_<Message>_<field>_size` for every string and `bytes` field without a callback | The maximum number of bytes the field can hold. The struct uses no dynamic memory, so choose the largest value to be accepted; the decoder reports an overflow for longer values. A missing definition is a compile error. |
| `<package>_<Message>_<field>_count` for every repeated field without a callback | The maximum number of elements the field can hold. A repeated string or bytes field also requires the size of each element. |
| The classes `<prefix>::InputStream` and `<prefix>::OutputStream` | The transfer of the bytes over a memory buffer, a queue or any other transport. The runtime only forward-declares these classes. |

### Messages and fields

| Setting | Default | Description |
|---------|---------|-------------|
| `<package>_<Message>_writeonly` | `0` | Excludes the message from the decoder, which saves flash and RAM. Use it for messages that the device only sends. |
| `<package>_<Message>_<field>_callback_en` with `HIKARIPB_CALLBACK` | `0` | Passes the field to an application function instead of storing it in the struct. Use it for fields that exceed the available RAM or that the application stores itself. See [Field callbacks](callbacks.md). |

### Optional features

| Setting | Default | Description |
|---------|---------|-------------|
| `HIKARIPB_ENABLE_FLOAT` | `0` | Enables `float` fields. When disabled, a `float` field is a compile error, which prevents floating-point code from being included inadvertently on targets without floating-point support. |
| `HIKARIPB_ENABLE_REPEATED_BYTES` | `0` | Enables repeated `string` and `bytes` fields. When disabled, such a field is a compile error and the corresponding decoder code is omitted. |
| `HIKARIPB_COMPRESS_ENUMS` | `1` | Gives an `enum` the smallest of `pb_u8`, `pb_u16` and `pb_u32` that holds the largest value that the `.proto` file declares for it as its underlying type. A value that is wider than that type, which a newer sender may use, is cut to its low bits. With `0`, the underlying type of every enum is `pb_u32`: the structs are larger, and the decoder stores every value of 32 bits as it was sent. |
| `HIKARIPB_CALLBACK` | `0` | Enables fields that are handled by callbacks, see [Field callbacks](callbacks.md). When disabled, the callback code is not compiled. |

### Limits

| Setting | Default | Description |
|---------|---------|-------------|
| `HIKARIPB_DEC_MAX_DEPTH` | `8U` | The maximum nesting depth accepted by the decoder, 1 to 255; the top-level message counts as one level. The decoder does not call itself: it keeps one small frame per level in the `Decoder` object, so a lower value reduces the size of the object, and the stack use of a decode is constant, whatever the nesting. Deeper input is a decode error. |
| `HIKARIPB_ENC_PAD_LENGTH` | `2U` | The number of bytes reserved for each length, 1 to 5. Use `3` for embedded fields longer than 16383 bytes (the decoder accepts up to 65535), or `1` if all embedded fields are shorter than 128 bytes, which saves one byte per field. A longer field cannot be written: size this setting for the longest field; `HIKARIPB_ASSERT` checks the length when a field is closed. |

### Error handling of the decoder

By default, the decoder skips unknown fields and stops at the first error. The following settings change this
behavior:

| Setting | Default | Description |
|---------|---------|-------------|
| `HIKARIPB_ERROR_ON_UNKNOWN_TAG` | `0` | Treats an unknown field as an error. Use it when sender and receiver share exactly the same schema, so that an unknown field indicates a fault, or to validate input from an untrusted source. |
| `HIKARIPB_CONTINUE_ON_UNKNOWN_TAG_ERROR` | `0` | Reports an unknown field without stopping the decoding. Requires `HIKARIPB_ERROR_ON_UNKNOWN_TAG`. |
| `HIKARIPB_CONTINUE_ON_OVERFLOW` | `0` | Skips a string, bytes field or repeated field that does not fit and records the error, so that the rest of the message is still decoded. |
| `HIKARIPB_CONTINUE_ON_CALLBACK_ERROR` | `0` | The same for a callback that returns false. |
| `HIKARIPB_CONTINUE_ON_ONEOF_ERROR` | `0` | The same for a second member of a oneof, which is skipped. |

In all of these cases, the error is retained: after decoding, `hasError()` of the decoder returns true and
`getError()` identifies the error. A message that was decoded with an error can hold invalid fields, even when a
`CONTINUE_ON_...` setting let the decoder go on: do not use it.

### Debugging and printing

| Setting | Default | Description |
|---------|---------|-------------|
| `HIKARIPB_DEBUG` | `0` | Enables checks for the development of the encoding code: the proxies use `HIKARIPB_ASSERT` to verify that data is written to the currently open proxy and not to a parent or a closed proxy. Combined with `HIKARIPB_PRINT_ENABLE`, the decoder also prints the names of the field and the message. |
| `HIKARIPB_ASSERT(x)` | no-op | The assertion used by these checks. Define it as `assert(x)`, as a trap or as a logging call to make the checks effective. |
| `HIKARIPB_PRINT_ENABLE`, `HIKARIPB_PRINT(...)`, `HIKARIPB_PRINTLN(...)` | disabled | Enables the `print()` method of the messages. Both print macros must be provided, for example based on `printf` or a logging function. When disabled, `print()` compiles to nothing. |
| `HIKARIPB_CHARS_PER_LINE`, `HIKARIPB_INDENT_SIZE` | `16`, `2` | The layout of `print()`: the number of bytes per line of a bytes field and the number of spaces per indentation level. |
| `HIKARIPB_U8_F` ... `HIKARIPB_U32_F`, `HIKARIPB_S8_F` ... `HIKARIPB_S32_F`, `HIKARIPB_X8_F` ... `HIKARIPB_X32_F`, `HIKARIPB_FLOAT_F` | `"u"`, `"d"`, `"x"`, `"g"` | The `printf` conversion specifiers used by `print()`. Change them if `pb_u32` is a `long`, as on 16-bit targets (`"lu"`), or if the `printf` implementation does not support `g`. |

### Performance

| Setting | Default | Description |
|---------|---------|-------------|
| `HIKARIPB_LIKELY(x)`, `HIKARIPB_UNLIKELY(x)`, `HIKARIPB_INLINE_ATTR`, `HIKARIPB_OPTIMIZE_ATTR` | no effect | Hooks for performance tuning. Define them, for example, as `__builtin_expect`, as `__attribute__((always_inline))` or as a section attribute that places the decoder in fast RAM. `HIKARIPB_INLINE_ATTR` marks the small functions of the hot path, the steps of the decoding of one field included, so that `always_inline` turns the loop of the decoder into one function. |
| `HIKARIPB_DEC_VARINT_UNROLL` | `5` | The number of leading bytes of a varint (a field key, a length or a value) that the decoder reads by straight-line code, 0 to 5; it reads the other bytes in a loop. `5` reads all of them in straight-line code, which is the fastest and the largest. `1` unrolls only the first byte, which holds every key and every value below 128, and loops for the rest. `0` has no straight-line code, which is the smallest. Every level decodes the same bytes to the same result. Up to two of the unrolled bytes (every key and every value below 16384) are read at each place where the decoder reads a varint, the others by one function that all of these places call, so the levels above 2 add little code. |

### Standard types and features

The runtime does not depend on the C or C++ library and compiles with `-nostdinc -nostdinc++ -ffreestanding
-fno-exceptions -fno-rtti`. The few definitions it requires are provided as macros in `<prefix>_types.h`, and
`<prefix>_config.h` can define any of them beforehand, in the same way as the settings:

| Macro | Default | Description |
|-------|---------|-------------|
| `pb_s8`, `pb_s16`, `pb_s32`, `pb_s64`, `pb_u8`, `pb_u16`, `pb_u32`, `pb_u64`, `pb_size` | the predefined type of the compiler (`__INT8_TYPE__` ... `__SIZE_TYPE__` on GCC and Clang), otherwise the corresponding standard type (`signed char`, `short`, `int`, ...) | The integer types of the runtime and of the generated structs. |
| `pb_tag` | the smallest of `pb_u8`, `pb_u16` and `pb_u32` that holds the largest field number of the schema | The type of a field number, chosen by the generator. Define it only to force a wider type; it must hold the largest field number. |
| `pb_msgid` | the smallest of `pb_u8`, `pb_u16` and `pb_u32` that holds the identifier of every message of the schema, which is the number of messages less one | The type of a message identifier, chosen by the generator. Define it only to force a wider type; it must hold the identifier of every message. |
| `PB_OFFSETOF(type, member)` | `__builtin_offsetof` where the compiler supports it | `offsetof`. |

Define these macros if the platform provides its own types, or to use the types of the C library: include the
corresponding header in `<prefix>_config.h` and define the macros, for example `#define pb_u32 uint32_t`. On GCC and
Clang, the macros denote the same types as the standard ones, so `uint32_t` and `pb_u32` can be mixed. The
configuration header is included before `<prefix>_types.h`, so the classes it declares must use built-in types such as
`unsigned char` or include `<stdint.h>` themselves. A switch that the preprocessor tests (`HIKARIPB_CALLBACK`,
`HIKARIPB_DEBUG`, ...) is defined as `0` or `1`.

### Typical configurations

- **A sensor that only sends data:** mark its messages as `writeonly`, leave `ENABLE_FLOAT` and `ENABLE_REPEATED_BYTES`
  disabled unless the schema requires them, provide a buffer in the output stream, and keep `ENC_PAD_LENGTH` at 2 or
  1.
- **A device that receives commands:** size the strings and counts for the longest command, set `DEC_MAX_DEPTH` to the
  nesting depth of the schema, and check `hasError()` after every decode. Enable `ERROR_ON_UNKNOWN_TAG` if the sender
  is not trusted.
- **A gateway that handles many streams:** use one `Encoder` or `Decoder` per stream, use callbacks for large payloads
  to avoid copying them, and enable `CONTINUE_ON_OVERFLOW` if a malformed field should not cause the rest of the
  message to be lost.
- **During development:** enable `DEBUG`, define `ASSERT` and provide the print macros.
