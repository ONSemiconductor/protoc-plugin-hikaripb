#include <criterion/criterion.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "expected_values.h"
#include "test_io.h"
#include "sample_message.pb.h"
#include "sample_scalars.pb.h"

// Encodes a SampleMessage with the shared expected values, verifies a local
// decode round-trip, then exports the raw bytes so test/py/check_interop.py
// can cross-check them against the generated Python bindings (no nanopb involved).
Test(sample_encode, roundtrip_and_export) {
    static const pb_u8 expected_payload[] = {
        EXPECTED_PAYLOAD_BYTE_0,
        EXPECTED_PAYLOAD_BYTE_1,
        EXPECTED_PAYLOAD_BYTE_2,
        EXPECTED_PAYLOAD_BYTE_3,
    };

    test_io_reset();

    samplepkg_SampleMessage_WrHandle root = samplepkg_SampleMessage_create();
    samplepkg_SampleMessage_set_opt_value(&root, EXPECTED_OPT_VALUE);
    samplepkg_SampleMessage_set_opt_uint(&root, EXPECTED_OPT_UINT);
    samplepkg_SampleMessage_set_flag(&root, EXPECTED_FLAG);
    samplepkg_SampleMessage_set_color(&root, (samplepkg_Color)EXPECTED_COLOR);
    samplepkg_SampleMessage_set_choice_u32(&root, EXPECTED_CHOICE_U32);

    samplepkg_Point_WrHandle location = samplepkg_SampleMessage_add_location(&root);
    samplepkg_Point_set_x(&location, EXPECTED_LOCATION_X);
    samplepkg_Point_set_y(&location, EXPECTED_LOCATION_Y);
    samplepkg_Point_destroy_submessage(&location);

    samplepkg_SampleMessage_payload_WrHandle payload = samplepkg_SampleMessage_add_payload(&root);
    samplepkg_SampleMessage_payload_addBytes(&payload, expected_payload, (pb_u16)EXPECTED_PAYLOAD_LENGTH);
    samplepkg_SampleMessage_payload_done(&payload);

    samplepkg_SampleMessage_tags_WrHandle tags = samplepkg_SampleMessage_add_tags(&root);
    samplepkg_SampleMessage_tags_add(&tags, (samplepkg_Color)EXPECTED_TAG_0);
    samplepkg_SampleMessage_tags_add(&tags, (samplepkg_Color)EXPECTED_TAG_1);
    samplepkg_SampleMessage_tags_done(&tags);

    samplepkg_Item_WrHandle item0 = samplepkg_SampleMessage_add_items(&root);
    samplepkg_Item_set_item_id(&item0, EXPECTED_ITEM0_ID);
    samplepkg_Item_set_checksum(&item0, EXPECTED_ITEM0_CHECKSUM);
    samplepkg_Item_set_kind(&item0, (samplepkg_ItemKind)EXPECTED_ITEM0_KIND);
    samplepkg_Item_destroy_submessage(&item0);

    samplepkg_Item_WrHandle item1 = samplepkg_SampleMessage_add_items(&root);
    samplepkg_Item_set_item_id(&item1, EXPECTED_ITEM1_ID);
    samplepkg_Item_set_checksum(&item1, EXPECTED_ITEM1_CHECKSUM);
    samplepkg_Item_set_kind(&item1, (samplepkg_ItemKind)EXPECTED_ITEM1_KIND);
    samplepkg_Item_destroy_submessage(&item1);

    samplepkg_SampleMessage_numbers_WrHandle numbers = samplepkg_SampleMessage_add_numbers(&root);
    samplepkg_SampleMessage_numbers_add(&numbers, EXPECTED_NUMBER_0);
    samplepkg_SampleMessage_numbers_add(&numbers, EXPECTED_NUMBER_1);
    samplepkg_SampleMessage_numbers_add(&numbers, EXPECTED_NUMBER_2);
    samplepkg_SampleMessage_numbers_done(&numbers);

    samplepkg_SampleMessage_label_WrHandle label = samplepkg_SampleMessage_add_label(&root);
    samplepkg_SampleMessage_label_addBytes(&label, (const pb_u8*)EXPECTED_LABEL, (pb_u16)EXPECTED_LABEL_LENGTH);
    samplepkg_SampleMessage_label_done(&label);

    samplepkg_Metadata_WrHandle metadata = samplepkg_SampleMessage_add_metadata(&root);
    samplepkg_Metadata_set_kind(&metadata, (samplepkg_MetadataKind)EXPECTED_METADATA_KIND);
    samplepkg_Metadata_set_revision(&metadata, EXPECTED_METADATA_REVISION);
    samplepkg_Metadata_destroy_submessage(&metadata);

    samplepkg_SparseTags_WrHandle sparse_tags = samplepkg_SampleMessage_add_sparse_tags(&root);
    samplepkg_SparseTags_set_tag_1(&sparse_tags, EXPECTED_SPARSE_TAG_1);
    samplepkg_SparseTags_set_tag_25(&sparse_tags, EXPECTED_SPARSE_TAG_25);
    samplepkg_SparseTags_set_tag_75(&sparse_tags, EXPECTED_SPARSE_TAG_75);
    samplepkg_SparseTags_set_tag_150(&sparse_tags, EXPECTED_SPARSE_TAG_150);
    samplepkg_SparseTags_set_tag_200(&sparse_tags, EXPECTED_SPARSE_TAG_200);
    samplepkg_SparseTags_destroy_submessage(&sparse_tags);

    cr_assert(!test_io_has_write_overflow(), "encoder write buffer overflowed");

    const pb_u8* encoded = test_io_get_write_buffer();
    const pb_u32 encoded_len = test_io_get_write_length();
    cr_assert(encoded_len > 0U, "no payload encoded");

    // Local round-trip: decode what we just encoded and compare a few fields.
    test_io_set_read_buffer(encoded, encoded_len);
    samplepkg_SampleMessage decoded;
    samplepkg_SampleMessage_clear(&decoded);
    samplepkg_SampleMessage_decode(&decoded);
    cr_assert_eq(decoded.opt_value, EXPECTED_OPT_VALUE);
    cr_assert_eq(decoded.location.x, EXPECTED_LOCATION_X);
    cr_assert_eq(decoded.sparse_tags.tag_1, EXPECTED_SPARSE_TAG_1);
    cr_assert_eq(decoded.sparse_tags.tag_75, EXPECTED_SPARSE_TAG_75);
    cr_assert_eq(decoded.sparse_tags.tag_200, EXPECTED_SPARSE_TAG_200);

    // Export the C-encoded bytes for the Python interop check.
    const char* out_dir = getenv("SAMPLE_INTEROP_DIR");
    if (out_dir == NULL) {
        out_dir = ".";
    }
    char out_path[512];
    snprintf(out_path, sizeof(out_path), "%s/encoded_from_c.bin", out_dir);

    FILE* f = fopen(out_path, "wb");
    cr_assert(f != NULL, "could not open %s for writing", out_path);
    cr_assert_eq(fwrite(encoded, 1, encoded_len, f), encoded_len);
    fclose(f);
}

// Writes encoded bytes to <SAMPLE_INTEROP_DIR>/<name> for test/py/check_interop.py.
static void export_bytes(const char* name, const pb_u8* data, pb_u32 len) {
    const char* out_dir = getenv("SAMPLE_INTEROP_DIR");
    if (out_dir == NULL) {
        out_dir = ".";
    }
    char out_path[512];
    snprintf(out_path, sizeof(out_path), "%s/%s", out_dir, name);

    FILE* f = fopen(out_path, "wb");
    cr_assert(f != NULL, "could not open %s for writing", out_path);
    cr_assert_eq(fwrite(data, 1, len, f), len);
    fclose(f);
}

// scalars.proto: the same flow for every scalar type (explicit zero/false included), a oneof member and the
// messages of shared/common.proto.
Test(sample_encode, scalars_roundtrip_and_export) {
    static const pb_u8 blob[] = EXPECTED_SC_BLOB;

    test_io_reset();

    scalarpkg_Scalars_WrHandle root = scalarpkg_Scalars_create();
    scalarpkg_Scalars_set_u32(&root, EXPECTED_SC_U32);
    scalarpkg_Scalars_set_s32(&root, EXPECTED_SC_S32);
    scalarpkg_Scalars_set_f32(&root, EXPECTED_SC_F32);
    scalarpkg_Scalars_set_sf32(&root, EXPECTED_SC_SF32);
    scalarpkg_Scalars_set_flt(&root, EXPECTED_SC_FLT);
    scalarpkg_Scalars_set_flag(&root, EXPECTED_SC_FLAG);
    scalarpkg_Scalars_set_level(&root, (scalarpkg_Level)EXPECTED_SC_LEVEL);

    scalarpkg_Scalars_text_WrHandle text = scalarpkg_Scalars_add_text(&root);
    scalarpkg_Scalars_text_addBytes(&text, (const pb_u8*)EXPECTED_SC_TEXT, (pb_u16)EXPECTED_SC_TEXT_LENGTH);
    scalarpkg_Scalars_text_done(&text);

    scalarpkg_Scalars_blob_WrHandle blob_hdl = scalarpkg_Scalars_add_blob(&root);
    scalarpkg_Scalars_blob_addBytes(&blob_hdl, blob, (pb_u16)EXPECTED_SC_BLOB_LENGTH);
    scalarpkg_Scalars_blob_done(&blob_hdl);

    scalarpkg_Scalars_set_opt_u32(&root, EXPECTED_SC_OPT_U32);

    scalarpkg_Scalars_opt_text_WrHandle opt_text = scalarpkg_Scalars_add_opt_text(&root);
    scalarpkg_Scalars_opt_text_addBytes(&opt_text, (const pb_u8*)EXPECTED_SC_OPT_TEXT,
                                        (pb_u16)EXPECTED_SC_OPT_TEXT_LENGTH);
    scalarpkg_Scalars_opt_text_done(&opt_text);

    scalarpkg_Scalars_set_opt_level(&root, (scalarpkg_Level)EXPECTED_SC_OPT_LEVEL);
    scalarpkg_Scalars_set_opt_flt(&root, EXPECTED_SC_OPT_FLT);
    scalarpkg_Scalars_set_opt_flag(&root, EXPECTED_SC_OPT_FLAG);
    scalarpkg_Scalars_set_from(&root, EXPECTED_SC_FROM);

    scalarpkg_Scalars_serialize_WrHandle serialize = scalarpkg_Scalars_add_serialize(&root);
    scalarpkg_Scalars_serialize_addBytes(&serialize, (const pb_u8*)EXPECTED_SC_SERIALIZE,
                                         (pb_u16)EXPECTED_SC_SERIALIZE_LENGTH);
    scalarpkg_Scalars_serialize_done(&serialize);

    scalarpkg_Scalars_clear_WrHandle clear = scalarpkg_Scalars_add_clear(&root);
    scalarpkg_Scalars_clear_addBytes(&clear, (const pb_u8*)EXPECTED_SC_CLEAR, (pb_u16)EXPECTED_SC_CLEAR_LENGTH);
    scalarpkg_Scalars_clear_done(&clear);

    cr_assert(!test_io_has_write_overflow(), "encoder write buffer overflowed");
    const pb_u8* encoded = test_io_get_write_buffer();
    const pb_u32 encoded_len = test_io_get_write_length();
    cr_assert(encoded_len > 0U, "no payload encoded");

    test_io_set_read_buffer(encoded, encoded_len);
    scalarpkg_Scalars decoded;
    scalarpkg_Scalars_clear(&decoded);
    scalarpkg_Scalars_decode(&decoded);
    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(decoded.u32, EXPECTED_SC_U32);
    cr_assert_eq(decoded.s32, EXPECTED_SC_S32);
    cr_assert(scalarpkg_Scalars_has_opt_u32(&decoded));
    cr_assert_eq(decoded.opt_u32, EXPECTED_SC_OPT_U32);

    export_bytes("scalars_from_c.bin", encoded, encoded_len);
}

Test(sample_encode, choice_roundtrip_and_export) {
    test_io_reset();

    scalarpkg_Choice_WrHandle root = scalarpkg_Choice_create();
    scalarpkg_Choice_text_WrHandle text = scalarpkg_Choice_add_text(&root);
    scalarpkg_Choice_text_addBytes(&text, (const pb_u8*)EXPECTED_CH_TEXT, (pb_u16)EXPECTED_CH_TEXT_LENGTH);
    scalarpkg_Choice_text_done(&text);

    shared_Stamp_WrHandle extra = scalarpkg_Choice_add_extra(&root);
    shared_Stamp_set_seconds(&extra, EXPECTED_CH_EXTRA_SECONDS);
    shared_Stamp_set_nanos(&extra, EXPECTED_CH_EXTRA_NANOS);
    shared_Stamp_set_unit(&extra, (shared_Unit)EXPECTED_CH_EXTRA_UNIT);
    shared_Stamp_destroy_submessage(&extra);

    shared_Stamp_WrHandle when = scalarpkg_Choice_add_when(&root);
    shared_Stamp_set_seconds(&when, EXPECTED_CH_WHEN_SECONDS);
    shared_Stamp_set_nanos(&when, EXPECTED_CH_WHEN_NANOS);
    shared_Stamp_set_unit(&when, (shared_Unit)EXPECTED_CH_WHEN_UNIT);
    shared_Stamp_destroy_submessage(&when);

    cr_assert(!test_io_has_write_overflow(), "encoder write buffer overflowed");
    const pb_u8* encoded = test_io_get_write_buffer();
    const pb_u32 encoded_len = test_io_get_write_length();
    cr_assert(encoded_len > 0U, "no payload encoded");

    test_io_set_read_buffer(encoded, encoded_len);
    scalarpkg_Choice decoded;
    scalarpkg_Choice_clear(&decoded);
    scalarpkg_Choice_decode(&decoded);
    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert(scalarpkg_Choice_has_text(&decoded));
    cr_assert(scalarpkg_Choice_has_extra(&decoded));
    cr_assert_eq(decoded.when.seconds, EXPECTED_CH_WHEN_SECONDS);

    export_bytes("choice_from_c.bin", encoded, encoded_len);
}

// Adds every element of the EXPECTED_RP_<NAME> list to the repeated field <name> of a Repeats message.
#define WRITE_LIST(root, name, type, values)                                           \
    do {                                                                               \
        static const type list[] = values;                                             \
        scalarpkg_Repeats_##name##_WrHandle hdl = scalarpkg_Repeats_add_##name(&root); \
        for (pb_u32 i = 0U; i < (pb_u32)(sizeof(list) / sizeof(list[0])); i++) {       \
            scalarpkg_Repeats_##name##_add(&hdl, list[i]);                             \
        }                                                                              \
        scalarpkg_Repeats_##name##_done(&hdl);                                         \
    } while (0)

Test(sample_encode, repeats_roundtrip_and_export) {
    static const pb_u32 stamp_seconds[] = EXPECTED_RP_STAMP_SECONDS;
    static const pb_u32 stamp_units[] = EXPECTED_RP_STAMP_UNIT;

    test_io_reset();

    scalarpkg_Repeats_WrHandle root = scalarpkg_Repeats_create();
    WRITE_LIST(root, u32, pb_u32, EXPECTED_RP_U32);
    WRITE_LIST(root, s32, pb_s32, EXPECTED_RP_S32);
    WRITE_LIST(root, f32, pb_u32, EXPECTED_RP_F32);
    WRITE_LIST(root, sf32, pb_s32, EXPECTED_RP_SF32);
    WRITE_LIST(root, flt, float, EXPECTED_RP_FLT);
    WRITE_LIST(root, flag, pb_bool, EXPECTED_RP_FLAG);
    WRITE_LIST(root, level, scalarpkg_Level, EXPECTED_RP_LEVEL);
    for (pb_u32 i = 0U; i < (pb_u32)(sizeof(stamp_seconds) / sizeof(stamp_seconds[0])); i++) {
        shared_Stamp_WrHandle stamp = scalarpkg_Repeats_add_stamps(&root);
        shared_Stamp_set_seconds(&stamp, stamp_seconds[i]);
        shared_Stamp_set_unit(&stamp, (shared_Unit)stamp_units[i]);
        shared_Stamp_destroy_submessage(&stamp);
    }

    cr_assert(!test_io_has_write_overflow(), "encoder write buffer overflowed");
    const pb_u8* encoded = test_io_get_write_buffer();
    const pb_u32 encoded_len = test_io_get_write_length();
    cr_assert(encoded_len > 0U, "no payload encoded");

    test_io_set_read_buffer(encoded, encoded_len);
    scalarpkg_Repeats decoded;
    scalarpkg_Repeats_clear(&decoded);
    scalarpkg_Repeats_decode(&decoded);
    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(decoded.u32.count, 3U);
    cr_assert_eq(decoded.stamps.count, 2U);

    export_bytes("repeats_from_c.bin", encoded, encoded_len);
}

// Repeated string and bytes: every element is written by its own add_<field>() call, an empty one is kept.
Test(sample_encode, textlists_roundtrip_and_export) {
    static const char* const texts[] = EXPECTED_TL_TEXT;
    static const pb_u8 blob_0[] = EXPECTED_TL_BLOB_0;
    static const pb_u8 blob_2[] = EXPECTED_TL_BLOB_2;

    test_io_reset();

    scalarpkg_TextLists_WrHandle root = scalarpkg_TextLists_create();
    for (pb_u32 i = 0U; i < (pb_u32)(sizeof(texts) / sizeof(texts[0])); i++) {
        scalarpkg_TextLists_text_WrHandle text = scalarpkg_TextLists_add_text(&root);
        scalarpkg_TextLists_text_addBytes(&text, (const pb_u8*)texts[i], (pb_u16)strlen(texts[i]));
        scalarpkg_TextLists_text_done(&text);
    }
    scalarpkg_TextLists_blob_WrHandle blob = scalarpkg_TextLists_add_blob(&root);
    scalarpkg_TextLists_blob_addBytes(&blob, blob_0, (pb_u16)sizeof(blob_0));
    scalarpkg_TextLists_blob_done(&blob);
    blob = scalarpkg_TextLists_add_blob(&root);
    scalarpkg_TextLists_blob_done(&blob);
    blob = scalarpkg_TextLists_add_blob(&root);
    scalarpkg_TextLists_blob_addBytes(&blob, blob_2, (pb_u16)sizeof(blob_2));
    scalarpkg_TextLists_blob_done(&blob);

    cr_assert(!test_io_has_write_overflow(), "encoder write buffer overflowed");
    const pb_u8* encoded = test_io_get_write_buffer();
    const pb_u32 encoded_len = test_io_get_write_length();
    cr_assert(encoded_len > 0U, "no payload encoded");

    test_io_set_read_buffer(encoded, encoded_len);
    scalarpkg_TextLists decoded;
    scalarpkg_TextLists_clear(&decoded);
    scalarpkg_TextLists_decode(&decoded);
    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(decoded.text.count, 3U);
    cr_assert_eq(decoded.text.item[2].length, 5U);
    cr_assert_eq(memcmp(decoded.text.item[2].data, "third", 5U), 0);
    cr_assert_eq(decoded.blob.count, 3U);
    cr_assert_eq(decoded.blob.item[1].length, 0U);

    export_bytes("textlists_from_c.bin", encoded, encoded_len);
}

Test(sample_encode, uint32_extend_pads_the_varint_to_its_length) {
    // the value as a varint of exactly len bytes: the bytes in front of the last have the continuation bit
    static const struct {
        pb_u32 value;
        pb_u8 len;
        pb_u8 bytes[5];
    } cases[] = {
        {1U, 3U, {0x81U, 0x80U, 0x00U}},
        {300U, 2U, {0xACU, 0x02U}},
        {300U, 4U, {0xACU, 0x82U, 0x80U, 0x00U}},
        {0xFFFFFFFFU, 5U, {0xFFU, 0xFFU, 0xFFU, 0xFFU, 0x0FU}},
        {7U, 0U, {0U}},
    };

    for (pb_u32 i = 0U; i < (pb_u32)(sizeof(cases) / sizeof(cases[0])); i++) {
        test_io_reset();
        sample_encode_uint32_extend(cases[i].value, cases[i].len);

        cr_assert_eq(test_io_get_write_length(), (pb_u32)cases[i].len, "case %u", i);
        cr_assert_eq(memcmp(test_io_get_write_buffer(), cases[i].bytes, cases[i].len), 0, "case %u", i);
    }
}

Test(sample_encode, uint32_extend_is_cut_to_the_five_bytes_of_a_varint) {
    // the length is asserted to be at most 5; with the assertion off (as in the tests) it is cut to 5
    static const pb_u8 expected[] = {0x81U, 0x80U, 0x80U, 0x80U, 0x00U};

    test_io_reset();
    sample_encode_uint32_extend(1U, 7U);

    cr_assert_eq(test_io_get_write_length(), (pb_u32)sizeof(expected));
    cr_assert_eq(memcmp(test_io_get_write_buffer(), expected, sizeof(expected)), 0);
}

Test(sample_encode, uint32_extend_is_decoded) {
    // u32 (field 1) of Scalars with the value 300 padded to 4 bytes
    test_io_reset();
    sample_encode_varint_u32(0x08U);
    sample_encode_uint32_extend(300U, 4U);
    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    scalarpkg_Scalars decoded;
    scalarpkg_Scalars_clear(&decoded);
    scalarpkg_Scalars_decode(&decoded);

    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(decoded.u32, 300U);
}
