#ifndef HIKARIPB_ALT_CONFIG_H
#define HIKARIPB_ALT_CONFIG_H
// Second configuration of the generated C++ code, for the static analysis (make analyze): every switch that the test
// configuration (../hikaripb_config.h) leaves off is on, so the code that depends on it is compiled and checked too. The
// code is only compiled, never linked: the print function and the assertion handler are declared, not defined.

#include <stdint.h>
#include <string.h>

#define HIKARIPB_DEBUG                         1
#define HIKARIPB_CALLBACK                      1
// A failed assertion does not return, as in a product: the analyzers see that the code after it never runs with the
// value that it checked.
[[noreturn]] void alt_assert_failed();
#define HIKARIPB_ASSERT(x)                     \
    do {                                       \
        if (!(x)) {                            \
            alt_assert_failed();               \
        }                                      \
    } while (false)
#define HIKARIPB_ENABLE_FLOAT                  1
#define HIKARIPB_ENABLE_REPEATED_BYTES         1
#define HIKARIPB_COMPRESS_ENUMS                0
#define HIKARIPB_CONTINUE_ON_OVERFLOW          1
#define HIKARIPB_CONTINUE_ON_CALLBACK_ERROR    1
#define HIKARIPB_CONTINUE_ON_ONEOF_ERROR       1
#define HIKARIPB_ERROR_ON_UNKNOWN_TAG          1
#define HIKARIPB_CONTINUE_ON_UNKNOWN_TAG_ERROR 1
#define HIKARIPB_DEC_MAX_DEPTH                 12U
#define HIKARIPB_DEC_VARINT_UNROLL             1
#define HIKARIPB_ENC_PAD_LENGTH                3U

#define HIKARIPB_PRINT_ENABLE 1
void alt_print(const char* format, ...);
#define HIKARIPB_PRINT(...)   alt_print(__VA_ARGS__)
#define HIKARIPB_PRINTLN(...) alt_print(__VA_ARGS__)

// Field storage sizes and counts: the same as the ones of the test configuration.
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

// The callbacks of the fields that the callback.proto schema routes through one.
#define callbackpkg_CallbackMsg_value_callback_en       1
#define callbackpkg_CallbackParent_child_callback_en    1
#define callbackpkg_CallbackParent_children_callback_en 1
#define callbackpkg_CallbackParent_numbers_callback_en  1
#define callbackpkg_CallbackParent_payload_callback_en  1
#define callbackpkg_CallbackChunks_chunks_callback_en   1
#define callbackpkg_CallbackChunks_names_size           8U
#define callbackpkg_CallbackChunks_names_count          3U

namespace hikaripb {

class InputStream {
    uint32_t offset = 0;
    uint8_t* buffer;
    uint32_t& msg_len;

   public:
    InputStream(uint8_t* data, uint32_t& length) : buffer(data), msg_len(length) {}

    bool read(uint8_t* data, uint16_t len) {
        if ((offset + len - 1U) >= msg_len) {
            return false;
        }
        memcpy(data, &buffer[offset], len);
        offset += len;
        return true;
    }

    bool skip(uint16_t len) {
        offset += len;
        return offset < msg_len;
    }

    bool pop(uint8_t* data) {
        if (offset >= msg_len) {
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

#endif  // HIKARIPB_ALT_CONFIG_H
