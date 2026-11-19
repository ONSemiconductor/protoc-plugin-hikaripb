"""API tests: constructors, defaults, presence, auto-created submessages, lists, oneofs, printing, copying."""

import ast
import copy
import enum
import inspect
import io
import pickle
import typing
import unittest

import support
from support import codec, message, scalars, shared, field, varint


class ConstructionTest(unittest.TestCase):
    def test_defaults(self):
        msg = message.SampleMessage()
        self.assertIsNone(msg.opt_value)
        self.assertIsNone(msg.opt_uint)
        self.assertIs(msg.flag, False)
        self.assertIs(msg.color, message.Color.COLOR_UNSPECIFIED)
        self.assertEqual(msg.payload, b"")
        self.assertEqual(msg.label, "")
        self.assertEqual((msg.tags, msg.items, msg.numbers), ([], [], []))
        self.assertEqual((msg.choice_u32, msg.choice_s32), (None, None))

    def test_scalar_defaults(self):
        msg = scalars.Scalars()
        self.assertEqual((msg.u32, msg.s32, msg.f32, msg.sf32, msg.flt, msg.flag), (0, 0, 0, 0, 0.0, False))
        self.assertIs(msg.level, scalars.Level.LEVEL_ZERO)
        self.assertEqual((msg.text, msg.blob), ("", b""))
        self.assertEqual((msg.opt_u32, msg.opt_text, msg.opt_level, msg.opt_flt, msg.opt_flag), (None,) * 5)

    def test_positional_arguments_follow_the_field_declaration(self):
        point = message.Point(3, 4)
        self.assertEqual((point.x, point.y), (3, 4))
        item = message.Item(1, 2, message.ItemKind.ITEM_KIND_SPECIAL)
        self.assertEqual((item.item_id, item.checksum, item.kind), (1, 2, message.ItemKind.ITEM_KIND_SPECIAL))

    def test_unknown_constructor_argument(self):
        with self.assertRaises(TypeError):
            message.Point(z=1)

    def test_attributes_cannot_be_invented(self):
        with self.assertRaises(AttributeError):
            message.Point().z = 1

    def test_python_keywords_and_base_class_methods_get_a_trailing_underscore(self):
        msg = scalars.Scalars(from_=7, serialize_="s", clear_="c")
        self.assertEqual((msg.from_, msg.serialize_, msg.clear_), (7, "s", "c"))
        self.assertEqual(msg.has_serialize_(), True)
        self.assertEqual(msg.serialize(), field(20, 0, b"\x07") + field(21, 2, b"s") + field(22, 2, b"c"))

    def test_nested_types_are_module_level_classes(self):
        self.assertTrue(issubclass(message.ItemKind, enum.IntEnum))
        self.assertTrue(issubclass(message.MetadataKind, enum.IntEnum))
        self.assertTrue(issubclass(message.Metadata, codec.Message))
        self.assertEqual(shared.Unit.UNIT_US, 2)

    def test_enums_are_int_enums(self):
        self.assertEqual(message.Color.COLOR_BLUE, 3)
        self.assertEqual(message.Color(2), message.Color.COLOR_GREEN)
        self.assertEqual(message.Color.COLOR_GREEN.name, "COLOR_GREEN")

    def test_proto_comments_become_docstrings(self):
        self.assertIn('"quotes", a \\backslash and """triple quotes"""', scalars.Scalars.__doc__)
        self.assertIn("Example proto file", message.Color.__doc__)


class DocstringTest(unittest.TestCase):
    """The comments of the .proto files document every generated item, so editors show them on mouseover."""

    @staticmethod
    def attribute_docs(module, class_name):
        """Docstrings written below plain `name: type` / `NAME = value` class statements."""
        tree = ast.parse(inspect.getsource(module))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
        docs = {}
        for node, following in zip(cls.body, cls.body[1:]):
            if not (isinstance(following, ast.Expr) and isinstance(following.value, ast.Constant)
                    and isinstance(following.value.value, str)):
                continue
            if isinstance(node, ast.AnnAssign):
                docs[node.target.id] = following.value.value.strip()
            elif isinstance(node, ast.Assign):
                docs[node.targets[0].id] = following.value.value.strip()
        return docs

    def test_enums_and_their_values(self):
        self.assertEqual(scalars.Level.__doc__.strip(), "Verbosity of a scalar.")
        self.assertEqual(shared.Unit.__doc__.strip(), "Unit of the nanos field.")
        self.assertEqual(self.attribute_docs(scalars, "Level"),
                         {"LEVEL_ZERO": "The lowest level.", "LEVEL_ONE": "The middle level."})
        self.assertEqual(self.attribute_docs(shared, "Unit"), {"UNIT_MS": "Milliseconds."})

    def test_plain_scalars_have_an_attribute_docstring(self):
        self.assertEqual(self.attribute_docs(scalars, "Scalars")["u32"], "Plain counter without presence.")
        self.assertEqual(self.attribute_docs(shared, "Stamp")["seconds"], "Whole seconds.")

    def test_properties_carry_the_comment_of_their_field(self):
        self.assertEqual(scalars.Scalars.text.__doc__.strip(), "Text that is only written when it was assigned.")
        self.assertEqual(scalars.Scalars.opt_u32.__doc__.strip(), "Optional counter, unset until assigned.")
        self.assertEqual(scalars.Repeats.stamps.__doc__.strip(), "Packed list of embedded messages.")
        self.assertEqual(scalars.Choice.when.__doc__.strip(), "Embedded message without explicit presence.")

    def test_the_constructor_lists_the_comments_of_the_fields(self):
        doc = scalars.Scalars.__init__.__doc__
        self.assertIn("u32 (int): Plain counter without presence.", doc)
        self.assertIn("text (str): Text that is only written when it was assigned.", doc)

    def test_methods_are_documented(self):
        for method in ("serialize", "deserialize", "print", "clear"):
            self.assertTrue(getattr(message.SampleMessage, method).__doc__, method)
        self.assertIn("optional field opt_value", message.SampleMessage.has_opt_value.__doc__)
        self.assertIn("oneof choice", message.SampleMessage.has_choice.__doc__)


class PresenceTest(unittest.TestCase):
    def test_has_methods_of_optional_scalars(self):
        msg = message.Point()
        self.assertFalse(msg.has_x())
        msg.x = 0
        self.assertTrue(msg.has_x())
        msg.x = None
        self.assertFalse(msg.has_x())

    def test_has_methods_of_optional_proto3_fields(self):
        msg = scalars.Scalars()
        for name in ("opt_u32", "opt_text", "opt_level", "opt_flt", "opt_flag"):
            self.assertFalse(getattr(msg, "has_" + name)(), name)
        msg.opt_text = ""
        msg.opt_level = scalars.Level.LEVEL_ZERO
        self.assertTrue(msg.has_opt_text() and msg.has_opt_level())

    def test_plain_scalars_have_no_has_method(self):
        self.assertFalse(hasattr(message.SampleMessage, "has_flag"))
        self.assertFalse(hasattr(message.SampleMessage, "has_color"))
        self.assertTrue(hasattr(message.SampleMessage, "has_opt_value"))

    def test_has_methods_of_bytes_string_and_repeated_fields(self):
        msg = message.SampleMessage()
        self.assertFalse(msg.has_payload() or msg.has_label() or msg.has_numbers() or msg.has_items())
        msg.payload = b""
        msg.label = ""
        msg.numbers.append(1)
        msg.items.add()
        self.assertTrue(msg.has_payload() and msg.has_label() and msg.has_numbers() and msg.has_items())

    def test_reading_a_field_does_not_set_it(self):
        msg = message.SampleMessage()
        _ = (msg.payload, msg.label, msg.location, msg.metadata)
        self.assertFalse(msg.has_payload() or msg.has_label() or msg.has_location() or msg.has_metadata())
        _ = msg.numbers
        self.assertFalse(msg.has_numbers())

    def test_has_location_follows_the_content_of_an_autocreated_child(self):
        msg = message.SampleMessage()
        msg.location.x = 1
        self.assertTrue(msg.has_location())
        msg.location.x = None
        self.assertFalse(msg.has_location())

    def test_assigned_empty_submessage_counts_as_set(self):
        msg = message.SampleMessage(location=message.Point())
        self.assertTrue(msg.has_location())
        msg.location = None
        self.assertFalse(msg.has_location())
        self.assertEqual(msg.serialize(), b"")

    def test_autocreated_child_is_the_same_object_on_every_read(self):
        msg = message.SampleMessage()
        self.assertIs(msg.location, msg.location)
        msg.location.y = 5
        self.assertEqual(msg.location.y, 5)

    def test_assigning_a_child_keeps_the_object(self):
        point = message.Point(x=1)
        msg = message.SampleMessage(location=point)
        self.assertIs(msg.location, point)
        point.y = 2
        self.assertEqual(msg.serialize(), b"\x2a\x04\x08\x02\x10\x04")


class OneofTest(unittest.TestCase):
    def test_setting_a_member_clears_the_others(self):
        msg = scalars.Choice(number=1)
        msg.text = "a"
        self.assertEqual((msg.number, msg.text), (None, "a"))
        msg.level = scalars.Level.LEVEL_ONE
        self.assertEqual((msg.text, msg.level), (None, scalars.Level.LEVEL_ONE))
        msg.stamp = shared.Stamp(seconds=1)
        self.assertEqual((msg.level, msg.stamp.seconds), (None, 1))

    def test_assigning_none_keeps_the_other_members(self):
        msg = scalars.Choice(number=1)
        msg.text = None
        self.assertEqual(msg.number, 1)

    def test_constructor_applies_the_oneof_rule(self):
        msg = message.SampleMessage(choice_u32=1, choice_s32=2)
        self.assertEqual((msg.choice_u32, msg.choice_s32), (None, 2))

    def test_members_outside_the_oneof_are_not_cleared(self):
        msg = scalars.Choice(number=1, extra=shared.Stamp(), when=shared.Stamp())
        msg.text = "x"
        self.assertTrue(msg.has_extra() and msg.has_when())


class MessageListTest(unittest.TestCase):
    def test_add_creates_and_appends(self):
        msg = message.SampleMessage()
        item = msg.items.add(item_id=5, checksum=6)
        self.assertIsInstance(item, message.Item)
        self.assertIs(msg.items[0], item)
        msg.items.add(7)
        self.assertEqual([i.item_id for i in msg.items], [5, 7])

    def test_list_operations_check_the_element_type(self):
        items = message.SampleMessage().items
        for operation in (lambda: items.append(5), lambda: items.append(message.Point()),
                          lambda: items.extend([message.Item(), 3]), lambda: items.insert(0, "x"),
                          lambda: items.__setitem__(0, None), lambda: items.__iadd__([1])):
            with self.subTest(operation=operation):
                with self.assertRaises(TypeError):
                    operation()
        self.assertEqual(len(items), 0)

    def test_list_operations(self):
        items = message.SampleMessage().items
        a, b, c = message.Item(item_id=1), message.Item(item_id=2), message.Item(item_id=3)
        items.append(a)
        items.extend([b])
        items.insert(0, c)
        items += [message.Item(item_id=4)]
        self.assertEqual([i.item_id for i in items], [3, 1, 2, 4])
        items[0] = message.Item(item_id=9)
        items[1:3] = [message.Item(item_id=8)]
        self.assertEqual([i.item_id for i in items], [9, 8, 4])
        items.remove(items[1])
        self.assertEqual(len(items), 2)

    def test_assigning_a_plain_list_creates_a_message_list(self):
        msg = message.SampleMessage()
        msg.items = [message.Item(item_id=1)]
        self.assertIsInstance(msg.items, codec.MessageList)
        self.assertIsNone(msg.items.add().item_id)
        with self.assertRaises(TypeError):
            msg.items = [1]

    def test_constructor_takes_a_list_of_messages(self):
        msg = message.SampleMessage(items=[message.Item(item_id=1)])
        msg.items.add(item_id=2)
        self.assertEqual([i.item_id for i in msg.items], [1, 2])
        with self.assertRaises(TypeError):
            message.SampleMessage(items=[message.Point()])

    def test_message_list_is_parameterized_by_its_element_type(self):
        alias = codec.MessageList[message.Item]
        self.assertIs(typing.get_origin(alias), codec.MessageList)
        self.assertEqual(typing.get_args(alias), (message.Item,))
        self.assertTrue(issubclass(codec.MessageList, list))

    def test_every_repeated_message_field_has_its_own_list_class(self):
        list_class = message.SampleMessage._list_items
        self.assertTrue(issubclass(list_class, codec.MessageList))
        msg = message.SampleMessage(items=[message.Item(item_id=1)])
        self.assertIs(type(msg.items), list_class)
        self.assertIs(type(message.SampleMessage().items), list_class)
        data = msg.serialize()
        self.assertIs(type(message.SampleMessage().deserialize(data).items), list_class)
        for clone in (copy.copy(msg), copy.deepcopy(msg), pickle.loads(pickle.dumps(msg))):
            self.assertIs(type(clone.items), list_class)
            self.assertEqual(clone, msg)

    def test_add_lists_the_fields_of_the_element_as_parameters(self):
        add = message.SampleMessage._list_items.add
        signature = inspect.signature(add)
        self.assertEqual(list(signature.parameters), ["self", "item_id", "checksum", "kind"])
        self.assertEqual([p.annotation for p in signature.parameters.values()][1:], ["int", "int", "ItemKind"])
        self.assertTrue(all(p.default is None for p in list(signature.parameters.values())[1:]))
        self.assertEqual(signature.return_annotation, "Item")
        self.assertEqual(message.SampleMessage(items=[message.Item(item_id=3)]).items.add(4, kind=1).kind, 1)

    def test_add_documents_the_fields_with_the_comments_of_the_proto_file(self):
        add = scalars.Repeats._list_stamps.add
        self.assertIn("seconds (int): Whole seconds.", add.__doc__)
        self.assertIn("Returns:", add.__doc__)
        self.assertEqual(scalars.Repeats._list_stamps.__doc__.strip(), "Packed list of embedded messages.")

    def test_add_names_the_types_of_other_modules_as_the_module_imports_them(self):
        signature = inspect.signature(scalars.Repeats._list_stamps.add)
        self.assertEqual(signature.parameters["unit"].annotation, "_shared_common_pb.Unit")
        self.assertEqual(signature.return_annotation, "_shared_common_pb.Stamp")
        stamp = scalars.Repeats().stamps.add(seconds=5, unit=shared.Unit.UNIT_MS)
        self.assertIsInstance(stamp, shared.Stamp)

    def test_assigned_list_is_copied(self):
        source = [1, 2]
        msg = message.SampleMessage(numbers=source)
        source.append(3)
        self.assertEqual(msg.numbers, [1, 2])
        msg.numbers = (4, 5)
        self.assertEqual(msg.numbers, [4, 5])
        msg.numbers = None
        self.assertFalse(msg.has_numbers())

    def test_repeated_scalars_are_plain_lists(self):
        msg = message.SampleMessage()
        msg.numbers.append(1)
        msg.numbers.extend([2, 3])
        msg.tags.append(message.Color.COLOR_RED)
        self.assertEqual(msg.serialize().hex(), "4a0101" "5a03010203")
        self.assertEqual(msg.numbers, [1, 2, 3])


class ObjectProtocolTest(unittest.TestCase):
    def test_equality_compares_the_encoded_content(self):
        self.assertEqual(support.full_sample_message(), support.full_sample_message())
        self.assertNotEqual(message.Point(x=1), message.Point(x=2))
        self.assertNotEqual(message.Point(x=0), message.Point())
        self.assertNotEqual(message.Point(x=1), message.Item(item_id=1))
        self.assertFalse(message.Point() == None)  # noqa: E711

    def test_a_read_only_child_does_not_affect_equality(self):
        a, b = message.SampleMessage(), message.SampleMessage()
        _ = a.location.x
        self.assertEqual(a, b)

    def test_messages_are_unhashable(self):
        with self.assertRaises(TypeError):
            hash(message.Point())

    def test_repr_lists_the_set_fields(self):
        self.assertEqual(repr(message.Point()), "Point()")
        self.assertEqual(repr(message.Point(x=1, y=0)), "Point(x=1, y=0)")
        self.assertEqual(repr(message.Item(item_id=2, kind=message.ItemKind.ITEM_KIND_NORMAL)),
                         "Item(item_id=2, kind=%r)" % message.ItemKind.ITEM_KIND_NORMAL)
        self.assertEqual(repr(message.SampleMessage(location=message.Point(x=1), numbers=[1])),
                         "SampleMessage(location=Point(x=1), numbers=[1])")

    def test_str_has_the_layout_of_the_c_and_cpp_print(self):
        msg = message.SampleMessage(
            opt_value=-1, flag=True, color=message.Color.COLOR_RED, location=message.Point(x=3), payload=b"\x01\xab",
            choice_s32=4, tags=[message.Color.COLOR_BLUE], items=[message.Item(item_id=1)], label="hi")
        self.assertEqual(str(msg), "\n".join([
            "SampleMessage:",
            "  opt_value: -1",
            "  flag: 1",
            "  color: COLOR_RED",
            "  location: ",
            "    x: 3",
            "  payload: ",
            "    01 AB ",
            "  choice_s32: 4",
            "  tags: ",
            "    COLOR_BLUE",
            "  items: ",
            "    item_id: 1",
            "    checksum: 0",
            "    kind: ITEM_KIND_UNSPECIFIED",
            "  label: ",
            "    hi",
            "",
        ]))

    def test_print_writes_the_same_text_to_a_file_object(self):
        msg = message.Point(x=1)
        out = io.StringIO()
        msg.print(out)
        self.assertEqual(out.getvalue(), str(msg))
        self.assertEqual(out.getvalue(), "Point:\n  x: 1\n")

    def test_print_shows_plain_scalars_always_and_unset_fields_never(self):
        self.assertEqual(str(message.SampleMessage()), "SampleMessage:\n  flag: 0\n  color: COLOR_UNSPECIFIED\n")
        self.assertEqual(str(message.Point()), "Point:\n")
        self.assertEqual(str(message.Point(x=0)), "Point:\n  x: 0\n")

    def test_print_lists_every_element_of_repeated_messages_with_its_own_header(self):
        msg = message.SampleMessage(items=[message.Item(item_id=1), message.Item(item_id=2)])
        text = str(msg)
        self.assertEqual(text.count("  items: \n"), 2)
        self.assertIn("  items: \n    item_id: 1\n    checksum: 0\n    kind: ITEM_KIND_UNSPECIFIED\n"
                      "  items: \n    item_id: 2\n", text)

    def test_print_splits_bytes_and_strings_into_lines_of_16(self):
        text = str(scalars.Scalars(blob=bytes(range(20)), text="0123456789abcdefXYZ"))
        self.assertIn("  blob: \n"
                      "    00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F \n"
                      "    10 11 12 13 \n", text)
        self.assertIn("  text: \n    0123456789abcdef\n    XYZ\n", text)

    def test_print_formats_scalars_like_the_c_helpers(self):
        text = str(scalars.Scalars(u32=7, s32=-7, f32=70, sf32=-70, flt=0.5, flag=True, level=99, opt_flag=False))
        for line in ("  u32: 7\n", "  s32: -7\n", "  f32: 70\n", "  sf32: -70\n", "  flt: 0.5\n", "  flag: 1\n",
                     "  level: 99\n", "  opt_flag: 0\n"):
            self.assertIn(line, text)

    def test_print_repeated_scalars_and_nested_messages(self):
        msg = scalars.Repeats(u32=[1, 2], stamps=[shared.Stamp(seconds=3)])
        self.assertEqual(str(msg), "\n".join([
            "Repeats:",
            "  u32: ",
            "    1",
            "    2",
            "  stamps: ",
            "    seconds: 3",
            "    nanos: 0",
            "    unit: UNIT_UNSPECIFIED",
            "",
        ]))

    def test_print_repeated_strings_have_one_header_per_element(self):
        self.assertEqual(str(scalars.TextLists(text=["a", "b"])), "TextLists:\n  text: \n    a\n  text: \n    b\n")

    def test_print_skips_children_that_were_only_read(self):
        msg = message.SampleMessage()
        _ = msg.location
        self.assertEqual(str(msg), "SampleMessage:\n  flag: 0\n  color: COLOR_UNSPECIFIED\n")
        msg.location.x = 5
        self.assertIn("  location: \n    x: 5\n", str(msg))

    def test_clear(self):
        msg = support.full_sample_message()
        self.assertIs(msg.clear(), msg)
        self.assertEqual(msg, message.SampleMessage())
        self.assertEqual(msg.serialize(), b"")
        self.assertFalse(msg.has_opt_value() or msg.has_location() or msg.has_items() or msg.has_choice_u32())
        self.assertIs(msg.color, message.Color.COLOR_UNSPECIFIED)

    def test_init_assigns_the_given_fields(self):
        msg = message.Point()
        self.assertIs(msg.init(x=1, y=None), msg)
        self.assertEqual((msg.x, msg.y), (1, None))

    def test_copy_and_pickle(self):
        original = support.full_sample_message()
        for clone in (copy.copy(original), copy.deepcopy(original), pickle.loads(pickle.dumps(original))):
            self.assertEqual(clone, original)
        deep = copy.deepcopy(original)
        deep.items.add(item_id=99)
        deep.location.x = 1000
        self.assertEqual(len(original.items), 2)
        self.assertEqual(original.location.x, -10)
        self.assertIsInstance(deep.items, codec.MessageList)

    def test_round_trip_through_the_wire(self):
        original = support.full_sample_message()
        self.assertEqual(message.SampleMessage().deserialize(original.serialize()), original)

    def test_runtime_helpers(self):
        self.assertIn(codec.COMPILED, (True, False))
        self.assertEqual(codec.DEFAULT_MAX_DEPTH, 100)


if __name__ == "__main__":
    unittest.main()
