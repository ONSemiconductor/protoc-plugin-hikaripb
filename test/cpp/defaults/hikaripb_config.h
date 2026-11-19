#ifndef HIKARIPB_DEFAULTS_CONFIG_H
#define HIKARIPB_DEFAULTS_CONFIG_H
// Third configuration of the generated C++ code, for the static analysis (make analyze): the defaults of the library,
// except the two switches that the schemas need. Callbacks are off, so every field has storage and the code of the
// callbacks is compiled out. The code is only compiled, never linked.

#include <stdint.h>
#include <string.h>

#define HIKARIPB_ENABLE_FLOAT          1
#define HIKARIPB_ENABLE_REPEATED_BYTES 1

// Field storage sizes and counts: the same as the ones of the test configuration, and the fields that it routes
// through a callback.
#define samplepkg_SampleMessage_payload_size  8U
#define samplepkg_SampleMessage_label_size    16U
#define samplepkg_SampleMessage_tags_count    3U
#define samplepkg_SampleMessage_items_count   2U
#define samplepkg_SampleMessage_numbers_count 3U

#define scalarpkg_Scalars_text_size      16U
#define scalarpkg_Scalars_blob_size      8U
#define scalarpkg_Scalars_opt_text_size  16U
#define scalarpkg_Scalars_serialize_size 8U
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
#define scalarpkg_TextLists_blob_size    5U
#define scalarpkg_TextLists_blob_count   3U

#define callbackpkg_CallbackParent_children_count 2U
#define callbackpkg_CallbackParent_numbers_count  4U
#define callbackpkg_CallbackParent_payload_size   8U
#define callbackpkg_CallbackChunks_chunks_size    8U
#define callbackpkg_CallbackChunks_chunks_count   3U
#define callbackpkg_CallbackChunks_names_size     8U
#define callbackpkg_CallbackChunks_names_count    3U

namespace hikaripb {

class InputStream {
    uint32_t offset = 0;
    const uint8_t* buffer;
    uint32_t length;

   public:
    InputStream(const uint8_t* data, uint32_t len) : buffer(data), length(len) {}

    bool read(uint8_t* data, uint16_t len) {
        if ((offset + len) > length) {
            return false;
        }
        memcpy(data, &buffer[offset], len);
        offset += len;
        return true;
    }

    bool skip(uint16_t len) {
        if ((offset + len) > length) {
            return false;
        }
        offset += len;
        return true;
    }

    bool pop(uint8_t* data) {
        if (offset >= length) {
            return false;
        }
        *data = buffer[offset];
        offset++;
        return true;
    }

    void setOffset(uint32_t value) { offset = value; }

    uint32_t getOffset() const { return offset; }
};

class OutputStream {
    uint32_t offset = 0;
    uint8_t* buffer;

   public:
    explicit OutputStream(uint8_t* data) : buffer(data) {}

    void write(const uint8_t* data, uint16_t len) {
        memcpy(&buffer[offset], data, len);
        offset += len;
    }

    void setOffset(uint32_t value) { offset = value; }

    uint32_t getOffset() const { return offset; }
};

}  // namespace hikaripb

#endif  // HIKARIPB_DEFAULTS_CONFIG_H
