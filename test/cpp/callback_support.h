#ifndef TEST_CPP_CALLBACK_SUPPORT_H
#define TEST_CPP_CALLBACK_SUPPORT_H

#include <cstdint>

// Test-controlled behavior/state for callbackpkg::CallbackMsg_value_callback
// (see callback.pb.h, referenced by hikaripb_bindings.cc which is shared across
// every C++ test binary).
void     test_callback_reset(bool should_fail);
uint32_t test_callback_call_count();
uint32_t test_callback_last_value();

// Test-controlled behavior/state for callbackpkg::CallbackParent_child_callback
// (single embedded submessage routed through a callback).
void     test_callback_child_reset(bool should_fail);
uint32_t test_callback_child_call_count();
uint32_t test_callback_child_last_id();

// Test-controlled behavior/state for callbackpkg::CallbackParent_children_callback
// (repeated embedded submessage; fires once per encountered element).
void     test_callback_children_reset();
uint32_t test_callback_children_call_count();
uint32_t test_callback_children_last_id();
uint32_t test_callback_children_id_sum();

// Test-controlled behavior/state for callbackpkg::CallbackParent_numbers_callback
// (repeated scalar; fires once per encountered element).
void     test_callback_numbers_reset();
uint32_t test_callback_numbers_call_count();
uint32_t test_callback_numbers_sum();
// From the reset on, the callback returns false at the call number `call` (1 is the first, 0 never), or returns true at
// it without reading its element.
void     test_callback_numbers_fail_at(uint32_t call);
void     test_callback_numbers_skip_at(uint32_t call);

// Test-controlled behavior/state for callbackpkg::CallbackParent_payload_callback
// (bytes field).
void     test_callback_payload_reset();
uint32_t test_callback_payload_call_count();
uint32_t test_callback_payload_length();
uint8_t  test_callback_payload_byte(uint32_t index);

// Test-controlled behavior/state for callbackpkg::CallbackChunks_chunks_callback
// (repeated bytes; fires once per encountered element, the callback owns the
// storage). The call with the 1-based number fail_at fails, 0 never fails.
void     test_callback_chunks_reset(uint32_t fail_at);
uint32_t test_callback_chunks_call_count();
uint32_t test_callback_chunks_length(uint32_t index);
uint8_t  test_callback_chunks_byte(uint32_t index, uint32_t offset);

#endif
