#include <criterion/criterion.h>

#include "callback_support.h"
#include "callback.pb.h"

// callbackpkg_CallbackMsg_value_callback_en is enabled in hikaripb_config.h, so
// the generated decoder routes the "value" field through the callback
// implemented in callback_support.cc instead of writing it into fixed struct
// storage.

Test(sample_callback_cpp, invoked_on_decode) {
    test_callback_reset(false);

    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = callbackpkg::CallbackMsg::WrProxy<true>(enc);
        root.set_value(4242U);
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    callbackpkg::CallbackMsg decoded;
    decoded.decode(dec);

    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(test_callback_call_count(), 1U);
    cr_assert_eq(test_callback_last_value(), 4242U);
}

Test(sample_callback_cpp, error_propagates) {
    test_callback_reset(true);

    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = callbackpkg::CallbackMsg::WrProxy<true>(enc);
        root.set_value(7U);
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    callbackpkg::CallbackMsg decoded;
    decoded.decode(dec);

    cr_assert_eq(test_callback_call_count(), 1U);
    cr_assert(dec.hasError());
    cr_assert_eq(dec.getError(), hikaripb::DecodeError::DECODER_CALLBACK_ERROR);
}

// CallbackParent routes every field except "value" through its own callback
// (see hikaripb_config.h); the tests below exercise a single embedded
// submessage, a repeated embedded submessage, a repeated scalar and a bytes
// field, in addition to the plain scalar already covered above.

Test(sample_callback_cpp, submessage_callback_invoked_on_decode) {
    test_callback_child_reset(false);

    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = callbackpkg::CallbackParent::WrProxy<true>(enc);
        root.set_value(11U);
        {
            auto child = root.add_child();
            child.set_id(99U);
        }
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    callbackpkg::CallbackParent decoded;
    decoded.decode(dec);

    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(decoded.value, 11U);
    cr_assert_eq(test_callback_child_call_count(), 1U);
    cr_assert_eq(test_callback_child_last_id(), 99U);
}

Test(sample_callback_cpp, submessage_callback_error_propagates) {
    test_callback_child_reset(true);

    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = callbackpkg::CallbackParent::WrProxy<true>(enc);
        {
            auto child = root.add_child();
            child.set_id(1U);
        }
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    callbackpkg::CallbackParent decoded;
    decoded.decode(dec);

    cr_assert_eq(test_callback_child_call_count(), 1U);
    cr_assert(dec.hasError());
    cr_assert_eq(dec.getError(), hikaripb::DecodeError::DECODER_CALLBACK_ERROR);
}

Test(sample_callback_cpp, repeated_submessage_callback_invoked_per_element) {
    test_callback_children_reset();

    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = callbackpkg::CallbackParent::WrProxy<true>(enc);
        {
            auto c0 = root.rpt_children();
            c0.set_id(1U);
        }
        {
            auto c1 = root.rpt_children();
            c1.set_id(2U);
        }
        {
            auto c2 = root.rpt_children();
            c2.set_id(3U);
        }
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    callbackpkg::CallbackParent decoded;
    decoded.decode(dec);

    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(test_callback_children_call_count(), 3U);
    cr_assert_eq(test_callback_children_last_id(), 3U);
    cr_assert_eq(test_callback_children_id_sum(), 1U + 2U + 3U);
}

Test(sample_callback_cpp, repeated_scalar_callback_invoked_per_element) {
    test_callback_numbers_reset();

    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = callbackpkg::CallbackParent::WrProxy<true>(enc);
        auto numbers = root.rpt_numbers();
        numbers.add(10U);
        numbers.add(20U);
        numbers.add(30U);
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    callbackpkg::CallbackParent decoded;
    decoded.decode(dec);

    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(test_callback_numbers_call_count(), 3U);
    cr_assert_eq(test_callback_numbers_sum(), 10U + 20U + 30U);
}

// numbers (field 4) with the elements 10, 20 and 30 one by one, not packed
static uint8_t unpacked_numbers[] = {0x20U, 0x0AU, 0x20U, 0x14U, 0x20U, 0x1EU};

static hikaripb::DecodeError decode_parent(uint8_t* data, uint32_t len) {
    hikaripb::InputStream is(data, len);
    hikaripb::Decoder<> dec(is);
    callbackpkg::CallbackParent decoded;
    decoded.decode(dec);
    return dec.getError();
}

// numbers with the elements 10, 20 and 30 in one packed field, as the encoder writes them
static hikaripb::DecodeError decode_packed_numbers() {
    static uint8_t buffer[64];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = callbackpkg::CallbackParent::WrProxy<true>(enc);
        auto numbers = root.rpt_numbers();
        numbers.add(10U);
        numbers.add(20U);
        numbers.add(30U);
    }
    return decode_parent(buffer, os.getOffset());
}

Test(sample_callback_cpp, unpacked_repeated_scalar_callback_invoked_per_element) {
    test_callback_numbers_reset();
    const hikaripb::DecodeError error = decode_parent(unpacked_numbers, (uint32_t)sizeof(unpacked_numbers));

    cr_assert_eq(error, hikaripb::DecodeError::DECODER_OK);
    cr_assert_eq(test_callback_numbers_call_count(), 3U);
    cr_assert_eq(test_callback_numbers_sum(), 10U + 20U + 30U);
}

Test(sample_callback_cpp, unpacked_repeated_scalar_callback_error_propagates) {
    test_callback_numbers_reset();
    test_callback_numbers_fail_at(2U);
    const hikaripb::DecodeError error = decode_parent(unpacked_numbers, (uint32_t)sizeof(unpacked_numbers));

    cr_assert_eq(error, hikaripb::DecodeError::DECODER_CALLBACK_ERROR);
    // decoding stops at the failing element
    cr_assert_eq(test_callback_numbers_call_count(), 2U);
    cr_assert_eq(test_callback_numbers_sum(), 10U);
}

Test(sample_callback_cpp, packed_repeated_scalar_callback_error_propagates) {
    test_callback_numbers_reset();
    test_callback_numbers_fail_at(2U);

    cr_assert_eq(decode_packed_numbers(), hikaripb::DecodeError::DECODER_CALLBACK_ERROR);
    cr_assert_eq(test_callback_numbers_call_count(), 2U);
    cr_assert_eq(test_callback_numbers_sum(), 10U);
}

Test(sample_callback_cpp, packed_repeated_scalar_callback_that_reads_nothing_is_an_error) {
    // the decoder would call it again for ever for the same element
    test_callback_numbers_reset();
    test_callback_numbers_skip_at(1U);

    cr_assert_eq(decode_packed_numbers(), hikaripb::DecodeError::DECODER_CALLBACK_ERROR);
    cr_assert_eq(test_callback_numbers_call_count(), 1U);
}

Test(sample_callback_cpp, bytes_callback_invoked_on_decode) {
    test_callback_payload_reset();

    static const uint8_t expected_payload[] = {0xAAU, 0xBBU, 0xCCU};

    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = callbackpkg::CallbackParent::WrProxy<true>(enc);
        auto payload = root.add_payload();
        payload.write(expected_payload, (uint16_t)sizeof(expected_payload));
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    callbackpkg::CallbackParent decoded;
    decoded.decode(dec);

    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(test_callback_payload_call_count(), 1U);
    cr_assert_eq(test_callback_payload_length(), (uint32_t)sizeof(expected_payload));
    cr_assert_eq(test_callback_payload_byte(0U), expected_payload[0]);
    cr_assert_eq(test_callback_payload_byte(1U), expected_payload[1]);
    cr_assert_eq(test_callback_payload_byte(2U), expected_payload[2]);
}

// CallbackChunks: "chunks" (repeated bytes) goes through its callback, "names" (repeated string) is stored in
// the struct. Every element is written by its own rpt_<field>() call.

namespace {

void add_chunk(callbackpkg::CallbackChunks::WrProxy<true>& root, const char* data, uint16_t len) {
    auto chunk = root.rpt_chunks();
    chunk.write(reinterpret_cast<const uint8_t*>(data), len);
}

void add_name(callbackpkg::CallbackChunks::WrProxy<true>& root, const char* data, uint16_t len) {
    auto name = root.rpt_names();
    name.write(reinterpret_cast<const uint8_t*>(data), len);
}

}  // namespace

Test(sample_callback_cpp, repeated_bytes_callback_invoked_per_element) {
    test_callback_chunks_reset(0U);

    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = callbackpkg::CallbackChunks::WrProxy<true>(enc);
        add_chunk(root, "ab", 2U);
        add_chunk(root, "", 0U);
        add_chunk(root, "cdef", 4U);
        add_name(root, "x", 1U);
        add_name(root, "yz", 2U);
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    callbackpkg::CallbackChunks decoded;
    decoded.decode(dec);

    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(test_callback_chunks_call_count(), 3U);
    cr_assert_eq(test_callback_chunks_length(0U), 2U);
    cr_assert_eq(test_callback_chunks_byte(0U, 0U), (uint8_t)'a');
    cr_assert_eq(test_callback_chunks_byte(0U, 1U), (uint8_t)'b');
    cr_assert_eq(test_callback_chunks_length(1U), 0U);
    cr_assert_eq(test_callback_chunks_length(2U), 4U);
    cr_assert_eq(test_callback_chunks_byte(2U, 0U), (uint8_t)'c');
    cr_assert_eq(test_callback_chunks_byte(2U, 3U), (uint8_t)'f');

    // the stored field is not affected by the callback of the other one
    cr_assert_eq(decoded.names.count, 2U);
    cr_assert_eq(decoded.names.item[0].length, 1U);
    cr_assert_eq(decoded.names.item[0].data[0], (uint8_t)'x');
    cr_assert_eq(decoded.names.item[1].length, 2U);
    cr_assert_eq(decoded.names.item[1].data[1], (uint8_t)'z');
}

Test(sample_callback_cpp, repeated_bytes_callback_is_not_limited_by_count_or_size) {
    test_callback_chunks_reset(0U);

    // 5 elements of 20 bytes: more than the 3 stored names and longer than their 8 bytes
    static const char twenty[] = "01234567890123456789";
    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = callbackpkg::CallbackChunks::WrProxy<true>(enc);
        for (uint32_t i = 0U; i < 5U; i++) {
            add_chunk(root, twenty, 20U);
        }
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    callbackpkg::CallbackChunks decoded;
    decoded.decode(dec);

    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(test_callback_chunks_call_count(), 5U);
    for (uint32_t i = 0U; i < 5U; i++) {
        cr_assert_eq(test_callback_chunks_length(i), 20U, "chunk[%u]", i);
        cr_assert_eq(test_callback_chunks_byte(i, 19U), (uint8_t)'9', "chunk[%u]", i);
    }
    cr_assert_eq(decoded.names.count, 0U);
}

Test(sample_callback_cpp, repeated_bytes_callback_and_stored_field_interleave) {
    test_callback_chunks_reset(0U);

    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = callbackpkg::CallbackChunks::WrProxy<true>(enc);
        add_name(root, "one", 3U);
        add_chunk(root, "A", 1U);
        add_name(root, "two", 3U);
        add_chunk(root, "BC", 2U);
        add_name(root, "six", 3U);  // the third name fills the stored field
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    callbackpkg::CallbackChunks decoded;
    decoded.decode(dec);

    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(test_callback_chunks_call_count(), 2U);
    cr_assert_eq(test_callback_chunks_length(1U), 2U);
    cr_assert_eq(decoded.names.count, 3U);
    cr_assert_eq(decoded.names.item[0].data[0], (uint8_t)'o');
    cr_assert_eq(decoded.names.item[1].data[0], (uint8_t)'t');
    cr_assert_eq(decoded.names.item[2].data[0], (uint8_t)'s');
}

Test(sample_callback_cpp, repeated_bytes_callback_error_propagates) {
    test_callback_chunks_reset(2U);

    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = callbackpkg::CallbackChunks::WrProxy<true>(enc);
        add_chunk(root, "ab", 2U);
        add_chunk(root, "cd", 2U);
        add_chunk(root, "ef", 2U);
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    callbackpkg::CallbackChunks decoded;
    decoded.decode(dec);

    cr_assert(dec.hasError());
    cr_assert_eq(dec.getError(), hikaripb::DecodeError::DECODER_CALLBACK_ERROR);
    // decoding stops at the failing element
    cr_assert_eq(test_callback_chunks_call_count(), 2U);
}
