#include "callback_support.h"

// The single_file=all build includes all.pb.h instead (see test/Makefile).
#ifndef CALLBACK_SUPPORT_PB_HEADER
#define CALLBACK_SUPPORT_PB_HEADER "callback.pb.h"
#endif
#include CALLBACK_SUPPORT_PB_HEADER

static uint32_t g_calls;
static uint32_t g_last_value;
static bool     g_should_fail;

void test_callback_reset(bool should_fail) {
    g_calls = 0U;
    g_last_value = 0U;
    g_should_fail = should_fail;
}

uint32_t test_callback_call_count() {
    return g_calls;
}

uint32_t test_callback_last_value() {
    return g_last_value;
}

namespace callbackpkg {
// callbackpkg_CallbackMsg_value_callback_en is enabled in hikaripb_config.h, so
// the generated decoder routes the "value" field through this callback
// instead of writing it into fixed struct storage.
bool CallbackMsg_value_callback(hikaripb::Decoder<>& decoder, const hikaripb::ItemDescriptor* dsc, uint16_t len, void** data) {
    g_calls++;
    if (g_should_fail) {
        return false;
    }
    *data = &g_last_value;
    decoder.decode_item(reinterpret_cast<uint8_t*>(*data), dsc, len);
    return true;
}
}  // namespace callbackpkg

// --- CallbackParent.child: single embedded submessage routed via callback ---

static uint32_t g_child_calls;
static uint32_t g_child_last_id;
static bool     g_child_should_fail;

void test_callback_child_reset(bool should_fail) {
    g_child_calls = 0U;
    g_child_last_id = 0U;
    g_child_should_fail = should_fail;
}

uint32_t test_callback_child_call_count() {
    return g_child_calls;
}

uint32_t test_callback_child_last_id() {
    return g_child_last_id;
}

// --- CallbackParent.children: repeated embedded submessage, one callback ---
// --- invocation per encountered element ---

static uint32_t g_children_calls;
static uint32_t g_children_last_id;
static uint32_t g_children_id_sum;

void test_callback_children_reset() {
    g_children_calls = 0U;
    g_children_last_id = 0U;
    g_children_id_sum = 0U;
}

uint32_t test_callback_children_call_count() {
    return g_children_calls;
}

uint32_t test_callback_children_last_id() {
    return g_children_last_id;
}

uint32_t test_callback_children_id_sum() {
    return g_children_id_sum;
}

// --- CallbackParent.numbers: repeated scalar, one callback invocation per ---
// --- encountered element (packed or sparse encoding alike) ---

static uint32_t g_numbers_calls;
static uint32_t g_numbers_sum;
static uint32_t g_numbers_fail_at;
static uint32_t g_numbers_skip_at;

void test_callback_numbers_reset() {
    g_numbers_calls = 0U;
    g_numbers_sum = 0U;
    g_numbers_fail_at = 0U;
    g_numbers_skip_at = 0U;
}

void test_callback_numbers_fail_at(uint32_t call) {
    g_numbers_fail_at = call;
}

void test_callback_numbers_skip_at(uint32_t call) {
    g_numbers_skip_at = call;
}

uint32_t test_callback_numbers_call_count() {
    return g_numbers_calls;
}

uint32_t test_callback_numbers_sum() {
    return g_numbers_sum;
}

// --- CallbackParent.payload: bytes field routed via callback ---

// The C++ decoder's BYTES case treats item_data as an hikaripb::ArrayWrapper*
// (uint32_t len followed by a flexible data[] member), unlike the C backend's
// tb_bytes which writes straight into a raw buffer - this storage mirrors
// that exact layout so decode_item() writes to the right offset.
struct PayloadWrapper {
    uint32_t len;
    uint8_t  data[32];
};

static uint32_t      g_payload_calls;
static PayloadWrapper g_payload_wrapper;

void test_callback_payload_reset() {
    g_payload_calls = 0U;
    g_payload_wrapper.len = 0U;
}

uint32_t test_callback_payload_call_count() {
    return g_payload_calls;
}

uint32_t test_callback_payload_length() {
    return g_payload_wrapper.len;
}

uint8_t test_callback_payload_byte(uint32_t index) {
    return g_payload_wrapper.data[index];
}

// --- CallbackChunks.chunks: repeated bytes, one callback invocation per ---
// --- encountered element ---

// every element is a hikaripb::ArrayWrapper as above
struct ChunkWrapper {
    uint32_t len;
    uint8_t  data[32];
};

static constexpr uint32_t CHUNKS_MAX = 8U;
static uint32_t           g_chunks_calls;
static uint32_t           g_chunks_fail_at;
static ChunkWrapper       g_chunks[CHUNKS_MAX];

void test_callback_chunks_reset(uint32_t fail_at) {
    g_chunks_calls = 0U;
    g_chunks_fail_at = fail_at;
}

uint32_t test_callback_chunks_call_count() {
    return g_chunks_calls;
}

uint32_t test_callback_chunks_length(uint32_t index) {
    return g_chunks[index].len;
}

uint8_t test_callback_chunks_byte(uint32_t index, uint32_t offset) {
    return g_chunks[index].data[offset];
}

namespace callbackpkg {
bool CallbackParent_child_callback(hikaripb::Decoder<>& decoder, const hikaripb::ItemDescriptor* dsc, uint16_t len, void** data) {
    static CallbackChild s_child;
    g_child_calls++;
    if (g_child_should_fail) {
        return false;
    }
    *data = &s_child;
    decoder.decode_item(reinterpret_cast<uint8_t*>(*data), dsc, len);
    g_child_last_id = s_child.id;
    return true;
}

bool CallbackParent_children_callback(hikaripb::Decoder<>& decoder, const hikaripb::ItemDescriptor* dsc, uint16_t len, void** data) {
    static CallbackChild s_child;
    g_children_calls++;
    *data = &s_child;
    decoder.decode_item(reinterpret_cast<uint8_t*>(*data), dsc, len);
    g_children_last_id = s_child.id;
    g_children_id_sum += s_child.id;
    return true;
}

bool CallbackParent_numbers_callback(hikaripb::Decoder<>& decoder, const hikaripb::ItemDescriptor* dsc, uint16_t len, void** data) {
    static uint32_t s_value;
    g_numbers_calls++;
    if (g_numbers_calls == g_numbers_fail_at) {
        return false;
    }
    if (g_numbers_calls == g_numbers_skip_at) {
        return true;  // the element is not read
    }
    *data = &s_value;
    decoder.decode_item(reinterpret_cast<uint8_t*>(*data), dsc, len);
    g_numbers_sum += s_value;
    return true;
}

bool CallbackParent_payload_callback(hikaripb::Decoder<>& decoder, const hikaripb::ItemDescriptor* dsc, uint16_t len, void** data) {
    g_payload_calls++;
    *data = &g_payload_wrapper;
    decoder.decode_item(reinterpret_cast<uint8_t*>(*data), dsc, len);
    return true;
}

bool CallbackChunks_chunks_callback(hikaripb::Decoder<>& decoder, const hikaripb::ItemDescriptor* dsc, uint16_t len, void** data) {
    const uint32_t index = g_chunks_calls++;
    if ((g_chunks_calls == g_chunks_fail_at) || (index >= CHUNKS_MAX) || (len > sizeof(ChunkWrapper::data))) {
        return false;
    }
    *data = &g_chunks[index];
    decoder.decode_item(reinterpret_cast<uint8_t*>(*data), dsc, len);
    return true;
}
}  // namespace callbackpkg
