# Field callbacks of the C++ generator

By default, the decoder stores every field in the struct of its message, in storage whose size is fixed in
`<prefix>_config.h`. A field callback passes a field to an application function instead. Callbacks are useful when:

- a field can be larger than the available RAM, for example a firmware image, and must be processed or forwarded in
  chunks;
- a repeated field has no practical upper bound, and each element can be processed as soon as it arrives;
- the application stores the field in memory of its own, for example in a buffer pool.

Callbacks affect only the decoder. The encoder writes a field with a callback in the same way as any other field, see
[Encode and decode](overview.md#encode-and-decode).

## Enable a callback

A callback is enabled in `<prefix>_config.h` with the global switch `<PREFIX>_CALLBACK` and one
`<package>_<Message>_<field>_callback_en` definition per field:

```cpp
#define WEATHER_CPP_CALLBACK 1
#define weather_Report_readings_callback_en 1   // replaces weather_Report_readings_count
#define weather_Report_station_callback_en  1   // replaces weather_Report_station_size
```

For a field with a callback:

- The struct member is a pointer of type `<package>_<Message>_<field>_cbtype` (`void*` unless defined otherwise)
  instead of storage. The field needs no `_size` or `_count` definition.
- `clear()` sets the member to `nullptr`, and `print()` prints `<field>: callback` instead of the value.
- `has_<field>()` reports the presence of the field in the same way as for any other field.

The application must define the callback function of every enabled field; a missing function is a link error.

## The callback function

The callback function is declared in the namespace of the message and named after the message and the field, with the
suffix `_callback`:

```cpp
namespace weather {
bool Report_readings_callback(weather_cpp::Decoder<>& decoder, const weather_cpp::ItemDescriptor* dsc, pb_u16 len,
                              void** data);
}  // namespace weather
```

| Parameter | Description |
|-----------|-------------|
| `decoder` | The decoder that decodes the message. |
| `dsc` | The descriptor of the field, to be passed on to `decoder.decode_item()`. |
| `len` | The length of the field on the wire for a string, a bytes field or an embedded message; `0` for a scalar or an enum. |
| `data` | The address of the struct member of the field. The callback can set the member to the storage that receives the field, so that the decoded struct refers to it. |
| Return value | `true` if the field was processed; `false` to report an error. |

The decoder calls the function as soon as the field arrives, while the message is being decoded. For a repeated field,
the decoder calls the function once per element, for packed and unpacked encoding alike; `len` is then the length of
the element.

The function must consume exactly the bytes of the field, or of the element, from the stream: either it decodes them
with `decoder.decode_item()`, or it reads them from `decoder.getStream()`. Otherwise, the rest of the message is not
decoded correctly.

## Decode the field into application storage

`decoder.decode_item()` decodes the field into storage provided by the callback:

```cpp
void decode_item(pb_u8* item_data, const ItemDescriptor* desc, pb_u32 len = 0);
```

| Type of the field | Storage passed as `item_data` | Result |
|-------------------|-------------------------------|--------|
| Scalar or enum | A variable of the type of the field (`pb_u32`, `pb_s32`, `bool`, `float`, the enum) | The value of the field. |
| `string`, `bytes` | A struct with a `pb_u32` length followed by a byte array, `struct { pb_u32 length; pb_u8 data[N]; }` | The length in the first member and the bytes of the field, without a terminating zero, in the array. `decode_item()` does not check the size of the array, so the callback must check `len` beforehand. |
| Embedded message | A struct of the type of the message | The complete message: the struct is cleared and decoded, including the callbacks of its own fields. |

The following callback processes each reading of a report as soon as it arrives, so that the report needs no storage
for its readings:

```cpp
#include "weather.pb.h"

namespace weather {
bool Report_readings_callback(weather_cpp::Decoder<>& decoder, const weather_cpp::ItemDescriptor* dsc, pb_u16 len,
                              void** data) {
    static Reading reading;

    *data = &reading;                                      // the member readings refers to the last reading
    decoder.decode_item(reinterpret_cast<pb_u8*>(&reading), dsc, len);
    if (!decoder.hasError()) {
        store_reading(reading.sensor_id, reading.temperature);   // application function
    }
    return true;
}
}  // namespace weather
```

## Read the field directly

A callback for a string or bytes field can also read the `len` bytes of the field itself from the input stream of the
decoder, for example to forward a large field in chunks:

```cpp
namespace weather {
bool Report_station_callback(weather_cpp::Decoder<>& decoder, const weather_cpp::ItemDescriptor* dsc, pb_u16 len,
                             void** data) {
    pb_u8 chunk[16];

    (void)dsc;
    (void)data;
    while (len > 0U) {
        const pb_u16 size = (len < sizeof(chunk)) ? len : static_cast<pb_u16>(sizeof(chunk));
        if (!decoder.getStream().read(chunk, size)) {
            return false;
        }
        forward_station_name(chunk, size);                 // application function
        len = static_cast<pb_u16>(len - size);
    }
    return true;
}
}  // namespace weather
```

## Error handling

If the callback returns `false`, the decoder records the error `DecodeError::DECODER_CALLBACK_ERROR` and stops
decoding. `hasError()` of the decoder then returns `true` and `getError()` returns this error.

With `<PREFIX>_CONTINUE_ON_CALLBACK_ERROR`, the decoder instead skips the field and continues with the rest of the
message; the error is retained. Because the decoder skips the complete field, a callback that reports an error must do
so before it consumes any byte of the field.
