# Using the C++ generator

`type=cpp` generates a self-contained C++17 codec: the `Encoder` and `Decoder` templates in the runtime namespace
(`hikaripb::` by default) and, for each `.proto` file, a header with one struct per message. Like the C generator, the
generated code performs no dynamic memory allocation, does no I/O of its own and includes no header of the C or C++
library. The C++ generator is a separate implementation and does not use the output of `type=c`.

## Generate

```sh
mkdir -p out
protoc --experimental_allow_proto3_optional \
    --plugin=protoc-gen-hikaripb=protoc/hikaripb.py \
    --proto_path=examples/proto \
    --hikaripb_out=type=cpp,prefix=weather_cpp:out \
    examples/proto/weather.proto
```

`prefix` names the runtime: the namespace `weather_cpp`, the macros `WEATHER_CPP_*` and the runtime files. The messages
keep the namespace of their `.proto` package (`weather::Report`), and the headers of the `.proto` files are not
prefixed. The remaining options are described in [Configuration options](configuration.md#generator-options).

| Generated file | Content |
|----------------|---------|
| `<prefix>_defines.h`, `<prefix>_encode.h`, `<prefix>_decode.h` | The shared runtime: wire types, `Encoder`, `Decoder`, the proxy classes for encoding and the descriptors. Generated once. |
| `<proto basename>.pb.h` | One per `.proto` file: a struct per message (with a nested `WrProxy` class for encoding) and an `enum` per enum. |
| `<prefix>_bindings.{h,cc}` | The `MessageId` enum and the table that maps a message ID to the descriptor of the message. |
| `<prefix>_types.h` | The standard types and features as macros: `pb_u8`, `pb_u32`, ... and `PB_OFFSETOF`. |
| `<prefix>_config_default.h` | The default value of every setting, included after the user's `<prefix>_config.h`. A comment lists the definitions that the configuration must provide for each message. |

## Write `<prefix>_config.h`

Every generated header includes `<prefix>_config.h`, followed by the generated `<prefix>_config_default.h`. The
configuration header is written by hand and placed on the include path (`config_path` adds a directory prefix to the
`#include`). Because it is included first, its definitions take precedence over every default. The configuration must
provide:

- The classes `<prefix>::InputStream` and `<prefix>::OutputStream`, which the runtime only forward-declares. An input
  stream provides `read`, `skip`, `pop`, `setOffset` and `getOffset`; an output stream provides `write`, `setOffset`
  and `getOffset`. Both operate on the buffer or transport of the application. A scalar field, its key and its value,
  is one call of `write`.
- A size for every string and `bytes` field, `<package>_<Message>_<field>_size`, and a count for every repeated
  field, `<package>_<Message>_<field>_count`. A missing definition is a compile error.

```cpp
#define WEATHER_CPP_PRINT_ENABLE 1
#define WEATHER_CPP_PRINT(...)   printf(__VA_ARGS__)
#define WEATHER_CPP_PRINTLN(...) do { printf(__VA_ARGS__); printf("\n"); } while (0)

#define weather_Reading_label_size    16U
#define weather_Report_station_size   16U
#define weather_Report_note_size      32U
#define weather_Report_readings_count 4U

namespace weather_cpp {
class InputStream  { /* read(uint8_t*, uint16_t), skip(uint16_t), pop(uint8_t*), setOffset(), getOffset() */ };
class OutputStream { /* write(const uint8_t*, uint16_t), setOffset(), getOffset() */ };
}  // namespace weather_cpp
```

All other settings have defaults in `<prefix>_config_default.h` and only need to be defined to change them, for
example `WEATHER_CPP_ENABLE_FLOAT` to support `float` fields, `<package>_<Message>_writeonly` for a message that is
only sent, or `..._callback_en` with `WEATHER_CPP_CALLBACK` for a field that is handled by application code (see
[Field callbacks](callbacks.md)).
[Configuration options](configuration.md#library-configuration) describes every setting and when to use it;
[Encoding and decoding](../how-it-works.md) explains how the encoder and the decoder work.

`examples/cpp/weather_cpp_config.h` is a complete, working configuration with memory-buffer streams.

## Encode and decode

```cpp
#include "weather.pb.h"   // <proto file>.pb.h, not prefixed

uint8_t buffer[256];

// Encode
weather_cpp::OutputStream os(buffer);
weather_cpp::Encoder<> enc(os);
{
    auto report = weather::Report::WrProxy<true>(enc);
    {
        auto station = report.add_station();               // a string is written as bytes
        station.write(reinterpret_cast<const uint8_t*>("roof-1"), 6U);
    }
    auto reading = report.rpt_readings();                  // an embedded message of a repeated field
    reading.set_sensor_id(1U);
    reading.set_temperature(215);
    reading.set_humidity(48U);
}                                                          // a message is closed when its proxy goes out of scope
uint32_t length = os.getOffset();

// Decode
weather_cpp::InputStream is(buffer, length);
weather_cpp::Decoder<> dec(is);
weather::Report decoded;
decoded.decode(dec);
if (dec.hasError()) {
    // dec.getError() identifies the error
}
for (uint32_t i = 0U; i < decoded.readings.count; i++) {
    const weather::Reading& r = decoded.readings.item[i];
    if (r.has_humidity()) { /* r.humidity is set */ }
}
decoded.print();   // requires PRINT_ENABLE
```

- A message is encoded through its `WrProxy` while it is being built: `set_<field>(value)` writes a scalar,
  `add_<field>()` opens a string or a bytes field, and `rpt_<field>()` opens an embedded message of a repeated field.
  An embedded message is closed when its proxy goes out of scope. A proxy can be neither copied nor moved: it is created
  where it is used, passed to a function by reference, as `examples/cpp/main.cc` does, or created in storage that you
  declare in front with placement new, from the result of the `add_<field>()` call. C++17 constructs it in place, and
  its destructor, called by you, ends the field:

  ```cpp
  alignas(Reading) unsigned char storage[sizeof(Reading)];  // Reading is weather::Reading::WrProxy<false>
  Reading* reading = ::new (static_cast<void*>(storage)) Reading(report.rpt_readings());
  reading->set_temperature(215);
  reading->~Reading();
  ```
- A decoded message is a plain struct. Each field with presence (`optional`, `oneof`, strings, bytes, messages) has a
  `has_<field>()` method. A string or bytes field is represented as `{ length, data[] }` and a repeated field as
  `{ count, item[] }`. The members are ordered by alignment, smallest first, to save padding (see
  [How it works](../how-it-works.md)).
- A `Decoder` can be neither copied nor moved: it holds the frames of the messages that it decodes and a pointer to the
  current one. Create it where it is used and pass it by reference, as the callbacks receive it.
- Fields whose names collide with a member of the struct (`clear`, `print`, `getItemDescriptor`, `getTagName`,
  `MSGID`, `WrProxy`) receive a trailing underscore.

The complete program is `examples/cpp/main.cc`.

## Build

Compile the generated `.cc` file together with the application code, and add the output directory and the directory
of the configuration header to the include path:

```sh
c++ -std=c++17 -Iout -I<dir of weather_cpp_config.h> main.cc out/*.cc -o weather
```

No other library needs to be compiled or linked: the runtime does not depend on the C or C++ library and compiles with
`-nostdinc -nostdinc++ -ffreestanding -fno-exceptions -fno-rtti`. Its types (`pb_u32`, ...) are macros that the
configuration can redefine, see [Standard types and features](configuration.md#standard-types-and-features).

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
use and the deviations from MISRA C++ and AUTOSAR C++14.
