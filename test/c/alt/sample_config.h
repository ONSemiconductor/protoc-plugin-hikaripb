#pragma once
// Second configuration of the generated C code, for the static analysis (make analyze): every switch that the test
// configuration (../sample_config.h) leaves off is on, so the code that depends on it is compiled and checked too. The
// code is only compiled, never linked: the print function and the callbacks are declared, not defined.

// For a standard checker the offset of a field is the offsetof of <stddef.h>, see <prefix>_types.h.
#include <stddef.h>
#define PB_OFFSETOF offsetof

#define SAMPLE_DEBUG                         1
#define SAMPLE_CALLBACK                      1
#define SAMPLE_ENABLE_MULTI_ENC              1
#define SAMPLE_ENABLE_MULTI_DEC              1
// A failed assertion does not return, as in a product: the analyzers see that the code after it never runs with the
// value that it checked.
_Noreturn void alt_assert_failed(void);
#define SAMPLE_ASSERT(x)                     \
    do {                                     \
        if (!(x)) {                          \
            alt_assert_failed();             \
        }                                    \
    } while (0)
#define SAMPLE_ENABLE_FLOAT                  1
#define SAMPLE_ENABLE_REPEATED_BYTES         1
#define SAMPLE_COMPRESS_ENUMS                0
#define SAMPLE_CONTINUE_ON_OVERFLOW          1
#define SAMPLE_CONTINUE_ON_CALLBACK_ERROR    1
#define SAMPLE_CONTINUE_ON_ONEOF_ERROR       1
#define SAMPLE_ERROR_ON_UNKNOWN_TAG          1
#define SAMPLE_CONTINUE_ON_UNKNOWN_TAG_ERROR 1
#define SAMPLE_DEC_MAX_DEPTH                 12U
#define SAMPLE_DEC_VARINT_UNROLL             1
#define SAMPLE_ENC_PAD_LENGTH                3U

#define SAMPLE_PRINT_ENABLE 1
void alt_print(const char* format, ...);
#define SAMPLE_PRINT(...)   alt_print(__VA_ARGS__)
#define SAMPLE_PRINTLN(...) alt_print(__VA_ARGS__)

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
#define scalarpkg_Scalars_clear_size     8U
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
