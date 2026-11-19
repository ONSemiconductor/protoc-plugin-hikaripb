#include <criterion/criterion.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <new>
#include <type_traits>

#include "expected_values.h"
#include "message.pb.h"
#include "scalars.pb.h"

// C++ mirror of test_encode.c: builds the same SampleMessage via the generated
// C++ hikaripb::Encoder/WrProxy API (protoc/cpp, faithfully ported from the
// reference protolib generator), verifies a local decode round-trip, then
// exports the raw bytes so the same Python interop check can cross-check them.
Test(sample_encode_cpp, roundtrip_and_export) {
    static uint8_t buffer[2048];
    static const uint8_t expected_payload[] = {
        EXPECTED_PAYLOAD_BYTE_0,
        EXPECTED_PAYLOAD_BYTE_1,
        EXPECTED_PAYLOAD_BYTE_2,
        EXPECTED_PAYLOAD_BYTE_3,
    };

    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);

    {
        auto root = samplepkg::SampleMessage::WrProxy<true>(enc);
        root.set_opt_value(EXPECTED_OPT_VALUE);
        root.set_opt_uint(EXPECTED_OPT_UINT);
        root.set_flag(EXPECTED_FLAG);
        root.set_color(static_cast<samplepkg::Color>(EXPECTED_COLOR));
        root.set_choice_u32(EXPECTED_CHOICE_U32);

        {
            auto location = root.add_location();
            location.set_x(EXPECTED_LOCATION_X);
            location.set_y(EXPECTED_LOCATION_Y);
        }
        {
            auto payload = root.add_payload();
            payload.write(expected_payload, (uint16_t)EXPECTED_PAYLOAD_LENGTH);
        }
        {
            auto tags = root.rpt_tags();
            tags.add(static_cast<samplepkg::Color>(EXPECTED_TAG_0));
            tags.add(static_cast<samplepkg::Color>(EXPECTED_TAG_1));
        }
        {
            auto item0 = root.rpt_items();
            item0.set_item_id(EXPECTED_ITEM0_ID);
            item0.set_checksum(EXPECTED_ITEM0_CHECKSUM);
            item0.set_kind(static_cast<samplepkg::ItemKind>(EXPECTED_ITEM0_KIND));
        }
        {
            auto item1 = root.rpt_items();
            item1.set_item_id(EXPECTED_ITEM1_ID);
            item1.set_checksum(EXPECTED_ITEM1_CHECKSUM);
            item1.set_kind(static_cast<samplepkg::ItemKind>(EXPECTED_ITEM1_KIND));
        }
        {
            auto numbers = root.rpt_numbers();
            numbers.add(EXPECTED_NUMBER_0);
            numbers.add(EXPECTED_NUMBER_1);
            numbers.add(EXPECTED_NUMBER_2);
        }
        {
            auto label = root.add_label();
            label.write((const uint8_t*)EXPECTED_LABEL, (uint16_t)EXPECTED_LABEL_LENGTH);
        }
        {
            auto metadata = root.add_metadata();
            metadata.set_kind(static_cast<samplepkg::MetadataKind>(EXPECTED_METADATA_KIND));
            metadata.set_revision(EXPECTED_METADATA_REVISION);
        }
        {
            auto sparse_tags = root.add_sparse_tags();
            sparse_tags.set_tag_1(EXPECTED_SPARSE_TAG_1);
            sparse_tags.set_tag_25(EXPECTED_SPARSE_TAG_25);
            sparse_tags.set_tag_75(EXPECTED_SPARSE_TAG_75);
            sparse_tags.set_tag_150(EXPECTED_SPARSE_TAG_150);
            sparse_tags.set_tag_200(EXPECTED_SPARSE_TAG_200);
        }
    }

    const uint32_t encoded_len = os.getOffset();
    cr_assert(encoded_len > 0U, "no payload encoded");

    // Local round-trip: decode what we just encoded via the C++ reader API.
    uint32_t read_len = encoded_len;
    hikaripb::InputStream is(buffer, read_len);
    hikaripb::Decoder<> dec(is);
    samplepkg::SampleMessage decoded;
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(decoded.opt_value, EXPECTED_OPT_VALUE);
    cr_assert_eq(decoded.location.x, EXPECTED_LOCATION_X);
    cr_assert_eq(decoded.sparse_tags.tag_1, EXPECTED_SPARSE_TAG_1);
    cr_assert_eq(decoded.sparse_tags.tag_75, EXPECTED_SPARSE_TAG_75);
    cr_assert_eq(decoded.sparse_tags.tag_200, EXPECTED_SPARSE_TAG_200);

    // Export the C++-encoded bytes for the Python interop check.
    const char* out_dir = getenv("SAMPLE_INTEROP_DIR");
    if (out_dir == NULL) {
        out_dir = ".";
    }
    char out_path[512];
    snprintf(out_path, sizeof(out_path), "%s/encoded_from_cpp.bin", out_dir);

    FILE* f = fopen(out_path, "wb");
    cr_assert(f != NULL, "could not open %s for writing", out_path);
    cr_assert_eq(fwrite(buffer, 1, encoded_len, f), encoded_len);
    fclose(f);
}

// Writes encoded bytes to <SAMPLE_INTEROP_DIR>/<name> for test/py/check_interop.py.
static void export_bytes(const char* name, const uint8_t* data, uint32_t len) {
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
Test(sample_encode_cpp, scalars_roundtrip_and_export) {
    static uint8_t buffer[2048];
    static const uint8_t blob[] = EXPECTED_SC_BLOB;

    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = scalarpkg::Scalars::WrProxy<true>(enc);
        root.set_u32(EXPECTED_SC_U32);
        root.set_s32(EXPECTED_SC_S32);
        root.set_f32(EXPECTED_SC_F32);
        root.set_sf32(EXPECTED_SC_SF32);
        root.set_flt(EXPECTED_SC_FLT);
        root.set_flag(EXPECTED_SC_FLAG);
        root.set_level(static_cast<scalarpkg::Level>(EXPECTED_SC_LEVEL));
        {
            auto text = root.add_text();
            text.write((const uint8_t*)EXPECTED_SC_TEXT, (uint16_t)EXPECTED_SC_TEXT_LENGTH);
        }
        {
            auto blob_proxy = root.add_blob();
            blob_proxy.write(blob, (uint16_t)EXPECTED_SC_BLOB_LENGTH);
        }
        root.set_opt_u32(EXPECTED_SC_OPT_U32);
        {
            auto opt_text = root.add_opt_text();
            opt_text.write((const uint8_t*)EXPECTED_SC_OPT_TEXT, (uint16_t)EXPECTED_SC_OPT_TEXT_LENGTH);
        }
        root.set_opt_level(static_cast<scalarpkg::Level>(EXPECTED_SC_OPT_LEVEL));
        root.set_opt_flt(EXPECTED_SC_OPT_FLT);
        root.set_opt_flag(EXPECTED_SC_OPT_FLAG);
        root.set_from(EXPECTED_SC_FROM);
        {
            auto serialize = root.add_serialize();
            serialize.write((const uint8_t*)EXPECTED_SC_SERIALIZE, (uint16_t)EXPECTED_SC_SERIALIZE_LENGTH);
        }
        {
            // the field "clear" is called clear_ because it would clash with Scalars::clear()
            auto clear = root.add_clear_();
            clear.write((const uint8_t*)EXPECTED_SC_CLEAR, (uint16_t)EXPECTED_SC_CLEAR_LENGTH);
        }
    }

    const uint32_t encoded_len = os.getOffset();
    cr_assert(encoded_len > 0U, "no payload encoded");

    uint32_t read_len = encoded_len;
    hikaripb::InputStream is(buffer, read_len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::Scalars decoded;
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(decoded.u32, EXPECTED_SC_U32);
    cr_assert_eq(decoded.s32, EXPECTED_SC_S32);
    cr_assert(decoded.has_opt_u32());
    cr_assert_eq(decoded.opt_u32, EXPECTED_SC_OPT_U32);

    export_bytes("scalars_from_cpp.bin", buffer, encoded_len);
}

Test(sample_encode_cpp, choice_roundtrip_and_export) {
    static uint8_t buffer[2048];

    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = scalarpkg::Choice::WrProxy<true>(enc);
        {
            auto text = root.add_text();
            text.write((const uint8_t*)EXPECTED_CH_TEXT, (uint16_t)EXPECTED_CH_TEXT_LENGTH);
        }
        {
            auto extra = root.add_extra();
            extra.set_seconds(EXPECTED_CH_EXTRA_SECONDS);
            extra.set_nanos(EXPECTED_CH_EXTRA_NANOS);
            extra.set_unit(static_cast<shared::Unit>(EXPECTED_CH_EXTRA_UNIT));
        }
        {
            auto when = root.add_when();
            when.set_seconds(EXPECTED_CH_WHEN_SECONDS);
            when.set_nanos(EXPECTED_CH_WHEN_NANOS);
            when.set_unit(static_cast<shared::Unit>(EXPECTED_CH_WHEN_UNIT));
        }
    }

    const uint32_t encoded_len = os.getOffset();
    cr_assert(encoded_len > 0U, "no payload encoded");

    uint32_t read_len = encoded_len;
    hikaripb::InputStream is(buffer, read_len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::Choice decoded;
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert(decoded.has_text());
    cr_assert(decoded.has_extra());
    cr_assert_eq(decoded.when.seconds, EXPECTED_CH_WHEN_SECONDS);

    export_bytes("choice_from_cpp.bin", buffer, encoded_len);
}

// Adds every element of the EXPECTED_RP_<NAME> list to the repeated field <name> of a Repeats message.
#define WRITE_LIST(root, name, type, values)                                     \
    do {                                                                         \
        static const type list[] = values;                                       \
        auto hdl = root.rpt_##name();                                            \
        for (uint32_t i = 0U; i < (uint32_t)(sizeof(list) / sizeof(list[0])); i++) { \
            hdl.add(list[i]);                                                    \
        }                                                                        \
    } while (0)

Test(sample_encode_cpp, repeats_roundtrip_and_export) {
    static uint8_t buffer[2048];
    static const uint32_t levels[] = EXPECTED_RP_LEVEL;
    static const uint32_t stamp_seconds[] = EXPECTED_RP_STAMP_SECONDS;
    static const uint32_t stamp_units[] = EXPECTED_RP_STAMP_UNIT;

    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = scalarpkg::Repeats::WrProxy<true>(enc);
        WRITE_LIST(root, u32, uint32_t, EXPECTED_RP_U32);
        WRITE_LIST(root, s32, int32_t, EXPECTED_RP_S32);
        WRITE_LIST(root, f32, uint32_t, EXPECTED_RP_F32);
        WRITE_LIST(root, sf32, int32_t, EXPECTED_RP_SF32);
        WRITE_LIST(root, flt, float, EXPECTED_RP_FLT);
        WRITE_LIST(root, flag, bool, EXPECTED_RP_FLAG);
        {
            auto level = root.rpt_level();
            for (uint32_t value : levels) {
                level.add(static_cast<scalarpkg::Level>(value));
            }
        }
        for (uint32_t i = 0U; i < (uint32_t)(sizeof(stamp_seconds) / sizeof(stamp_seconds[0])); i++) {
            auto stamp = root.rpt_stamps();
            stamp.set_seconds(stamp_seconds[i]);
            stamp.set_unit(static_cast<shared::Unit>(stamp_units[i]));
        }
    }

    const uint32_t encoded_len = os.getOffset();
    cr_assert(encoded_len > 0U, "no payload encoded");

    uint32_t read_len = encoded_len;
    hikaripb::InputStream is(buffer, read_len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::Repeats decoded;
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(decoded.u32.count, 3U);
    cr_assert_eq(decoded.stamps.count, 2U);

    export_bytes("repeats_from_cpp.bin", buffer, encoded_len);
}

// Repeated string and bytes: every element is written by its own rpt_<field>() call, an empty one is kept.
Test(sample_encode_cpp, textlists_roundtrip_and_export) {
    static uint8_t buffer[2048];
    static const char* const texts[] = EXPECTED_TL_TEXT;
    static const uint8_t blob_0[] = EXPECTED_TL_BLOB_0;
    static const uint8_t blob_2[] = EXPECTED_TL_BLOB_2;

    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);
    {
        auto root = scalarpkg::TextLists::WrProxy<true>(enc);
        for (const char* text : texts) {
            auto element = root.rpt_text();
            element.write((const uint8_t*)text, (uint16_t)strlen(text));
        }
        {
            auto blob = root.rpt_blob();
            blob.write(blob_0, (uint16_t)sizeof(blob_0));
        }
        { auto blob = root.rpt_blob(); }
        {
            auto blob = root.rpt_blob();
            blob.write(blob_2, (uint16_t)sizeof(blob_2));
        }
    }

    const uint32_t encoded_len = os.getOffset();
    cr_assert(encoded_len > 0U, "no payload encoded");

    uint32_t read_len = encoded_len;
    hikaripb::InputStream is(buffer, read_len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::TextLists decoded;
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(decoded.text.count, 3U);
    cr_assert_eq(decoded.text.item[2].length, 5U);
    cr_assert_eq(memcmp(decoded.text.item[2].data, "third", 5U), 0);
    cr_assert_eq(decoded.blob.count, 3U);
    cr_assert_eq(decoded.blob.item[1].length, 0U);

    export_bytes("textlists_from_cpp.bin", buffer, encoded_len);
}

// A proxy is neither copied nor moved: the length of its field is written by its destructor. A proxy that has to live in
// storage that is declared in front is created there with placement new from the result of add_<field>(); C++17 constructs
// it in place, without a copy, and its destructor ends the field.
static_assert(!std::is_copy_constructible<hikaripb::BytesProxy>::value, "a copy would write the length twice");
static_assert(!std::is_copy_constructible<scalarpkg::Choice::WrProxy<true>>::value, "a proxy is not copied");
static_assert(!std::is_copy_constructible<shared::Stamp::WrProxy<false>>::value, "a copy would write the length twice");
static_assert(!std::is_move_constructible<hikaripb::BytesProxy>::value, "a move would write the length twice");
static_assert(!std::is_move_constructible<scalarpkg::Choice::WrProxy<true>>::value, "a proxy is not moved");
static_assert(!std::is_move_constructible<shared::Stamp::WrProxy<false>>::value, "a move would write the length twice");
static_assert(std::is_destructible<hikaripb::BytesProxy>::value, "the destructor ends the field");
static_assert(std::is_destructible<shared::Stamp::WrProxy<false>>::value, "the destructor ends the field");

static void expect_same_bytes(const uint8_t* placed, uint32_t placed_len, const uint8_t* direct, uint32_t direct_len) {
    cr_assert_eq(placed_len, direct_len);
    cr_assert_eq(memcmp(placed, direct, direct_len), 0);
}

// Each case writes a field after the one that was ended by the destructor: it ends the field once, at that moment.
Test(sample_encode_cpp, a_message_proxy_in_place_ends_its_field_when_it_is_destroyed) {
    static uint8_t placed[64];
    static uint8_t direct[64];
    hikaripb::OutputStream os_placed(placed);
    hikaripb::Encoder<> enc_placed(os_placed);
    hikaripb::OutputStream os_direct(direct);
    hikaripb::Encoder<> enc_direct(os_direct);

    {
        using Stamp = shared::Stamp::WrProxy<false>;
        alignas(Stamp) unsigned char storage[sizeof(Stamp)];
        auto root = scalarpkg::Choice::WrProxy<true>(enc_placed);

        Stamp* when = ::new (static_cast<void*>(storage)) Stamp(root.add_when());
        when->set_seconds(7U);
        when->set_nanos(9U);
        when->~Stamp();
        root.set_number(5U);
    }
    {
        auto root = scalarpkg::Choice::WrProxy<true>(enc_direct);
        {
            auto when = root.add_when();
            when.set_seconds(7U);
            when.set_nanos(9U);
        }
        root.set_number(5U);
    }
    expect_same_bytes(placed, os_placed.getOffset(), direct, os_direct.getOffset());

    uint32_t placed_len = os_placed.getOffset();
    hikaripb::InputStream is(placed, placed_len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::Choice decoded;
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(decoded.when.seconds, 7U);
    cr_assert_eq(decoded.when.nanos, 9U);
    cr_assert_eq(decoded.value.number, 5U);
}

Test(sample_encode_cpp, a_bytes_proxy_in_place_ends_its_field_when_it_is_destroyed) {
    static uint8_t placed[64];
    static uint8_t direct[64];
    hikaripb::OutputStream os_placed(placed);
    hikaripb::Encoder<> enc_placed(os_placed);
    hikaripb::OutputStream os_direct(direct);
    hikaripb::Encoder<> enc_direct(os_direct);

    {
        using Blob = hikaripb::BytesProxy;
        alignas(Blob) unsigned char storage[sizeof(Blob)];
        auto root = scalarpkg::Scalars::WrProxy<true>(enc_placed);

        Blob* blob = ::new (static_cast<void*>(storage)) Blob(root.add_blob());
        blob->write(reinterpret_cast<const uint8_t*>("abc"), 3U);
        blob->~Blob();
        root.set_u32(1U);
    }
    {
        auto root = scalarpkg::Scalars::WrProxy<true>(enc_direct);
        {
            auto blob = root.add_blob();
            blob.write(reinterpret_cast<const uint8_t*>("abc"), 3U);
        }
        root.set_u32(1U);
    }
    expect_same_bytes(placed, os_placed.getOffset(), direct, os_direct.getOffset());

    uint32_t placed_len = os_placed.getOffset();
    hikaripb::InputStream is(placed, placed_len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::Scalars decoded;
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(decoded.blob.length, 3U);
    cr_assert_eq(memcmp(decoded.blob.data, "abc", 3U), 0);
    cr_assert_eq(decoded.u32, 1U);
}

Test(sample_encode_cpp, a_dense_proxy_in_place_ends_its_field_when_it_is_destroyed) {
    static uint8_t placed[64];
    static uint8_t direct[64];
    hikaripb::OutputStream os_placed(placed);
    hikaripb::Encoder<> enc_placed(os_placed);
    hikaripb::OutputStream os_direct(direct);
    hikaripb::Encoder<> enc_direct(os_direct);

    {
        auto root = scalarpkg::Repeats::WrProxy<true>(enc_placed);
        using Numbers = decltype(root.rpt_u32());
        alignas(Numbers) unsigned char storage[sizeof(Numbers)];

        Numbers* numbers = ::new (static_cast<void*>(storage)) Numbers(root.rpt_u32());
        numbers->add(1U);
        numbers->add(300U);
        numbers->~Numbers();
        auto signed_numbers = root.rpt_s32();
        signed_numbers.add(-1);
    }
    {
        auto root = scalarpkg::Repeats::WrProxy<true>(enc_direct);
        {
            auto numbers = root.rpt_u32();
            numbers.add(1U);
            numbers.add(300U);
        }
        auto signed_numbers = root.rpt_s32();
        signed_numbers.add(-1);
    }
    expect_same_bytes(placed, os_placed.getOffset(), direct, os_direct.getOffset());

    uint32_t placed_len = os_placed.getOffset();
    hikaripb::InputStream is(placed, placed_len);
    hikaripb::Decoder<> dec(is);
    scalarpkg::Repeats decoded;
    decoded.decode(dec);
    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(decoded.u32.count, 2U);
    cr_assert_eq(decoded.u32.item[1], 300U);
    cr_assert_eq(decoded.s32.count, 1U);
    cr_assert_eq(decoded.s32.item[0], -1);
}

Test(sample_encode_cpp, a_top_level_proxy_can_be_created_in_place) {
    static uint8_t placed[64];
    static uint8_t direct[64];
    hikaripb::OutputStream os_placed(placed);
    hikaripb::Encoder<> enc_placed(os_placed);
    hikaripb::OutputStream os_direct(direct);
    hikaripb::Encoder<> enc_direct(os_direct);

    using Root = scalarpkg::Choice::WrProxy<true>;
    alignas(Root) unsigned char storage[sizeof(Root)];
    Root* in_place = ::new (static_cast<void*>(storage)) Root(enc_placed);
    in_place->set_number(5U);
    in_place->~Root();
    auto root = Root(enc_direct);
    root.set_number(5U);

    expect_same_bytes(placed, os_placed.getOffset(), direct, os_direct.getOffset());
}
