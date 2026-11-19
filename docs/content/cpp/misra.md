# Coding standards and safety (C++)

The code that `type=cpp` generates is written to the rules of MISRA C++ and AUTOSAR C++14 that tools can check, for
projects to a safety standard such as ISO 26262. It does not make a product compliant by itself: the application, its
configuration header, its streams and its callbacks, and the process (deviation records, tool qualification, review)
remain the task of the project.

## Properties of the generated code

- **No dynamic memory, no exceptions, no RTTI, no recursion, no `goto`, no C or C++ library.** The runtime needs C++17
  and compiles with `-nostdinc -nostdinc++ -ffreestanding -fno-exceptions -fno-rtti`. The `Decoder` keeps the nesting
  levels in an array of `HIKARIPB_DEC_MAX_DEPTH` frames, so its stack use is constant, and every loop is bounded by the
  input, a size, a count or the maximum depth.
- **The input cannot write outside of the message.** The decoder checks every length, size, count, nesting depth and
  wire type before it stores a value, and input that ends within a field is an error.
- **Every decode error is reported**: `hasError()` and `getError()` of the `Decoder` tell it after the decode.
- **A configuration that cannot work does not compile**, for example a missing size or count, or a setting out of its
  range.
- **The preconditions are asserted** with `HIKARIPB_ASSERT`, for example that the length of a field fits the bytes
  that the encoder reserved for it.

## Assumptions of use

- A message that was decoded with an error is not used: it can hold partly written fields.
- `HIKARIPB_ASSERT`, a no-op by default, is defined as a handler that brings the system to its safe state and does not
  return.

## Deviations

The generated code deviates from the rules below on purpose; a project that claims compliance records them. The rule
numbers are those of MISRA C++:2008 and AUTOSAR C++14.

| Id | Rules | Where | Reason |
|----|-------|-------|--------|
| DEV-1 | M5-2-7, M5-2-8 | `pointer_cast` | The decoder is driven by tables: it reads and writes a field through a pointer of its type at the offset of its descriptor (from `PB_OFFSETOF` of the generated struct, after checking the wire type). `pointer_cast` in `<prefix>_defines.h` is the only place of this conversion. |
| DEV-2 | M9-5-1 | `ItemDescriptor`, `oneof`, float | Unions: the size and count or the callback of a field (tagged by `hasCallback`; `std::variant` needs the library), a `oneof` of the schema, the bits of a `float`. |
| DEV-3 | M5-0-15 | `ArrayWrapper::data()`, `UnionWrapper::data()` | The elements of a repeated field and the member of a `oneof` follow their header in memory. |
| DEV-4 | M5-2-12, A18-1-1 | streams, messages | Strings, bytes and repeated fields are C arrays of a configured size: `std::array` needs the library. |
| DEV-5 | M16-0-3 | print macros | `HIKARIPB_PRINT` and `HIKARIPB_PRINTLN` are defined as nothing when printing is switched off. |
| DEV-6 | A7-2-3 | enumerations | The enumerations are unscoped, so the application uses the enumerators as plain names, like in C. |
| DEV-7 | C++ Core Guidelines ES.31 | settings | The settings are macros: `<prefix>_config.h` overrides them, and `#if` removes the code that a switch does not need. |
| DEV-8 | C++ Core Guidelines Type.6, ES.20 | `Decoder::stack`, the buffers of the `Encoder` | Not initialised on purpose: each frame and buffer is written before it is read (M8-5-1 and A8-5-0 are met), and a fill would cost `HIKARIPB_DEC_MAX_DEPTH` frames per `Decoder` and a `memset` per field. |
