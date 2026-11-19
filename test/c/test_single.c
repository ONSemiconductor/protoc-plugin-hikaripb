#include <criterion/criterion.h>
#include <string.h>

#include "callback_support.h"
#include "expected_values.h"
#include "sample_all.pb.h"
#include "test_io.h"

// sample_all.pb.h was generated with single_file=all: one header/source pair holds the messages of
// message.proto, depth.proto, callback.proto and scalars.proto + shared/common.proto (no per-.proto
// sample_<name>.pb.h exists).

Test(sample_single, message_proto_round_trip) {
    test_io_reset();

    samplepkg_SampleMessage_WrHandle root = samplepkg_SampleMessage_create();
    samplepkg_SampleMessage_set_opt_value(&root, EXPECTED_OPT_VALUE);
    samplepkg_SampleMessage_set_choice_u32(&root, EXPECTED_CHOICE_U32);

    samplepkg_Point_WrHandle location = samplepkg_SampleMessage_add_location(&root);
    samplepkg_Point_set_x(&location, EXPECTED_LOCATION_X);
    samplepkg_Point_set_y(&location, EXPECTED_LOCATION_Y);
    samplepkg_Point_destroy_submessage(&location);

    samplepkg_SampleMessage_label_WrHandle label = samplepkg_SampleMessage_add_label(&root);
    samplepkg_SampleMessage_label_addBytes(&label, (const pb_u8*)EXPECTED_LABEL, (pb_u16)EXPECTED_LABEL_LENGTH);
    samplepkg_SampleMessage_label_done(&label);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    samplepkg_SampleMessage decoded;
    samplepkg_SampleMessage_clear(&decoded);
    samplepkg_SampleMessage_decode(&decoded);

    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(decoded.opt_value, EXPECTED_OPT_VALUE);
    cr_assert_eq(decoded.choice.choice_u32, EXPECTED_CHOICE_U32);
    cr_assert_eq(decoded.location.x, EXPECTED_LOCATION_X);
    cr_assert_eq(decoded.location.y, EXPECTED_LOCATION_Y);
    cr_assert_eq(decoded.label.length, EXPECTED_LABEL_LENGTH);
    cr_assert_eq(memcmp(decoded.label.data, EXPECTED_LABEL, EXPECTED_LABEL_LENGTH), 0);
}

Test(sample_single, depth_proto_round_trip) {
    test_io_reset();

    depthpkg_DepthL0_WrHandle h0 = depthpkg_DepthL0_create();
    depthpkg_DepthL0_set_value(&h0, 10U);
    depthpkg_DepthL1_WrHandle h1 = depthpkg_DepthL0_add_next(&h0);
    depthpkg_DepthL1_set_value(&h1, 11U);
    depthpkg_DepthL2_WrHandle h2 = depthpkg_DepthL1_add_next(&h1);
    depthpkg_DepthL2_set_value(&h2, 12U);
    depthpkg_DepthL2_destroy_submessage(&h2);
    depthpkg_DepthL1_destroy_submessage(&h1);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    depthpkg_DepthL0 decoded;
    depthpkg_DepthL0_clear(&decoded);
    depthpkg_DepthL0_decode(&decoded);

    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(decoded.value, 10U);
    cr_assert_eq(decoded.next.value, 11U);
    cr_assert_eq(decoded.next.next.value, 12U);
    cr_assert(!depthpkg_DepthL2_has_next(&decoded.next.next));
}

Test(sample_single, callback_proto_round_trip) {
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

// scalars.proto imports shared/common.proto: both live in the one header, the imported type is used directly.
Test(sample_single, scalars_proto_round_trip) {
    test_io_reset();

    scalarpkg_Choice_WrHandle root = scalarpkg_Choice_create();
    scalarpkg_Choice_set_number(&root, EXPECTED_CHOICE_U32);
    shared_Stamp_WrHandle when = scalarpkg_Choice_add_when(&root);
    shared_Stamp_set_seconds(&when, EXPECTED_CH_WHEN_SECONDS);
    shared_Stamp_set_unit(&when, (shared_Unit)EXPECTED_CH_WHEN_UNIT);
    shared_Stamp_destroy_submessage(&when);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    scalarpkg_Choice decoded;
    scalarpkg_Choice_clear(&decoded);
    scalarpkg_Choice_decode(&decoded);

    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert(scalarpkg_Choice_has_number(&decoded));
    cr_assert_eq(decoded.value.number, EXPECTED_CHOICE_U32);
    cr_assert(scalarpkg_Choice_has_when(&decoded));
    cr_assert_eq(decoded.when.seconds, EXPECTED_CH_WHEN_SECONDS);
    cr_assert_eq((pb_u32)decoded.when.unit, EXPECTED_CH_WHEN_UNIT);
}

// repeated string and bytes: the stored TextLists of scalars.proto and the callback-driven CallbackChunks
Test(sample_single, repeated_bytes_round_trip) {
    test_callback_chunks_reset(0U);
    test_io_reset();

    scalarpkg_TextLists_WrHandle lists = scalarpkg_TextLists_create();
    scalarpkg_TextLists_text_WrHandle text = scalarpkg_TextLists_add_text(&lists);
    scalarpkg_TextLists_text_addBytes(&text, (const pb_u8*)"abc", 3U);
    scalarpkg_TextLists_text_done(&text);
    text = scalarpkg_TextLists_add_text(&lists);
    scalarpkg_TextLists_text_done(&text);

    cr_assert(!test_io_has_write_overflow());
    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    scalarpkg_TextLists decoded;
    scalarpkg_TextLists_decode(&decoded);
    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(decoded.text.count, 2U);
    cr_assert_eq(decoded.text.item[0].length, 3U);
    cr_assert_eq(memcmp(decoded.text.item[0].data, "abc", 3U), 0);
    cr_assert_eq(decoded.text.item[1].length, 0U);

    test_io_reset();
    callbackpkg_CallbackChunks_WrHandle chunks = callbackpkg_CallbackChunks_create();
    callbackpkg_CallbackChunks_chunks_WrHandle chunk = callbackpkg_CallbackChunks_add_chunks(&chunks);
    callbackpkg_CallbackChunks_chunks_addBytes(&chunk, (const pb_u8*)"xy", 2U);
    callbackpkg_CallbackChunks_chunks_done(&chunk);

    cr_assert(!test_io_has_write_overflow());
    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    callbackpkg_CallbackChunks decoded_chunks;
    callbackpkg_CallbackChunks_decode(&decoded_chunks);
    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(test_callback_chunks_call_count(), 1U);
    cr_assert_eq(test_callback_chunks_length(0U), 2U);
    cr_assert_eq(test_callback_chunks_byte(0U, 1U), (pb_u8)'y');
}
