# Using the C generator

`type=c` generates a compact C encoder and decoder runtime and, for each `.proto` file, a header and a source file
containing its structs, enums and functions. The generated code performs no dynamic memory allocation, does no I/O of
its own and includes no header of the C library. The application defines the size of every string and repeated field
in a configuration header and provides the functions that read from and write to the transport.

## Generate

```sh
mkdir -p out
protoc --experimental_allow_proto3_optional \
    --plugin=protoc-gen-hikaripb=protoc/hikaripb.py \
    --proto_path=examples/proto \
    --hikaripb_out=type=c,prefix=weather_c:out \
    examples/proto/weather.proto
```

`prefix` is the prefix of every symbol and macro of the runtime (`weather_c_defines.h`, `WEATHER_C_PRINT`, ...); the
default is `hikaripb`. Messages are named after the package of their `.proto` file: `weather.Report` becomes
`weather_Report`. The remaining options are described in [Configuration options](configuration.md#generator-options).

| Generated file | Content |
|----------------|---------|
| `<prefix>_defines.{h,c}`, `<prefix>_encode.{h,c}`, `<prefix>_decode.{h,c}` | The runtime shared by all messages, generated once. |
| `<prefix>_<proto basename>.pb.{h,c}` | One pair per `.proto` file, containing the structs, enums and functions of its messages. |
| `<prefix>_bindings.{h,c}` | The table that maps a message ID to the descriptor of the message. |
| `<prefix>_types.h` | The standard types and features as macros: `pb_u8`, `pb_u32`, `pb_bool`, ..., `PB_NULL` and `PB_OFFSETOF`. |
| `<prefix>_config_default.h` | The default value of every setting, included after the user's `<prefix>_config.h`. A comment lists the definitions that the configuration must provide for each message. |

## Write `<prefix>_config.h`

The generated headers include `<prefix>_config.h`, followed by the generated `<prefix>_config_default.h`. The
configuration header is written by hand and placed on the include path (`config_path` adds a directory prefix to the
`#include`). Because it is included first, its definitions take precedence over every default. The structs use no
dynamic memory, so the configuration must define a size for every string and `bytes` field and a count for every
repeated field; the comment at the end of `<prefix>_config_default.h` lists the required definitions:

```c
#ifndef WEATHER_C_CONFIG_H
#define WEATHER_C_CONFIG_H

#include <stdio.h>

/* Message printing: both macros must be defined. */
#define WEATHER_C_PRINT_ENABLE 1
#define WEATHER_C_PRINT(...)   printf(__VA_ARGS__)
#define WEATHER_C_PRINTLN(...) do { printf(__VA_ARGS__); printf("\n"); } while (0)

/* <package>_<Message>_<field>_size for strings and bytes, ..._count for repeated fields. */
#define weather_Reading_label_size    16U
#define weather_Report_station_size   16U
#define weather_Report_note_size      32U
#define weather_Report_readings_count 4U

#endif
```

All other settings have defaults in `<prefix>_config_default.h` and only need to be defined to change them, for
example `WEATHER_C_ENABLE_FLOAT` to support `float` fields or `WEATHER_C_DEC_MAX_DEPTH` to set the maximum nesting
depth accepted by the decoder. [Configuration options](configuration.md#library-configuration) describes every setting
and when to use it.

Instead of storing a field in the struct, the decoder can pass it to an application function, for example to process
a large field in chunks, see [Field callbacks](callbacks.md).

## Provide the transport

The runtime calls the following functions, declared in `<prefix>_defines.h`, to transfer the bytes:

| Encoding | Decoding |
|----------|----------|
| `void <prefix>_write(const pb_u8* data, pb_u16 len)` | `pb_bool <prefix>_read(pb_u8* data, pb_u16 len)` |
| `void <prefix>_setWriteOffset(pb_u32 offset)` | `pb_bool <prefix>_skip(pb_u16 len)` |
| `pb_u32 <prefix>_getWriteOffset(void)` | `pb_bool <prefix>_pop(pb_u8* data)` (one byte) |
| | `pb_u32 <prefix>_getReadOffset(void)` |

The encoder writes a message while it is being built: it reserves space for the length of an embedded message and
fills in the length afterwards using `setWriteOffset`. A scalar field, its key and its value, is one call of `write`.
`examples/c/main.c` implements all of these functions on a single memory buffer. [Encoding and decoding](../how-it-works.md)
describes this mechanism and its implications for the transport.

## Encode and decode

```c
#include "weather_c_weather.pb.h"   /* <prefix>_<proto file>.pb.h */

/* Encode */
weather_Report_WrHandle report = weather_Report_create();

weather_Report_station_WrHandle station = weather_Report_add_station(&report);
weather_Report_station_addBytes(&station, (const pb_u8*)"roof-1", 6U);
weather_Report_station_done(&station);

weather_Reading_WrHandle reading = weather_Report_add_readings(&report);
weather_Reading_set_sensor_id(&reading, 1U);
weather_Reading_set_temperature(&reading, 215);
weather_Reading_set_humidity(&reading, 48U);
weather_Reading_destroy_submessage(&reading);

/* Decode: the struct is filled from the transport */
weather_Report decoded;
weather_Report_clear(&decoded);
weather_Report_decode(&decoded);
if (weather_c_hasError()) {
    /* weather_c_getError() identifies the error */
}
for (pb_u32 i = 0U; i < decoded.readings.count; i++) {
    const weather_Reading* r = &decoded.readings.item[i];
    if (weather_Reading_has_humidity(r)) { /* r->humidity is set */ }
}
weather_Report_print(&decoded);   /* requires PRINT_ENABLE */
```

- A message is written through a *write handle* (`<message>_WrHandle`). `<message>_create()` starts a top-level
  message, `<message>_add_<field>(&handle)` opens an embedded message, a string or a bytes field,
  `<message>_set_<field>(&handle, value)` writes a scalar, and the corresponding `_destroy_submessage` or `_done`
  function closes an embedded field.
- A decoded message is a plain struct. Each field with presence (`optional`, `oneof`, strings, bytes, messages) has a
  `<message>_has_<field>()` function. A string or bytes field is represented as `{ length, data[] }` and a repeated
  field as `{ count, item[] }`.
- `<message>_print()` prints the content of a message.

### Macros and proxy structs

The header of each message also provides macros and structs of function pointers that write the same bytes, with
calls of the form `name->set_<field>(&name_hdl, value)`:

```c
weather_Report_WrTop(report);    /* defines report_hdl, the write handle, and report, the proxy */

weather_Report_station_Wr(station, report->add_station(&report_hdl));
station->write(&station_hdl, (const pb_u8*)"roof-1", 6U);
station->done(&station_hdl);

weather_Reading_Wr(reading, report->add_readings(&report_hdl));
reading->set_sensor_id(&reading_hdl, 1U);
reading->set_temperature(&reading_hdl, 215);
reading->set_humidity(&reading_hdl, 48U);
reading->done(&reading_hdl);
```

- `<message>_WrTop(name)` starts a top-level message (`<message>_WrTop(name, ctx)` with `<PREFIX>_ENABLE_MULTI_ENC`).
  The macro defines the write handle `name_hdl` and `name`, a pointer to a `static const struct <message>_WrProxyTop`
  in the header that holds the functions of the message: `set_<field>` for a scalar and `add_<field>` for an embedded
  message, a string, a bytes field or a repeated field.
- `<message>_Wr(name, handle)` does the same for an embedded message, using a `<message>_WrProxy`, which additionally
  provides `done`. `<message>_<field>_Wr(name, handle)` does the same for a string, bytes or repeated scalar field;
  its proxy provides `write` or `add`, and `done`.
- Because the macros declare variables, a message that is written several times must be placed in a separate block
  each time. `name_hdl` is the write handle used by the functions above, so both styles can be mixed within one
  message.

The complete program is `examples/c/main.c` with `examples/c/weather_c_config.h`. It writes the report first with the
functions and then with the macros, and verifies that both produce the same bytes.

## Build

Compile every `.c` file in the output directory together with the application code, and add the output directory to
the include path:

```sh
cc -std=c11 -Iout -I<dir of weather_c_config.h> main.c out/*.c -o weather
```

No other library needs to be compiled or linked: the runtime does not depend on the C library and compiles with
`-nostdinc -ffreestanding`. Its types (`pb_u32`, `pb_bool`, ...) are macros that the configuration can redefine, see
[Standard types and features](configuration.md#standard-types-and-features).

## Limitations

- The supported field types are `uint32`, `sint32`, `fixed32`, `sfixed32`, `float`, `bool`, enums, `string`, `bytes`
  and messages; integers are therefore limited to 32 bits. Any other type (`int32`, `int64`, `uint64`, `double`, ...)
  causes the generator to stop with an error.
- All storage is statically sized: every string, `bytes` and repeated field requires a size or count in
  `<prefix>_config.h`, unless it is passed to a [callback](callbacks.md).
- A message cannot contain itself, either directly or through other messages. Such a message can be excluded with
  `ignore`.
- A second member of a `oneof` on the wire is a decode error; it does not replace the first member.
- Each message holds one presence bit for every field number up to its largest, so large field numbers consume RAM: a
  field number of 1000 requires 126 bytes, 10000 about 1.2 KB. The descriptors address a field with a 16-bit offset,
  so a message struct must remain below 64 KB; the generator rejects field numbers above 524279, for which the bitmap
  alone would exceed this limit.
- The decoder accepts strings, `bytes` fields and embedded messages of up to 65535 bytes. The encoder accepts up to
  16383 bytes unless `HIKARIPB_ENC_PAD_LENGTH` is increased.

## Coding standards and safety

[Coding standards and safety](misra.md) describes the properties of the generated code, the assumptions of
use and the deviations from MISRA C:2012.
