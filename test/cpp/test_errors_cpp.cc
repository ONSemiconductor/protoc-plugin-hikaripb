#include <criterion/criterion.h>

#include "expected_values.h"
#include "message.pb.h"
#include "scalars.pb.h"

// C++ mirror of test_errors.c: verifies the generated hikaripb::Decoder reports
// the correct DecodeError for each failure mode instead of silently
// corrupting data.

Test(sample_errors_cpp, repeated_overflow) {
    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);

    {
        // samplepkg_SampleMessage_tags_count is configured to 3; write a 4th to overflow it.
        auto root = samplepkg::SampleMessage::WrProxy<true>(enc);
        auto tags = root.rpt_tags();
        tags.add(samplepkg::COLOR_RED);
        tags.add(samplepkg::COLOR_GREEN);
        tags.add(samplepkg::COLOR_BLUE);
        tags.add(samplepkg::COLOR_RED);
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    samplepkg::SampleMessage decoded;
    decoded.decode(dec);

    cr_assert(dec.hasError());
    cr_assert_eq(dec.getError(), hikaripb::DecodeError::DECODER_REPEATED_OVERFLOW);
}

Test(sample_errors_cpp, bytes_overflow) {
    static uint8_t buffer[2048];
    static const uint8_t too_long[] = {1, 2, 3, 4, 5, 6, 7, 8, 9};  // samplepkg_SampleMessage_payload_size is 8
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);

    {
        auto root = samplepkg::SampleMessage::WrProxy<true>(enc);
        auto payload = root.add_payload();
        payload.write(too_long, (uint16_t)sizeof(too_long));
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    samplepkg::SampleMessage decoded;
    decoded.decode(dec);

    cr_assert(dec.hasError());
    cr_assert_eq(dec.getError(), hikaripb::DecodeError::DECODER_BYTES_OVERFLOW);
}

Test(sample_errors_cpp, repeated_bytes_overflow) {
    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);

    {
        // scalarpkg_TextLists_text_count is configured to 3; write a 4th to overflow it.
        auto root = scalarpkg::TextLists::WrProxy<true>(enc);
        for (uint32_t i = 0U; i < 4U; i++) {
            auto text = root.rpt_text();
            text.write((const uint8_t*)"x", 1U);
        }
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::TextLists decoded;
    decoded.decode(dec);

    cr_assert(dec.hasError());
    cr_assert_eq(dec.getError(), hikaripb::DecodeError::DECODER_REPEATED_OVERFLOW);
    cr_assert_eq(decoded.text.count, 3U);
}

Test(sample_errors_cpp, repeated_bytes_element_overflow) {
    static uint8_t buffer[2048];
    static const uint8_t fits[] = {1, 2, 3, 4, 5};
    static const uint8_t too_long[] = {1, 2, 3, 4, 5, 6};  // scalarpkg_TextLists_blob_size is 5
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);

    {
        auto root = scalarpkg::TextLists::WrProxy<true>(enc);
        {
            auto blob = root.rpt_blob();
            blob.write(fits, (uint16_t)sizeof(fits));
        }
        {
            auto blob = root.rpt_blob();
            blob.write(too_long, (uint16_t)sizeof(too_long));
        }
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::TextLists decoded;
    decoded.decode(dec);

    cr_assert(dec.hasError());
    cr_assert_eq(dec.getError(), hikaripb::DecodeError::DECODER_BYTES_OVERFLOW);
    cr_assert_eq(decoded.blob.count, 1U);
}

Test(sample_errors_cpp, oneof_conflict) {
    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);

    {
        // Writing both members of the "choice" oneof is not prevented at encode
        // time; the decoder must detect the conflict when it sees the 2nd tag.
        auto root = samplepkg::SampleMessage::WrProxy<true>(enc);
        root.set_choice_u32(EXPECTED_CHOICE_U32);
        root.set_choice_s32(-1);
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    samplepkg::SampleMessage decoded;
    decoded.decode(dec);

    cr_assert(dec.hasError());
    cr_assert_eq(dec.getError(), hikaripb::DecodeError::DECODER_ONEOF_ERROR);
}

Test(sample_errors_cpp, unknown_tag) {
    // Hand-crafted wire bytes: tag 99 (not a field of SampleMessage) with wire
    // type VARINT, followed by a 1-byte varint value. HIKARIPB_ERROR_ON_UNKNOWN_TAG
    // is enabled in hikaripb_config.h, so this must surface as a decode error
    // rather than being silently skipped.
    static uint8_t raw[] = {0x98U, 0x06U, 0x05U};  // tag=99,wiretype=VARINT ; value=5

    uint32_t len = (uint32_t)sizeof(raw);
    hikaripb::InputStream is(raw, len);
    hikaripb::Decoder<> dec(is);
    samplepkg::SampleMessage decoded;
    decoded.decode(dec);

    cr_assert(dec.hasError());
    cr_assert_eq(dec.getError(), hikaripb::DecodeError::DECODER_UNKNOWN_TAG);
}

Test(sample_errors_cpp, unexpected_eof) {
    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);

    {
        auto root = samplepkg::SampleMessage::WrProxy<true>(enc);
        root.set_opt_value(EXPECTED_OPT_VALUE);
        auto location = root.add_location();
        location.set_x(EXPECTED_LOCATION_X);
        location.set_y(EXPECTED_LOCATION_Y);
    }

    // Truncate the valid buffer mid-message so the length-delimited "location"
    // submessage runs past the end of the available input.
    uint32_t full_len = os.getOffset();
    cr_assert(full_len > 2U);
    uint32_t truncated_len = full_len - 2U;
    hikaripb::InputStream is(buffer, truncated_len);
    hikaripb::Decoder<> dec(is);
    samplepkg::SampleMessage decoded;
    decoded.decode(dec);

    cr_assert(dec.hasError());
    cr_assert_eq(dec.getError(), hikaripb::DecodeError::DECODER_UNEXPECTED_EOF);
}

Test(sample_errors_cpp, varint_overflow) {
    // tag=2 (opt_uint), wiretype=VARINT, followed by an oversized 6-byte varint
    // (the 5th continuation byte alone already exceeds the 32-bit payload width).
    static uint8_t raw[] = {0x10U, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0x01U};

    uint32_t len = (uint32_t)sizeof(raw);
    hikaripb::InputStream is(raw, len);
    hikaripb::Decoder<> dec(is);
    samplepkg::SampleMessage decoded;
    decoded.decode(dec);

    cr_assert_eq(dec.getError(), hikaripb::DecodeError::DECODER_VARINT_OVERFLOW);
}

Test(sample_errors_cpp, empty_packed_field) {
    // field 1 (u32) is a packed field without an element, field 2 (s32) is a packed field with the element -1:
    // the empty field must not swallow or misread the field that follows it
    static uint8_t raw[] = {0x0AU, 0x00U, 0x12U, 0x01U, 0x01U};

    uint32_t len = (uint32_t)sizeof(raw);
    hikaripb::InputStream is(raw, len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::Repeats decoded;
    decoded.decode(dec);

    cr_assert(!dec.hasError());
    cr_assert_eq(decoded.u32.count, 0U);
    cr_assert_eq(decoded.s32.count, 1U);
    cr_assert_eq(decoded.s32.item[0], -1);
}

Test(sample_errors_cpp, length_above_16_bits) {
    // field 9 (blob) of 65541 (0x10005) bytes: cut to 16 bits the length would be 5 and fit the 8 bytes of storage
    static uint8_t raw[] = {0x4AU, 0x85U, 0x80U, 0x04U, 0x01U, 0x02U, 0x03U, 0x04U, 0x05U};

    uint32_t len = (uint32_t)sizeof(raw);
    hikaripb::InputStream is(raw, len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::Scalars decoded;
    decoded.decode(dec);

    cr_assert(dec.hasError());
    cr_assert_eq(dec.getError(), hikaripb::DecodeError::DECODER_BYTES_OVERFLOW);
}

Test(sample_errors_cpp, wire_type_mismatch) {
    // field 1 (u32, a varint) as a length-delimited field: it is not the field of the schema, so it is an unknown tag
    // and its value is not stored
    static uint8_t raw[] = {0x0AU, 0x01U, 0x05U};

    uint32_t len = (uint32_t)sizeof(raw);
    hikaripb::InputStream is(raw, len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::Scalars decoded;
    decoded.decode(dec);

    cr_assert(dec.hasError());
    cr_assert_eq(dec.getError(), hikaripb::DecodeError::DECODER_UNKNOWN_TAG);
    cr_assert_eq(decoded.u32, 0U);
}

static hikaripb::DecodeError decode_scalars(uint8_t* data, uint32_t len) {
    hikaripb::InputStream is(data, len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::Scalars decoded;
    decoded.decode(dec);
    return dec.getError();
}

Test(sample_errors_cpp, input_ends_inside_a_varint) {
    // u32 (field 1) with the 5-byte value 0xFFFFFFFF: the input ends after 1, 2, 3 and 4 bytes of it
    static uint8_t raw[] = {0x08U, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0x0FU};

    for (uint32_t len = 2U; len < (uint32_t)sizeof(raw); len++) {
        cr_assert_eq(decode_scalars(raw, len), hikaripb::DecodeError::DECODER_UNEXPECTED_EOF, "%u bytes of the value",
                     len - 1U);
    }
}

Test(sample_errors_cpp, input_ends_inside_a_too_long_varint) {
    // the fifth byte of the value already overflows 32 bits and announces a sixth, which the input does not hold
    static uint8_t raw[] = {0x08U, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0xFFU};

    cr_assert_eq(decode_scalars(raw, (uint32_t)sizeof(raw)), hikaripb::DecodeError::DECODER_VARINT_OVERFLOW);
}

Test(sample_errors_cpp, input_ends_inside_a_bytes_or_fixed32_field) {
    // blob (field 9) of 5 bytes, of which the input holds 2, and f32 (field 3, fixed32) with 2 of its 4 bytes
    static uint8_t blob[] = {0x4AU, 0x05U, 0x01U, 0x02U};
    static uint8_t fixed[] = {0x1DU, 0x01U, 0x02U};

    cr_assert_eq(decode_scalars(blob, (uint32_t)sizeof(blob)), hikaripb::DecodeError::DECODER_UNEXPECTED_EOF, "bytes");
    cr_assert_eq(decode_scalars(fixed, (uint32_t)sizeof(fixed)), hikaripb::DecodeError::DECODER_UNEXPECTED_EOF,
                 "fixed32");
}

Test(sample_errors_cpp, unpacked_repeated_overflow) {
    // u32 (field 1) of Repeats holds 4 elements: the fifth of the unpacked elements 1 to 5 overflows it
    static uint8_t raw[] = {0x08U, 0x01U, 0x08U, 0x02U, 0x08U, 0x03U, 0x08U, 0x04U, 0x08U, 0x05U};

    uint32_t len = (uint32_t)sizeof(raw);
    hikaripb::InputStream is(raw, len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::Repeats decoded;
    decoded.decode(dec);

    cr_assert(dec.hasError());
    cr_assert_eq(dec.getError(), hikaripb::DecodeError::DECODER_REPEATED_OVERFLOW);
    cr_assert_eq(decoded.u32.count, 4U);
    for (uint32_t i = 0U; i < 4U; i++) {
        cr_assert_eq(decoded.u32.item[i], i + 1U, "u32[%u]", i);
    }
}
