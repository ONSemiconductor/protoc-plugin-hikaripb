# Coding standards and safety (C)

The code that `type=c` generates is written to MISRA C:2012, for projects to a safety standard such as ISO 26262. It does
not make a product compliant by itself: the application, its configuration header, its transport functions and its
callbacks, and the process (deviation records, tool qualification, review) remain the task of the project.

## Properties of the generated code

- **No dynamic memory, no recursion, no `goto`, no C library.** The runtime compiles with `-nostdinc -ffreestanding`.
  The decoder keeps the nesting levels in an array of `HIKARIPB_DEC_MAX_DEPTH` frames, so its stack use is constant,
  and every loop is bounded by the input, a size, a count or the maximum depth.
- **The input cannot write outside of the message.** The decoder checks every length, size, count, nesting depth and
  wire type before it stores a value, and input that ends within a field is an error.
- **Every decode error is reported**: `<prefix>_hasError()` and `<prefix>_getError()` tell it after the decode.
- **A configuration that cannot work does not compile**, for example a missing size or count, or a setting out of its
  range.
- **The preconditions are asserted** with `HIKARIPB_ASSERT`, for example that the length of a field fits the bytes
  that the encoder reserved for it.

## Assumptions of use

- A message that was decoded with an error is not used: it can hold partly written fields.
- `HIKARIPB_ASSERT`, a no-op by default, is defined as a handler that brings the system to its safe state and does not
  return.

## Deviations

The generated code deviates from the rules below on purpose, a project that claims compliance records these deviations (MISRA Compliance:2020).

| Id | Rules | Where | Reason |
|----|-------|-------|--------|
| DEV-1 | 11.3, 11.5 | decoder | The decoder is driven by tables: it reads and writes a field through a pointer of its type at the offset of its descriptor (from `PB_OFFSETOF` of the generated struct, after checking the wire type). The message is a `void*` in the generic functions and callbacks, and `clear()` has the type `void(void*)`. |
| DEV-2 | 15.5 | `decode_uint32`, `decode_uint32_rest` | They return as soon as the last byte of a varint is read. |
| DEV-3 | 19.2 | descriptors, `oneof`, float | Unions: the size and count or the callback of a field, a `oneof` of the schema, the bits of a `float`. |
| DEV-4 | 20.5 | print macros | `HIKARIPB_PRINT` and `HIKARIPB_PRINTLN` are defined as nothing when printing is switched off. |
| DEV-5 | 20.10 | `<message>_Wr`, `PB_STATIC_ASSERT` | `##` builds the name of a write handle, and the name of a static assertion for a compiler without `_Static_assert`. |

### Findings that are not violations

| Id | Rule | Reason |
|----|------|--------|
| FP-1 | 20.7 | The macro parameter is the operand of `##` (an exception of the rule) or a declarator. |
| FP-2 | 11.8 | No qualifier is removed: the context of a `const` handle is a `void* const`, the member of a `const` struct a `const` pointer. |
| FP-3 | 2.7 | The parameter `len` of a decode function of the item types is used by the functions of the same table that need it. |
