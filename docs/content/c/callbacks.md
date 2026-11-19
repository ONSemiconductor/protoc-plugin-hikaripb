# Field callbacks of the C generator

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

```c
#define WEATHER_C_CALLBACK 1
#define weather_Report_readings_callback_en 1   /* replaces weather_Report_readings_count */
#define weather_Report_station_callback_en  1   /* replaces weather_Report_station_size */
```

For a field with a callback:

- The struct member is a pointer instead of storage: `void*` for a repeated field, and
  `<package>_<Message>_<field>_cbtype` (`void*` unless defined otherwise) for any other field. The field needs no
  `_size` or `_count` definition.
- `<message>_clear()` sets the member to `PB_NULL`, and `<message>_print()` prints `<field>: callback` instead of the
  value.
- `<message>_has_<field>()` reports the presence of the field in the same way as for any other field.

The application must define the callback function of every enabled field; a missing function is a link error.

## The callback function

The callback function is named after the field, with the suffix `_callback`:

```c
pb_bool weather_Report_readings_callback(const struct weather_c_ItemDescriptor* desc, pb_u16 len, void** item_data);
```

| Parameter | Description |
|-----------|-------------|
| `desc` | The descriptor of the field, to be passed on to `<prefix>_decode_item()`. |
| `len` | The length of the field on the wire for a string, a bytes field or an embedded message; `0` for a scalar or an enum. |
| `item_data` | The address of the struct member of the field. The callback can set the member to the storage that receives the field, so that the decoded struct refers to it. |
| Return value | Non-zero if the field was processed; zero to report an error. |

With `<PREFIX>_ENABLE_MULTI_DEC`, the function receives the decode context as an additional first parameter,
`struct <prefix>_DecodeContext* decoder_ctx`. Its member `io_ctx` is the pointer that was passed to
`<prefix>_DecodeContext_create()`, through which the callback can reach the state of the application.

The decoder calls the function as soon as the field arrives, while the message is being decoded. For a repeated field,
the decoder calls the function once per element, for packed and unpacked encoding alike; `len` is then the length of
the element.

The function must consume exactly the bytes of the field, or of the element, from the transport: either it decodes them
with `<prefix>_decode_item()`, or it reads them with the transport functions. Otherwise, the rest of the message is not
decoded correctly.

## Decode the field into application storage

`<prefix>_decode_item()` decodes the field into storage provided by the callback. With `<PREFIX>_ENABLE_MULTI_DEC`, it
takes the decode context as its first parameter.

```c
void <prefix>_decode_item(pb_u8* item_data, const struct <prefix>_ItemDescriptor* desc, pb_u32 len);
```

| Type of the field | Storage passed as `item_data` | Result |
|-------------------|-------------------------------|--------|
| Scalar or enum | A variable of the C type of the field (`pb_u32`, `pb_s32`, `pb_bool`, `float`, the type of the enum) | The value of the field. |
| `string`, `bytes` | A byte array of at least `len` bytes | The `len` bytes of the field, without a terminating zero. `<prefix>_decode_item()` does not check the size of the array, so the callback must check `len` beforehand. |
| Embedded message | A struct of the type of the message | The complete message: the struct is cleared and decoded, including the callbacks of its own fields. |

The following callback processes each reading of a report as soon as it arrives, so that the report needs no storage
for its readings:

```c
#include "weather_c_weather.pb.h"

pb_bool weather_Report_readings_callback(const struct weather_c_ItemDescriptor* desc, pb_u16 len, void** item_data) {
    static weather_Reading reading;

    *item_data = &reading;                                 /* the member readings refers to the last reading */
    weather_c_decode_item((pb_u8*)&reading, desc, len);
    if (!weather_c_hasError()) {
        store_reading(reading.sensor_id, reading.temperature);   /* application function */
    }
    return 1U;
}
```

## Read the field directly

A callback for a string or bytes field can also read the `len` bytes of the field itself, with the transport
functions of the application, for example to forward a large field in chunks:

```c
pb_bool weather_Report_station_callback(const struct weather_c_ItemDescriptor* desc, pb_u16 len, void** item_data) {
    pb_u8 chunk[16];

    (void)desc;
    (void)item_data;
    while (len > 0U) {
        const pb_u16 size = (len < (pb_u16)sizeof(chunk)) ? len : (pb_u16)sizeof(chunk);
        if (!weather_c_read(chunk, size)) {
            return 0U;
        }
        forward_station_name(chunk, size);                 /* application function */
        len = (pb_u16)(len - size);
    }
    return 1U;
}
```

With `<PREFIX>_ENABLE_MULTI_DEC`, the transport functions take `decoder_ctx->io_ctx` as their first argument.

## Error handling

If the callback returns zero, the decoder records the error `<PREFIX>_DECODER_CALLBACK_ERROR` and stops decoding.
`<prefix>_hasError()` then returns true and `<prefix>_getError()` returns this error.

With `<PREFIX>_CONTINUE_ON_CALLBACK_ERROR`, the decoder instead skips the field and continues with the rest of the
message; the error is retained. Because the decoder skips the complete field, a callback that reports an error must do
so before it consumes any byte of the field.
