#ifndef TEST_CPP_EXPECTED_VALUES_H
#define TEST_CPP_EXPECTED_VALUES_H

#include <cstdint>

// Constants used by the C++ encode/decode tests, mirrored in test/c/expected_values.h
// and test/py/expected_values.py so all three generators' interop checks agree.

#define EXPECTED_OPT_VALUE ((int32_t) - 42)
#define EXPECTED_OPT_UINT  ((uint32_t)7U)
#define EXPECTED_FLAG      ((bool) true)
#define EXPECTED_COLOR     ((uint32_t)2U) /* COLOR_GREEN */

#define EXPECTED_LOCATION_X ((int32_t) - 10)
#define EXPECTED_LOCATION_Y ((int32_t)20)

#define EXPECTED_PAYLOAD_LENGTH ((uint32_t)4U)
#define EXPECTED_PAYLOAD_BYTE_0 ((uint8_t)0xDEU)
#define EXPECTED_PAYLOAD_BYTE_1 ((uint8_t)0xADU)
#define EXPECTED_PAYLOAD_BYTE_2 ((uint8_t)0xBEU)
#define EXPECTED_PAYLOAD_BYTE_3 ((uint8_t)0xEFU)

#define EXPECTED_CHOICE_U32 ((uint32_t)4242U)

#define EXPECTED_TAGS_COUNT ((uint32_t)2U)
#define EXPECTED_TAG_0      ((uint32_t)1U) /* COLOR_RED */
#define EXPECTED_TAG_1      ((uint32_t)3U) /* COLOR_BLUE */

#define EXPECTED_ITEMS_COUNT      ((uint32_t)2U)
#define EXPECTED_ITEM0_ID         ((uint32_t)111U)
#define EXPECTED_ITEM0_CHECKSUM   ((uint32_t)0x0A0B0C0DU)
#define EXPECTED_ITEM0_KIND       ((uint32_t)1U) /* ITEM_KIND_NORMAL */
#define EXPECTED_ITEM1_ID         ((uint32_t)222U)
#define EXPECTED_ITEM1_CHECKSUM   ((uint32_t)0x01020304U)
#define EXPECTED_ITEM1_KIND       ((uint32_t)2U) /* ITEM_KIND_SPECIAL */

#define EXPECTED_NUMBERS_COUNT ((uint32_t)3U)
#define EXPECTED_NUMBER_0      ((uint32_t)7U)
#define EXPECTED_NUMBER_1      ((uint32_t)77U)
#define EXPECTED_NUMBER_2      ((uint32_t)777U)

#define EXPECTED_LABEL        "proto"
#define EXPECTED_LABEL_LENGTH ((uint32_t)5U)

#define EXPECTED_METADATA_KIND     ((uint32_t)1U) /* METADATA_KIND_PRIMARY */
#define EXPECTED_METADATA_REVISION ((uint32_t)9U)

// SparseTags: a lone tag, large gaps between tags, and a tag number (200)
// near the pb_u8 tag-storage ceiling that forces a multi-byte wire tag.
#define EXPECTED_SPARSE_TAG_1   ((uint32_t)1U)
#define EXPECTED_SPARSE_TAG_25  ((uint32_t)25U)
#define EXPECTED_SPARSE_TAG_75  ((uint32_t)75U)
#define EXPECTED_SPARSE_TAG_150 ((uint32_t)150U)
#define EXPECTED_SPARSE_TAG_200 ((uint32_t)200U)

// scalars.proto (generated from test/proto, the python tests use the same schema): Scalars holds every
// scalar type, an explicit zero/false next to the plain fields, and the fields named like python keywords.
#define EXPECTED_SC_U32           ((uint32_t)3000000000U)
#define EXPECTED_SC_S32           ((int32_t) - 123456)
#define EXPECTED_SC_F32           ((uint32_t)0xDEADBEEFU)
#define EXPECTED_SC_SF32          ((int32_t) - 1234567)
#define EXPECTED_SC_FLT           1.5f
#define EXPECTED_SC_FLAG          ((bool) true)
#define EXPECTED_SC_LEVEL         ((uint32_t)2U) /* LEVEL_TWO */
#define EXPECTED_SC_TEXT          "scalar text"
#define EXPECTED_SC_TEXT_LENGTH   ((uint32_t)11U)
#define EXPECTED_SC_BLOB          {0x01U, 0x02U, 0x03U, 0xFFU}
#define EXPECTED_SC_BLOB_LENGTH   ((uint32_t)4U)
#define EXPECTED_SC_OPT_U32       ((uint32_t)0U)
#define EXPECTED_SC_OPT_TEXT      "opt"
#define EXPECTED_SC_OPT_TEXT_LENGTH ((uint32_t)3U)
#define EXPECTED_SC_OPT_LEVEL     ((uint32_t)1U) /* LEVEL_ONE */
#define EXPECTED_SC_OPT_FLT       (-0.25f)
#define EXPECTED_SC_OPT_FLAG      ((bool) false)
#define EXPECTED_SC_FROM          ((uint32_t)17U)
#define EXPECTED_SC_SERIALIZE     "ser"
#define EXPECTED_SC_SERIALIZE_LENGTH ((uint32_t)3U)
#define EXPECTED_SC_CLEAR         "clr"
#define EXPECTED_SC_CLEAR_LENGTH  ((uint32_t)3U)

// Choice: the oneof member `text` plus two messages of shared/common.proto
#define EXPECTED_CH_TEXT           "choice"
#define EXPECTED_CH_TEXT_LENGTH    ((uint32_t)6U)
#define EXPECTED_CH_EXTRA_SECONDS  ((uint32_t)11U)
#define EXPECTED_CH_EXTRA_NANOS    ((uint32_t)22U)
#define EXPECTED_CH_EXTRA_UNIT     ((uint32_t)2U) /* UNIT_US */
#define EXPECTED_CH_WHEN_SECONDS   ((uint32_t)33U)
#define EXPECTED_CH_WHEN_NANOS     ((uint32_t)44U)
#define EXPECTED_CH_WHEN_UNIT      ((uint32_t)1U) /* UNIT_MS */

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
