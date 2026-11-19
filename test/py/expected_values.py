# Mirrors test/c/expected_values.h and test/cpp/expected_values.h so all three
# generators' interop checks agree on what a "correctly decoded" message looks like.

OPT_VALUE = -42
OPT_UINT = 7
FLAG = True
COLOR = 2  # COLOR_GREEN

LOCATION_X = -10
LOCATION_Y = 20

PAYLOAD = bytes([0xDE, 0xAD, 0xBE, 0xEF])

CHOICE_U32 = 4242

TAGS = [1, 3]  # COLOR_RED, COLOR_BLUE

ITEMS = [
    {"item_id": 111, "checksum": 0x0A0B0C0D, "kind": 1},  # ITEM_KIND_NORMAL
    {"item_id": 222, "checksum": 0x01020304, "kind": 2},  # ITEM_KIND_SPECIAL
]

NUMBERS = [7, 77, 777]

LABEL = "proto"

METADATA_KIND = 1  # METADATA_KIND_PRIMARY
METADATA_REVISION = 9

# SparseTags: a lone tag, large gaps between tags, and a tag number (200)
# near the pb_u8 tag-storage ceiling that forces a multi-byte wire tag.
SPARSE_TAG_1 = 1
SPARSE_TAG_25 = 25
SPARSE_TAG_75 = 75
SPARSE_TAG_150 = 150
SPARSE_TAG_200 = 200

# scalars.proto (constructor arguments): every scalar type, an explicit zero/false next to the plain fields
# and the fields named like python keywords.
SCALARS = dict(
    u32=3000000000, s32=-123456, f32=0xDEADBEEF, sf32=-1234567, flt=1.5, flag=True, level=2,  # LEVEL_TWO
    text="scalar text", blob=bytes([0x01, 0x02, 0x03, 0xFF]),
    opt_u32=0, opt_text="opt", opt_level=1, opt_flt=-0.25, opt_flag=False,  # LEVEL_ONE
    from_=17, serialize_="ser", clear_="clr",
)

# Choice: the oneof member `text` plus two messages of shared/common.proto
CHOICE_TEXT = "choice"
CHOICE_EXTRA = dict(seconds=11, nanos=22, unit=2)  # UNIT_US
CHOICE_WHEN = dict(seconds=33, nanos=44, unit=1)  # UNIT_MS

# Repeats: one packed list per scalar type and two repeated messages
REPEATS = dict(
    u32=[1, 300, 70000], s32=[-1, 2, -300], f32=[7, 0xFFFFFFFF], sf32=[-5, 5], flt=[0.5, -2.0],
    flag=[True, False, True], level=[1, 2, 0],
)
REPEATS_STAMPS = [dict(seconds=1, nanos=0, unit=0), dict(seconds=2, nanos=0, unit=1)]

# TextLists: repeated string and bytes, both with an empty element in the middle
TEXTLISTS = dict(text=["first", "", "third"], blob=[bytes([0x01, 0x02, 0x03]), b"", bytes([0xFF])])
