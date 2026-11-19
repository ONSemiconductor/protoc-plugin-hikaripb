#include <criterion/criterion.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "expected_values.h"
#include "test_io.h"
#include "sample_message.pb.h"
#include "sample_scalars.pb.h"

// Reads the bytes exported by test/py/check_interop.py (produced with the
// generated Python bindings + default google protobuf python_out) and decodes
// them with the generated C API, closing the loop on cross-language interop.
Test(sample_decode, import_from_python) {
    const char* in_dir = getenv("SAMPLE_INTEROP_DIR");
    if (in_dir == NULL) {
        in_dir = ".";
    }
    char in_path[512];
    snprintf(in_path, sizeof(in_path), "%s/encoded_from_python.bin", in_dir);

    FILE* f = fopen(in_path, "rb");
    cr_assert(f != NULL, "could not open %s for reading (run the python interop step first)", in_path);

    static pb_u8 buffer[2048];
    size_t read_len = fread(buffer, 1, sizeof(buffer), f);
    fclose(f);
    cr_assert(read_len > 0U, "python-encoded payload is empty");

    test_io_reset();
    test_io_set_read_buffer(buffer, (pb_u32)read_len);

    samplepkg_SampleMessage decoded;
    samplepkg_SampleMessage_clear(&decoded);
    samplepkg_SampleMessage_decode(&decoded);

    cr_assert(samplepkg_SampleMessage_has_opt_value(&decoded));
    cr_assert_eq(decoded.opt_value, EXPECTED_OPT_VALUE);
    cr_assert(samplepkg_SampleMessage_has_opt_uint(&decoded));
    cr_assert_eq(decoded.opt_uint, EXPECTED_OPT_UINT);
    cr_assert_eq(decoded.flag, EXPECTED_FLAG);
    cr_assert_eq((pb_u32)decoded.color, EXPECTED_COLOR);

    cr_assert(samplepkg_SampleMessage_has_location(&decoded));
    cr_assert_eq(decoded.location.x, EXPECTED_LOCATION_X);
    cr_assert_eq(decoded.location.y, EXPECTED_LOCATION_Y);

    cr_assert(samplepkg_SampleMessage_has_payload(&decoded));
    cr_assert_eq(decoded.payload.length, EXPECTED_PAYLOAD_LENGTH);
    cr_assert_eq(decoded.payload.data[0], EXPECTED_PAYLOAD_BYTE_0);
    cr_assert_eq(decoded.payload.data[1], EXPECTED_PAYLOAD_BYTE_1);
    cr_assert_eq(decoded.payload.data[2], EXPECTED_PAYLOAD_BYTE_2);
    cr_assert_eq(decoded.payload.data[3], EXPECTED_PAYLOAD_BYTE_3);

    cr_assert(samplepkg_SampleMessage_has_choice(&decoded));
    cr_assert(samplepkg_SampleMessage_has_choice_u32(&decoded));
    cr_assert_eq(decoded.choice.choice_u32, EXPECTED_CHOICE_U32);

    cr_assert_eq(decoded.tags.count, EXPECTED_TAGS_COUNT);
    cr_assert_eq((pb_u32)decoded.tags.item[0], EXPECTED_TAG_0);
    cr_assert_eq((pb_u32)decoded.tags.item[1], EXPECTED_TAG_1);

    cr_assert_eq(decoded.items.count, EXPECTED_ITEMS_COUNT);
    cr_assert_eq(decoded.items.item[0].item_id, EXPECTED_ITEM0_ID);
    cr_assert_eq(decoded.items.item[0].checksum, EXPECTED_ITEM0_CHECKSUM);
    cr_assert_eq((pb_u32)decoded.items.item[0].kind, EXPECTED_ITEM0_KIND);
    cr_assert_eq(decoded.items.item[1].item_id, EXPECTED_ITEM1_ID);
    cr_assert_eq(decoded.items.item[1].checksum, EXPECTED_ITEM1_CHECKSUM);
    cr_assert_eq((pb_u32)decoded.items.item[1].kind, EXPECTED_ITEM1_KIND);

    cr_assert_eq(decoded.numbers.count, EXPECTED_NUMBERS_COUNT);
    cr_assert_eq(decoded.numbers.item[0], EXPECTED_NUMBER_0);
    cr_assert_eq(decoded.numbers.item[1], EXPECTED_NUMBER_1);
    cr_assert_eq(decoded.numbers.item[2], EXPECTED_NUMBER_2);

    cr_assert(samplepkg_SampleMessage_has_label(&decoded));
    cr_assert_eq(decoded.label.length, EXPECTED_LABEL_LENGTH);
    cr_assert_eq(memcmp(decoded.label.data, EXPECTED_LABEL, EXPECTED_LABEL_LENGTH), 0);

    cr_assert(samplepkg_SampleMessage_has_metadata(&decoded));
    cr_assert_eq((pb_u32)decoded.metadata.kind, EXPECTED_METADATA_KIND);
    cr_assert(samplepkg_Metadata_has_revision(&decoded.metadata));
    cr_assert_eq(decoded.metadata.revision, EXPECTED_METADATA_REVISION);

    cr_assert(samplepkg_SampleMessage_has_sparse_tags(&decoded));
    cr_assert_eq(decoded.sparse_tags.tag_1, EXPECTED_SPARSE_TAG_1);
    cr_assert_eq(decoded.sparse_tags.tag_25, EXPECTED_SPARSE_TAG_25);
    cr_assert_eq(decoded.sparse_tags.tag_75, EXPECTED_SPARSE_TAG_75);
    cr_assert_eq(decoded.sparse_tags.tag_150, EXPECTED_SPARSE_TAG_150);
    cr_assert_eq(decoded.sparse_tags.tag_200, EXPECTED_SPARSE_TAG_200);
}

// Loads <SAMPLE_INTEROP_DIR>/<name> (written by test/py/check_interop.py) into the shared read buffer of the test io.
static void import_bytes(const char* name) {
    const char* in_dir = getenv("SAMPLE_INTEROP_DIR");
    if (in_dir == NULL) {
        in_dir = ".";
    }
    char in_path[512];
    snprintf(in_path, sizeof(in_path), "%s/%s", in_dir, name);

    FILE* f = fopen(in_path, "rb");
    cr_assert(f != NULL, "could not open %s for reading (run the python interop step first)", in_path);

    static pb_u8 buffer[2048];
    size_t read_len = fread(buffer, 1, sizeof(buffer), f);
    fclose(f);
    cr_assert(read_len > 0U, "python-encoded payload %s is empty", name);

    test_io_reset();
    test_io_set_read_buffer(buffer, (pb_u32)read_len);
}

Test(sample_decode, scalars_import_from_python) {
    static const pb_u8 expected_blob[] = EXPECTED_SC_BLOB;

    import_bytes("scalars_from_python.bin");
    scalarpkg_Scalars decoded;
    scalarpkg_Scalars_clear(&decoded);
    scalarpkg_Scalars_decode(&decoded);
    cr_assert(!sample_hasError(), "decode error %d", sample_getError());

    cr_assert_eq(decoded.u32, EXPECTED_SC_U32);
    cr_assert_eq(decoded.s32, EXPECTED_SC_S32);
    cr_assert_eq(decoded.f32, EXPECTED_SC_F32);
    cr_assert_eq(decoded.sf32, EXPECTED_SC_SF32);
    cr_assert(decoded.flt == EXPECTED_SC_FLT);
    cr_assert_eq(decoded.flag, EXPECTED_SC_FLAG);
    cr_assert_eq((pb_u32)decoded.level, EXPECTED_SC_LEVEL);

    cr_assert(scalarpkg_Scalars_has_text(&decoded));
    cr_assert_eq(decoded.text.length, EXPECTED_SC_TEXT_LENGTH);
    cr_assert_eq(memcmp(decoded.text.data, EXPECTED_SC_TEXT, EXPECTED_SC_TEXT_LENGTH), 0);
    cr_assert(scalarpkg_Scalars_has_blob(&decoded));
    cr_assert_eq(decoded.blob.length, EXPECTED_SC_BLOB_LENGTH);
    cr_assert_eq(memcmp(decoded.blob.data, expected_blob, EXPECTED_SC_BLOB_LENGTH), 0);

    // explicit presence: zero and false are present, not just default
    cr_assert(scalarpkg_Scalars_has_opt_u32(&decoded));
    cr_assert_eq(decoded.opt_u32, EXPECTED_SC_OPT_U32);
    cr_assert(scalarpkg_Scalars_has_opt_text(&decoded));
    cr_assert_eq(decoded.opt_text.length, EXPECTED_SC_OPT_TEXT_LENGTH);
    cr_assert_eq(memcmp(decoded.opt_text.data, EXPECTED_SC_OPT_TEXT, EXPECTED_SC_OPT_TEXT_LENGTH), 0);
    cr_assert(scalarpkg_Scalars_has_opt_level(&decoded));
    cr_assert_eq((pb_u32)decoded.opt_level, EXPECTED_SC_OPT_LEVEL);
    cr_assert(scalarpkg_Scalars_has_opt_flt(&decoded));
    cr_assert(decoded.opt_flt == EXPECTED_SC_OPT_FLT);
    cr_assert(scalarpkg_Scalars_has_opt_flag(&decoded));
    cr_assert_eq(decoded.opt_flag, EXPECTED_SC_OPT_FLAG);

    cr_assert_eq(decoded.from, EXPECTED_SC_FROM);
    cr_assert(scalarpkg_Scalars_has_serialize(&decoded));
    cr_assert_eq(decoded.serialize.length, EXPECTED_SC_SERIALIZE_LENGTH);
    cr_assert_eq(memcmp(decoded.serialize.data, EXPECTED_SC_SERIALIZE, EXPECTED_SC_SERIALIZE_LENGTH), 0);
    cr_assert(scalarpkg_Scalars_has_clear(&decoded));
    cr_assert_eq(decoded.clear.length, EXPECTED_SC_CLEAR_LENGTH);
    cr_assert_eq(memcmp(decoded.clear.data, EXPECTED_SC_CLEAR, EXPECTED_SC_CLEAR_LENGTH), 0);
}

Test(sample_decode, choice_import_from_python) {
    import_bytes("choice_from_python.bin");
    scalarpkg_Choice decoded;
    scalarpkg_Choice_clear(&decoded);
    scalarpkg_Choice_decode(&decoded);
    cr_assert(!sample_hasError(), "decode error %d", sample_getError());

    cr_assert(scalarpkg_Choice_has_value(&decoded));
    cr_assert(scalarpkg_Choice_has_text(&decoded));
    cr_assert(!scalarpkg_Choice_has_number(&decoded));
    cr_assert_eq(decoded.value.text.length, EXPECTED_CH_TEXT_LENGTH);
    cr_assert_eq(memcmp(decoded.value.text.data, EXPECTED_CH_TEXT, EXPECTED_CH_TEXT_LENGTH), 0);

    cr_assert(scalarpkg_Choice_has_extra(&decoded));
    cr_assert_eq(decoded.extra.seconds, EXPECTED_CH_EXTRA_SECONDS);
    cr_assert_eq(decoded.extra.nanos, EXPECTED_CH_EXTRA_NANOS);
    cr_assert_eq((pb_u32)decoded.extra.unit, EXPECTED_CH_EXTRA_UNIT);
    cr_assert(scalarpkg_Choice_has_when(&decoded));
    cr_assert_eq(decoded.when.seconds, EXPECTED_CH_WHEN_SECONDS);
    cr_assert_eq(decoded.when.nanos, EXPECTED_CH_WHEN_NANOS);
    cr_assert_eq((pb_u32)decoded.when.unit, EXPECTED_CH_WHEN_UNIT);
}

Test(sample_decode, repeats_import_from_python) {
    static const pb_u32 u32s[] = EXPECTED_RP_U32;
    static const pb_s32 s32s[] = EXPECTED_RP_S32;
    static const pb_u32 f32s[] = EXPECTED_RP_F32;
    static const pb_s32 sf32s[] = EXPECTED_RP_SF32;
    static const float flts[] = EXPECTED_RP_FLT;
    static const pb_bool flags[] = EXPECTED_RP_FLAG;
    static const pb_u32 levels[] = EXPECTED_RP_LEVEL;
    static const pb_u32 stamp_seconds[] = EXPECTED_RP_STAMP_SECONDS;
    static const pb_u32 stamp_units[] = EXPECTED_RP_STAMP_UNIT;

    import_bytes("repeats_from_python.bin");
    scalarpkg_Repeats decoded;
    scalarpkg_Repeats_clear(&decoded);
    scalarpkg_Repeats_decode(&decoded);
    cr_assert(!sample_hasError(), "decode error %d", sample_getError());

    cr_assert_eq(decoded.u32.count, sizeof(u32s) / sizeof(u32s[0]));
    for (pb_u32 i = 0U; i < decoded.u32.count; i++) {
        cr_assert_eq(decoded.u32.item[i], u32s[i], "u32[%u]", i);
    }
    cr_assert_eq(decoded.s32.count, sizeof(s32s) / sizeof(s32s[0]));
    for (pb_u32 i = 0U; i < decoded.s32.count; i++) {
        cr_assert_eq(decoded.s32.item[i], s32s[i], "s32[%u]", i);
    }
    cr_assert_eq(decoded.f32.count, sizeof(f32s) / sizeof(f32s[0]));
    for (pb_u32 i = 0U; i < decoded.f32.count; i++) {
        cr_assert_eq(decoded.f32.item[i], f32s[i], "f32[%u]", i);
    }
    cr_assert_eq(decoded.sf32.count, sizeof(sf32s) / sizeof(sf32s[0]));
    for (pb_u32 i = 0U; i < decoded.sf32.count; i++) {
        cr_assert_eq(decoded.sf32.item[i], sf32s[i], "sf32[%u]", i);
    }
    cr_assert_eq(decoded.flt.count, sizeof(flts) / sizeof(flts[0]));
    for (pb_u32 i = 0U; i < decoded.flt.count; i++) {
        cr_assert(decoded.flt.item[i] == flts[i], "flt[%u]", i);
    }
    cr_assert_eq(decoded.flag.count, sizeof(flags) / sizeof(flags[0]));
    for (pb_u32 i = 0U; i < decoded.flag.count; i++) {
        cr_assert_eq(decoded.flag.item[i], flags[i], "flag[%u]", i);
    }
    cr_assert_eq(decoded.level.count, sizeof(levels) / sizeof(levels[0]));
    for (pb_u32 i = 0U; i < decoded.level.count; i++) {
        cr_assert_eq((pb_u32)decoded.level.item[i], levels[i], "level[%u]", i);
    }
    cr_assert_eq(decoded.stamps.count, sizeof(stamp_seconds) / sizeof(stamp_seconds[0]));
    for (pb_u32 i = 0U; i < decoded.stamps.count; i++) {
        cr_assert_eq(decoded.stamps.item[i].seconds, stamp_seconds[i], "stamps[%u].seconds", i);
        cr_assert_eq((pb_u32)decoded.stamps.item[i].unit, stamp_units[i], "stamps[%u].unit", i);
    }
}

Test(sample_decode, textlists_import_from_python) {
    static const char* const texts[] = EXPECTED_TL_TEXT;
    static const pb_u8 blob_0[] = EXPECTED_TL_BLOB_0;
    static const pb_u8 blob_2[] = EXPECTED_TL_BLOB_2;

    import_bytes("textlists_from_python.bin");
    scalarpkg_TextLists decoded;
    scalarpkg_TextLists_clear(&decoded);
    scalarpkg_TextLists_decode(&decoded);
    cr_assert(!sample_hasError(), "decode error %d", sample_getError());

    cr_assert_eq(decoded.text.count, sizeof(texts) / sizeof(texts[0]));
    for (pb_u32 i = 0U; i < decoded.text.count; i++) {
        cr_assert_eq(decoded.text.item[i].length, strlen(texts[i]), "text[%u] length", i);
        cr_assert_eq(memcmp(decoded.text.item[i].data, texts[i], decoded.text.item[i].length), 0, "text[%u]", i);
    }
    cr_assert_eq(decoded.blob.count, 3U);
    cr_assert_eq(decoded.blob.item[0].length, sizeof(blob_0));
    cr_assert_eq(memcmp(decoded.blob.item[0].data, blob_0, sizeof(blob_0)), 0);
    cr_assert_eq(decoded.blob.item[1].length, 0U);
    cr_assert_eq(decoded.blob.item[2].length, sizeof(blob_2));
    cr_assert_eq(memcmp(decoded.blob.item[2].data, blob_2, sizeof(blob_2)), 0);
}

// Hand-written wire bytes: the elements of the two fields are interleaved, two lengths are padded varints
// (as the encoders write them), there is an empty element in each field and the last blob fills its 5 bytes.
Test(sample_decode, textlists_wire_interleaved_and_padded) {
    static const pb_u8 raw[] = {
        0x0AU, 0x01U, 'a',                                   // text[0] = "a"
        0x12U, 0x02U, 0x01U, 0x02U,                          // blob[0] = 01 02
        0x0AU, 0x82U, 0x00U, 'b',  'c',                      // text[1] = "bc", the length 2 padded to two bytes
        0x12U, 0x00U,                                        // blob[1] = empty
        0x0AU, 0x00U,                                        // text[2] = empty
        0x12U, 0x85U, 0x00U, 0x01U, 0x02U, 0x03U, 0x04U, 0x05U,  // blob[2] = 5 bytes, padded length
    };

    test_io_reset();
    test_io_set_read_buffer(raw, (pb_u32)sizeof(raw));
    scalarpkg_TextLists decoded;
    scalarpkg_TextLists_clear(&decoded);
    scalarpkg_TextLists_decode(&decoded);
    cr_assert(!sample_hasError(), "decode error %d", sample_getError());

    cr_assert_eq(decoded.text.count, 3U);
    cr_assert_eq(decoded.text.item[0].length, 1U);
    cr_assert_eq(decoded.text.item[0].data[0], (pb_u8)'a');
    cr_assert_eq(decoded.text.item[1].length, 2U);
    cr_assert_eq(memcmp(decoded.text.item[1].data, "bc", 2U), 0);
    cr_assert_eq(decoded.text.item[2].length, 0U);

    cr_assert_eq(decoded.blob.count, 3U);
    cr_assert_eq(decoded.blob.item[0].length, 2U);
    cr_assert_eq(decoded.blob.item[0].data[1], 0x02U);
    cr_assert_eq(decoded.blob.item[1].length, 0U);
    cr_assert_eq(decoded.blob.item[2].length, 5U);
    cr_assert_eq(decoded.blob.item[2].data[0], 0x01U);
    cr_assert_eq(decoded.blob.item[2].data[4], 0x05U);
}

Test(sample_decode, textlists_decode_replaces_the_previous_elements) {
    static const pb_u8 two[] = {0x0AU, 0x01U, 'a', 0x0AU, 0x01U, 'b', 0x12U, 0x01U, 0x09U};
    static const pb_u8 one[] = {0x0AU, 0x01U, 'z'};

    scalarpkg_TextLists decoded;
    test_io_reset();
    test_io_set_read_buffer(two, (pb_u32)sizeof(two));
    scalarpkg_TextLists_decode(&decoded);
    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(decoded.text.count, 2U);
    cr_assert_eq(decoded.blob.count, 1U);

    test_io_reset();
    test_io_set_read_buffer(one, (pb_u32)sizeof(one));
    scalarpkg_TextLists_decode(&decoded);
    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(decoded.text.count, 1U);
    cr_assert_eq(decoded.text.item[0].data[0], (pb_u8)'z');
    cr_assert_eq(decoded.blob.count, 0U);
}

Test(sample_decode, textlists_empty_message_has_no_elements) {
    static const pb_u8 raw[] = {0U};

    scalarpkg_TextLists decoded;
    memset(&decoded, 0xFF, sizeof(decoded));
    test_io_reset();
    test_io_set_read_buffer(raw, 0U);
    scalarpkg_TextLists_decode(&decoded);
    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(decoded.text.count, 0U);
    cr_assert_eq(decoded.blob.count, 0U);
}

Test(sample_decode, varint_of_every_length) {
    // u32 (field 1) of Scalars with the largest value of each length of a varint, 1 to 5 bytes
    static const struct {
        pb_u8 bytes[6];
        pb_u32 len;
        pb_u32 value;
    } cases[] = {
        {{0x08U, 0x7FU}, 2U, 127U},
        {{0x08U, 0xFFU, 0x7FU}, 3U, 16383U},
        {{0x08U, 0xFFU, 0xFFU, 0x7FU}, 4U, 2097151U},
        {{0x08U, 0xFFU, 0xFFU, 0xFFU, 0x7FU}, 5U, 268435455U},
        {{0x08U, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0x0FU}, 6U, 4294967295U},
    };

    for (pb_u32 i = 0U; i < (pb_u32)(sizeof(cases) / sizeof(cases[0])); i++) {
        test_io_reset();
        test_io_set_read_buffer(cases[i].bytes, cases[i].len);
        scalarpkg_Scalars decoded;
        scalarpkg_Scalars_clear(&decoded);
        scalarpkg_Scalars_decode(&decoded);

        cr_assert(!sample_hasError(), "%u bytes: decode error %d", cases[i].len - 1U, sample_getError());
        cr_assert_eq(decoded.u32, cases[i].value, "%u bytes", cases[i].len - 1U);
    }
}

static scalarpkg_Wide decode_wide(const pb_u8* data, pb_u32 len) {
    scalarpkg_Wide decoded;
    test_io_set_read_buffer(data, len);
    scalarpkg_Wide_clear(&decoded);
    scalarpkg_Wide_decode(&decoded);
    return decoded;
}

Test(sample_decode, enum_stored_in_16_bits) {
    // the largest value of Width is 300: the enum is stored in 16 bits (COMPRESS_ENUMS), a wider value is cut to them
    static const pb_u8 top[] = {0x08U, 0xFFU, 0xFFU, 0x03U};    // width = 65535
    static const pb_u8 wider[] = {0x08U, 0xF0U, 0xA2U, 0x04U};  // width = 70000

    test_io_reset();
    scalarpkg_Wide_WrHandle root = scalarpkg_Wide_create();
    scalarpkg_Wide_set_width(&root, scalarpkg_Width_WIDTH_MAX);
    scalarpkg_Wide_set_opt_width(&root, scalarpkg_Width_WIDTH_MAX);
    cr_assert(!test_io_has_write_overflow());

    scalarpkg_Wide decoded = decode_wide(test_io_get_write_buffer(), test_io_get_write_length());
    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(sizeof(decoded.width), 2U);
    cr_assert_eq((pb_u32)decoded.width, 300U);
    cr_assert(scalarpkg_Wide_has_opt_width(&decoded));
    cr_assert_eq((pb_u32)decoded.opt_width, 300U);

    test_io_reset();
    decoded = decode_wide(top, (pb_u32)sizeof(top));
    cr_assert(!sample_hasError());
    cr_assert_eq((pb_u32)decoded.width, 65535U);

    test_io_reset();
    decoded = decode_wide(wider, (pb_u32)sizeof(wider));
    cr_assert(!sample_hasError());
    cr_assert_eq((pb_u32)decoded.width, 70000U & 0xFFFFU);
}
