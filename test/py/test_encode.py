"""Encoder tests: golden wire bytes, protobuf presence rules and agreement with protoc's own python runtime."""

import struct
import unittest

import support
from support import codec, message, scalars, shared, field, varint


# SampleMessage of expected_values.py; the bytes were checked against protoc's python runtime.
GOLDEN_SAMPLE_MESSAGE = (
    "0853" "1007" "1801" "2002"
    "2a04" "08131028"
    "3204" "deadbeef"
    "3892" "21"
    "4a02" "0103"
    "5209" "086f" "150d0c0b0a" "1801"
    "520a" "08de01" "1504030201" "1802"
    "5a04" "074d8906"
    "6205" "70726f746f"
    "6a04" "08011009"
    "7210" "0801" "c80119" "d8044b" "b0099601" "c00cc801"
)


class EncodeTest(unittest.TestCase):
    def test_full_message_golden_bytes(self):
        self.assertEqual(support.full_sample_message().serialize().hex(), GOLDEN_SAMPLE_MESSAGE)

    def test_serialize_returns_bytes(self):
        self.assertIs(type(support.full_sample_message().serialize()), bytes)

    def test_serialize_does_not_change_the_message(self):
        msg = support.full_sample_message()
        self.assertEqual(msg.serialize(), msg.serialize())

    def test_runtime_flavour(self):
        if support.EXPECT_COMPILED is not None:
            self.assertEqual(codec.COMPILED, support.EXPECT_COMPILED == "1")

    @support.requires_reference
    def test_agrees_with_protoc_python_runtime(self):
        ref = support.ref_message.SampleMessage()
        ref.ParseFromString(support.full_sample_message().serialize())
        self.assertEqual(ref.opt_value, -42)
        self.assertEqual(ref.location.y, 20)
        self.assertEqual(ref.WhichOneof("choice"), "choice_u32")
        self.assertEqual([i.item_id for i in ref.items], [111, 222])
        self.assertEqual(ref.SerializeToString(), support.full_sample_message().serialize())


class PresenceTest(unittest.TestCase):
    def test_empty_message_encodes_to_nothing(self):
        self.assertEqual(message.SampleMessage().serialize(), b"")

    def test_default_values_of_plain_scalars_are_omitted(self):
        msg = message.SampleMessage(flag=False, color=message.Color.COLOR_UNSPECIFIED, tags=[], numbers=[])
        self.assertEqual(msg.serialize(), b"")
        self.assertEqual(message.Item(checksum=0, kind=message.ItemKind.ITEM_KIND_UNSPECIFIED).serialize(), b"")

    def test_optional_scalar_is_written_even_when_zero(self):
        self.assertEqual(message.Point(x=0).serialize(), b"\x08\x00")
        self.assertEqual(message.SampleMessage(opt_uint=0).serialize(), b"\x10\x00")

    def test_oneof_member_is_written_even_when_zero(self):
        self.assertEqual(message.SampleMessage(choice_s32=0).serialize(), b"\x40\x00")

    def test_explicitly_assigned_empty_submessage_is_written(self):
        self.assertEqual(message.SampleMessage(location=message.Point()).serialize(), b"\x2a\x00")
        msg = message.SampleMessage()
        msg.location = message.Point()
        self.assertEqual(msg.serialize(), b"\x2a\x00")

    def test_submessage_that_was_only_read_is_not_written(self):
        msg = message.SampleMessage()
        self.assertEqual(msg.location.x, None)
        self.assertEqual(msg.metadata.kind, message.MetadataKind.METADATA_KIND_UNSPECIFIED)
        self.assertEqual(msg.serialize(), b"")

    def test_filled_autocreated_submessage_is_written(self):
        msg = message.SampleMessage()
        msg.location.x = 3
        self.assertEqual(msg.serialize(), b"\x2a\x02\x08\x06")

    def test_set_empty_bytes_and_string_are_written(self):
        self.assertEqual(message.SampleMessage(payload=b"", label="").serialize(), b"\x32\x00\x62\x00")

    def test_unset_bytes_and_string_are_not_written(self):
        msg = message.SampleMessage()
        self.assertEqual((msg.payload, msg.label), (b"", ""))
        self.assertEqual(msg.serialize(), b"")

    def test_fields_are_written_in_field_number_order(self):
        msg = message.SampleMessage(label="x", opt_uint=1, sparse_tags=message.SparseTags(tag_200=2, tag_1=1))
        self.assertEqual(msg.serialize().hex(), "1001" "620178" "7205" "0801" "c00c02")

    def test_repeated_scalars_are_packed(self):
        self.assertEqual(message.SampleMessage(numbers=[7, 77, 777]).serialize().hex(), "5a04074d8906")
        self.assertEqual(message.SampleMessage(tags=[message.Color.COLOR_RED]).serialize().hex(), "4a0101")

    def test_empty_repeated_field_is_not_written(self):
        msg = message.SampleMessage()
        self.assertEqual(msg.numbers, [])
        self.assertEqual(msg.items, [])
        self.assertEqual(msg.serialize(), b"")

    def test_repeated_messages_are_written_one_by_one(self):
        msg = message.SampleMessage(items=[message.Item(item_id=1), message.Item(item_id=2), message.Item()])
        self.assertEqual(msg.serialize().hex(), "5202" "0801" "5202" "0802" "5200")

    def test_oneof_keeps_the_last_assigned_member_only(self):
        msg = message.SampleMessage(choice_u32=5)
        msg.choice_s32 = -1
        self.assertEqual(msg.serialize().hex(), "4001")
        msg.choice_u32 = 6
        self.assertEqual(msg.serialize().hex(), "3806")


class ScalarWireTest(unittest.TestCase):
    def assert_encodes(self, msg, *fields):
        self.assertEqual(msg.serialize(), b"".join(fields))

    def test_uint32(self):
        self.assert_encodes(scalars.Scalars(u32=300), field(1, 0, varint(300)))
        self.assert_encodes(scalars.Scalars(u32=0xFFFFFFFF), field(1, 0, varint(0xFFFFFFFF)))

    def test_integers_may_be_any_object_with_an_index_method(self):
        class Index:
            def __index__(self):
                return 300

        self.assert_encodes(scalars.Scalars(u32=Index()), field(1, 0, varint(300)))
        self.assert_encodes(scalars.Scalars(s32=True), field(2, 0, b"\x02"))

    def test_sint32_zigzag(self):
        for value, wire in ((-1, 1), (1, 2), (-2, 3), (2147483647, 4294967294), (-2147483648, 4294967295)):
            with self.subTest(value=value):
                self.assert_encodes(scalars.Scalars(s32=value), field(2, 0, varint(wire)))

    def test_fixed32_and_sfixed32(self):
        self.assert_encodes(scalars.Scalars(f32=0x01020304), field(3, 5, b"\x04\x03\x02\x01"))
        self.assert_encodes(scalars.Scalars(f32=0xFFFFFFFF), field(3, 5, b"\xff\xff\xff\xff"))
        self.assert_encodes(scalars.Scalars(sf32=-2), field(4, 5, b"\xfe\xff\xff\xff"))
        self.assert_encodes(scalars.Scalars(sf32=-2147483648), field(4, 5, b"\x00\x00\x00\x80"))
        self.assert_encodes(scalars.Scalars(sf32=2147483647), field(4, 5, b"\xff\xff\xff\x7f"))

    def test_float(self):
        self.assert_encodes(scalars.Scalars(flt=1.5), field(5, 5, struct.pack("<f", 1.5)))
        self.assert_encodes(scalars.Scalars(flt=float("inf")), field(5, 5, struct.pack("<f", float("inf"))))
        self.assertEqual(scalars.Scalars(flt=float("nan")).serialize()[:1], b"\x2d")
        # negative zero differs from the default and is written
        self.assert_encodes(scalars.Scalars(flt=-0.0), field(5, 5, struct.pack("<f", -0.0)))
        self.assert_encodes(scalars.Scalars(flt=0.0))
        self.assert_encodes(scalars.Scalars(opt_flt=0.0), field(13, 5, b"\x00\x00\x00\x00"))

    def test_bool_and_enum(self):
        self.assert_encodes(scalars.Scalars(flag=True), field(6, 0, b"\x01"))
        self.assert_encodes(scalars.Scalars(opt_flag=False), field(14, 0, b"\x00"))
        self.assert_encodes(scalars.Scalars(level=scalars.Level.LEVEL_TWO), field(7, 0, b"\x02"))
        self.assert_encodes(scalars.Scalars(level=17), field(7, 0, b"\x11"))
        self.assert_encodes(scalars.Scalars(opt_level=scalars.Level.LEVEL_ZERO), field(12, 0, b"\x00"))

    def test_string_and_bytes(self):
        self.assert_encodes(scalars.Scalars(text="h\u00e9llo \u20ac"), field(8, 2, "h\u00e9llo \u20ac".encode("utf-8")))
        self.assert_encodes(scalars.Scalars(blob=b"\x00\x01"), field(9, 2, b"\x00\x01"))
        self.assert_encodes(scalars.Scalars(blob=bytearray(b"ab")), field(9, 2, b"ab"))
        self.assert_encodes(scalars.Scalars(blob=memoryview(b"ab")), field(9, 2, b"ab"))
        self.assert_encodes(scalars.Scalars(opt_text=""), field(11, 2, b""))

    def test_renamed_fields(self):
        self.assert_encodes(scalars.Scalars(from_=1, serialize_="a", clear_="b"),
                            field(20, 0, b"\x01"), field(21, 2, b"a"), field(22, 2, b"b"))

    def test_repeated_scalars_are_packed(self):
        msg = scalars.Repeats(u32=[1, 300], s32=[-1, 1], f32=[1], sf32=[-1], flt=[1.0], flag=[True, False],
                              level=[scalars.Level.LEVEL_ONE, scalars.Level.LEVEL_TWO])
        self.assertEqual(msg.serialize(), b"".join([
            field(1, 2, b"\x01" + varint(300)),
            field(2, 2, b"\x01\x02"),
            field(3, 2, b"\x01\x00\x00\x00"),
            field(4, 2, b"\xff\xff\xff\xff"),
            field(5, 2, struct.pack("<f", 1.0)),
            field(6, 2, b"\x01\x00"),
            field(7, 2, b"\x01\x02"),
        ]))

    def test_repeated_strings_and_bytes_are_not_packed(self):
        msg = scalars.TextLists(text=["a", ""], blob=[b"\x01"])
        self.assertEqual(msg.serialize(), field(1, 2, b"a") + field(1, 2, b"") + field(2, 2, b"\x01"))

    def test_repeated_messages_are_not_packed(self):
        msg = scalars.Repeats(stamps=[shared.Stamp(seconds=1), shared.Stamp(unit=shared.Unit.UNIT_US)])
        self.assertEqual(msg.serialize(), field(8, 2, field(1, 0, b"\x01")) + field(8, 2, field(3, 0, b"\x02")))

    def test_message_from_another_module(self):
        msg = scalars.Choice(stamp=shared.Stamp(seconds=5), when=shared.Stamp(nanos=1))
        self.assertEqual(msg.serialize(), field(3, 2, field(1, 0, b"\x05")) + field(6, 2, field(2, 0, b"\x01")))

    def test_oneof_message_member_clears_the_others(self):
        msg = scalars.Choice(number=1)
        msg.stamp = shared.Stamp()
        self.assertIsNone(msg.number)
        self.assertEqual(msg.serialize(), field(3, 2))

    @support.requires_reference
    def test_scalars_agree_with_protoc_python_runtime(self):
        ref = support.ref_scalars

        msg = scalars.Scalars(u32=7, s32=-7, f32=70, sf32=-70, flt=0.5, flag=True, level=scalars.Level.LEVEL_ONE,
                              text="t", blob=b"b", opt_u32=0, opt_text="o", opt_level=scalars.Level.LEVEL_TWO)
        parsed = ref.Scalars()
        parsed.ParseFromString(msg.serialize())
        self.assertEqual((parsed.u32, parsed.s32, parsed.f32, parsed.sf32, parsed.flt), (7, -7, 70, -70, 0.5))
        self.assertTrue(parsed.HasField("opt_u32"))
        self.assertEqual(parsed.SerializeToString(), msg.serialize())


if __name__ == "__main__":
    unittest.main()
