#!/usr/bin/env python3
"""Cross-language interop check between the C/C++ generators and the python generator.

The python side is the generated native codec (type=py); protoc's own python runtime is not involved.

Usage:
    check_interop.py <generated_py_dir> <interop_dir> [output_name]

<generated_py_dir> must contain the type=py output (prefix=sample) of test/proto.
<interop_dir> is where encoded_from_c.bin / encoded_from_cpp.bin (message.proto) and
scalars_from_c.bin / choice_from_c.bin / repeats_from_c.bin / textlists_from_c.bin (+ _cpp; scalars.proto) are read from and the
python-encoded bytes are written to (encoded_from_python.bin, scalars_from_python.bin, ... unless output_name
says otherwise: its "encoded" prefix is replaced by the message name).
"""
import os
import sys

import expected_values as ev


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print(__doc__, file=sys.stderr)
        return 1

    generated_py_dir = sys.argv[1]
    interop_dir = sys.argv[2]
    output_name = sys.argv[3] if len(sys.argv) == 4 else "encoded_from_python.bin"
    sys.path.insert(0, generated_py_dir)

    import sample_codec  # noqa: E402  (path set above)
    from message_pb import SampleMessage, Point, Item, Color, Metadata, ItemKind, MetadataKind, SparseTags  # noqa: E402
    from scalars_pb import Scalars, Choice, Repeats, TextLists  # noqa: E402
    from shared.common_pb import Stamp  # noqa: E402

    flavour = "compiled" if sample_codec.COMPILED else "pure python"

    def _verify_decoded(decoded, source: str) -> None:
        assert decoded.opt_value == ev.OPT_VALUE, f"opt_value mismatch: {decoded.opt_value}"
        assert decoded.opt_uint == ev.OPT_UINT, f"opt_uint mismatch: {decoded.opt_uint}"
        assert decoded.flag == ev.FLAG, f"flag mismatch: {decoded.flag}"
        assert int(decoded.color) == ev.COLOR, f"color mismatch: {decoded.color}"
        assert decoded.location.x == ev.LOCATION_X, f"location.x mismatch: {decoded.location.x}"
        assert decoded.location.y == ev.LOCATION_Y, f"location.y mismatch: {decoded.location.y}"
        assert decoded.payload == ev.PAYLOAD, f"payload mismatch: {decoded.payload}"
        assert decoded.choice_u32 == ev.CHOICE_U32, f"choice_u32 mismatch: {decoded.choice_u32}"
        assert decoded.choice_s32 is None, f"choice_s32 must stay unset: {decoded.choice_s32}"
        assert [int(t) for t in decoded.tags] == ev.TAGS, f"tags mismatch: {decoded.tags}"
        assert [{"item_id": i.item_id, "checksum": i.checksum, "kind": int(i.kind)} for i in decoded.items] == ev.ITEMS, \
            f"items mismatch: {decoded.items}"
        assert list(decoded.numbers) == ev.NUMBERS, f"numbers mismatch: {decoded.numbers}"
        assert decoded.label == ev.LABEL, f"label mismatch: {decoded.label}"
        assert int(decoded.metadata.kind) == ev.METADATA_KIND, f"metadata.kind mismatch: {decoded.metadata.kind}"
        assert decoded.metadata.revision == ev.METADATA_REVISION, f"metadata.revision mismatch: {decoded.metadata.revision}"
        assert decoded.sparse_tags.tag_1 == ev.SPARSE_TAG_1, f"sparse_tags.tag_1 mismatch: {decoded.sparse_tags.tag_1}"
        assert decoded.sparse_tags.tag_25 == ev.SPARSE_TAG_25, f"sparse_tags.tag_25 mismatch: {decoded.sparse_tags.tag_25}"
        assert decoded.sparse_tags.tag_75 == ev.SPARSE_TAG_75, f"sparse_tags.tag_75 mismatch: {decoded.sparse_tags.tag_75}"
        assert decoded.sparse_tags.tag_150 == ev.SPARSE_TAG_150, f"sparse_tags.tag_150 mismatch: {decoded.sparse_tags.tag_150}"
        assert decoded.sparse_tags.tag_200 == ev.SPARSE_TAG_200, f"sparse_tags.tag_200 mismatch: {decoded.sparse_tags.tag_200}"
        print(f"check_interop: {source}-encoded payload decoded correctly by the Python bindings ({flavour} codec)")

    # 1) Decode the bytes the C encode test produced and check the values.
    with open(os.path.join(interop_dir, "encoded_from_c.bin"), "rb") as f:
        c_encoded = f.read()
    _verify_decoded(SampleMessage().deserialize(c_encoded), "C")

    # 1b) Same check for the C++ encode test's output, if present.
    cpp_bin_path = os.path.join(interop_dir, "encoded_from_cpp.bin")
    if os.path.isfile(cpp_bin_path):
        with open(cpp_bin_path, "rb") as f:
            _verify_decoded(SampleMessage().deserialize(f.read()), "C++")

    # 2) Build the same message from Python and export it for the C/C++ decode tests.
    encoded_msg = SampleMessage(
        opt_value=ev.OPT_VALUE,
        opt_uint=ev.OPT_UINT,
        flag=ev.FLAG,
        color=Color(ev.COLOR),
        location=Point(x=ev.LOCATION_X, y=ev.LOCATION_Y),
        payload=ev.PAYLOAD,
        choice_u32=ev.CHOICE_U32,
        tags=[Color(t) for t in ev.TAGS],
        items=[Item(item_id=i["item_id"], checksum=i["checksum"], kind=ItemKind(i["kind"])) for i in ev.ITEMS],
        numbers=ev.NUMBERS,
        label=ev.LABEL,
        metadata=Metadata(kind=MetadataKind(ev.METADATA_KIND), revision=ev.METADATA_REVISION),
        sparse_tags=SparseTags(
            tag_1=ev.SPARSE_TAG_1,
            tag_25=ev.SPARSE_TAG_25,
            tag_75=ev.SPARSE_TAG_75,
            tag_150=ev.SPARSE_TAG_150,
            tag_200=ev.SPARSE_TAG_200,
        ),
    )
    py_encoded = encoded_msg.serialize()

    py_bin_path = os.path.join(interop_dir, output_name)
    with open(py_bin_path, "wb") as f:
        f.write(py_encoded)

    print(f"check_interop: wrote {len(py_encoded)} bytes to {py_bin_path}")

    # 3) scalars.proto: the C/C++ encoded Scalars/Choice/Repeats must decode to the values the python side builds
    # from the same constants, and the python encoding of them is exported for the C/C++ decode tests.
    def _choice():
        return Choice(text=ev.CHOICE_TEXT, extra=Stamp(**ev.CHOICE_EXTRA), when=Stamp(**ev.CHOICE_WHEN))

    def _repeats():
        return Repeats(stamps=[Stamp(**s) for s in ev.REPEATS_STAMPS], **ev.REPEATS)

    schema = {"scalars": (Scalars, lambda: Scalars(**ev.SCALARS)), "choice": (Choice, _choice),
              "repeats": (Repeats, _repeats), "textlists": (TextLists, lambda: TextLists(**ev.TEXTLISTS))}

    for source, suffix in (("C", "c"), ("C++", "cpp")):
        for name, (cls, build) in schema.items():
            path = os.path.join(interop_dir, f"{name}_from_{suffix}.bin")
            if suffix == "cpp" and not os.path.isfile(path):
                continue
            with open(path, "rb") as f:
                decoded = cls().deserialize(f.read())
            assert decoded == build(), f"{source}-encoded {name} mismatch:\n{decoded}\nexpected:\n{build()}"
            if name == "scalars":
                assert decoded.has_opt_u32() and decoded.opt_u32 == 0, "explicit zero lost"
                assert decoded.has_opt_flag() and decoded.opt_flag is False, "explicit false lost"
            if name == "choice":
                assert decoded.has_text() and not decoded.has_number(), "oneof member lost"
            print(f"check_interop: {source}-encoded {name} decoded correctly by the Python bindings ({flavour} codec)")

    for name, (cls, build) in schema.items():
        path = os.path.join(interop_dir, output_name.replace("encoded", name, 1))
        with open(path, "wb") as f:
            f.write(build().serialize())
    return 0


if __name__ == "__main__":
    sys.exit(main())
