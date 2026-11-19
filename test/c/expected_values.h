#ifndef TEST_C_EXPECTED_VALUES_H
#define TEST_C_EXPECTED_VALUES_H

#include "sample_defines.h"

// Constants used by the C encode/decode tests, mirrored in test/cpp/expected_values.h
// and test/py/expected_values.py so all three generators' interop checks agree.

#define EXPECTED_OPT_VALUE ((pb_s32) - 42)
#define EXPECTED_OPT_UINT  ((pb_u32)7U)
#define EXPECTED_FLAG      ((pb_bool) true)
#define EXPECTED_COLOR     ((pb_u32)2U) /* COLOR_GREEN */

#define EXPECTED_LOCATION_X ((pb_s32) - 10)
#define EXPECTED_LOCATION_Y ((pb_s32)20)

#define EXPECTED_PAYLOAD_LENGTH ((pb_u32)4U)
#define EXPECTED_PAYLOAD_BYTE_0 ((pb_u8)0xDEU)
#define EXPECTED_PAYLOAD_BYTE_1 ((pb_u8)0xADU)
#define EXPECTED_PAYLOAD_BYTE_2 ((pb_u8)0xBEU)
#define EXPECTED_PAYLOAD_BYTE_3 ((pb_u8)0xEFU)

#define EXPECTED_CHOICE_U32 ((pb_u32)4242U)

#define EXPECTED_TAGS_COUNT ((pb_u32)2U)
#define EXPECTED_TAG_0      ((pb_u32)1U) /* COLOR_RED */
#define EXPECTED_TAG_1      ((pb_u32)3U) /* COLOR_BLUE */

#define EXPECTED_ITEMS_COUNT      ((pb_u32)2U)
#define EXPECTED_ITEM0_ID         ((pb_u32)111U)
#define EXPECTED_ITEM0_CHECKSUM   ((pb_u32)0x0A0B0C0DU)
#define EXPECTED_ITEM0_KIND       ((pb_u32)1U) /* ITEM_KIND_NORMAL */
#define EXPECTED_ITEM1_ID         ((pb_u32)222U)
#define EXPECTED_ITEM1_CHECKSUM   ((pb_u32)0x01020304U)
#define EXPECTED_ITEM1_KIND       ((pb_u32)2U) /* ITEM_KIND_SPECIAL */

#define EXPECTED_NUMBERS_COUNT ((pb_u32)3U)
#define EXPECTED_NUMBER_0      ((pb_u32)7U)
#define EXPECTED_NUMBER_1      ((pb_u32)77U)
#define EXPECTED_NUMBER_2      ((pb_u32)777U)

#define EXPECTED_LABEL        "proto"
#define EXPECTED_LABEL_LENGTH ((pb_u32)5U)

#define EXPECTED_METADATA_KIND     ((pb_u32)1U) /* METADATA_KIND_PRIMARY */
#define EXPECTED_METADATA_REVISION ((pb_u32)9U)

// SparseTags: a lone tag, large gaps between tags, and a tag number (200)
// near the pb_u8 tag-storage ceiling that forces a multi-byte wire tag.
#define EXPECTED_SPARSE_TAG_1   ((pb_u32)1U)
#define EXPECTED_SPARSE_TAG_25  ((pb_u32)25U)
#define EXPECTED_SPARSE_TAG_75  ((pb_u32)75U)
#define EXPECTED_SPARSE_TAG_150 ((pb_u32)150U)
#define EXPECTED_SPARSE_TAG_200 ((pb_u32)200U)

// scalars.proto (generated from test/proto, the python tests use the same schema): Scalars holds every
// scalar type, an explicit zero/false next to the plain fields, and the fields named like python keywords.
#define EXPECTED_SC_U32           ((pb_u32)3000000000U)
#define EXPECTED_SC_S32           ((pb_s32) - 123456)
#define EXPECTED_SC_F32           ((pb_u32)0xDEADBEEFU)
#define EXPECTED_SC_SF32          ((pb_s32) - 1234567)
#define EXPECTED_SC_FLT           1.5f
#define EXPECTED_SC_FLAG          ((pb_bool) true)
#define EXPECTED_SC_LEVEL         ((pb_u32)2U) /* LEVEL_TWO */
#define EXPECTED_SC_TEXT          "scalar text"
#define EXPECTED_SC_TEXT_LENGTH   ((pb_u32)11U)
#define EXPECTED_SC_BLOB          {0x01U, 0x02U, 0x03U, 0xFFU}
#define EXPECTED_SC_BLOB_LENGTH   ((pb_u32)4U)
#define EXPECTED_SC_OPT_U32       ((pb_u32)0U)
#define EXPECTED_SC_OPT_TEXT      "opt"
#define EXPECTED_SC_OPT_TEXT_LENGTH ((pb_u32)3U)
#define EXPECTED_SC_OPT_LEVEL     ((pb_u32)1U) /* LEVEL_ONE */
#define EXPECTED_SC_OPT_FLT       (-0.25f)
#define EXPECTED_SC_OPT_FLAG      ((pb_bool) false)
#define EXPECTED_SC_FROM          ((pb_u32)17U)
#define EXPECTED_SC_SERIALIZE     "ser"
#define EXPECTED_SC_SERIALIZE_LENGTH ((pb_u32)3U)
#define EXPECTED_SC_CLEAR         "clr"
#define EXPECTED_SC_CLEAR_LENGTH  ((pb_u32)3U)

// Choice: the oneof member `text` plus two messages of shared/common.proto
#define EXPECTED_CH_TEXT           "choice"
#define EXPECTED_CH_TEXT_LENGTH    ((pb_u32)6U)
#define EXPECTED_CH_EXTRA_SECONDS  ((pb_u32)11U)
#define EXPECTED_CH_EXTRA_NANOS    ((pb_u32)22U)
#define EXPECTED_CH_EXTRA_UNIT     ((pb_u32)2U) /* UNIT_US */
#define EXPECTED_CH_WHEN_SECONDS   ((pb_u32)33U)
#define EXPECTED_CH_WHEN_NANOS     ((pb_u32)44U)
#define EXPECTED_CH_WHEN_UNIT      ((pb_u32)1U) /* UNIT_MS */

// Repeats: one packed list per scalar type and two repeated messages
#define EXPECTED_RP_U32           {1U, 300U, 70000U}
#define EXPECTED_RP_S32           {-1, 2, -300}
#define EXPECTED_RP_F32           {7U, 0xFFFFFFFFU}
#define EXPECTED_RP_SF32          {-5, 5}
#define EXPECTED_RP_FLT           {0.5f, -2.0f}
#define EXPECTED_RP_FLAG          {true, false, true}
#define EXPECTED_RP_LEVEL         {1U, 2U, 0U}
#define EXPECTED_RP_STAMP_SECONDS {1U, 2U}
#define EXPECTED_RP_STAMP_UNIT    {0U, 1U}

// TextLists: repeated string and bytes, both with an empty element in the middle
#define EXPECTED_TL_TEXT   {"first", "", "third"}
#define EXPECTED_TL_BLOB_0 {0x01U, 0x02U, 0x03U}
#define EXPECTED_TL_BLOB_2 {0xFFU}

#endif
