"""A message without fields (empty.proto: Ping), alone and embedded in Pong."""

import unittest

import support
from support import codec, empty, field

Code = codec.DecodeErrorCode


def build():
    return empty.Pong(seq=7, ping=empty.Ping(), ack=empty.Ping())


class EmptyMessageTest(unittest.TestCase):
    def test_an_empty_message_has_no_bytes(self):
        self.assertTrue(issubclass(empty.Ping, codec.Message))
        self.assertEqual(empty.Ping().serialize(), b"")
        self.assertEqual(empty.Ping().deserialize(b""), empty.Ping())

    def test_wire_format(self):
        self.assertEqual(build().serialize(), field(1, 0, b"\x07") + field(2, 2) + field(3, 2))

    def test_round_trip(self):
        decoded = empty.Pong().deserialize(build().serialize())
        self.assertEqual(decoded, build())
        self.assertEqual(decoded.seq, 7)
        self.assertTrue(decoded.has_ping())
        self.assertTrue(decoded.has_ack())
        self.assertTrue(decoded.has_reply())

    def test_a_field_of_an_empty_message_is_unknown(self):
        raw = field(1, 0, b"\x05")
        self.assertEqual(empty.Ping().deserialize(raw), empty.Ping())
        with self.assertRaises(codec.DecodeError) as caught:
            empty.Ping().deserialize(raw, strict=True)
        self.assertEqual(caught.exception.code, Code.UNKNOWN_TAG)

    @support.requires_reference
    def test_agrees_with_protoc(self):
        mine = build().serialize()
        theirs = support.ref_empty.Pong.FromString(mine)
        self.assertEqual(theirs.seq, 7)
        self.assertTrue(theirs.HasField("ping"))
        self.assertEqual(theirs.WhichOneof("reply"), "ack")
        self.assertEqual(theirs.SerializeToString(), mine)


if __name__ == "__main__":
    unittest.main()
