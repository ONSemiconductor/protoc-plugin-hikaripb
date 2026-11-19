"""Nesting depth tests (mirror of test_depth.c / test_depth_cpp.cc): the decoder limits embedded message levels."""

import unittest

import support
from support import codec, depth, scalars

MAX_DEPTH = 12  # same limit as the C/C++ test configurations


def chain(levels):
    """DepthL0 -> DepthL1 -> ... holding `levels` messages in total (L0 is level 1)."""
    classes = [getattr(depth, "DepthL%d" % i) for i in range(levels)]
    root = classes[0](value=0)
    node = root
    for i in range(1, levels):
        node.next = classes[i](value=i)
        node = node.next
    return root


def node_chain(levels):
    """Node -> Node -> ... holding `levels` messages in total."""
    root = scalars.Node(value=0)
    node = root
    for i in range(1, levels):
        node.next = scalars.Node(value=i)
        node = node.next
    return root


class DepthTest(unittest.TestCase):
    def test_ten_levels_decode_successfully(self):
        data = chain(10).serialize()
        decoded = depth.DepthL0().deserialize(data, max_depth=MAX_DEPTH)
        node = decoded
        for level in range(10):
            self.assertEqual(node.value, level)
            node = node.next
        self.assertFalse(decoded.next.next.next.next.next.next.next.next.next.has_next())

    def test_fourteen_levels_exceed_the_max_depth(self):
        data = chain(14).serialize()
        with self.assertRaises(codec.DecodeError) as caught:
            depth.DepthL0().deserialize(data, max_depth=MAX_DEPTH)
        self.assertEqual(caught.exception.code, codec.DecodeErrorCode.DEPTH_EXCEEDED)

    def test_the_limit_counts_levels_including_the_root(self):
        data = chain(12).serialize()
        depth.DepthL0().deserialize(data, max_depth=12)
        with self.assertRaises(codec.DecodeError) as caught:
            depth.DepthL0().deserialize(data, max_depth=11)
        self.assertEqual(caught.exception.code, codec.DecodeErrorCode.DEPTH_EXCEEDED)

    def test_a_message_without_children_needs_one_level(self):
        depth.DepthL13().deserialize(depth.DepthL13(value=1).serialize(), max_depth=1)
        with self.assertRaises(codec.DecodeError):
            depth.DepthL12().deserialize(depth.DepthL12(next=depth.DepthL13(value=1)).serialize(), max_depth=1)

    def test_default_limit(self):
        ok = node_chain(codec.DEFAULT_MAX_DEPTH).serialize()
        scalars.Node().deserialize(ok)
        with self.assertRaises(codec.DecodeError) as caught:
            scalars.Node().deserialize(node_chain(codec.DEFAULT_MAX_DEPTH + 1).serialize())
        self.assertEqual(caught.exception.code, codec.DecodeErrorCode.DEPTH_EXCEEDED)

    def test_deep_chain_with_a_raised_limit(self):
        decoded = scalars.Node().deserialize(node_chain(300).serialize(), max_depth=1000)
        count = 0
        while decoded is not None:
            count += 1
            decoded = decoded.next if decoded.has_next() else None
        self.assertEqual(count, 300)


if __name__ == "__main__":
    unittest.main()
