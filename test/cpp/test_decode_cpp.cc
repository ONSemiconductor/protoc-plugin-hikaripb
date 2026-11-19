#include <criterion/criterion.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "expected_values.h"
#include "message.pb.h"
#include "scalars.pb.h"

// C++ mirror of test_decode.c: reads the bytes exported by
// test/py/check_interop.py (produced with the generated Python bindings)
// and decodes them with the generated C++ hikaripb::Decoder/WrProxy API.
Test(sample_decode_cpp, import_from_python) {
    const char* in_dir = getenv("SAMPLE_INTEROP_DIR");
    if (in_dir == NULL) {
        in_dir = ".";
    }
    char in_path[512];
    snprintf(in_path, sizeof(in_path), "%s/encoded_from_python.bin", in_dir);

    FILE* f = fopen(in_path, "rb");
    cr_assert(f != NULL, "could not open %s for reading (run the python interop step first)", in_path);

    static uint8_t buffer[2048];
    size_t read_len = fread(buffer, 1, sizeof(buffer), f);
    fclose(f);
    cr_assert(read_len > 0U, "python-encoded payload is empty");

    uint32_t msg_len = (uint32_t)read_len;
    hikaripb::InputStream is(buffer, msg_len);
    hikaripb::Decoder<> dec(is);

    samplepkg::SampleMessage decoded;
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());

    cr_assert(decoded.has_opt_value());
    cr_assert_eq(decoded.opt_value, EXPECTED_OPT_VALUE);
    cr_assert(decoded.has_opt_uint());
    cr_assert_eq(decoded.opt_uint, EXPECTED_OPT_UINT);
    cr_assert_eq(decoded.flag, EXPECTED_FLAG);
    cr_assert_eq((uint32_t)decoded.color, EXPECTED_COLOR);

    cr_assert(decoded.has_location());
    cr_assert_eq(decoded.location.x, EXPECTED_LOCATION_X);
    cr_assert_eq(decoded.location.y, EXPECTED_LOCATION_Y);

    cr_assert(decoded.has_payload());
    cr_assert_eq(decoded.payload.length, EXPECTED_PAYLOAD_LENGTH);
    cr_assert_eq(decoded.payload.data[0], EXPECTED_PAYLOAD_BYTE_0);
    cr_assert_eq(decoded.payload.data[1], EXPECTED_PAYLOAD_BYTE_1);
    cr_assert_eq(decoded.payload.data[2], EXPECTED_PAYLOAD_BYTE_2);
    cr_assert_eq(decoded.payload.data[3], EXPECTED_PAYLOAD_BYTE_3);

    cr_assert(decoded.has_choice());
    cr_assert(decoded.has_choice_u32());
    cr_assert_eq(decoded.choice.choice_u32, EXPECTED_CHOICE_U32);

    cr_assert_eq(decoded.tags.count, EXPECTED_TAGS_COUNT);
    cr_assert_eq((uint32_t)decoded.tags.item[0], EXPECTED_TAG_0);
    cr_assert_eq((uint32_t)decoded.tags.item[1], EXPECTED_TAG_1);

    cr_assert_eq(decoded.items.count, EXPECTED_ITEMS_COUNT);
    cr_assert_eq(decoded.items.item[0].item_id, EXPECTED_ITEM0_ID);
    cr_assert_eq(decoded.items.item[0].checksum, EXPECTED_ITEM0_CHECKSUM);
    cr_assert_eq((uint32_t)decoded.items.item[0].kind, EXPECTED_ITEM0_KIND);
    cr_assert_eq(decoded.items.item[1].item_id, EXPECTED_ITEM1_ID);
    cr_assert_eq(decoded.items.item[1].checksum, EXPECTED_ITEM1_CHECKSUM);
    cr_assert_eq((uint32_t)decoded.items.item[1].kind, EXPECTED_ITEM1_KIND);

    cr_assert_eq(decoded.numbers.count, EXPECTED_NUMBERS_COUNT);
    cr_assert_eq(decoded.numbers.item[0], EXPECTED_NUMBER_0);
    cr_assert_eq(decoded.numbers.item[1], EXPECTED_NUMBER_1);
    cr_assert_eq(decoded.numbers.item[2], EXPECTED_NUMBER_2);

    cr_assert(decoded.has_label());
    cr_assert_eq(decoded.label.length, EXPECTED_LABEL_LENGTH);
    cr_assert_eq(memcmp(decoded.label.data, EXPECTED_LABEL, EXPECTED_LABEL_LENGTH), 0);

    cr_assert(decoded.has_metadata());
    cr_assert_eq((uint32_t)decoded.metadata.kind, EXPECTED_METADATA_KIND);
    cr_assert(decoded.metadata.has_revision());
    cr_assert_eq(decoded.metadata.revision, EXPECTED_METADATA_REVISION);

    cr_assert(decoded.has_sparse_tags());
    cr_assert_eq(decoded.sparse_tags.tag_1, EXPECTED_SPARSE_TAG_1);
    cr_assert_eq(decoded.sparse_tags.tag_25, EXPECTED_SPARSE_TAG_25);
    cr_assert_eq(decoded.sparse_tags.tag_75, EXPECTED_SPARSE_TAG_75);
    cr_assert_eq(decoded.sparse_tags.tag_150, EXPECTED_SPARSE_TAG_150);
    cr_assert_eq(decoded.sparse_tags.tag_200, EXPECTED_SPARSE_TAG_200);
}

// Loads <SAMPLE_INTEROP_DIR>/<name> (written by test/py/check_interop.py) into a static buffer.
static uint32_t import_bytes(const char* name, uint8_t* buffer, size_t capacity) {
    const char* in_dir = getenv("SAMPLE_INTEROP_DIR");
    if (in_dir == NULL) {
        in_dir = ".";
    }
    char in_path[512];
    snprintf(in_path, sizeof(in_path), "%s/%s", in_dir, name);

    FILE* f = fopen(in_path, "rb");
    cr_assert(f != NULL, "could not open %s for reading (run the python interop step first)", in_path);
    size_t read_len = fread(buffer, 1, capacity, f);
    fclose(f);
    cr_assert(read_len > 0U, "python-encoded payload %s is empty", name);
    return (uint32_t)read_len;
}

Test(sample_decode_cpp, scalars_import_from_python) {
    static uint8_t buffer[2048];
    static const uint8_t expected_blob[] = EXPECTED_SC_BLOB;

    uint32_t msg_len = import_bytes("scalars_from_python.bin", buffer, sizeof(buffer));
    hikaripb::InputStream is(buffer, msg_len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::Scalars decoded;
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());

    cr_assert_eq(decoded.u32, EXPECTED_SC_U32);
    cr_assert_eq(decoded.s32, EXPECTED_SC_S32);
    cr_assert_eq(decoded.f32, EXPECTED_SC_F32);
    cr_assert_eq(decoded.sf32, EXPECTED_SC_SF32);
    cr_assert(decoded.flt == EXPECTED_SC_FLT);
    cr_assert_eq(decoded.flag, EXPECTED_SC_FLAG);
    cr_assert_eq((uint32_t)decoded.level, EXPECTED_SC_LEVEL);

    cr_assert(decoded.has_text());
    cr_assert_eq(decoded.text.length, EXPECTED_SC_TEXT_LENGTH);
    cr_assert_eq(memcmp(decoded.text.data, EXPECTED_SC_TEXT, EXPECTED_SC_TEXT_LENGTH), 0);
    cr_assert(decoded.has_blob());
    cr_assert_eq(decoded.blob.length, EXPECTED_SC_BLOB_LENGTH);
    cr_assert_eq(memcmp(decoded.blob.data, expected_blob, EXPECTED_SC_BLOB_LENGTH), 0);

    // explicit presence: zero and false are present, not just default
    cr_assert(decoded.has_opt_u32());
    cr_assert_eq(decoded.opt_u32, EXPECTED_SC_OPT_U32);
    cr_assert(decoded.has_opt_text());
    cr_assert_eq(decoded.opt_text.length, EXPECTED_SC_OPT_TEXT_LENGTH);
    cr_assert_eq(memcmp(decoded.opt_text.data, EXPECTED_SC_OPT_TEXT, EXPECTED_SC_OPT_TEXT_LENGTH), 0);
    cr_assert(decoded.has_opt_level());
    cr_assert_eq((uint32_t)decoded.opt_level, EXPECTED_SC_OPT_LEVEL);
    cr_assert(decoded.has_opt_flt());
    cr_assert(decoded.opt_flt == EXPECTED_SC_OPT_FLT);
    cr_assert(decoded.has_opt_flag());
    cr_assert_eq(decoded.opt_flag, EXPECTED_SC_OPT_FLAG);

    cr_assert_eq(decoded.from, EXPECTED_SC_FROM);
    cr_assert(decoded.has_serialize());
    cr_assert_eq(decoded.serialize.length, EXPECTED_SC_SERIALIZE_LENGTH);
    cr_assert_eq(memcmp(decoded.serialize.data, EXPECTED_SC_SERIALIZE, EXPECTED_SC_SERIALIZE_LENGTH), 0);
    cr_assert(decoded.has_clear_());
    cr_assert_eq(decoded.clear_.length, EXPECTED_SC_CLEAR_LENGTH);
    cr_assert_eq(memcmp(decoded.clear_.data, EXPECTED_SC_CLEAR, EXPECTED_SC_CLEAR_LENGTH), 0);
}

Test(sample_decode_cpp, choice_import_from_python) {
    static uint8_t buffer[2048];

    uint32_t msg_len = import_bytes("choice_from_python.bin", buffer, sizeof(buffer));
    hikaripb::InputStream is(buffer, msg_len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::Choice decoded;
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());

    cr_assert(decoded.has_text());
    cr_assert(!decoded.has_number());
    cr_assert_eq(decoded.value.text.length, EXPECTED_CH_TEXT_LENGTH);
    cr_assert_eq(memcmp(decoded.value.text.data, EXPECTED_CH_TEXT, EXPECTED_CH_TEXT_LENGTH), 0);

    cr_assert(decoded.has_extra());
    cr_assert_eq(decoded.extra.seconds, EXPECTED_CH_EXTRA_SECONDS);
    cr_assert_eq(decoded.extra.nanos, EXPECTED_CH_EXTRA_NANOS);
    cr_assert_eq((uint32_t)decoded.extra.unit, EXPECTED_CH_EXTRA_UNIT);
    cr_assert(decoded.has_when());
    cr_assert_eq(decoded.when.seconds, EXPECTED_CH_WHEN_SECONDS);
    cr_assert_eq(decoded.when.nanos, EXPECTED_CH_WHEN_NANOS);
    cr_assert_eq((uint32_t)decoded.when.unit, EXPECTED_CH_WHEN_UNIT);
}

Test(sample_decode_cpp, repeats_import_from_python) {
    static uint8_t buffer[2048];
    static const uint32_t u32s[] = EXPECTED_RP_U32;
    static const int32_t s32s[] = EXPECTED_RP_S32;
    static const uint32_t f32s[] = EXPECTED_RP_F32;
    static const int32_t sf32s[] = EXPECTED_RP_SF32;
    static const float flts[] = EXPECTED_RP_FLT;
    static const bool flags[] = EXPECTED_RP_FLAG;
    static const uint32_t levels[] = EXPECTED_RP_LEVEL;
    static const uint32_t stamp_seconds[] = EXPECTED_RP_STAMP_SECONDS;
    static const uint32_t stamp_units[] = EXPECTED_RP_STAMP_UNIT;

    uint32_t msg_len = import_bytes("repeats_from_python.bin", buffer, sizeof(buffer));
    hikaripb::InputStream is(buffer, msg_len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::Repeats decoded;
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());

    cr_assert_eq(decoded.u32.count, sizeof(u32s) / sizeof(u32s[0]));
    for (uint32_t i = 0U; i < decoded.u32.count; i++) {
        cr_assert_eq(decoded.u32.item[i], u32s[i], "u32[%u]", i);
    }
    cr_assert_eq(decoded.s32.count, sizeof(s32s) / sizeof(s32s[0]));
    for (uint32_t i = 0U; i < decoded.s32.count; i++) {
        cr_assert_eq(decoded.s32.item[i], s32s[i], "s32[%u]", i);
    }
    cr_assert_eq(decoded.f32.count, sizeof(f32s) / sizeof(f32s[0]));
    for (uint32_t i = 0U; i < decoded.f32.count; i++) {
        cr_assert_eq(decoded.f32.item[i], f32s[i], "f32[%u]", i);
    }
    cr_assert_eq(decoded.sf32.count, sizeof(sf32s) / sizeof(sf32s[0]));
    for (uint32_t i = 0U; i < decoded.sf32.count; i++) {
        cr_assert_eq(decoded.sf32.item[i], sf32s[i], "sf32[%u]", i);
    }
    cr_assert_eq(decoded.flt.count, sizeof(flts) / sizeof(flts[0]));
    for (uint32_t i = 0U; i < decoded.flt.count; i++) {
        cr_assert(decoded.flt.item[i] == flts[i], "flt[%u]", i);
    }
    cr_assert_eq(decoded.flag.count, sizeof(flags) / sizeof(flags[0]));
    for (uint32_t i = 0U; i < decoded.flag.count; i++) {
        cr_assert_eq(decoded.flag.item[i], flags[i], "flag[%u]", i);
    }
    cr_assert_eq(decoded.level.count, sizeof(levels) / sizeof(levels[0]));
    for (uint32_t i = 0U; i < decoded.level.count; i++) {
        cr_assert_eq((uint32_t)decoded.level.item[i], levels[i], "level[%u]", i);
    }
    cr_assert_eq(decoded.stamps.count, sizeof(stamp_seconds) / sizeof(stamp_seconds[0]));
    for (uint32_t i = 0U; i < decoded.stamps.count; i++) {
        cr_assert_eq(decoded.stamps.item[i].seconds, stamp_seconds[i], "stamps[%u].seconds", i);
        cr_assert_eq((uint32_t)decoded.stamps.item[i].unit, stamp_units[i], "stamps[%u].unit", i);
    }
}

Test(sample_decode_cpp, textlists_import_from_python) {
    static uint8_t buffer[2048];
    static const char* const texts[] = EXPECTED_TL_TEXT;
    static const uint8_t blob_0[] = EXPECTED_TL_BLOB_0;
    static const uint8_t blob_2[] = EXPECTED_TL_BLOB_2;

    uint32_t msg_len = import_bytes("textlists_from_python.bin", buffer, sizeof(buffer));
    hikaripb::InputStream is(buffer, msg_len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::TextLists decoded;
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());

    cr_assert_eq(decoded.text.count, sizeof(texts) / sizeof(texts[0]));
    for (uint32_t i = 0U; i < decoded.text.count; i++) {
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
Test(sample_decode_cpp, textlists_wire_interleaved_and_padded) {
    static uint8_t buffer[] = {
        0x0AU, 0x01U, 'a',                                   // text[0] = "a"
        0x12U, 0x02U, 0x01U, 0x02U,                          // blob[0] = 01 02
        0x0AU, 0x82U, 0x00U, 'b',  'c',                      // text[1] = "bc", the length 2 padded to two bytes
        0x12U, 0x00U,                                        // blob[1] = empty
        0x0AU, 0x00U,                                        // text[2] = empty
        0x12U, 0x85U, 0x00U, 0x01U, 0x02U, 0x03U, 0x04U, 0x05U,  // blob[2] = 5 bytes, padded length
    };

    uint32_t msg_len = sizeof(buffer);
    hikaripb::InputStream is(buffer, msg_len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::TextLists decoded;
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());

    cr_assert_eq(decoded.text.count, 3U);
    cr_assert_eq(decoded.text.item[0].length, 1U);
    cr_assert_eq(decoded.text.item[0].data[0], (uint8_t)'a');
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

Test(sample_decode_cpp, textlists_decode_replaces_the_previous_elements) {
    static uint8_t two[] = {0x0AU, 0x01U, 'a', 0x0AU, 0x01U, 'b', 0x12U, 0x01U, 0x09U};
    static uint8_t one[] = {0x0AU, 0x01U, 'z'};

    scalarpkg::TextLists decoded;
    uint32_t two_len = sizeof(two);
    hikaripb::InputStream is_two(two, two_len);
    hikaripb::Decoder<> dec_two(is_two);
    decoded.decode(dec_two);
    cr_assert(!dec_two.hasError(), "decode error %d", dec_two.getError());
    cr_assert_eq(decoded.text.count, 2U);
    cr_assert_eq(decoded.blob.count, 1U);

    uint32_t one_len = sizeof(one);
    hikaripb::InputStream is_one(one, one_len);
    hikaripb::Decoder<> dec_one(is_one);
    decoded.decode(dec_one);
    cr_assert(!dec_one.hasError(), "decode error %d", dec_one.getError());
    cr_assert_eq(decoded.text.count, 1U);
    cr_assert_eq(decoded.text.item[0].data[0], (uint8_t)'z');
    cr_assert_eq(decoded.blob.count, 0U);
}

Test(sample_decode_cpp, textlists_empty_message_has_no_elements) {
    static uint8_t buffer[1];

    scalarpkg::TextLists decoded;
    memset(&decoded, 0xFF, sizeof(decoded));
    uint32_t msg_len = 0U;
    hikaripb::InputStream is(buffer, msg_len);
    hikaripb::Decoder<> dec(is);
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(decoded.text.count, 0U);
    cr_assert_eq(decoded.blob.count, 0U);
}

Test(sample_decode_cpp, varint_of_every_length) {
    // u32 (field 1) of Scalars with the largest value of each length of a varint, 1 to 5 bytes
    static struct {
        uint8_t bytes[6];
        uint32_t len;
        uint32_t value;
    } cases[] = {
        {{0x08U, 0x7FU}, 2U, 127U},
        {{0x08U, 0xFFU, 0x7FU}, 3U, 16383U},
        {{0x08U, 0xFFU, 0xFFU, 0x7FU}, 4U, 2097151U},
        {{0x08U, 0xFFU, 0xFFU, 0xFFU, 0x7FU}, 5U, 268435455U},
        {{0x08U, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0x0FU}, 6U, 4294967295U},
    };

    for (auto& c : cases) {
        uint32_t len = c.len;
        hikaripb::InputStream is(c.bytes, len);
        hikaripb::Decoder<> dec(is);
        scalarpkg::Scalars decoded;
        decoded.decode(dec);

        cr_assert(!dec.hasError(), "%u bytes: decode error %d", c.len - 1U, dec.getError());
        cr_assert_eq(decoded.u32, c.value, "%u bytes", c.len - 1U);
    }
}

static hikaripb::DecodeError decode_wide(uint8_t* data, uint32_t len, scalarpkg::Wide& decoded) {
    hikaripb::InputStream is(data, len);
    hikaripb::Decoder<> dec(is);
    decoded.decode(dec);
    return dec.getError();
}

Test(sample_decode_cpp, enum_stored_in_16_bits) {
    // the largest value of Width is 300: the enum is stored in 16 bits (COMPRESS_ENUMS), a wider value is cut to them
    static uint8_t buffer[64];
    static uint8_t top[] = {0x08U, 0xFFU, 0xFFU, 0x03U};    // width = 65535
    static uint8_t wider[] = {0x08U, 0xF0U, 0xA2U, 0x04U};  // width = 70000
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = scalarpkg::Wide::WrProxy<true>(enc);
        root.set_width(scalarpkg::WIDTH_MAX);
        root.set_opt_width(scalarpkg::WIDTH_MAX);
    }

    scalarpkg::Wide decoded;
    cr_assert_eq(decode_wide(buffer, os.getOffset(), decoded), hikaripb::DecodeError::DECODER_OK);
    cr_assert_eq(sizeof(decoded.width), 2U);
    cr_assert_eq((uint32_t)decoded.width, 300U);
    cr_assert(decoded.has_opt_width());
    cr_assert_eq((uint32_t)decoded.opt_width, 300U);

    cr_assert_eq(decode_wide(top, (uint32_t)sizeof(top), decoded), hikaripb::DecodeError::DECODER_OK);
    cr_assert_eq((uint32_t)decoded.width, 65535U);

    cr_assert_eq(decode_wide(wider, (uint32_t)sizeof(wider), decoded), hikaripb::DecodeError::DECODER_OK);
    cr_assert_eq((uint32_t)decoded.width, 70000U & 0xFFFFU);
}
