#include <criterion/criterion.h>

#include "empty.pb.h"

// C++ mirror of test_empty.c: Ping (empty.proto) has no field. It is written and read like any other message,
// alone and embedded in Pong.

Test(sample_empty_cpp, embedded_empty_messages_round_trip) {
    static uint8_t buffer[64];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);

    {
        auto pong = emptypkg::Pong::WrProxy<true>(enc);
        pong.set_seq(7U);
        {
            auto ping = pong.add_ping();
        }
        {
            auto ack = pong.add_ack();
        }
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    emptypkg::Pong decoded;
    decoded.decode(dec);

    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(decoded.seq, 7U);
    cr_assert(decoded.has_ping());
    cr_assert(decoded.has_ack());
    cr_assert(decoded.has_reply());
}

Test(sample_empty_cpp, empty_message_has_no_bytes) {
    static uint8_t buffer[8];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto ping = emptypkg::Ping::WrProxy<true>(enc);
        (void)ping;
    }
    cr_assert_eq(os.getOffset(), 0U);

    uint32_t len = 0U;
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    emptypkg::Ping decoded;
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
}

Test(sample_empty_cpp, a_field_of_an_empty_message_is_unknown) {
    // tag 1, wire type VARINT, value 5: Ping has no tag 1; HIKARIPB_ERROR_ON_UNKNOWN_TAG is enabled in hikaripb_config.h
    static uint8_t raw[] = {0x08U, 0x05U};

    uint32_t len = (uint32_t)sizeof(raw);
    hikaripb::InputStream is(raw, len);
    hikaripb::Decoder<> dec(is);
    emptypkg::Ping decoded;
    decoded.decode(dec);

    cr_assert(dec.hasError());
    cr_assert_eq(dec.getError(), hikaripb::DecodeError::DECODER_UNKNOWN_TAG);
}
