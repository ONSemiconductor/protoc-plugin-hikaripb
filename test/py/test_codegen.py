"""Generator tests: the single_file option of every backend, the python prefix option and option validation.

Runs protoc with the plugin from this repository, so it needs `protoc` on PATH (skipped otherwise).
"""

import glob
import os
import shutil
import subprocess
import tempfile
import unittest
import warnings

import support

PROTOC = os.environ.get("PROTOC", "protoc")
PLUGIN = os.environ.get("HIKARIPB_PLUGIN", os.path.join(support.ROOT, "protoc", "hikaripb.py"))
PROTO_DIR = os.path.join(support.ROOT, "test", "proto")
PROTOS = sorted(glob.glob(os.path.join(PROTO_DIR, "**", "*.proto"), recursive=True))
MODULES = {"message_pb.py", "depth_pb.py", "callback_pb.py", "nested_pb.py", "scalars_pb.py", "empty_pb.py",
           "shared/common_pb.py"}


@unittest.skipUnless(shutil.which(PROTOC), "protoc not available")
class CodegenTest(unittest.TestCase):
    def generate(self, options, protos=PROTOS):
        out = tempfile.mkdtemp(prefix="hikaripb_test_")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        command = [PROTOC, "--experimental_allow_proto3_optional", "--plugin=protoc-gen-hikaripb=" + PLUGIN]
        command += ["--proto_path=" + PROTO_DIR]
        command += ["--hikaripb_out=%s:%s" % (options, out)] + protos
        result = subprocess.run(command, capture_output=True, text=True)
        return result, out

    def files(self, options, protos=PROTOS):
        result, out = self.generate(options, protos)
        self.assertEqual(result.returncode, 0, result.stderr)
        found = set()
        for folder, _, names in os.walk(out):
            found.update(os.path.relpath(os.path.join(folder, n), out).replace(os.sep, "/") for n in names)
        return found, out

    def test_python_default_is_one_module_per_proto_file(self):
        found, _ = self.files("type=py")
        self.assertEqual(found, MODULES | {"hikaripb_codec.py", "hikaripb_codec.pxd", "hikaripb_build_ext.py"})

    def test_python_prefix_names_the_runtime_modules(self):
        found, out = self.files("type=py,prefix=abc")
        self.assertEqual(found, MODULES | {"abc_codec.py", "abc_codec.pxd", "abc_build_ext.py"})
        with open(os.path.join(out, "message_pb.py"), encoding="utf-8") as f:
            self.assertIn("import abc_codec as _codec", f.read())

    def test_python_single_file(self):
        found, out = self.files("type=py,single_file=everything")
        self.assertEqual(found, {"everything_pb.py", "hikaripb_codec.py", "hikaripb_codec.pxd", "hikaripb_build_ext.py"})
        with open(os.path.join(out, "everything_pb.py"), encoding="utf-8") as f:
            text = f.read()
        for name in ("class SampleMessage(", "class DepthL13(", "class CallbackParent(", "class Color(IntEnum)",
                     "class Scalars(", "class Stamp(", "class Unit(IntEnum)"):
            self.assertIn(name, text)
        self.assertIn("callback.proto, depth.proto, empty.proto, message.proto, nested.proto, shared/common.proto, scalars.proto",
                      text)

    def test_python_subdirectories_follow_the_proto_layout(self):
        found, out = self.files("type=py")
        self.assertIn("shared/common_pb.py", found)
        with open(os.path.join(out, "scalars_pb.py"), encoding="utf-8") as f:
            self.assertIn("import shared.common_pb as ", f.read())

    def test_ignore_skips_messages_of_the_c_and_cpp_backends(self):
        found, out = self.files("type=c,prefix=sample,ignore=scalarpkg_Node|scalarpkg_TextLists")
        with open(os.path.join(out, "sample_scalars.pb.h"), encoding="utf-8") as f:
            header = f.read()
        self.assertIn("scalarpkg_Scalars", header)
        self.assertNotIn("scalarpkg_Node", header)
        self.assertNotIn("scalarpkg_TextLists", header)
        found, out = self.files("type=cpp,ignore=scalarpkg_Node|scalarpkg_TextLists")
        with open(os.path.join(out, "scalars.pb.h"), encoding="utf-8") as f:
            header = f.read()
        self.assertIn("struct Scalars", header)
        self.assertNotIn("struct Node", header)
        self.assertNotIn("struct TextLists", header)

    def test_single_file_needs_a_user_provided_name(self):
        for backend in ("c", "cpp", "py"):
            for options in ("type=%s,single_file", "type=%s,single_file="):
                with self.subTest(backend=backend, options=options):
                    result, _ = self.generate(options % backend)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("single_file needs a name", result.stderr)

    def test_no_stub_files_are_generated(self):
        for options in ("type=py", "type=py,single_file=all", "type=c", "type=cpp"):
            with self.subTest(options=options):
                found, _ = self.files(options)
                self.assertFalse([name for name in found if name.endswith(".pyi")])

    def test_c_single_file(self):
        found, out = self.files("type=c,prefix=sample,single_file=all")
        self.assertTrue({"sample_all.pb.h", "sample_all.pb.c", "sample_bindings.c", "sample_bindings.h",
                         "sample_defines.h", "sample_encode.c", "sample_decode.c"} <= found)
        self.assertFalse({"sample_message.pb.h", "sample_depth.pb.h", "sample_callback.pb.h",
                          "sample_scalars.pb.h"} & found)
        with open(os.path.join(out, "sample_all.pb.h"), encoding="utf-8") as f:
            header = f.read()
        for name in ("samplepkg_SampleMessage", "depthpkg_DepthL13", "callbackpkg_CallbackParent",
                     "scalarpkg_Scalars", "shared_Stamp"):
            self.assertIn(name, header)
        with open(os.path.join(out, "sample_bindings.c"), encoding="utf-8") as f:
            self.assertIn('#include "sample_all.pb.h"', f.read())

    def test_cpp_single_file(self):
        found, out = self.files("type=cpp,single_file=all")
        self.assertTrue({"all.pb.h", "hikaripb_bindings.cc", "hikaripb_bindings.h", "hikaripb_defines.h"} <= found)
        self.assertFalse({"message.pb.h", "depth.pb.h", "callback.pb.h", "scalars.pb.h"} & found)
        with open(os.path.join(out, "all.pb.h"), encoding="utf-8") as f:
            header = f.read()
        # one namespace block per .proto file
        for namespace in ("namespace callbackpkg", "namespace depthpkg", "namespace samplepkg",
                          "namespace scalarpkg", "namespace shared"):
            self.assertIn(namespace, header)

    def test_invalid_single_file_names_are_rejected(self):
        for backend in ("c", "cpp", "py"):
            for name in ("a-b", "a/b", "1abc", "a.b"):
                with self.subTest(backend=backend, name=name):
                    result, _ = self.generate("type=%s,single_file=%s" % (backend, name))
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Invalid single_file name", result.stderr)

    def test_duplicate_class_names_are_reported(self):
        out = tempfile.mkdtemp(prefix="hikaripb_test_")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        a = os.path.join(out, "a.proto")
        b = os.path.join(out, "b.proto")
        for path, package in ((a, "pkg_a"), (b, "pkg_b")):
            with open(path, "w", encoding="utf-8") as f:
                f.write('syntax = "proto3";\npackage %s;\nmessage Same { uint32 v = 1; }\n' % package)
        command = [PROTOC, "--plugin=protoc-gen-hikaripb=" + PLUGIN, "--proto_path=" + out,
                   "--hikaripb_out=type=py,single_file=all:" + out, a, b]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("would both generate class Same", result.stderr)
        # separate modules do not collide
        command[-3] = "--hikaripb_out=type=py:" + out
        self.assertEqual(subprocess.run(command, capture_output=True, text=True).returncode, 0)

    def test_messages_and_enums_nested_to_any_depth_are_generated(self):
        nested = [os.path.join(PROTO_DIR, "nested.proto")]
        _, out = self.files("type=c,prefix=sample", nested)
        with open(os.path.join(out, "sample_nested.pb.h"), encoding="utf-8") as f:
            header = f.read()
        for name in ("nestedpkg_LeafKind_t", "nestedpkg_InnerKind_t", "nestedpkg_MiddleKind_t", "nestedpkg_OuterKind_t"):
            self.assertIn(name, header)
        # a message follows the messages nested in it
        positions = [header.index("} nestedpkg_%s;" % name) for name in ("Leaf", "Inner", "Middle", "Outer")]
        self.assertEqual(positions, sorted(positions))

        _, out = self.files("type=cpp", nested)
        with open(os.path.join(out, "nested.pb.h"), encoding="utf-8") as f:
            header = f.read()
        for name in ("enum LeafKind", "enum InnerKind", "enum MiddleKind", "enum OuterKind"):
            self.assertIn(name, header)
        positions = [header.index("struct %s " % name) for name in ("Leaf", "Inner", "Middle", "Outer")]
        self.assertEqual(positions, sorted(positions))

    def test_c_and_cpp_resolve_types_of_other_packages_by_their_full_name(self):
        out = tempfile.mkdtemp(prefix="hikaripb_test_")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        schemas = {
            "a.proto": 'package pkg_a;\nenum Mode { MODE_A = 0; }\nmessage Config { uint32 a = 1; }\n',
            "b.proto": 'package pkg_b;\nenum Mode { MODE_B = 0; }\nmessage Config { uint32 b = 1; }\n',
            "use.proto": 'package pkg_use;\nimport "a.proto";\nimport "b.proto";\n'
                         'message Use { pkg_a.Config first = 1; pkg_b.Config second = 2; pkg_a.Mode mode_a = 3; pkg_b.Mode mode_b = 4; }\n',
        }
        for name, text in schemas.items():
            with open(os.path.join(out, name), "w", encoding="utf-8") as f:
                f.write('syntax = "proto3";\n' + text)
        protos = [os.path.join(out, name) for name in schemas]

        def generate(options):
            target = os.path.join(out, options.split(",")[0].replace("=", "_"))
            os.mkdir(target)
            command = [PROTOC, "--plugin=protoc-gen-hikaripb=" + PLUGIN, "--proto_path=" + out,
                       "--hikaripb_out=%s:%s" % (options, target)] + protos
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return target

        with open(os.path.join(generate("type=c"), "hikaripb_use.pb.h"), encoding="utf-8") as f:
            header = f.read()
        self.assertIn("#define pkg_use_Use_first_ctype pkg_a_Config", header)
        self.assertIn("#define pkg_use_Use_second_ctype pkg_b_Config", header)
        self.assertIn("#define pkg_use_Use_mode_a_ctype pkg_a_Mode_t", header)
        self.assertIn("#define pkg_use_Use_mode_b_ctype pkg_b_Mode_t", header)
        with open(os.path.join(generate("type=cpp"), "use.pb.h"), encoding="utf-8") as f:
            header = f.read()
        self.assertIn("addMsg<pkg_a::Config>(1)", header)
        self.assertIn("addMsg<pkg_b::Config>(2)", header)
        self.assertIn("set_mode_a(pkg_a::Mode", header)
        self.assertIn("set_mode_b(pkg_b::Mode", header)


OLD_NAME = "on" + "cp"  # the default prefix used before 2.0.0 must not appear anywhere any more


class NamingTest(unittest.TestCase):
    def test_no_reference_to_the_old_default_name_in_the_project(self):
        skipped_dirs = {".git", "build", "docs", "__pycache__"}
        found = []
        for folder, dirs, names in os.walk(support.ROOT):
            dirs[:] = [d for d in dirs if d not in skipped_dirs]
            for name in names:
                path = os.path.join(folder, name)
                relative = os.path.relpath(path, support.ROOT)
                if OLD_NAME in relative.lower():
                    found.append(relative)
                    continue
                try:
                    with open(path, encoding="utf-8") as f:
                        text = f.read()
                except (UnicodeDecodeError, OSError):
                    continue
                if OLD_NAME in text.lower():
                    found.append(relative)
        self.assertEqual(found, [])

    @unittest.skipUnless(shutil.which(PROTOC), "protoc not available")
    def test_generated_files_with_default_options_do_not_mention_it(self):
        for backend in ("c", "cpp", "py"):
            with self.subTest(backend=backend):
                out = tempfile.mkdtemp(prefix="hikaripb_test_")
                self.addCleanup(shutil.rmtree, out, ignore_errors=True)
                command = [PROTOC, "--experimental_allow_proto3_optional", "--plugin=protoc-gen-hikaripb=" + PLUGIN,
                           "--proto_path=" + PROTO_DIR, "--hikaripb_out=type=%s:%s" % (backend, out)] + PROTOS
                self.assertEqual(subprocess.run(command, capture_output=True, text=True).returncode, 0)
                for folder, _, names in os.walk(out):
                    for name in names:
                        self.assertNotIn(OLD_NAME, name.lower())
                        with open(os.path.join(folder, name), encoding="utf-8") as f:
                            self.assertNotIn(OLD_NAME, f.read().lower(), name)


class GeneratedSourceTest(unittest.TestCase):
    def test_generated_modules_compile_without_warnings(self):
        sources = []
        for folder in (support.GEN_DIR, support.SINGLE_DIR):
            for root, _, names in os.walk(folder):
                sources += [os.path.join(root, n) for n in names if n.endswith(".py")]
        self.assertGreater(len(sources), 8)
        for path in sources:
            with self.subTest(path=os.path.relpath(path, support.GENERATED)):
                with open(path, encoding="utf-8") as f:
                    text = f.read()
                with warnings.catch_warnings():
                    warnings.simplefilter("error")
                    compile(text, path, "exec")


class SingleFileModuleTest(unittest.TestCase):
    """The module generated with single_file=all (see test/Makefile) behaves like the per-proto modules."""

    @classmethod
    def setUpClass(cls):
        if not os.path.isdir(support.SINGLE_DIR):
            raise unittest.SkipTest("single_file output %s not generated" % support.SINGLE_DIR)
        import importlib
        import sys

        sys.path.insert(0, support.SINGLE_DIR)
        cls.all_pb = importlib.import_module("all_pb")
        cls.codec = importlib.import_module("hikaripb_codec")

    def test_directory_content(self):
        names = {n for n in os.listdir(support.SINGLE_DIR) if n.endswith((".py", ".pxd"))}
        self.assertEqual(names, {"all_pb.py", "hikaripb_codec.py", "hikaripb_codec.pxd", "hikaripb_build_ext.py"})

    def test_all_types_live_in_the_one_module(self):
        for name in ("SampleMessage", "Point", "Item", "Metadata", "Color", "ItemKind", "MetadataKind", "SparseTags",
                     "DepthL0", "DepthL13", "CallbackMsg", "CallbackChild", "CallbackParent",
                     "Scalars", "Repeats", "TextLists", "Choice", "Node", "Stamp", "Level", "Unit"):
            self.assertTrue(hasattr(self.all_pb, name), name)

    def test_the_runtime_is_the_one_with_the_default_prefix(self):
        self.assertTrue(issubclass(self.all_pb.SampleMessage, self.codec.Message))
        self.assertIsNot(self.codec, support.codec)

    def test_wire_format_is_identical_to_the_per_proto_modules(self):
        mine = support.full_sample_message().serialize()
        ported = self.all_pb.SampleMessage().deserialize(mine)
        self.assertEqual(ported.serialize(), mine)
        self.assertEqual(self.all_pb.SampleMessage(label="x").serialize(), support.message.SampleMessage(label="x").serialize())

    def test_types_from_what_used_to_be_other_files_reference_each_other_directly(self):
        msg = self.all_pb.Choice(stamp=self.all_pb.Stamp(seconds=5, unit=self.all_pb.Unit.UNIT_MS))
        again = self.all_pb.Choice().deserialize(msg.serialize())
        self.assertEqual((again.stamp.seconds, again.stamp.unit), (5, self.all_pb.Unit.UNIT_MS))
        self.assertIs(type(again.stamp), self.all_pb.Stamp)

    def test_depth_chain(self):
        node = self.all_pb.DepthL0(value=1, next=self.all_pb.DepthL1(value=2))
        decoded = self.all_pb.DepthL0().deserialize(node.serialize())
        self.assertEqual((decoded.value, decoded.next.value), (1, 2))


if __name__ == "__main__":
    unittest.main()
