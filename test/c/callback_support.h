#ifndef TEST_C_CALLBACK_SUPPORT_H
#define TEST_C_CALLBACK_SUPPORT_H

#include "sample_defines.h"

#ifdef __cplusplus
extern "C" {
#endif

// Test-controlled behavior/state for callbackpkg_CallbackMsg_value_callback
// (see sample_callback.pb.c, always linked in since every generated .c file
// is shared across all C test binaries).
void   test_callback_reset(pb_bool should_fail);
pb_u32 test_callback_call_count(void);
pb_u32 test_callback_last_value(void);

// Test-controlled behavior/state for callbackpkg_CallbackParent_child_callback
// (single embedded submessage routed through a callback).
void   test_callback_child_reset(pb_bool should_fail);
pb_u32 test_callback_child_call_count(void);
pb_u32 test_callback_child_last_id(void);

// Test-controlled behavior/state for callbackpkg_CallbackParent_children_callback
// (repeated embedded submessage; fires once per encountered element).
void   test_callback_children_reset(void);
pb_u32 test_callback_children_call_count(void);
pb_u32 test_callback_children_last_id(void);
pb_u32 test_callback_children_id_sum(void);

// Test-controlled behavior/state for callbackpkg_CallbackParent_numbers_callback
// (repeated scalar; fires once per encountered element).
void   test_callback_numbers_reset(void);
pb_u32 test_callback_numbers_call_count(void);
pb_u32 test_callback_numbers_sum(void);
// From the reset on, the callback returns false at the call number `call` (1 is the first, 0 never), or returns true at
// it without reading its element.
void   test_callback_numbers_fail_at(pb_u32 call);
void   test_callback_numbers_skip_at(pb_u32 call);

// Test-controlled behavior/state for callbackpkg_CallbackParent_payload_callback
// (bytes field).
void   test_callback_payload_reset(void);
pb_u32 test_callback_payload_call_count(void);
pb_u32 test_callback_payload_length(void);
pb_u8  test_callback_payload_byte(pb_u32 index);

// Test-controlled behavior/state for callbackpkg_CallbackChunks_chunks_callback
// (repeated bytes; fires once per encountered element, the callback owns the
// storage). The call with the 1-based number fail_at fails, 0 never fails.
void   test_callback_chunks_reset(pb_u32 fail_at);
pb_u32 test_callback_chunks_call_count(void);
pb_u32 test_callback_chunks_length(pb_u32 index);
pb_u8  test_callback_chunks_byte(pb_u32 index, pb_u32 offset);

#ifdef __cplusplus
}
#endif

#endif
