#include <criterion/criterion.h>

#include "test_io.h"
#include "sample_empty.pb.h"

// empty.proto: Ping has no field. It is written and read like any other message, alone and embedded in Pong.

Test(sample_empty, embedded_empty_messages_round_trip) {
    test_io_reset();

    emptypkg_Pong_WrHandle pong = emptypkg_Pong_create();
    emptypkg_Pong_set_seq(&pong, 7U);
    emptypkg_Ping_WrHandle ping = emptypkg_Pong_add_ping(&pong);
    emptypkg_Ping_destroy_submessage(&ping);
    emptypkg_Ping_WrHandle ack = emptypkg_Pong_add_ack(&pong);
    emptypkg_Ping_destroy_submessage(&ack);
    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    emptypkg_Pong decoded;
    emptypkg_Pong_clear(&decoded);
    emptypkg_Pong_decode(&decoded);

    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(decoded.seq, 7U);
    cr_assert(emptypkg_Pong_has_ping(&decoded));
    cr_assert(emptypkg_Pong_has_ack(&decoded));
    cr_assert(emptypkg_Pong_has_reply(&decoded));
}

Test(sample_empty, empty_message_has_no_bytes) {
    test_io_reset();
    emptypkg_Ping_WrHandle ping = emptypkg_Ping_create();
    emptypkg_Ping_destroy_submessage(&ping);
    cr_assert_eq(test_io_get_write_length(), 0U);

    emptypkg_Ping decoded;
    emptypkg_Ping_clear(&decoded);
    test_io_set_read_buffer(test_io_get_write_buffer(), 0U);
    emptypkg_Ping_decode(&decoded);
    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
}

Test(sample_empty, a_field_of_an_empty_message_is_unknown) {
    // tag 1, wire type VARINT, value 5: Ping has no tag 1; SAMPLE_ERROR_ON_UNKNOWN_TAG is enabled in sample_config.h
    static const pb_u8 raw[] = {0x08U, 0x05U};

    test_io_reset();
    test_io_set_read_buffer(raw, (pb_u32)sizeof(raw));
    emptypkg_Ping decoded;
    emptypkg_Ping_clear(&decoded);
    emptypkg_Ping_decode(&decoded);

    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_UNKNOWN_TAG);
}
