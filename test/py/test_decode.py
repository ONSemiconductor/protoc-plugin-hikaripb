"""Decoder tests: golden bytes, protobuf wire flexibility (packed/unpacked, padding, unknown fields) and presence."""

import struct
import unittest

import support
from support import codec, message, scalars, shared, field, varint
from test_encode import GOLDEN_SAMPLE_MESSAGE


class DecodeTest(unittest.TestCase):
    def test_golden_bytes(self):
        support.assert_matches_expected(self, message.SampleMessage().deserialize(bytes.fromhex(GOLDEN_SAMPLE_MESSAGE)))

    def test_deserialize_returns_the_message(self):
        msg = message.SampleMessage()
        self.assertIs(msg.deserialize(b""), msg)

    def test_empty_input_gives_an_empty_message(self):
        msg = message.SampleMessage().deserialize(b"")
        self.assertEqual(msg.serialize(), b"")
        self.assertFalse(msg.has_opt_value() or msg.has_location() or msg.has_items())

    def test_input_may_be_any_bytes_like_object(self):
        data = bytes.fromhex(GOLDEN_SAMPLE_MESSAGE)
        for wrapper in (bytes, bytearray, memoryview):
            with self.subTest(wrapper=wrapper.__name__):
                support.assert_matches_expected(self, message.SampleMessage().deserialize(wrapper(data)))

    def test_deserialize_replaces_the_previous_content(self):
        msg = support.full_sample_message()
        msg.deserialize(field(1, 0, varint(2)))
        self.assertEqual(msg.opt_value, 1)
        self.assertEqual(msg.serialize(), field(1, 0, varint(2)))
        self.assertFalse(msg.has_location() or msg.has_items() or msg.has_choice_u32())

    def test_presence_after_decoding(self):
        msg = message.SampleMessage().deserialize(bytes.fromhex(GOLDEN_SAMPLE_MESSAGE))
        for name in ("opt_value", "opt_uint", "location", "payload", "choice_u32", "tags", "items", "numbers",
                     "label", "metadata", "sparse_tags"):
            with self.subTest(field=name):
                self.assertTrue(getattr(msg, "has_" + name)())
        self.assertFalse(msg.has_choice_s32())
        self.assertTrue(msg.metadata.has_revision())

    def test_empty_submessage_on_the_wire_is_kept(self):
        msg = message.SampleMessage().deserialize(b"\x2a\x00")
        self.assertTrue(msg.has_location())
        self.assertEqual(msg.serialize(), b"\x2a\x00")

    def test_unset_optional_scalars_stay_none(self):
        msg = message.SampleMessage().deserialize(field(3, 0, b"\x01"))
        self.assertIsNone(msg.opt_value)
        self.assertIsNone(msg.opt_uint)
        self.assertIs(msg.flag, True)
        self.assertFalse(msg.has_opt_value())

    def test_enum_values_become_enum_members_unknown_ones_stay_integers(self):
        msg = message.SampleMessage().deserialize(field(4, 0, b"\x02"))
        self.assertIs(msg.color, message.Color.COLOR_GREEN)
        msg = message.SampleMessage().deserialize(field(4, 0, b"\x63"))
        self.assertEqual(msg.color, 99)
        self.assertNotIsInstance(msg.color, message.Color)
        self.assertEqual(msg.serialize(), field(4, 0, b"\x63"))

    def test_packed_and_unpacked_repeated_scalars_are_both_accepted(self):
        packed = field(11, 2, b"\x01\x02")
        unpacked = field(11, 0, b"\x01") + field(11, 0, b"\x02")
        self.assertEqual(message.SampleMessage().deserialize(packed).numbers, [1, 2])
        self.assertEqual(message.SampleMessage().deserialize(unpacked).numbers, [1, 2])
        mixed = packed + unpacked + packed
        self.assertEqual(message.SampleMessage().deserialize(mixed).numbers, [1, 2, 1, 2, 1, 2])

    def test_empty_packed_field(self):
        msg = message.SampleMessage().deserialize(field(11, 2))
        self.assertEqual(msg.numbers, [])

    def test_padded_varints_as_written_by_the_c_encoder(self):
        # the C/C++ encoders write every length prefix padded to two bytes (0x84 0x00 == 4)
        data = b"\x2a\x84\x00" + field(1, 0, varint(20)) + field(2, 0, varint(40))
        msg = message.SampleMessage().deserialize(data)
        self.assertEqual((msg.location.x, msg.location.y), (10, 20))
        # padding is allowed for values too: 0x86 0x80 0x00 == 6 == zigzag(3)
        self.assertEqual(message.SampleMessage().deserialize(field(1, 0, b"\x86\x80\x00")).opt_value, 3)

    def test_unknown_fields_are_skipped(self):
        junk = (field(90, 0, varint(2 ** 40)) + field(91, 1, b"12345678") + field(92, 2, b"abc") +
                field(93, 5, b"1234"))
        data = junk + field(2, 0, b"\x07") + junk
        msg = message.SampleMessage().deserialize(data)
        self.assertEqual(msg.opt_uint, 7)

    def test_known_field_with_the_wrong_wire_type_is_skipped(self):
        msg = message.SampleMessage().deserialize(field(2, 2, b"abc") + field(3, 0, b"\x01"))
        self.assertIsNone(msg.opt_uint)
        self.assertTrue(msg.flag)

    def test_last_value_of_a_scalar_wins(self):
        msg = message.SampleMessage().deserialize(field(2, 0, b"\x01") + field(2, 0, b"\x02"))
        self.assertEqual(msg.opt_uint, 2)

    def test_repeated_submessage_field_appends(self):
        data = field(10, 2, field(1, 0, b"\x01")) + field(10, 2, field(1, 0, b"\x02"))
        msg = message.SampleMessage().deserialize(data)
        self.assertEqual([i.item_id for i in msg.items], [1, 2])
        self.assertIsInstance(msg.items, codec.MessageList)

    def test_oneof_last_member_wins_by_default(self):
        msg = message.SampleMessage().deserialize(field(7, 0, b"\x05") + field(8, 0, b"\x03"))
        self.assertIsNone(msg.choice_u32)
        self.assertEqual(msg.choice_s32, -2)
        msg = message.SampleMessage().deserialize(field(8, 0, b"\x03") + field(7, 0, b"\x05"))
        self.assertEqual((msg.choice_u32, msg.choice_s32), (5, None))

    def test_string_decoding(self):
        text = "h\u00e9llo \u20ac \U0001F600"
        msg = scalars.Scalars().deserialize(field(8, 2, text.encode("utf-8")))
        self.assertEqual(msg.text, text)
        self.assertIsInstance(msg.text, str)

    def test_bytes_decoding(self):
        msg = scalars.Scalars().deserialize(field(9, 2, b"\x00\xff"))
        self.assertEqual(msg.blob, b"\x00\xff")
        self.assertIs(type(msg.blob), bytes)

    def test_scalar_types(self):
        data = b"".join([
            field(1, 0, varint(0xFFFFFFFF)), field(2, 0, varint(4294967295)), field(3, 5, b"\xff\xff\xff\xff"),
            field(4, 5, b"\x00\x00\x00\x80"), field(5, 5, struct.pack("<f", -2.5)), field(6, 0, b"\x02"),
            field(10, 0, b"\x00"), field(13, 5, struct.pack("<f", 0.0)),
        ])
        msg = scalars.Scalars().deserialize(data)
        self.assertEqual((msg.u32, msg.s32, msg.f32, msg.sf32, msg.flt, msg.flag), (0xFFFFFFFF, -2 ** 31, 0xFFFFFFFF, -2 ** 31, -2.5, True))
        self.assertEqual((msg.opt_u32, msg.opt_flt), (0, 0.0))
        self.assertTrue(msg.has_opt_u32() and msg.has_opt_flt())

    def test_sint32_zigzag_values(self):
        for wire, value in ((0, 0), (1, -1), (2, 1), (3, -2), (4294967294, 2147483647), (4294967295, -2147483648)):
            with self.subTest(wire=wire):
                self.assertEqual(scalars.Scalars().deserialize(field(2, 0, varint(wire))).s32, value)

    def test_repeated_scalar_types(self):
        data = b"".join([
            field(1, 2, b"\x01" + varint(300)), field(2, 2, b"\x01\x02"), field(3, 2, b"\x01\x00\x00\x00"),
            field(4, 2, b"\xff\xff\xff\xff"), field(5, 2, struct.pack("<ff", 1.0, -1.0)), field(6, 2, b"\x01\x00"),
            field(7, 2, b"\x01\x05"),
        ])
        msg = scalars.Repeats().deserialize(data)
        self.assertEqual(msg.u32, [1, 300])
        self.assertEqual(msg.s32, [-1, 1])
        self.assertEqual((msg.f32, msg.sf32), ([1], [-1]))
        self.assertEqual(msg.flt, [1.0, -1.0])
        self.assertEqual(msg.flag, [True, False])
        self.assertEqual(msg.level, [scalars.Level.LEVEL_ONE, 5])

    def test_repeated_strings_and_bytes(self):
        data = field(1, 2, b"a") + field(1, 2, b"") + field(2, 2, b"\x01")
        msg = scalars.TextLists().deserialize(data)
        self.assertEqual((msg.text, msg.blob), (["a", ""], [b"\x01"]))

    def test_message_from_another_module(self):
        msg = scalars.Choice().deserialize(field(3, 2, field(1, 0, b"\x05") + field(3, 0, b"\x01")))
        self.assertIsInstance(msg.stamp, shared.Stamp)
        self.assertEqual((msg.stamp.seconds, msg.stamp.unit), (5, shared.Unit.UNIT_MS))
        self.assertTrue(msg.has_stamp())
        self.assertFalse(msg.has_when())

    def test_oneof_members_read_none_until_set(self):
        msg = scalars.Choice()
        self.assertEqual((msg.number, msg.text, msg.stamp, msg.level), (None, None, None, None))

    @support.requires_reference
    def test_reference_encoded_message(self):
        ref = support.ref_message.SampleMessage(opt_value=-5, flag=True, color=2, label="x", numbers=[1, 1000])
        ref.location.x = 4
        ref.items.add(item_id=9, checksum=3, kind=1)
        ref.choice_s32 = -8
        msg = message.SampleMessage().deserialize(ref.SerializeToString())
        self.assertEqual((msg.opt_value, msg.flag, msg.color, msg.label, msg.numbers), (-5, True, 2, "x", [1, 1000]))
        self.assertEqual((msg.location.x, msg.location.y), (4, None))
        self.assertEqual([(i.item_id, i.checksum, int(i.kind)) for i in msg.items], [(9, 3, 1)])
        self.assertEqual(msg.choice_s32, -8)


if __name__ == "__main__":
    unittest.main()
