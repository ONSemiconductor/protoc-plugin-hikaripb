"""Randomised cross-check against protoc's own python runtime (the reference implementation of the wire format):
both implementations must produce identical bytes and read each other's output."""

import random
import struct
import unittest

import support
from support import scalars, shared

ITERATIONS = 300

U32 = [0, 1, 127, 128, 300, 16383, 16384, 2 ** 31, 2 ** 32 - 1]
S32 = [0, 1, -1, 63, -64, 64, 2 ** 31 - 1, -2 ** 31]
FLOATS = [0.0, 0.5, -0.25, 1.0, 1234.5, -1e10, float("inf"), 3.4028234663852886e38]
TEXTS = ["a", "hello", "h\u00e9llo", "\u20ac" * 5, "x" * 200]
BLOBS = [b"\x00", b"\xff\x00\xfe", bytes(range(200))]


def pick(rng, values):
    return rng.choice(values)


def maybe(rng, values, odds=0.6):
    return rng.choice(values) if rng.random() < odds else None


def many(rng, values, limit=5):
    return [rng.choice(values) for _ in range(rng.randint(0, limit))]


def random_stamp_args(rng):
    return dict(seconds=pick(rng, U32), nanos=pick(rng, U32), unit=pick(rng, [0, 1, 2]))


def fill_reference_stamp(stamp, args):
    """Set every field of a reference submessage and mark it present even when all values are defaults."""
    stamp.SetInParent()
    for name, value in args.items():
        setattr(stamp, name, value)


def random_scalars_args(rng):
    """Constructor arguments valid for both the generated class and the reference class."""
    args = dict(u32=pick(rng, U32), s32=pick(rng, S32), f32=pick(rng, U32), sf32=pick(rng, S32),
                flt=pick(rng, FLOATS), flag=rng.random() < 0.5, level=pick(rng, [0, 1, 2]))
    for name, values in (("text", TEXTS), ("blob", BLOBS), ("opt_u32", U32), ("opt_text", TEXTS + [""]),
                         ("opt_level", [0, 1, 2]), ("opt_flt", FLOATS), ("opt_flag", [True, False])):
        value = maybe(rng, values)
        if value is not None:
            args[name] = value
    return args


class WireAgreementTest(unittest.TestCase):
    """Scalars/Repeats/TextLists/Choice (scalars.proto) and SampleMessage (message.proto)."""

    def setUp(self):
        self.rng = random.Random(20240607)

    @support.requires_reference
    def test_scalars_both_directions(self):
        ref = support.ref_scalars
        for _ in range(ITERATIONS):
            args = random_scalars_args(self.rng)
            mine = scalars.Scalars(**args)
            theirs = ref.Scalars(**args)

            self.assertEqual(mine.serialize(), theirs.SerializeToString(), args)
            decoded = scalars.Scalars().deserialize(theirs.SerializeToString())
            self.assertEqual(decoded, mine)
            for name in ("opt_u32", "opt_text", "opt_level", "opt_flt", "opt_flag"):
                self.assertEqual(getattr(decoded, "has_" + name)(), theirs.HasField(name), name)
            self.assertEqual(ref.Scalars.FromString(mine.serialize()), theirs)

    @support.requires_reference
    def test_repeated_fields_both_directions(self):
        ref = support.ref_scalars
        rng = self.rng
        for _ in range(ITERATIONS):
            args = dict(u32=many(rng, U32), s32=many(rng, S32), f32=many(rng, U32), sf32=many(rng, S32),
                        flt=many(rng, FLOATS), flag=many(rng, [True, False]), level=many(rng, [0, 1, 2, 7]))
            stamps = [random_stamp_args(rng) for _ in range(rng.randint(0, 3))]

            mine = scalars.Repeats(stamps=[shared.Stamp(**s) for s in stamps], **args)
            theirs = ref.Repeats(**args)
            for s in stamps:
                theirs.stamps.add(**s)

            self.assertEqual(mine.serialize(), theirs.SerializeToString(), args)
            decoded = scalars.Repeats().deserialize(theirs.SerializeToString())
            self.assertEqual(decoded, mine)
            self.assertEqual(len(decoded.stamps), len(stamps))

    @support.requires_reference
    def test_repeated_strings_and_bytes_both_directions(self):
        ref = support.ref_scalars
        rng = self.rng
        for _ in range(ITERATIONS):
            args = dict(text=many(rng, TEXTS + [""]), blob=many(rng, BLOBS + [b""]))
            mine = scalars.TextLists(**args)
            theirs = ref.TextLists(**args)

            self.assertEqual(mine.serialize(), theirs.SerializeToString(), args)
            self.assertEqual(scalars.TextLists().deserialize(theirs.SerializeToString()), mine)

    @support.requires_reference
    def test_oneof_and_submessages_both_directions(self):
        ref = support.ref_scalars
        rng = self.rng
        for _ in range(ITERATIONS):
            member = rng.choice(["number", "text", "stamp", "level", None])
            mine = scalars.Choice()
            theirs = ref.Choice()
            if member == "number":
                mine.number = theirs.number = pick(rng, U32)
            elif member == "text":
                mine.text = theirs.text = pick(rng, TEXTS)
            elif member == "stamp":
                args = random_stamp_args(rng)
                mine.stamp = shared.Stamp(**args)
                fill_reference_stamp(theirs.stamp, args)
            elif member == "level":
                mine.level = theirs.level = pick(rng, [0, 1, 2])
            if rng.random() < 0.5:
                args = random_stamp_args(rng)
                mine.extra = shared.Stamp(**args)
                fill_reference_stamp(theirs.extra, args)

            self.assertEqual(mine.serialize(), theirs.SerializeToString(), member)
            decoded = scalars.Choice().deserialize(theirs.SerializeToString())
            self.assertEqual(decoded, mine)
            self.assertEqual(decoded.has_extra(), theirs.HasField("extra"))
            if member is not None:
                self.assertEqual(getattr(decoded, "has_" + member)(), True)

    @support.requires_reference
    def test_sample_message_both_directions(self):
        ref = support.ref_message
        message = support.message
        rng = self.rng
        for _ in range(ITERATIONS):
            args = dict(
                flag=rng.random() < 0.5, color=pick(rng, [0, 1, 2, 3]), numbers=many(rng, U32), tags=many(rng, [0, 1, 2, 3]),
                label=pick(rng, TEXTS + [""]) if rng.random() < 0.3 else "",
            )
            for name, values in (("opt_value", S32), ("opt_uint", U32)):
                value = maybe(rng, values)
                if value is not None:
                    args[name] = value
            theirs = ref.SampleMessage(**args)
            mine_args = dict(args)
            mine_args["label"] = args["label"] or None
            mine_args["tags"] = [message.Color(t) for t in args["tags"]]
            mine = message.SampleMessage(**mine_args)
            if rng.random() < 0.5:
                x, y = pick(rng, S32), pick(rng, S32)
                mine.location = message.Point(x=x, y=y)
                theirs.location.x = x
                theirs.location.y = y
            for _ in range(rng.randint(0, 3)):
                values = dict(item_id=pick(rng, U32), checksum=pick(rng, U32), kind=pick(rng, [0, 1, 2]))
                mine.items.add(**values)
                theirs.items.add(**values)
            if rng.random() < 0.5:
                value = pick(rng, U32)
                mine.choice_u32 = theirs.choice_u32 = value
            if rng.random() < 0.3:
                mine.payload = theirs.payload = pick(rng, BLOBS)

            self.assertEqual(mine.serialize(), theirs.SerializeToString(), args)
            decoded = message.SampleMessage().deserialize(theirs.SerializeToString())
            self.assertEqual(decoded, mine)
            self.assertEqual(decoded.serialize(), theirs.SerializeToString())

    def test_float_round_trip_is_bit_exact(self):
        for bits in (0x00000000, 0x80000000, 0x00000001, 0x7F7FFFFF, 0x7F800000, 0xFF800000, 0x3F800000, 0xC0490FDB):
            value = struct.unpack("<f", struct.pack("<I", bits))[0]
            data = scalars.Scalars(opt_flt=value).serialize()
            back = scalars.Scalars().deserialize(data).opt_flt
            self.assertEqual(struct.pack("<f", back), struct.pack("<I", bits))

    def test_nan_round_trip(self):
        back = scalars.Scalars().deserialize(scalars.Scalars(flt=float("nan")).serialize()).flt
        self.assertNotEqual(back, back)


if __name__ == "__main__":
    unittest.main()
