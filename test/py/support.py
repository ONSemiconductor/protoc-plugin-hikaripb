"""Shared setup of the python test suite: locates the generated modules and imports them.

The Makefile (test/Makefile) generates everything and exports the locations:

    HIKARIPB_PY_DIR         type=py output (prefix=sample), pure Python or compiled with Cython
    HIKARIPB_PY_REF_DIR     protoc's own --python_out output, used as an independent reference
    HIKARIPB_PY_SINGLE_DIR  type=py output generated with single_file=all
    HIKARIPB_EXPECT_COMPILED  "1"/"0": assert that the runtime codec is (not) the Cython extension
"""

import importlib
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
GENERATED = os.path.join(ROOT, "build", "test", "generated")

GEN_DIR = os.environ.get("HIKARIPB_PY_DIR", os.path.join(GENERATED, "py"))
REF_DIR = os.environ.get("HIKARIPB_PY_REF_DIR", os.path.join(GENERATED, "py_ref"))
SINGLE_DIR = os.environ.get("HIKARIPB_PY_SINGLE_DIR", os.path.join(GENERATED, "py_single"))
EXPECT_COMPILED = os.environ.get("HIKARIPB_EXPECT_COMPILED")

sys.path.insert(0, GEN_DIR)

codec = importlib.import_module("sample_codec")
message = importlib.import_module("message_pb")
depth = importlib.import_module("depth_pb")
callback = importlib.import_module("callback_pb")
scalars = importlib.import_module("scalars_pb")
shared = importlib.import_module("shared.common_pb")
nested = importlib.import_module("nested_pb")
empty = importlib.import_module("empty_pb")

try:
    sys.path.insert(0, REF_DIR)
    ref_message = importlib.import_module("message_pb2")
    ref_depth = importlib.import_module("depth_pb2")
    ref_scalars = importlib.import_module("scalars_pb2")
    ref_nested = importlib.import_module("nested_pb2")
    ref_empty = importlib.import_module("empty_pb2")
except ImportError:
    ref_message = ref_depth = ref_scalars = ref_nested = ref_empty = None
finally:
    sys.path.remove(REF_DIR)

requires_reference = unittest.skipIf(ref_message is None, "google protobuf reference bindings not available")


def varint(value):
    """Reference varint encoder for hand-crafted wire data."""
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def field(number, wire, payload=b""):
    """One hand-crafted wire field: key + payload (the payload of wire type 2 gets its length prefix)."""
    body = varint(len(payload)) + payload if wire == 2 else payload
    return varint((number << 3) | wire) + body


def full_sample_message():
    """SampleMessage holding the values shared with the C/C++ tests (see expected_values.py)."""
    import expected_values as ev

    return message.SampleMessage(
        opt_value=ev.OPT_VALUE,
        opt_uint=ev.OPT_UINT,
        flag=ev.FLAG,
        color=message.Color(ev.COLOR),
        location=message.Point(x=ev.LOCATION_X, y=ev.LOCATION_Y),
        payload=ev.PAYLOAD,
        choice_u32=ev.CHOICE_U32,
        tags=[message.Color(t) for t in ev.TAGS],
        items=[message.Item(item_id=i["item_id"], checksum=i["checksum"], kind=message.ItemKind(i["kind"]))
               for i in ev.ITEMS],
        numbers=ev.NUMBERS,
        label=ev.LABEL,
        metadata=message.Metadata(kind=message.MetadataKind(ev.METADATA_KIND), revision=ev.METADATA_REVISION),
        sparse_tags=message.SparseTags(
            tag_1=ev.SPARSE_TAG_1,
            tag_25=ev.SPARSE_TAG_25,
            tag_75=ev.SPARSE_TAG_75,
            tag_150=ev.SPARSE_TAG_150,
            tag_200=ev.SPARSE_TAG_200,
        ),
    )


def assert_matches_expected(test, decoded):
    """Check a decoded SampleMessage against expected_values.py (same checks as the C/C++ decode tests)."""
    import expected_values as ev

    test.assertEqual(decoded.opt_value, ev.OPT_VALUE)
    test.assertEqual(decoded.opt_uint, ev.OPT_UINT)
    test.assertIs(decoded.flag, ev.FLAG)
    test.assertEqual(int(decoded.color), ev.COLOR)
    test.assertEqual((decoded.location.x, decoded.location.y), (ev.LOCATION_X, ev.LOCATION_Y))
    test.assertEqual(decoded.payload, ev.PAYLOAD)
    test.assertEqual(decoded.choice_u32, ev.CHOICE_U32)
    test.assertIsNone(decoded.choice_s32)
    test.assertEqual([int(t) for t in decoded.tags], ev.TAGS)
    test.assertEqual([{"item_id": i.item_id, "checksum": i.checksum, "kind": int(i.kind)} for i in decoded.items],
                     ev.ITEMS)
    test.assertEqual(list(decoded.numbers), ev.NUMBERS)
    test.assertEqual(decoded.label, ev.LABEL)
    test.assertEqual(int(decoded.metadata.kind), ev.METADATA_KIND)
    test.assertEqual(decoded.metadata.revision, ev.METADATA_REVISION)
    sparse = decoded.sparse_tags
    test.assertEqual((sparse.tag_1, sparse.tag_25, sparse.tag_75, sparse.tag_150, sparse.tag_200),
                     (ev.SPARSE_TAG_1, ev.SPARSE_TAG_25, ev.SPARSE_TAG_75, ev.SPARSE_TAG_150, ev.SPARSE_TAG_200))
