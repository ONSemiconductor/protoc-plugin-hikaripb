#include "callback_support.h"

// The single_file=all build includes sample_all.pb.h instead (see test/Makefile).
#ifndef CALLBACK_SUPPORT_PB_HEADER
#define CALLBACK_SUPPORT_PB_HEADER "sample_callback.pb.h"
#endif
#include CALLBACK_SUPPORT_PB_HEADER

static pb_u32  g_calls;
static pb_u32  g_last_value;
static pb_bool g_should_fail;

void test_callback_reset(pb_bool should_fail) {
    g_calls = 0U;
    g_last_value = 0U;
    g_should_fail = should_fail;
}

pb_u32 test_callback_call_count(void) {
    return g_calls;
}

pb_u32 test_callback_last_value(void) {
    return g_last_value;
}

// callbackpkg_CallbackMsg_value_callback_en is enabled in sample_config.h, so
// the generated decoder routes the "value" field through this callback
// instead of writing it into fixed struct storage.
pb_bool callbackpkg_CallbackMsg_value_callback(const struct sample_ItemDescriptor* desc, pb_u16 len, void** item_data) {
    g_calls++;
    if (g_should_fail) {
        return false;
    }
    *item_data = &g_last_value;
    sample_decode_item(*item_data, desc, len);
    return true;
}

// --- CallbackParent.child: single embedded submessage routed via callback ---

static pb_u32  g_child_calls;
static pb_u32  g_child_last_id;
static pb_bool g_child_should_fail;

void test_callback_child_reset(pb_bool should_fail) {
    g_child_calls = 0U;
    g_child_last_id = 0U;
    g_child_should_fail = should_fail;
}

pb_u32 test_callback_child_call_count(void) {
    return g_child_calls;
}

pb_u32 test_callback_child_last_id(void) {
    return g_child_last_id;
}

pb_bool callbackpkg_CallbackParent_child_callback(const struct sample_ItemDescriptor* desc, pb_u16 len, void** item_data) {
    static callbackpkg_CallbackChild s_child;
    g_child_calls++;
    if (g_child_should_fail) {
        return false;
    }
    *item_data = &s_child;
    sample_decode_item(*item_data, desc, len);
    g_child_last_id = s_child.id;
    return true;
}

// --- CallbackParent.children: repeated embedded submessage, one callback ---
// --- invocation per encountered element ---

static pb_u32 g_children_calls;
static pb_u32 g_children_last_id;
static pb_u32 g_children_id_sum;

void test_callback_children_reset(void) {
    g_children_calls = 0U;
    g_children_last_id = 0U;
    g_children_id_sum = 0U;
}

pb_u32 test_callback_children_call_count(void) {
    return g_children_calls;
}

pb_u32 test_callback_children_last_id(void) {
    return g_children_last_id;
}

pb_u32 test_callback_children_id_sum(void) {
    return g_children_id_sum;
}

pb_bool callbackpkg_CallbackParent_children_callback(const struct sample_ItemDescriptor* desc, pb_u16 len, void** item_data) {
    static callbackpkg_CallbackChild s_child;
    g_children_calls++;
    *item_data = &s_child;
    sample_decode_item(*item_data, desc, len);
    g_children_last_id = s_child.id;
    g_children_id_sum += s_child.id;
    return true;
}

// --- CallbackParent.numbers: repeated scalar, one callback invocation per ---
// --- encountered element (packed or sparse encoding alike) ---

static pb_u32 g_numbers_calls;
static pb_u32 g_numbers_sum;
static pb_u32 g_numbers_fail_at;
static pb_u32 g_numbers_skip_at;

void test_callback_numbers_reset(void) {
    g_numbers_calls = 0U;
    g_numbers_sum = 0U;
    g_numbers_fail_at = 0U;
    g_numbers_skip_at = 0U;
}

void test_callback_numbers_fail_at(pb_u32 call) {
    g_numbers_fail_at = call;
}

void test_callback_numbers_skip_at(pb_u32 call) {
    g_numbers_skip_at = call;
}

pb_u32 test_callback_numbers_call_count(void) {
    return g_numbers_calls;
}

pb_u32 test_callback_numbers_sum(void) {
    return g_numbers_sum;
}

pb_bool callbackpkg_CallbackParent_numbers_callback(const struct sample_ItemDescriptor* desc, pb_u16 len, void** item_data) {
    static pb_u32 s_value;
    g_numbers_calls++;
    if (g_numbers_calls == g_numbers_fail_at) {
        return false;
    }
    if (g_numbers_calls == g_numbers_skip_at) {
        return true;  // the element is not read
    }
    *item_data = &s_value;
    sample_decode_item(*item_data, desc, len);
    g_numbers_sum += s_value;
    return true;
}

// --- CallbackParent.payload: bytes field routed via callback ---

static pb_u32 g_payload_calls;
static pb_u32 g_payload_length;
static pb_u8  g_payload_data[32];

void test_callback_payload_reset(void) {
    g_payload_calls = 0U;
    g_payload_length = 0U;
}

pb_u32 test_callback_payload_call_count(void) {
    return g_payload_calls;
}

pb_u32 test_callback_payload_length(void) {
    return g_payload_length;
}

pb_u8 test_callback_payload_byte(pb_u32 index) {
    return g_payload_data[index];
}

pb_bool callbackpkg_CallbackParent_payload_callback(const struct sample_ItemDescriptor* desc, pb_u16 len, void** item_data) {
    g_payload_calls++;
    *item_data = g_payload_data;
    sample_decode_item(*item_data, desc, len);
    g_payload_length = len;
    return true;
}

// --- CallbackChunks.chunks: repeated bytes, one callback invocation per ---
// --- encountered element ---

#define CHUNKS_MAX 8U
#define CHUNK_SIZE 32U

static pb_u32 g_chunks_calls;
static pb_u32 g_chunks_fail_at;
static pb_u32 g_chunks_length[CHUNKS_MAX];
static pb_u8  g_chunks_data[CHUNKS_MAX][CHUNK_SIZE];

void test_callback_chunks_reset(pb_u32 fail_at) {
    g_chunks_calls = 0U;
    g_chunks_fail_at = fail_at;
}

pb_u32 test_callback_chunks_call_count(void) {
    return g_chunks_calls;
}

pb_u32 test_callback_chunks_length(pb_u32 index) {
    return g_chunks_length[index];
}

pb_u8 test_callback_chunks_byte(pb_u32 index, pb_u32 offset) {
    return g_chunks_data[index][offset];
}

pb_bool callbackpkg_CallbackChunks_chunks_callback(const struct sample_ItemDescriptor* desc, pb_u16 len, void** item_data) {
    const pb_u32 index = g_chunks_calls++;
    if ((g_chunks_calls == g_chunks_fail_at) || (index >= CHUNKS_MAX) || (len > CHUNK_SIZE)) {
        return false;
    }
    *item_data = g_chunks_data[index];
    sample_decode_item(*item_data, desc, len);
    g_chunks_length[index] = len;
    return true;
}
