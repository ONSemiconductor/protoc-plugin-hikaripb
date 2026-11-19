# Encoding and decoding

The generated C and C++ code is made for devices with little memory: it **encodes on the fly** and **decodes directly
into a fixed-size struct**. The Python codec works on complete buffers. These principles explain most of the library
configuration of the [C](c/configuration.md#library-configuration), [C++](cpp/configuration.md#library-configuration)
and [Python](python/configuration.md#library-configuration) generators.

## Encoding on the fly (C and C++)

Each `set_<field>` and `add_<field>` call writes its field to the transport at once, in the order of the calls. The
encoder keeps no copy of the message and needs no buffer, only a small handle for each message that is open.

A string, bytes field, embedded message or packed repeated field starts with its length, which is known only after its
content. The encoder reserves `<PREFIX>_ENC_PAD_LENGTH` bytes for it (2 by default, enough for 16383 bytes), writes the
content, then goes back and writes the length into the reserved bytes as a padded varint. Every protobuf decoder accepts
it; the message is a few bytes longer than its shortest encoding. As a result:

- **The output must be seekable.** A memory buffer is; for a UART, write the message into a buffer and send it when it
  is complete.
- **Close an embedded message before its parent is continued**: `done` or `destroy_submessage` in C, the end of the
  scope of its proxy in C++. `<PREFIX>_DEBUG` checks it.
- **Every value that is set is written**, a proto3 default too: do not set the fields that are not needed.
- **A message that is only sent needs no decoder**: mark it as `writeonly`.

## Decoding into a fixed struct (C and C++)

The decoder parses while it reads from the transport, so the message is never held in memory as a whole. The top-level
message ends with the input: give the decoder exactly one message.

- **A plain struct of a fixed size.** Scalars are stored in place, a string or bytes field as `{ length, data[size] }`,
  a repeated field as `{ count, item[count] }`, with the sizes and counts of the configuration; nothing is allocated.
  Before decoding, the presence bits, the lengths, the counts and the fields without presence are cleared, so such a
  field is zero when it is absent. An optional field or an embedded message is not cleared, which saves the time of a
  large message: `has_<field>()` tells whether it was on the wire, and its value is valid only when it was.
- **The members are ordered by alignment**, one-byte members first, then two-byte ones, then the others (a `oneof` is
  its tag and its union), so the struct has as little padding as possible. Use the members by name, not by position.
- **A table per message locates the fields**: the offset and the type of every field. A field number that is not in the
  table, or a field whose wire type does not match its type, is skipped, so a newer sender does not break an older
  receiver; `<PREFIX>_ERROR_ON_UNKNOWN_TAG` makes it an error. Packed and unpacked repeated fields are both accepted.
- **Constant stack use.** The decoder does not recurse: it keeps the nesting levels in an array of
  `<PREFIX>_DEC_MAX_DEPTH` frames.
- **No data is truncated silently.** A string or bytes field longer than its size, a length above 65535, a repeated
  field with more elements than its count, nesting beyond the limit, a second member of a `oneof`, a varint wider than
  32 bits and input that ends within a field are errors; a `bool` is true for every value other than 0. The decoder
  stops at the first error unless a `<PREFIX>_CONTINUE_ON_...` setting makes it skip the field. `hasError()` and
  `getError()` tell the result: **do not use a message that was decoded with an error**, it can hold partly written
  fields.
- **Callbacks pass a field to the application** instead of storing it ([C](c/callbacks.md), [C++](cpp/callbacks.md)):
  the function decodes the field into its own storage or reads its bytes, in chunks if it is larger than the RAM.
- **A presence bitmap records the fields on the wire**, one bit per field number up to the largest. Keep the field
  numbers small: a field number of 1000 costs 126 bytes in every message struct.

The C and C++ decoders accept strings, bytes fields and embedded messages of up to 65535 bytes, and 32-bit integers.

## Python

The Python codec does not need to save memory and works on complete buffers. `serialize()` writes the shortest
encoding and omits default values. `deserialize()` takes the complete message as `bytes`, accepts packed and unpacked
repeated fields, checks that strings are valid UTF-8 and skips unknown fields. `max_depth` limits the nesting, and
`strict=True` makes unknown fields, mismatched wire types and several members of a `oneof` errors. The error codes are
those of the C generator.
