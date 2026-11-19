#pragma once
// Hand-written config consumed by the generated sample_defines.h / sample_bindings.h
// (referenced via the protoc "config_path" option, defaulted to no sub-directory here).

#include <stdbool.h>

#define SAMPLE_DEBUG            0
#define SAMPLE_CALLBACK         1
#define SAMPLE_ENABLE_MULTI_ENC 0
#define SAMPLE_ENABLE_MULTI_DEC 0
#define SAMPLE_ASSERT(x)        (void)(x)
#define SAMPLE_PRINT_ENABLE     0
// scalars.proto has float and repeated string/bytes fields.
#define SAMPLE_ENABLE_FLOAT          1
#define SAMPLE_ENABLE_REPEATED_BYTES 1
// Bumped from the default (8) so test_depth.c can successfully decode a
// 10-level-deep DepthL0..DepthL9 chain; a 14-level chain still exceeds this
// and is used to exercise DECODER_DEPTH_EXCEEDED.
#define SAMPLE_DEC_MAX_DEPTH    12U
// Only test_errors.c relies on this (crafted unknown-tag input); harmless for
// every other test since valid encoded data never contains an unknown tag.
#define SAMPLE_ERROR_ON_UNKNOWN_TAG 1

// Field storage sizes for variable-length / repeated members of SampleMessage.
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
#define scalarpkg_TextLists_blob_size    5U  // not a multiple of 4: the elements are padded
#define scalarpkg_TextLists_blob_count   3U

// Only test_callback.c relies on this; harmless for every other test since
// no other field enables its own _callback_en override.
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
