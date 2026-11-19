"""Error tests (mirror of test_errors.c / test_errors_cpp.cc): malformed input raises DecodeError with the right code,
unencodable values raise EncodeError."""

import pickle
import unittest

import support
from support import codec, message, scalars, field, varint

Code = codec.DecodeErrorCode


class DecodeErrorTest(unittest.TestCase):
    def assert_decode_error(self, data, code, msg_class=None, **options):
        with self.assertRaises(codec.DecodeError) as caught:
            (msg_class or message.SampleMessage)().deserialize(data, **options)
        self.assertEqual(caught.exception.code, code, str(caught.exception))
        return caught.exception

    def test_codes_match_the_c_generator(self):
        self.assertEqual(
            [Code.UNKNOWN_WIRETYPE, Code.UNEXPECTED_EOF, Code.ONEOF_ERROR, Code.VARINT_OVERFLOW, Code.UNKNOWN_TAG,
             Code.DEPTH_EXCEEDED],
            [1, 2, 4, 7, 8, 9])

    def test_decode_error_is_a_codec_error(self):
        error = self.assert_decode_error(b"\x08", Code.UNEXPECTED_EOF)
        self.assertIsInstance(error, codec.CodecError)
        self.assertIn("offset", str(error))

    def test_decode_error_survives_pickling(self):
        error = pickle.loads(pickle.dumps(self.assert_decode_error(b"\x08", Code.UNEXPECTED_EOF)))
        self.assertEqual((error.code, type(error)), (Code.UNEXPECTED_EOF, codec.DecodeError))

    def test_oneof_conflict_in_strict_mode(self):
        both = field(7, 0, varint(4242)) + field(8, 0, b"\x01")
        self.assert_decode_error(both, Code.ONEOF_ERROR, strict=True)
        self.assert_decode_error(field(8, 0, b"\x01") + field(7, 0, varint(4242)), Code.ONEOF_ERROR, strict=True)
        # the same member twice is not a conflict
        message.SampleMessage().deserialize(field(7, 0, b"\x01") + field(7, 0, b"\x02"), strict=True)

    def test_oneof_conflict_is_resolved_by_the_last_member_otherwise(self):
        msg = message.SampleMessage().deserialize(field(7, 0, varint(4242)) + field(8, 0, b"\x01"))
        self.assertEqual((msg.choice_u32, msg.choice_s32), (None, -1))

    def test_unknown_tag_in_strict_mode(self):
        # tag 99, wire type varint, value 5 - same bytes as the C test
        raw = b"\x98\x06\x05"
        self.assert_decode_error(raw, Code.UNKNOWN_TAG, strict=True)
        self.assertEqual(message.SampleMessage().deserialize(raw).serialize(), b"")

    def test_unknown_tag_inside_a_submessage_in_strict_mode(self):
        self.assert_decode_error(field(5, 2, field(9, 0, b"\x01")), Code.UNKNOWN_TAG, strict=True)

    def test_unexpected_eof_in_a_truncated_message(self):
        data = (message.SampleMessage(opt_value=-42, location=message.Point(x=-10, y=20))).serialize()
        self.assertGreater(len(data), 2)
        self.assert_decode_error(data[:-2], Code.UNEXPECTED_EOF)

    def test_every_truncation_point_is_reported(self):
        data = support.full_sample_message().serialize()
        failures = 0
        for cut in range(1, len(data)):
            try:
                message.SampleMessage().deserialize(data[:cut])
            except codec.DecodeError as error:
                failures += 1
                self.assertEqual(error.code, Code.UNEXPECTED_EOF)
        self.assertGreater(failures, len(data) // 2)

    def test_truncated_fields(self):
        self.assert_decode_error(b"\x08", Code.UNEXPECTED_EOF)                  # key without value
        self.assert_decode_error(b"\x10\x80", Code.UNEXPECTED_EOF)              # varint with continuation bit
        self.assert_decode_error(b"\x80", Code.UNEXPECTED_EOF)                  # key with continuation bit
        self.assert_decode_error(b"\x1a\x05ab", Code.UNEXPECTED_EOF, scalars.Scalars)  # length past the end
        self.assert_decode_error(b"\x1d\x01\x02\x03", Code.UNEXPECTED_EOF, scalars.Scalars)  # fixed32 cut
        self.assert_decode_error(b"\x62\x03ab", Code.UNEXPECTED_EOF)            # string cut
        self.assert_decode_error(b"\x4a\x03\x01", Code.UNEXPECTED_EOF)          # packed field cut
        self.assert_decode_error(field(90, 1, b"\x01\x02"), Code.UNEXPECTED_EOF)  # unknown fixed64 cut
        self.assert_decode_error(field(90, 5, b"\x01\x02"), Code.UNEXPECTED_EOF)  # unknown fixed32 cut

    def test_packed_scalar_must_not_cross_its_length(self):
        # a packed fixed32 list of length 3 cannot hold a value
        self.assert_decode_error(field(3, 2, b"\x01\x02\x03") + b"\x00" * 8, Code.UNEXPECTED_EOF, scalars.Repeats)

    def test_varint_overflow(self):
        # tag=2 (opt_uint) followed by a 6-byte varint, same bytes as the C test
        raw = b"\x10\xff\xff\xff\xff\xff\x01"
        self.assert_decode_error(raw, Code.VARINT_OVERFLOW)

    def test_values_wider_than_32_bits_overflow(self):
        self.assert_decode_error(field(2, 0, varint(2 ** 32)), Code.VARINT_OVERFLOW)
        self.assert_decode_error(field(4, 0, varint(2 ** 32)), Code.VARINT_OVERFLOW)
        self.assert_decode_error(field(11, 2, varint(2 ** 32)), Code.VARINT_OVERFLOW)

    def test_varints_wider_than_64_bits_overflow(self):
        self.assert_decode_error(b"\x10" + b"\xff" * 10 + b"\x01", Code.VARINT_OVERFLOW)
        self.assert_decode_error(b"\x10" + b"\xff" * 9 + b"\x02", Code.VARINT_OVERFLOW)
        # skipping an unknown field has to detect it too
        self.assert_decode_error(b"\xe0\x05" + b"\xff" * 10 + b"\x01", Code.VARINT_OVERFLOW)

    def test_field_key_wider_than_32_bits_overflows(self):
        self.assert_decode_error(varint(2 ** 33) + b"\x00", Code.VARINT_OVERFLOW)

    def test_unsupported_wire_types(self):
        for wire in (3, 4, 6, 7):
            with self.subTest(wire=wire):
                self.assert_decode_error(field(2, wire), Code.UNKNOWN_WIRETYPE)
                self.assert_decode_error(field(90, wire), Code.UNKNOWN_WIRETYPE)

    def test_wire_type_mismatch(self):
        wrong = field(2, 2, b"abc")
        self.assertIsNone(message.SampleMessage().deserialize(wrong).opt_uint)
        self.assert_decode_error(wrong, Code.WIRETYPE_MISMATCH, strict=True)
        self.assert_decode_error(field(5, 0, b"\x01"), Code.WIRETYPE_MISMATCH, strict=True)

    def test_invalid_utf8(self):
        error = self.assert_decode_error(field(8, 2, b"\xff\xfe"), Code.INVALID_UTF8, scalars.Scalars)
        self.assertIn("Scalars.text", str(error))

    def test_error_in_a_submessage(self):
        self.assert_decode_error(field(5, 2, b"\x08"), Code.UNEXPECTED_EOF)
        self.assert_decode_error(field(10, 2, field(1, 0, varint(2 ** 32))), Code.VARINT_OVERFLOW)

    def test_submessage_length_may_not_exceed_its_parent(self):
        # location claims 10 bytes but its parent (item 10) only holds 4
        inner = field(5, 2)[:1] + b"\x0a" + b"\x08\x01"
        self.assert_decode_error(field(10, 2, inner) + b"\x00" * 20, Code.UNEXPECTED_EOF, message.SampleMessage)

    def test_unsupported_input_type(self):
        for data in ("text", 5, None, [1, 2]):
            with self.subTest(data=data):
                with self.assertRaises(TypeError):
                    message.SampleMessage().deserialize(data)

    def test_message_stays_usable_after_an_error(self):
        msg = message.SampleMessage()
        with self.assertRaises(codec.DecodeError):
            msg.deserialize(b"\x08")
        msg.deserialize(field(2, 0, b"\x03"))
        self.assertEqual(msg.opt_uint, 3)


class EncodeErrorTest(unittest.TestCase):
    def assert_encode_error(self, msg, *names):
        with self.assertRaises(codec.EncodeError) as caught:
            msg.serialize()
        for name in names:
            self.assertIn(name, str(caught.exception))
        self.assertIsInstance(caught.exception, ValueError)

    def test_uint32_out_of_range(self):
        self.assert_encode_error(scalars.Scalars(u32=-1), "Scalars.u32")
        self.assert_encode_error(scalars.Scalars(u32=2 ** 32), "Scalars.u32")
        self.assert_encode_error(scalars.Scalars(u32=2 ** 70), "Scalars.u32")
        self.assert_encode_error(scalars.Scalars(opt_u32=-5), "Scalars.opt_u32")

    def test_sint32_out_of_range(self):
        self.assert_encode_error(scalars.Scalars(s32=2 ** 31), "Scalars.s32")
        self.assert_encode_error(scalars.Scalars(s32=-2 ** 31 - 1), "Scalars.s32")

    def test_fixed32_out_of_range(self):
        self.assert_encode_error(scalars.Scalars(f32=-1), "Scalars.f32")
        self.assert_encode_error(scalars.Scalars(f32=2 ** 32), "Scalars.f32")
        self.assert_encode_error(scalars.Scalars(sf32=2 ** 31), "Scalars.sf32")
        self.assert_encode_error(scalars.Scalars(sf32=-2 ** 31 - 1), "Scalars.sf32")

    def test_enum_out_of_range(self):
        self.assert_encode_error(scalars.Scalars(level=-1), "Scalars.level")

    def test_float_out_of_range_and_wrong_types(self):
        self.assert_encode_error(scalars.Scalars(flt=1e300), "Scalars.flt")
        self.assert_encode_error(scalars.Scalars(flt="1.0"), "Scalars.flt")

    def test_wrong_scalar_types(self):
        self.assert_encode_error(scalars.Scalars(u32="7"), "Scalars.u32")
        self.assert_encode_error(scalars.Scalars(u32=1.5), "Scalars.u32")
        self.assert_encode_error(scalars.Scalars(s32=None, f32=object()), "Scalars.f32")

    def test_bytes_and_string_types(self):
        self.assert_encode_error(scalars.Scalars(text=b"bytes"), "Scalars.text")
        self.assert_encode_error(scalars.Scalars(text=5), "Scalars.text")
        self.assert_encode_error(scalars.Scalars(blob="text"), "Scalars.blob")
        self.assert_encode_error(scalars.Scalars(blob=5), "Scalars.blob")
        self.assert_encode_error(scalars.Scalars(text="\ud800"), "Scalars.text")

    def test_error_in_a_repeated_field(self):
        self.assert_encode_error(scalars.Repeats(u32=[1, -2]), "Repeats.u32")
        self.assert_encode_error(scalars.TextLists(text=["a", 1]), "TextLists.text")
        self.assert_encode_error(scalars.TextLists(blob=[b"a", "b"]), "TextLists.blob")

    def test_error_in_a_nested_message_names_the_inner_field(self):
        msg = message.SampleMessage(items=[message.Item(item_id=2 ** 40)])
        self.assert_encode_error(msg, "Item.item_id")
        self.assert_encode_error(message.SampleMessage(location=message.Point(x=2 ** 40)), "Point.x")

    def test_repeated_scalars_must_be_iterable(self):
        msg = scalars.Repeats()
        msg._u32 = 5
        self.assert_encode_error(msg, "Repeats.u32")

    def test_message_fields_check_the_type(self):
        msg = message.SampleMessage()
        with self.assertRaises(TypeError):
            msg.location = message.Item()
        with self.assertRaises(TypeError):
            msg.location = 5
        with self.assertRaises(TypeError):
            message.SampleMessage(metadata=message.Point())


if __name__ == "__main__":
    unittest.main()
