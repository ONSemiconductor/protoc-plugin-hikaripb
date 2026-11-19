#include <criterion/criterion.h>

#include "test_io.h"
#include "expected_values.h"
#include "sample_message.pb.h"
#include "sample_scalars.pb.h"

// Verifies that the generated decoder reports the correct DecodeError for
// each failure mode instead of silently corrupting data.

Test(sample_errors, repeated_overflow) {
    test_io_reset();

    samplepkg_SampleMessage_WrHandle root = samplepkg_SampleMessage_create();
    // samplepkg_SampleMessage_tags_count is configured to 3; write a 4th to overflow it.
    samplepkg_SampleMessage_tags_WrHandle tags = samplepkg_SampleMessage_add_tags(&root);
    samplepkg_SampleMessage_tags_add(&tags, samplepkg_Color_COLOR_RED);
    samplepkg_SampleMessage_tags_add(&tags, samplepkg_Color_COLOR_GREEN);
    samplepkg_SampleMessage_tags_add(&tags, samplepkg_Color_COLOR_BLUE);
    samplepkg_SampleMessage_tags_add(&tags, samplepkg_Color_COLOR_RED);
    samplepkg_SampleMessage_tags_done(&tags);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    samplepkg_SampleMessage decoded;
    samplepkg_SampleMessage_clear(&decoded);
    samplepkg_SampleMessage_decode(&decoded);

    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_REPEATED_OVERFLOW);
}

Test(sample_errors, bytes_overflow) {
    test_io_reset();

    static const pb_u8 too_long[] = {1, 2, 3, 4, 5, 6, 7, 8, 9};  // samplepkg_SampleMessage_payload_size is 8
    samplepkg_SampleMessage_WrHandle root = samplepkg_SampleMessage_create();
    samplepkg_SampleMessage_payload_WrHandle payload = samplepkg_SampleMessage_add_payload(&root);
    samplepkg_SampleMessage_payload_addBytes(&payload, too_long, (pb_u16)sizeof(too_long));
    samplepkg_SampleMessage_payload_done(&payload);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    samplepkg_SampleMessage decoded;
    samplepkg_SampleMessage_clear(&decoded);
    samplepkg_SampleMessage_decode(&decoded);

    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_BYTES_OVERFLOW);
}

Test(sample_errors, repeated_bytes_overflow) {
    test_io_reset();

    scalarpkg_TextLists_WrHandle root = scalarpkg_TextLists_create();
    // scalarpkg_TextLists_text_count is configured to 3; write a 4th to overflow it.
    for (pb_u32 i = 0U; i < 4U; i++) {
        scalarpkg_TextLists_text_WrHandle text = scalarpkg_TextLists_add_text(&root);
        scalarpkg_TextLists_text_addBytes(&text, (const pb_u8*)"x", 1U);
        scalarpkg_TextLists_text_done(&text);
    }

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    scalarpkg_TextLists decoded;
    scalarpkg_TextLists_clear(&decoded);
    scalarpkg_TextLists_decode(&decoded);

    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_REPEATED_OVERFLOW);
    cr_assert_eq(decoded.text.count, 3U);
}

Test(sample_errors, repeated_bytes_element_overflow) {
    test_io_reset();

    static const pb_u8 fits[] = {1, 2, 3, 4, 5};
    static const pb_u8 too_long[] = {1, 2, 3, 4, 5, 6};  // scalarpkg_TextLists_blob_size is 5
    scalarpkg_TextLists_WrHandle root = scalarpkg_TextLists_create();
    scalarpkg_TextLists_blob_WrHandle blob = scalarpkg_TextLists_add_blob(&root);
    scalarpkg_TextLists_blob_addBytes(&blob, fits, (pb_u16)sizeof(fits));
    scalarpkg_TextLists_blob_done(&blob);
    blob = scalarpkg_TextLists_add_blob(&root);
    scalarpkg_TextLists_blob_addBytes(&blob, too_long, (pb_u16)sizeof(too_long));
    scalarpkg_TextLists_blob_done(&blob);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    scalarpkg_TextLists decoded;
    scalarpkg_TextLists_clear(&decoded);
    scalarpkg_TextLists_decode(&decoded);

    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_BYTES_OVERFLOW);
    cr_assert_eq(decoded.blob.count, 1U);
}

Test(sample_errors, oneof_conflict) {
    test_io_reset();

    // Writing both members of the "choice" oneof is not prevented at encode
    // time; the decoder must detect the conflict when it sees the 2nd tag.
    samplepkg_SampleMessage_WrHandle root = samplepkg_SampleMessage_create();
    samplepkg_SampleMessage_set_choice_u32(&root, EXPECTED_CHOICE_U32);
    samplepkg_SampleMessage_set_choice_s32(&root, -1);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    samplepkg_SampleMessage decoded;
    samplepkg_SampleMessage_clear(&decoded);
    samplepkg_SampleMessage_decode(&decoded);

    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_ONEOF_ERROR);
}

Test(sample_errors, unknown_tag) {
    // Hand-crafted wire bytes: tag 99 (not a field of SampleMessage) with
    // wire type VARINT, followed by a 1-byte varint value. SAMPLE_ERROR_ON_UNKNOWN_TAG
    // is enabled in sample_config.h, so this must surface as a decode error
    // rather than being silently skipped.
    static const pb_u8 raw[] = {0x98U, 0x06U, 0x05U};  // tag=99,wiretype=VARINT ; value=5

    test_io_reset();
    test_io_set_read_buffer(raw, (pb_u32)sizeof(raw));
    samplepkg_SampleMessage decoded;
    samplepkg_SampleMessage_clear(&decoded);
    samplepkg_SampleMessage_decode(&decoded);

    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_UNKNOWN_TAG);
}

Test(sample_errors, unexpected_eof) {
    test_io_reset();

    samplepkg_SampleMessage_WrHandle root = samplepkg_SampleMessage_create();
    samplepkg_SampleMessage_set_opt_value(&root, EXPECTED_OPT_VALUE);
    samplepkg_Point_WrHandle location = samplepkg_SampleMessage_add_location(&root);
    samplepkg_Point_set_x(&location, EXPECTED_LOCATION_X);
    samplepkg_Point_set_y(&location, EXPECTED_LOCATION_Y);
    samplepkg_Point_destroy_submessage(&location);

    cr_assert(!test_io_has_write_overflow());

    // Truncate the valid buffer mid-message so the length-delimited "location"
    // submessage runs past the end of the available input.
    const pb_u32 full_len = test_io_get_write_length();
    cr_assert(full_len > 2U);
    test_io_set_read_buffer(test_io_get_write_buffer(), full_len - 2U);
    samplepkg_SampleMessage decoded;
    samplepkg_SampleMessage_clear(&decoded);
    samplepkg_SampleMessage_decode(&decoded);

    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_UNEXPECTED_EOF);
}

Test(sample_errors, varint_overflow) {
    // tag=2 (opt_uint), wiretype=VARINT, followed by an oversized 6-byte varint
    // (the 5th continuation byte alone already exceeds the 32-bit payload width).
    static const pb_u8 raw[] = {0x10U, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0x01U};

    test_io_reset();
    test_io_set_read_buffer(raw, (pb_u32)sizeof(raw));
    samplepkg_SampleMessage decoded;
    samplepkg_SampleMessage_clear(&decoded);
    samplepkg_SampleMessage_decode(&decoded);

    cr_assert_eq(sample_getError(), SAMPLE_DECODER_VARINT_OVERFLOW);
}

Test(sample_errors, empty_packed_field) {
    // field 1 (u32) is a packed field without an element, field 2 (s32) is a packed field with the element -1:
    // the empty field must not swallow or misread the field that follows it
    static const pb_u8 raw[] = {0x0AU, 0x00U, 0x12U, 0x01U, 0x01U};

    test_io_reset();
    test_io_set_read_buffer(raw, (pb_u32)sizeof(raw));
    scalarpkg_Repeats decoded;
    scalarpkg_Repeats_clear(&decoded);
    scalarpkg_Repeats_decode(&decoded);

    cr_assert(!sample_hasError());
    cr_assert_eq(decoded.u32.count, 0U);
    cr_assert_eq(decoded.s32.count, 1U);
    cr_assert_eq(decoded.s32.item[0], -1);
}

Test(sample_errors, length_above_16_bits) {
    // field 9 (blob) of 65541 (0x10005) bytes: cut to 16 bits the length would be 5 and fit the 8 bytes of storage
    static const pb_u8 raw[] = {0x4AU, 0x85U, 0x80U, 0x04U, 0x01U, 0x02U, 0x03U, 0x04U, 0x05U};

    test_io_reset();
    test_io_set_read_buffer(raw, (pb_u32)sizeof(raw));
    scalarpkg_Scalars decoded;
    scalarpkg_Scalars_clear(&decoded);
    scalarpkg_Scalars_decode(&decoded);

    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_BYTES_OVERFLOW);
}

Test(sample_errors, wire_type_mismatch) {
    // field 1 (u32, a varint) as a length-delimited field: it is not the field of the schema, so it is an unknown tag
    // and its value is not stored
    static const pb_u8 raw[] = {0x0AU, 0x01U, 0x05U};

    test_io_reset();
    test_io_set_read_buffer(raw, (pb_u32)sizeof(raw));
    scalarpkg_Scalars decoded;
    scalarpkg_Scalars_clear(&decoded);
    scalarpkg_Scalars_decode(&decoded);

    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_UNKNOWN_TAG);
    cr_assert_eq(decoded.u32, 0U);
}

static void decode_scalars(const pb_u8* data, pb_u32 len) {
    test_io_reset();
    test_io_set_read_buffer(data, len);
    scalarpkg_Scalars decoded;
    scalarpkg_Scalars_clear(&decoded);
    scalarpkg_Scalars_decode(&decoded);
}

Test(sample_errors, input_ends_inside_a_varint) {
    // u32 (field 1) with the 5-byte value 0xFFFFFFFF: the input ends after 1, 2, 3 and 4 bytes of it
    static const pb_u8 raw[] = {0x08U, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0x0FU};

    for (pb_u32 len = 2U; len < (pb_u32)sizeof(raw); len++) {
        decode_scalars(raw, len);
        cr_assert(sample_hasError(), "%u bytes of the value", len - 1U);
        cr_assert_eq(sample_getError(), SAMPLE_DECODER_UNEXPECTED_EOF, "%u bytes of the value", len - 1U);
    }
}

Test(sample_errors, input_ends_inside_a_too_long_varint) {
    // the fifth byte of the value already overflows 32 bits and announces a sixth, which the input does not hold
    static const pb_u8 raw[] = {0x08U, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0xFFU};

    decode_scalars(raw, (pb_u32)sizeof(raw));
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_VARINT_OVERFLOW);
}

Test(sample_errors, input_ends_inside_a_bytes_or_fixed32_field) {
    // blob (field 9) of 5 bytes, of which the input holds 2, and f32 (field 3, fixed32) with 2 of its 4 bytes
    static const pb_u8 blob[] = {0x4AU, 0x05U, 0x01U, 0x02U};
    static const pb_u8 fixed[] = {0x1DU, 0x01U, 0x02U};

    decode_scalars(blob, (pb_u32)sizeof(blob));
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_UNEXPECTED_EOF, "bytes");
    decode_scalars(fixed, (pb_u32)sizeof(fixed));
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_UNEXPECTED_EOF, "fixed32");
}

Test(sample_errors, unpacked_repeated_overflow) {
    // u32 (field 1) of Repeats holds 4 elements: the fifth of the unpacked elements 1 to 5 overflows it
    static const pb_u8 raw[] = {0x08U, 0x01U, 0x08U, 0x02U, 0x08U, 0x03U, 0x08U, 0x04U, 0x08U, 0x05U};

    test_io_reset();
    test_io_set_read_buffer(raw, (pb_u32)sizeof(raw));
    scalarpkg_Repeats decoded;
    scalarpkg_Repeats_clear(&decoded);
    scalarpkg_Repeats_decode(&decoded);

    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_REPEATED_OVERFLOW);
    cr_assert_eq(decoded.u32.count, 4U);
    for (pb_u32 i = 0U; i < 4U; i++) {
        cr_assert_eq(decoded.u32.item[i], i + 1U, "u32[%u]", i);
    }
}
