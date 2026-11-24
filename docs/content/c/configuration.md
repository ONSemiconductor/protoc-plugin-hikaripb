# Configuration options of the C generator

The C generator is configured at two levels. The options of `--hikaripb_out` determine what `protoc` generates; the
macros in `<prefix>_config.h` determine how the generated code behaves and which resources it uses at run time. The
syntax of the options, on the command line and in a configuration file, is described in
[Generator options](../options.md). [Encoding and decoding](../how-it-works.md) explains how the encoder and the
decoder work, which is the basis for most of the settings.

## Generator options

`type=c` selects this generator, and `config_file` names a [configuration file](../options.md#configuration-file). The
generator also reads the following options:

| Option | Default | Description |
|--------|---------|-------------|
| `prefix` | `hikaripb` | Prefix of every symbol, macro and file of the runtime (`<prefix>_defines.h`, `<prefix>_read`, `<PREFIX>_ASSERT`, ...) and of the files generated for the `.proto` files. |
| `single_file` | *(off)* | Generates `<prefix>_<name>.pb.h` and `.pb.c` for all `.proto` files instead of one `<prefix>_<basename>.pb.h` and `.pb.c` pair per file. See [single_file](../options.md#single_file). |
| `ignore` | *(none)* | Messages and enums to exclude. For a message, the struct, its functions and its entry in the bindings are omitted; for an enum, the enum itself. See [ignore](../options.md#ignore). |
| `namespace_override` | *(none)* | Replaces the leading part of the package names in the symbol names: with `acme`, `esb_gpio_fldConfig` becomes `acme_gpio_fldConfig`. See [namespace_override](../options.md#namespace_override). |
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
default prefix `hikaripb`; with another prefix, they begin accordingly, for example with `WEATHER_C_`.

### Required definitions

| Definition | Description |
|------------|-------------|
| `<package>_<Message>_<field>_size` for every string and `bytes` field without a callback | The maximum number of bytes the field can hold. The struct uses no dynamic memory, so choose the largest value to be accepted; the decoder reports an overflow for longer values. A missing definition is a compile error. |
| `<package>_<Message>_<field>_count` for every repeated field without a callback | The maximum number of elements the field can hold. A repeated string or bytes field also requires the size of each element. |
| The functions `<prefix>_read`, `_skip`, `_pop`, `_getReadOffset`, `_write`, `_setWriteOffset` and `_getWriteOffset` | The transfer of the bytes over a memory buffer, a queue or any other transport, see [Provide the transport](overview.md#provide-the-transport). |

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
| `HIKARIPB_COMPRESS_ENUMS` | `1` | Stores an enum field in the smallest of `pb_u8`, `pb_u16` and `pb_u32` that holds the largest value that the `.proto` file declares for the enum. A value that is wider than that type, which a newer sender may use, is cut to its low bits. With `0`, every enum is a `pb_u32`: the structs are larger, and the decoder stores every value of 32 bits as it was sent. The type of an enum is `<enum>_t`. |
| `HIKARIPB_CALLBACK` | `0` | Enables fields that are handled by callbacks, see [Field callbacks](callbacks.md). When disabled, the callback code is not compiled. |
| `HIKARIPB_ENABLE_MULTI_ENC`, `HIKARIPB_ENABLE_MULTI_DEC` | `0` | Enables several streams to be encoded or decoded concurrently, for example from several threads, connections or interrupts. The functions then take a context pointer, which is passed on to the transport functions. When disabled, a single global context is used. |

### Limits

| Setting | Default | Description |
|---------|---------|-------------|
| `HIKARIPB_DEC_MAX_DEPTH` | `8U` | The maximum nesting depth accepted by the decoder, 1 to 255; the top-level message counts as one level. The decoder does not call itself: it keeps one small frame per level in its state, so a lower value reduces memory usage, and the stack use of a decode is constant, whatever the nesting. Deeper input is a decode error. |
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

In all of these cases, the error is retained: after decoding, `<prefix>_hasError()` returns true and
`<prefix>_getError()` identifies the error. A message that was decoded with an error can hold invalid fields, even when
a `CONTINUE_ON_...` setting let the decoder go on: do not use it.

### Debugging and printing

| Setting | Default | Description |
|---------|---------|-------------|
| `HIKARIPB_DEBUG` | `0` | Enables checks for the development of the encoding code: the write handles use `HIKARIPB_ASSERT` to verify that data is written to the currently open handle and not to a parent or a closed handle. Combined with `HIKARIPB_PRINT_ENABLE`, the decoder also prints the names of the field and the message. |
| `HIKARIPB_ASSERT(x)` | no-op | The assertion used by these checks. Define it as `assert(x)`, as a trap or as a logging call to make the checks effective. |
| `HIKARIPB_PRINT_ENABLE`, `HIKARIPB_PRINT(...)`, `HIKARIPB_PRINTLN(...)` | disabled | Enables the `<message>_print()` functions. Both print macros must be provided, for example based on `printf` or a logging function. Defining only one of them is a compile error. When disabled, `print()` compiles to nothing. |
| `HIKARIPB_CHARS_PER_LINE`, `HIKARIPB_INDENT_SIZE` | `16`, `2` | The layout of `print()`: the number of bytes per line of a bytes field and the number of spaces per indentation level. |
| `HIKARIPB_U8_F` ... `HIKARIPB_U32_F`, `HIKARIPB_S8_F` ... `HIKARIPB_S32_F`, `HIKARIPB_X8_F` ... `HIKARIPB_X32_F`, `HIKARIPB_FLOAT_F` | `"u"`, `"d"`, `"x"`, `"g"` | The `printf` conversion specifiers used by `print()`. Change them if `pb_u32` is a `long`, as on 16-bit targets (`"lu"`), or if the `printf` implementation does not support `g`. |

### Performance

| Setting | Default | Description |
|---------|---------|-------------|
| `HIKARIPB_LIKELY(x)`, `HIKARIPB_UNLIKELY(x)`, `HIKARIPB_INLINE_ATTR`, `HIKARIPB_OPTIMIZE_ATTR` | no effect | Hooks for performance tuning. Define them, for example, as `__builtin_expect`, as `__attribute__((always_inline))` or as a section attribute that places the decoder in fast RAM. `HIKARIPB_INLINE_ATTR` marks the small functions of the hot path of the decoder, the steps of the decoding of one field included, so that `always_inline` turns its loop into one function. |
| `HIKARIPB_DEC_VARINT_UNROLL` | `5` | The number of leading bytes of a varint (a field key, a length or a value) that the decoder reads by straight-line code, 0 to 5; it reads the other bytes in a loop. `5` reads all of them in straight-line code, which is the fastest and the largest. `1` unrolls only the first byte, which holds every key and every value below 128, and loops for the rest. `0` has no straight-line code, which is the smallest. Every level decodes the same bytes to the same result. Up to two of the unrolled bytes (every key and every value below 16384) are read at each place where the decoder reads a varint, the others by one function that all of these places call, so the levels above 2 add little code. |

The decoder reads every byte with `<prefix>_pop()`, which the application defines in another source file: build with
link-time optimization (`-flto`), so that the compiler can inline it. On a Cortex-M4 this saves about 30 % of the
instructions of a decode.

### Standard types and features

The runtime does not depend on the C library and compiles with `-nostdinc -ffreestanding`. The few definitions it
requires are provided as macros in `<prefix>_types.h`, and `<prefix>_config.h` can define any of them beforehand, in
the same way as the settings:

| Macro | Default | Description |
|-------|---------|-------------|
| `pb_s8`, `pb_s16`, `pb_s32`, `pb_s64`, `pb_u8`, `pb_u16`, `pb_u32`, `pb_u64`, `pb_size` | the predefined type of the compiler (`__INT8_TYPE__` ... `__SIZE_TYPE__` on GCC and Clang), otherwise the corresponding standard type (`signed char`, `short`, `int`, ...) | The integer types of the runtime. |
| `pb_bool` | `unsigned char` | The boolean type. |
| `PB_TRUE`, `PB_FALSE` | `((pb_bool)1U)`, `((pb_bool)0U)` | The values of a `pb_bool`. The runtime always compares with these macros and never defines `true` or `false`, which belong to `<stdbool.h>`. |
| `pb_tag` | the smallest of `pb_u8`, `pb_u16` and `pb_u32` that holds the largest field number of the schema | The type of a field number, chosen by the generator. Define it only to force a wider type; it must hold the largest field number. |
| `pb_msgid` | the smallest of `pb_u8`, `pb_u16` and `pb_u32` that holds the identifier of every message of the schema, which is the number of messages less one | The type of a message identifier, chosen by the generator. Define it only to force a wider type; it must hold the identifier of every message. |
| `PB_NULL`, `PB_OFFSETOF(type, member)` | `((void*)0)`, `__builtin_offsetof` where the compiler supports it | The null pointer and `offsetof`. |

Define these macros if the platform provides its own types, for example in the `Platform_Types.h` of AUTOSAR, or to
use the types and macros of the C library. Include the corresponding header in `<prefix>_config.h` and define the
macros:

```c
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define pb_s8   int8_t
#define pb_s16  int16_t
#define pb_s32  int32_t
#define pb_s64  int64_t
#define pb_u8   uint8_t
#define pb_u16  uint16_t
#define pb_u32  uint32_t
#define pb_u64  uint64_t
#define pb_size size_t
#define pb_bool bool
#define PB_NULL NULL
#define PB_OFFSETOF(type, member) offsetof(type, member)
```

A `pb_bool` that is defined as `bool` works with `PB_TRUE` and `PB_FALSE` left as they are. The transport functions and
`HIKARIPB_PRINT` are provided by the application, which must also include the headers they require: a configuration
that uses `printf` must include `<stdio.h>`. A switch that the preprocessor tests (`HIKARIPB_CALLBACK`, `HIKARIPB_DEBUG`,
...) is defined as `0` or `1`, not as `true` or `false`: in C, the preprocessor evaluates an undefined `true` as `0`.

### Typical configurations

- **A sensor that only sends data:** mark its messages as `writeonly`, leave `ENABLE_FLOAT` and `ENABLE_REPEATED_BYTES`
  disabled unless the schema requires them, provide a buffer in the transport, and keep `ENC_PAD_LENGTH` at 2 or 1.
- **A device that receives commands:** size the strings and counts for the longest command, set `DEC_MAX_DEPTH` to the
  nesting depth of the schema, and check `<prefix>_hasError()` after every decode. Enable `ERROR_ON_UNKNOWN_TAG` if
  the sender is not trusted.
- **A gateway that handles many streams:** enable `ENABLE_MULTI_DEC`, use callbacks for large payloads to avoid copying
  them, and enable `CONTINUE_ON_OVERFLOW` if a malformed field should not cause the rest of the message to be lost.
- **During development:** enable `DEBUG`, define `ASSERT` and provide the print macros.
