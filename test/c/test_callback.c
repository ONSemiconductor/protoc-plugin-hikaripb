#include <criterion/criterion.h>

#include "test_io.h"
#include "callback_support.h"
#include "sample_callback.pb.h"

// callbackpkg_CallbackMsg_value_callback_en is enabled in sample_config.h, so
// the generated decoder routes the "value" field through the callback
// implemented in callback_support.c instead of writing it into fixed struct
// storage.

Test(sample_callback, invoked_on_decode) {
    test_callback_reset(false);
    test_io_reset();

    callbackpkg_CallbackMsg_WrHandle root = callbackpkg_CallbackMsg_create();
    callbackpkg_CallbackMsg_set_value(&root, 4242U);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    callbackpkg_CallbackMsg decoded;
    callbackpkg_CallbackMsg_clear(&decoded);
    callbackpkg_CallbackMsg_decode(&decoded);

    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(test_callback_call_count(), 1U);
    cr_assert_eq(test_callback_last_value(), 4242U);
}

Test(sample_callback, error_propagates) {
    test_callback_reset(true);
    test_io_reset();

    callbackpkg_CallbackMsg_WrHandle root = callbackpkg_CallbackMsg_create();
    callbackpkg_CallbackMsg_set_value(&root, 7U);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    callbackpkg_CallbackMsg decoded;
    callbackpkg_CallbackMsg_clear(&decoded);
    callbackpkg_CallbackMsg_decode(&decoded);

    cr_assert_eq(test_callback_call_count(), 1U);
    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_CALLBACK_ERROR);
}

// CallbackParent routes every field except "value" through its own callback
// (see sample_config.h); the tests below exercise a single embedded
// submessage, a repeated embedded submessage, a repeated scalar and a bytes
// field, in addition to the plain scalar already covered above.

Test(sample_callback, submessage_callback_invoked_on_decode) {
    test_callback_child_reset(false);
    test_io_reset();

    callbackpkg_CallbackParent_WrHandle root = callbackpkg_CallbackParent_create();
    callbackpkg_CallbackParent_set_value(&root, 11U);
    callbackpkg_CallbackChild_WrHandle child = callbackpkg_CallbackParent_add_child(&root);
    callbackpkg_CallbackChild_set_id(&child, 99U);
    callbackpkg_CallbackChild_destroy_submessage(&child);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    callbackpkg_CallbackParent decoded;
    callbackpkg_CallbackParent_clear(&decoded);
    callbackpkg_CallbackParent_decode(&decoded);

    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(decoded.value, 11U);
    cr_assert_eq(test_callback_child_call_count(), 1U);
    cr_assert_eq(test_callback_child_last_id(), 99U);
}

Test(sample_callback, submessage_callback_error_propagates) {
    test_callback_child_reset(true);
    test_io_reset();

    callbackpkg_CallbackParent_WrHandle root = callbackpkg_CallbackParent_create();
    callbackpkg_CallbackChild_WrHandle child = callbackpkg_CallbackParent_add_child(&root);
    callbackpkg_CallbackChild_set_id(&child, 1U);
    callbackpkg_CallbackChild_destroy_submessage(&child);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    callbackpkg_CallbackParent decoded;
    callbackpkg_CallbackParent_clear(&decoded);
    callbackpkg_CallbackParent_decode(&decoded);

    cr_assert_eq(test_callback_child_call_count(), 1U);
    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_CALLBACK_ERROR);
}

Test(sample_callback, repeated_submessage_callback_invoked_per_element) {
    test_callback_children_reset();
    test_io_reset();

    callbackpkg_CallbackParent_WrHandle root = callbackpkg_CallbackParent_create();

    callbackpkg_CallbackChild_WrHandle c0 = callbackpkg_CallbackParent_add_children(&root);
    callbackpkg_CallbackChild_set_id(&c0, 1U);
    callbackpkg_CallbackChild_destroy_submessage(&c0);

    callbackpkg_CallbackChild_WrHandle c1 = callbackpkg_CallbackParent_add_children(&root);
    callbackpkg_CallbackChild_set_id(&c1, 2U);
    callbackpkg_CallbackChild_destroy_submessage(&c1);

    callbackpkg_CallbackChild_WrHandle c2 = callbackpkg_CallbackParent_add_children(&root);
    callbackpkg_CallbackChild_set_id(&c2, 3U);
    callbackpkg_CallbackChild_destroy_submessage(&c2);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    callbackpkg_CallbackParent decoded;
    callbackpkg_CallbackParent_clear(&decoded);
    callbackpkg_CallbackParent_decode(&decoded);

    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(test_callback_children_call_count(), 3U);
    cr_assert_eq(test_callback_children_last_id(), 3U);
    cr_assert_eq(test_callback_children_id_sum(), 1U + 2U + 3U);
}

Test(sample_callback, repeated_scalar_callback_invoked_per_element) {
    test_callback_numbers_reset();
    test_io_reset();

    callbackpkg_CallbackParent_WrHandle root = callbackpkg_CallbackParent_create();
    callbackpkg_CallbackParent_numbers_WrHandle numbers = callbackpkg_CallbackParent_add_numbers(&root);
    callbackpkg_CallbackParent_numbers_add(&numbers, 10U);
    callbackpkg_CallbackParent_numbers_add(&numbers, 20U);
    callbackpkg_CallbackParent_numbers_add(&numbers, 30U);
    callbackpkg_CallbackParent_numbers_done(&numbers);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    callbackpkg_CallbackParent decoded;
    callbackpkg_CallbackParent_clear(&decoded);
    callbackpkg_CallbackParent_decode(&decoded);

    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(test_callback_numbers_call_count(), 3U);
    cr_assert_eq(test_callback_numbers_sum(), 10U + 20U + 30U);
}

// numbers (field 4) with the elements 10, 20 and 30 one by one, not packed
static const pb_u8 unpacked_numbers[] = {0x20U, 0x0AU, 0x20U, 0x14U, 0x20U, 0x1EU};

static void decode_parent(const pb_u8* data, pb_u32 len) {
    test_io_reset();
    test_io_set_read_buffer(data, len);
    callbackpkg_CallbackParent decoded;
    callbackpkg_CallbackParent_clear(&decoded);
    callbackpkg_CallbackParent_decode(&decoded);
}

// numbers with the elements 10, 20 and 30 in one packed field, as the encoder writes them
static void decode_packed_numbers(void) {
    test_io_reset();
    callbackpkg_CallbackParent_WrHandle root = callbackpkg_CallbackParent_create();
    callbackpkg_CallbackParent_numbers_WrHandle numbers = callbackpkg_CallbackParent_add_numbers(&root);
    callbackpkg_CallbackParent_numbers_add(&numbers, 10U);
    callbackpkg_CallbackParent_numbers_add(&numbers, 20U);
    callbackpkg_CallbackParent_numbers_add(&numbers, 30U);
    callbackpkg_CallbackParent_numbers_done(&numbers);
    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    callbackpkg_CallbackParent decoded;
    callbackpkg_CallbackParent_clear(&decoded);
    callbackpkg_CallbackParent_decode(&decoded);
}

Test(sample_callback, unpacked_repeated_scalar_callback_invoked_per_element) {
    test_callback_numbers_reset();
    decode_parent(unpacked_numbers, (pb_u32)sizeof(unpacked_numbers));

    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(test_callback_numbers_call_count(), 3U);
    cr_assert_eq(test_callback_numbers_sum(), 10U + 20U + 30U);
}

Test(sample_callback, unpacked_repeated_scalar_callback_error_propagates) {
    test_callback_numbers_reset();
    test_callback_numbers_fail_at(2U);
    decode_parent(unpacked_numbers, (pb_u32)sizeof(unpacked_numbers));

    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_CALLBACK_ERROR);
    // decoding stops at the failing element
    cr_assert_eq(test_callback_numbers_call_count(), 2U);
    cr_assert_eq(test_callback_numbers_sum(), 10U);
}

Test(sample_callback, packed_repeated_scalar_callback_error_propagates) {
    test_callback_numbers_reset();
    test_callback_numbers_fail_at(2U);
    decode_packed_numbers();

    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_CALLBACK_ERROR);
    cr_assert_eq(test_callback_numbers_call_count(), 2U);
    cr_assert_eq(test_callback_numbers_sum(), 10U);
}

Test(sample_callback, packed_repeated_scalar_callback_that_reads_nothing_is_an_error) {
    // the decoder would call it again for ever for the same element
    test_callback_numbers_reset();
    test_callback_numbers_skip_at(1U);
    decode_packed_numbers();

    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_CALLBACK_ERROR);
    cr_assert_eq(test_callback_numbers_call_count(), 1U);
}

Test(sample_callback, bytes_callback_invoked_on_decode) {
    test_callback_payload_reset();
    test_io_reset();

    static const pb_u8 expected_payload[] = {0xAAU, 0xBBU, 0xCCU};

    callbackpkg_CallbackParent_WrHandle root = callbackpkg_CallbackParent_create();
    callbackpkg_CallbackParent_payload_WrHandle payload = callbackpkg_CallbackParent_add_payload(&root);
    callbackpkg_CallbackParent_payload_addBytes(&payload, expected_payload, (pb_u16)sizeof(expected_payload));
    callbackpkg_CallbackParent_payload_done(&payload);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    callbackpkg_CallbackParent decoded;
    callbackpkg_CallbackParent_clear(&decoded);
    callbackpkg_CallbackParent_decode(&decoded);

    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(test_callback_payload_call_count(), 1U);
    cr_assert_eq(test_callback_payload_length(), (pb_u32)sizeof(expected_payload));
    cr_assert_eq(test_callback_payload_byte(0U), expected_payload[0]);
    cr_assert_eq(test_callback_payload_byte(1U), expected_payload[1]);
    cr_assert_eq(test_callback_payload_byte(2U), expected_payload[2]);
}

// CallbackChunks: "chunks" (repeated bytes) goes through its callback, "names" (repeated string) is stored in
// the struct. Every element is written by its own add_<field>() call.

static void add_chunk(callbackpkg_CallbackChunks_WrHandle* root, const char* data, pb_u16 len) {
    callbackpkg_CallbackChunks_chunks_WrHandle chunk = callbackpkg_CallbackChunks_add_chunks(root);
    callbackpkg_CallbackChunks_chunks_addBytes(&chunk, (const pb_u8*)data, len);
    callbackpkg_CallbackChunks_chunks_done(&chunk);
}

static void add_name(callbackpkg_CallbackChunks_WrHandle* root, const char* data, pb_u16 len) {
    callbackpkg_CallbackChunks_names_WrHandle name = callbackpkg_CallbackChunks_add_names(root);
    callbackpkg_CallbackChunks_names_addBytes(&name, (const pb_u8*)data, len);
    callbackpkg_CallbackChunks_names_done(&name);
}

static void decode_written(callbackpkg_CallbackChunks* decoded) {
    cr_assert(!test_io_has_write_overflow());
    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    callbackpkg_CallbackChunks_clear(decoded);
    callbackpkg_CallbackChunks_decode(decoded);
}

Test(sample_callback, repeated_bytes_callback_invoked_per_element) {
    test_callback_chunks_reset(0U);
    test_io_reset();

    callbackpkg_CallbackChunks_WrHandle root = callbackpkg_CallbackChunks_create();
    add_chunk(&root, "ab", 2U);
    add_chunk(&root, "", 0U);
    add_chunk(&root, "cdef", 4U);
    add_name(&root, "x", 1U);
    add_name(&root, "yz", 2U);

    callbackpkg_CallbackChunks decoded;
    decode_written(&decoded);

    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(test_callback_chunks_call_count(), 3U);
    cr_assert_eq(test_callback_chunks_length(0U), 2U);
    cr_assert_eq(test_callback_chunks_byte(0U, 0U), (pb_u8)'a');
    cr_assert_eq(test_callback_chunks_byte(0U, 1U), (pb_u8)'b');
    cr_assert_eq(test_callback_chunks_length(1U), 0U);
    cr_assert_eq(test_callback_chunks_length(2U), 4U);
    cr_assert_eq(test_callback_chunks_byte(2U, 0U), (pb_u8)'c');
    cr_assert_eq(test_callback_chunks_byte(2U, 3U), (pb_u8)'f');

    // the stored field is not affected by the callback of the other one
    cr_assert_eq(decoded.names.count, 2U);
    cr_assert_eq(decoded.names.item[0].length, 1U);
    cr_assert_eq(decoded.names.item[0].data[0], (pb_u8)'x');
    cr_assert_eq(decoded.names.item[1].length, 2U);
    cr_assert_eq(decoded.names.item[1].data[1], (pb_u8)'z');
}

Test(sample_callback, repeated_bytes_callback_is_not_limited_by_count_or_size) {
    test_callback_chunks_reset(0U);
    test_io_reset();

    // 5 elements of 20 bytes: more than the 3 stored names and longer than their 8 bytes
    static const char twenty[] = "01234567890123456789";
    callbackpkg_CallbackChunks_WrHandle root = callbackpkg_CallbackChunks_create();
    for (pb_u32 i = 0U; i < 5U; i++) {
        add_chunk(&root, twenty, 20U);
    }

    callbackpkg_CallbackChunks decoded;
    decode_written(&decoded);

    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(test_callback_chunks_call_count(), 5U);
    for (pb_u32 i = 0U; i < 5U; i++) {
        cr_assert_eq(test_callback_chunks_length(i), 20U, "chunk[%u]", i);
        cr_assert_eq(test_callback_chunks_byte(i, 19U), (pb_u8)'9', "chunk[%u]", i);
    }
    cr_assert_eq(decoded.names.count, 0U);
}

Test(sample_callback, repeated_bytes_callback_and_stored_field_interleave) {
    test_callback_chunks_reset(0U);
    test_io_reset();

    callbackpkg_CallbackChunks_WrHandle root = callbackpkg_CallbackChunks_create();
    add_name(&root, "one", 3U);
    add_chunk(&root, "A", 1U);
    add_name(&root, "two", 3U);
    add_chunk(&root, "BC", 2U);
    add_name(&root, "six", 3U);  // the third name fills the stored field

    callbackpkg_CallbackChunks decoded;
    decode_written(&decoded);

    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(test_callback_chunks_call_count(), 2U);
    cr_assert_eq(test_callback_chunks_length(1U), 2U);
    cr_assert_eq(decoded.names.count, 3U);
    cr_assert_eq(decoded.names.item[0].data[0], (pb_u8)'o');
    cr_assert_eq(decoded.names.item[1].data[0], (pb_u8)'t');
    cr_assert_eq(decoded.names.item[2].data[0], (pb_u8)'s');
}

Test(sample_callback, repeated_bytes_callback_error_propagates) {
    test_callback_chunks_reset(2U);
    test_io_reset();

    callbackpkg_CallbackChunks_WrHandle root = callbackpkg_CallbackChunks_create();
    add_chunk(&root, "ab", 2U);
    add_chunk(&root, "cd", 2U);
    add_chunk(&root, "ef", 2U);

    callbackpkg_CallbackChunks decoded;
    decode_written(&decoded);

    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_CALLBACK_ERROR);
    // decoding stops at the failing element
    cr_assert_eq(test_callback_chunks_call_count(), 2U);
}
