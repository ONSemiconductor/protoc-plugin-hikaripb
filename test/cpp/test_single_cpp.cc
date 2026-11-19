#include <criterion/criterion.h>

#include "all.pb.h"
#include "callback_support.h"
#include "expected_values.h"

// all.pb.h was generated with single_file=all: one header holds the messages of message.proto,
// depth.proto, callback.proto and scalars.proto + shared/common.proto, each in its own namespace
// (no per-.proto <name>.pb.h exists).

Test(sample_single_cpp, message_proto_round_trip) {
    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = samplepkg::SampleMessage::WrProxy<true>(enc);
        root.set_opt_value(EXPECTED_OPT_VALUE);
        root.set_choice_u32(EXPECTED_CHOICE_U32);
        {
            auto location = root.add_location();
            location.set_x(EXPECTED_LOCATION_X);
            location.set_y(EXPECTED_LOCATION_Y);
        }
        {
            auto label = root.add_label();
            label.write((const uint8_t*)EXPECTED_LABEL, (uint16_t)EXPECTED_LABEL_LENGTH);
        }
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    samplepkg::SampleMessage decoded;
    decoded.decode(dec);

    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(decoded.opt_value, EXPECTED_OPT_VALUE);
    cr_assert_eq(decoded.location.x, EXPECTED_LOCATION_X);
    cr_assert_eq(decoded.location.y, EXPECTED_LOCATION_Y);
    cr_assert_eq(decoded.label.length, EXPECTED_LABEL_LENGTH);
}

// scalars.proto imports shared/common.proto: both live in the one header, the imported type is used directly.
Test(sample_single_cpp, scalars_proto_round_trip) {
    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = scalarpkg::Choice::WrProxy<true>(enc);
        root.set_number(EXPECTED_CHOICE_U32);
        auto when = root.add_when();
        when.set_seconds(EXPECTED_CH_WHEN_SECONDS);
        when.set_unit(static_cast<shared::Unit>(EXPECTED_CH_WHEN_UNIT));
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::Choice decoded;
    decoded.decode(dec);

    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert(decoded.has_number());
    cr_assert_eq(decoded.value.number, EXPECTED_CHOICE_U32);
    cr_assert(decoded.has_when());
    cr_assert_eq(decoded.when.seconds, EXPECTED_CH_WHEN_SECONDS);
    cr_assert_eq((uint32_t)decoded.when.unit, EXPECTED_CH_WHEN_UNIT);
}

// repeated string and bytes: the stored TextLists of scalars.proto and the callback-driven CallbackChunks
Test(sample_single_cpp, repeated_bytes_round_trip) {
    test_callback_chunks_reset(0U);

    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto lists = scalarpkg::TextLists::WrProxy<true>(enc);
        {
            auto text = lists.rpt_text();
            text.write(reinterpret_cast<const uint8_t*>("abc"), 3U);
        }
        { auto text = lists.rpt_text(); }
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::TextLists decoded;
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(decoded.text.count, 2U);
    cr_assert_eq(decoded.text.item[0].length, 3U);
    cr_assert_eq(memcmp(decoded.text.item[0].data, "abc", 3U), 0);
    cr_assert_eq(decoded.text.item[1].length, 0U);

    hikaripb::OutputStream chunk_os(buffer);
    hikaripb::Encoder<> chunk_enc(chunk_os);
    {
        auto chunks = callbackpkg::CallbackChunks::WrProxy<true>(chunk_enc);
        auto chunk = chunks.rpt_chunks();
        chunk.write(reinterpret_cast<const uint8_t*>("xy"), 2U);
    }

    uint32_t chunk_len = chunk_os.getOffset();
    hikaripb::InputStream chunk_is(buffer, chunk_len);
    hikaripb::Decoder<> chunk_dec(chunk_is);
    callbackpkg::CallbackChunks decoded_chunks;
    decoded_chunks.decode(chunk_dec);
    cr_assert(!chunk_dec.hasError(), "decode error %d", chunk_dec.getError());
    cr_assert_eq(test_callback_chunks_call_count(), 1U);
    cr_assert_eq(test_callback_chunks_length(0U), 2U);
    cr_assert_eq(test_callback_chunks_byte(0U, 1U), (uint8_t)'y');
}

Test(sample_single_cpp, depth_proto_round_trip) {
    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = depthpkg::DepthL0::WrProxy<true>(enc);
        root.set_value(10U);
        auto n1 = root.add_next();
        n1.set_value(11U);
        auto n2 = n1.add_next();
        n2.set_value(12U);
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    depthpkg::DepthL0 decoded;
    decoded.decode(dec);

    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(decoded.value, 10U);
    cr_assert_eq(decoded.next.value, 11U);
    cr_assert_eq(decoded.next.next.value, 12U);
    cr_assert(!decoded.next.next.has_next());
}

Test(sample_single_cpp, callback_proto_round_trip) {
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
