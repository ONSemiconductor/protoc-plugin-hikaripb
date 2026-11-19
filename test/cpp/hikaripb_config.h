/**
 * @file    hikaripb_config.h
 * @brief   protobuf configuration + stream implementations for the protoc/cpp test suite.
 *
 * Consumed by the generated message.pb.h / hikaripb_defines.h / hikaripb_bindings.h (see
 * protoc/cpp). Field size/count overrides below match test/cpp/expected_values.h.
 */
#ifndef HIKARIPB_CONFIG_H
#define HIKARIPB_CONFIG_H

#include <stdint.h>
#include <string.h>

#define HIKARIPB_DEBUG 0
// scalars.proto has float and repeated string/bytes fields.
#define HIKARIPB_ENABLE_FLOAT          1
#define HIKARIPB_ENABLE_REPEATED_BYTES 1
#define HIKARIPB_CALLBACK 1
// Bumped from the default (8) so test_depth_cpp.cc can successfully decode a
// 10-level-deep DepthL0..DepthL9 chain; a 14-level chain still exceeds this
// and is used to exercise DecodeError::DECODER_DEPTH_EXCEEDED.
#define HIKARIPB_DEC_MAX_DEPTH 12
// Only test_errors_cpp.cc relies on this (crafted unknown-tag input);
// harmless for every other test since valid encoded data never contains an
// unknown tag.
#define HIKARIPB_ERROR_ON_UNKNOWN_TAG 1

#define samplepkg_SampleMessage_payload_size 8U
#define samplepkg_SampleMessage_label_size   16U
#define samplepkg_SampleMessage_tags_count   3U
#define samplepkg_SampleMessage_items_count  2U
#define samplepkg_SampleMessage_numbers_count 3U

// Field storage sizes for the messages of scalars.proto.
#define scalarpkg_Scalars_text_size      16U
#define scalarpkg_Scalars_blob_size      8U
#define scalarpkg_Scalars_opt_text_size  16U
#define scalarpkg_Scalars_serialize_size 8U
// the field "clear" is renamed "clear_": it would clash with the generated Scalars::clear()
#define scalarpkg_Scalars_clear__size    8U
#define scalarpkg_Choice_text_size       16U
#define scalarpkg_Repeats_u32_count      4U
#define scalarpkg_Repeats_s32_count      4U
#define scalarpkg_Repeats_f32_count      4U
#define scalarpkg_Repeats_sf32_count     4U
#define scalarpkg_Repeats_flt_count      4U
#define scalarpkg_Repeats_flag_count     4U
#define scalarpkg_Repeats_level_count    4U
#define scalarpkg_Repeats_stamps_count   2U
#define scalarpkg_TextLists_text_size    8U
#define scalarpkg_TextLists_text_count   3U
#define scalarpkg_TextLists_blob_size    5U  // not a multiple of 4: the elements are padded
#define scalarpkg_TextLists_blob_count   3U

// Only test_callback_cpp.cc relies on this; harmless for every other test
// since no other field enables its own _callback_en override.
#define callbackpkg_CallbackMsg_value_callback_en 1

// CallbackParent routes every field except "value" through a callback, to
// exercise the callback path for a submessage, a repeated submessage, a
// repeated scalar and a bytes field (in addition to the plain scalar above).
#define callbackpkg_CallbackParent_child_callback_en    1
#define callbackpkg_CallbackParent_children_callback_en 1
#define callbackpkg_CallbackParent_numbers_callback_en  1
#define callbackpkg_CallbackParent_payload_callback_en  1

// CallbackChunks: "chunks" (repeated bytes) goes through a callback, "names" (repeated string) is stored.
#define callbackpkg_CallbackChunks_chunks_callback_en 1
#define callbackpkg_CallbackChunks_names_size         8U
#define callbackpkg_CallbackChunks_names_count        3U

namespace hikaripb {

class InputStream {
    uint32_t offset = 0;
    uint8_t* buffer;
    uint32_t& msg_len;

   public:
    InputStream(uint8_t* buffer, uint32_t& msg_len) : buffer(buffer), msg_len(msg_len) {}

    bool read(uint8_t* data, uint16_t len) {
        if ((offset + len - 1) >= msg_len) {
            return false;
        }
        memcpy(data, &buffer[offset], len);
        offset += len;
        return true;
    }

    bool skip(uint16_t len) {
        offset += len;
        if (offset >= msg_len) {
            return false;
        }
        return true;
    }

    bool pop(uint8_t* data) {
        if (offset >= msg_len) {
            return false;
        }
        *data = buffer[offset];
        offset++;
        return true;
    }

    void setOffset(uint32_t offset) { this->offset = offset; }

    uint32_t getOffset() const { return offset; }
};

class OutputStream {
    uint32_t offset = 0;
    uint8_t* buffer;

   public:
    OutputStream(uint8_t* buffer) : buffer(buffer) {}

    void write(const uint8_t* data, uint16_t len) {
        memcpy(&buffer[offset], data, len);
        offset += len;
    }

    void setOffset(uint32_t offset) { this->offset = offset; }

    uint32_t getOffset() const { return offset; }
};

}  // namespace hikaripb

#endif  // HIKARIPB_CONFIG_H
