"""Messages and enums declared inside each other four levels deep (nested.proto: Outer.Middle.Inner.Leaf)."""

import enum
import unittest

import support
from support import codec, field, nested, varint


def build():
    return nested.Outer(
        kind=nested.OuterKind.OUTER_KIND_SECOND,
        middle=nested.Middle(
            kind=nested.MiddleKind.MIDDLE_KIND_FIRST,
            inner=nested.Inner(
                kind=nested.InnerKind.INNER_KIND_SECOND,
                leaf=nested.Leaf(kind=nested.LeafKind.LEAF_KIND_FIRST, value=1234))),
        shortcut=nested.Leaf(kind=nested.LeafKind.LEAF_KIND_SECOND, value=77))


class NestedTypesTest(unittest.TestCase):
    def test_every_level_is_a_module_level_class(self):
        for name in ("Outer", "Middle", "Inner", "Leaf"):
            self.assertTrue(issubclass(getattr(nested, name), codec.Message), name)
        for name in ("OuterKind", "MiddleKind", "InnerKind", "LeafKind"):
            self.assertTrue(issubclass(getattr(nested, name), enum.IntEnum), name)

    def test_wire_format(self):
        leaf = field(1, 0, b"\x01") + field(2, 0, varint(1234))
        inner = field(1, 0, b"\x02") + field(2, 2, leaf)
        middle = field(1, 0, b"\x01") + field(2, 2, inner)
        shortcut = field(1, 0, b"\x02") + field(2, 0, varint(77))
        self.assertEqual(build().serialize(), field(1, 0, b"\x02") + field(2, 2, middle) + field(3, 2, shortcut))

    def test_round_trip(self):
        decoded = nested.Outer().deserialize(build().serialize())
        self.assertEqual(decoded, build())
        self.assertEqual(decoded.kind, nested.OuterKind.OUTER_KIND_SECOND)
        self.assertEqual(decoded.middle.kind, nested.MiddleKind.MIDDLE_KIND_FIRST)
        self.assertEqual(decoded.middle.inner.kind, nested.InnerKind.INNER_KIND_SECOND)
        self.assertEqual(decoded.middle.inner.leaf.kind, nested.LeafKind.LEAF_KIND_FIRST)
        self.assertEqual(decoded.middle.inner.leaf.value, 1234)
        self.assertEqual(decoded.shortcut.value, 77)

    @support.requires_reference
    def test_agrees_with_protoc(self):
        mine = build().serialize()
        theirs = support.ref_nested.Outer.FromString(mine)
        self.assertEqual(theirs.middle.inner.leaf.value, 1234)
        self.assertEqual(theirs.shortcut.value, 77)
        self.assertEqual(theirs.SerializeToString(), mine)
        self.assertEqual(nested.Outer().deserialize(theirs.SerializeToString()), build())


if __name__ == "__main__":
    unittest.main()
