"""Tests of the namespace override and of `ignore`, which every backend supports (protoc/names.py).

The unit tests need nothing but Python; the runs of the plugin need `protoc` on PATH (skipped otherwise).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "protoc"))

from names import Ignored, Namespaces, type_names  # noqa: E402

PROTOC = os.environ.get("PROTOC", "protoc")
# protoc cannot start a Python script as a plugin on Windows
PLUGIN = os.environ.get("HIKARIPB_PLUGIN") or os.path.join(
    ROOT, "protoc", "protoc-gen-hikaripb.bat" if os.name == "nt" else "hikaripb.py")

# two packages with `demo` in common: demo.core and demo.extra.sub
CORE = """syntax = "proto3";
package demo.core;

// A thing.
message Thing {
   uint32 id = 1;  // Identifier.
}

// Kinds of things.
enum Kind {
   kindNone = 0;  // No kind.
   kindSome = 1;  // Some kind.
}
"""
EXTRA = """syntax = "proto3";
package demo.extra.sub;

import "core.proto";

// A part of a @ref .demo.core.Thing of a @ref core.Kind.
message Part {
   demo.core.Thing thing = 1;  // The thing.
   demo.core.Kind kind = 2;  // The kind.
   uint32 count = 3;  // How many.
}

// Left over.
message Spare {
   uint32 value = 1;  // A value.
}
"""


class NamespacesTest(unittest.TestCase):
    def packages(self, shared, override, *packages):
        namespaces = Namespaces(shared, override)
        return [namespaces.package(package) for package in packages]

    def test_the_part_that_all_packages_share_is_replaced(self):
        packages = ("esb", "esb.gpio", "esb.net.core")
        self.assertEqual(self.packages(packages, "abc", *packages), ["abc", "abc.gpio", "abc.net.core"])

    def test_the_longest_shared_part_is_replaced(self):
        packages = ("esb.net.core", "esb.net.phy")
        self.assertEqual(self.packages(packages, "x.y", *packages), ["x.y.core", "x.y.phy"])

    def test_one_package_is_replaced_as_a_whole(self):
        self.assertEqual(self.packages(["demo.core"], "acme", "demo.core"), ["acme"])

    def test_packages_that_share_nothing_get_the_override_in_front(self):
        self.assertEqual(self.packages(["a.b", "c"], "x", "a.b", "c"), ["x.a.b", "x.c"])

    def test_a_name_is_shared_only_as_a_whole(self):
        self.assertEqual(self.packages(["esbx", "esb.gpio"], "x", "esbx", "esb.gpio"), ["x.esbx", "x.esb.gpio"])

    def test_a_file_without_a_package_shares_nothing(self):
        self.assertEqual(self.packages(["", "a"], "x", "", "a"), ["x", "x.a"])

    def test_without_an_override_the_packages_stay(self):
        for override in ("", "  ", "."):
            self.assertEqual(self.packages(["a", "a.b"], override, "a", "a.b"), ["a", "a.b"])

    def test_double_colons_and_spaces_in_the_override(self):
        self.assertEqual(self.packages(["a"], " x :: y ", "a"), ["x.y"])

    def test_the_names_of_a_namespace(self):
        self.assertEqual(Namespaces(["a.b", "a.c"], "x").parts("a.c"), ["x", "c"])
        self.assertEqual(Namespaces().parts("a.c"), ["a", "c"])


class IgnoredTest(unittest.TestCase):
    def test_a_type_has_many_names(self):
        names = type_names("demo.extra.sub", "acme.extra.sub", "Spare")
        for entry in ("demo.extra.sub.Spare", ".demo.extra.sub.Spare", "demo_extra_sub_Spare",
                      "demo::extra::sub::Spare", "acme.extra.sub.Spare", "acme_extra_sub_Spare"):
            with self.subTest(entry=entry):
                self.assertTrue(Ignored([entry]).matches(names))
        for entry in ("Spare", "extra.sub.Spare", "demo.core.Spare", "demo.extra.sub.Part", "demo_extra_sub", ""):
            with self.subTest(entry=entry):
                self.assertFalse(Ignored([entry]).matches(names))

    def test_a_nested_type_is_named_in_full_and_flat(self):
        names = type_names("p", "q", "Outer.Inner")
        for entry in ("p.Outer.Inner", "p_Outer_Inner", "p.Inner", "p_Inner", "q.Outer.Inner", "q_Inner"):
            with self.subTest(entry=entry):
                self.assertTrue(Ignored([entry]).matches(names))
        self.assertFalse(Ignored(["Inner", "p.Outer"]).matches(names))

    def test_a_type_without_a_package(self):
        self.assertTrue(Ignored(["Msg"]).matches(type_names("", "", "Msg")))
        self.assertTrue(Ignored(["acme.Msg"]).matches(type_names("", "acme", "Msg")))

    def test_nothing_is_ignored_without_entries(self):
        self.assertFalse(Ignored().matches(["a.B", "a_B"]))
        self.assertFalse(Ignored([]).matches([]))

    def test_any_name_counts(self):
        self.assertTrue(Ignored(["x"]).matches(["a", "x"]))


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


@unittest.skipUnless(shutil.which(PROTOC), "protoc not available")
class BackendTest(unittest.TestCase):
    def tmp(self):
        path = tempfile.mkdtemp(prefix="hikaripb_test_")
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        return path

    def setUp(self):
        self.proto_dir = self.tmp()
        write(os.path.join(self.proto_dir, "core.proto"), CORE)
        write(os.path.join(self.proto_dir, "extra.proto"), EXTRA)

    def run_plugin(self, options, cwd=None, out=None):
        """The result of protoc and the generated files by name, as text."""
        out = out or self.tmp()
        command = [PROTOC, "--experimental_allow_proto3_optional", "--plugin=protoc-gen-hikaripb=" + PLUGIN,
                   "--proto_path=" + self.proto_dir, "--hikaripb_out=%s:%s" % (options, out),
                   os.path.join(self.proto_dir, "core.proto"), os.path.join(self.proto_dir, "extra.proto")]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", cwd=cwd)
        files = {}
        for folder, _, names in os.walk(out):
            for name in names:
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8", errors="replace") as f:
                    files[os.path.relpath(path, out).replace(os.sep, "/")] = f.read()
        return result, files

    def generate(self, options):
        result, files = self.run_plugin(options)
        self.assertEqual(result.returncode, 0, result.stderr)
        return files

    def assertNone(self, text, files):
        """No generated file contains the text."""
        for name, content in files.items():
            self.assertNotIn(text, content, name)

    # namespace_override

    def test_c_replaces_the_shared_part_of_the_namespace(self):
        files = self.generate("type=c,namespace_override=acme")
        self.assertIn("typedef struct acme_core_Thing {", files["hikaripb_core.pb.h"])
        self.assertIn("acme_core_Kind", files["hikaripb_core.pb.h"])
        self.assertIn("typedef struct acme_extra_sub_Part {", files["hikaripb_extra.pb.h"])
        self.assertIn("acme_extra_sub_Part_thing_ctype acme_core_Thing", files["hikaripb_extra.pb.h"])
        self.assertNone("demo_", files)

    def test_c_names_the_packages_by_default(self):
        files = self.generate("type=c")
        self.assertIn("typedef struct demo_core_Thing {", files["hikaripb_core.pb.h"])
        self.assertIn("typedef struct demo_extra_sub_Part {", files["hikaripb_extra.pb.h"])

    def test_cpp_replaces_the_shared_part_of_the_namespace(self):
        files = self.generate("type=cpp,namespace_override=acme")
        self.assertIn("namespace acme::core", files["core.pb.h"])
        self.assertIn("namespace acme::extra::sub", files["extra.pb.h"])
        self.assertIn("acme::core::Thing", files["extra.pb.h"])
        self.assertNone("demo::", files)
        self.assertNone("namespace demo", files)

    def test_py_puts_the_modules_into_the_package(self):
        out = self.tmp()
        result, files = self.run_plugin("type=py,namespace_override=acme", out=out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(files), {"acme/core_pb.py", "acme/extra_pb.py", "hikaripb_codec.py",
                                      "hikaripb_codec.pxd", "hikaripb_build_ext.py"})
        self.assertIn("import acme.core_pb as _acme_core_pb", files["acme/extra_pb.py"])
        # the generated modules work: the package is importable from the output directory
        code = ("from acme.core_pb import Thing, Kind\nfrom acme.extra_pb import Part\n"
                "part = Part(thing=Thing(id=7), kind=Kind.kindSome, count=3)\n"
                "back = Part().deserialize(part.serialize())\n"
                "assert (back.thing.id, back.kind, back.count) == (7, Kind.kindSome, 3), back\n")
        run = subprocess.run([sys.executable, "-c", code], cwd=out, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_py_keeps_the_layout_by_default(self):
        files = self.generate("type=py")
        self.assertEqual(set(files), {"core_pb.py", "extra_pb.py", "hikaripb_codec.py", "hikaripb_codec.pxd",
                                      "hikaripb_build_ext.py"})

    def test_py_replaces_the_package_of_the_modules(self):
        # the modules of the files below a directory are replaced as far as all of them are in it
        write(os.path.join(self.proto_dir, "api", "one.proto"), 'syntax = "proto3";\nmessage One { uint32 v = 1; }\n')
        write(os.path.join(self.proto_dir, "api", "sub", "two.proto"), 'syntax = "proto3";\nmessage Two { uint32 v = 1; }\n')
        out = self.tmp()
        command = [PROTOC, "--plugin=protoc-gen-hikaripb=" + PLUGIN, "--proto_path=" + self.proto_dir,
                   "--hikaripb_out=type=py,namespace_override=acme.v2:" + out,
                   os.path.join(self.proto_dir, "api", "one.proto"), os.path.join(self.proto_dir, "api", "sub", "two.proto")]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(os.path.isfile(os.path.join(out, "acme", "v2", "one_pb.py")))
        self.assertTrue(os.path.isfile(os.path.join(out, "acme", "v2", "sub", "two_pb.py")))

    def test_docs_show_the_overridden_names(self):
        files = self.generate("type=sphinxdocs,omit_conf,namespace_override=acme")
        core, extra = files["core-protocol.md"], files["extra-protocol.md"]
        self.assertIn("(hikaripb.acme.core.Thing)=", core)
        self.assertIn("*Message* `acme.core.Thing`", core)
        self.assertIn("*Enumeration* `acme.core.Kind`", core)
        self.assertIn("(hikaripb.acme.extra.sub.Part.thing)=", extra)
        # the type of a field is named as short as the scope allows, and links to the symbol
        self.assertIn("[`core.Thing`](#hikaripb.acme.core.Thing)", extra)
        self.assertIn("**Package:** `acme.extra.sub`", files["extra.md"])
        self.assertNone("demo", files)

    def test_docs_resolve_the_references_with_the_names_of_the_schema(self):
        result, files = self.run_plugin("type=sphinxdocs,omit_conf,namespace_override=acme")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("cannot resolve", result.stderr)
        # an absolute name is shown as the symbol is named now, a relative one as it is written
        self.assertIn("A part of a [`acme.core.Thing`](#hikaripb.acme.core.Thing) of a "
                      "[`core.Kind`](#hikaripb.acme.core.Kind).", files["extra-protocol.md"])

    def test_docs_show_the_names_of_the_schema_by_default(self):
        files = self.generate("type=sphinxdocs,omit_conf")
        self.assertIn("A part of a [`demo.core.Thing`](#hikaripb.demo.core.Thing) of a "
                      "[`core.Kind`](#hikaripb.demo.core.Kind).", files["extra-protocol.md"])
        self.assertIn("[`core.Thing`](#hikaripb.demo.core.Thing)", files["extra-protocol.md"])

    # ignore

    def test_every_backend_leaves_out_what_ignore_names(self):
        options = "ignore=demo.extra.sub.Spare"
        files = self.generate("type=c," + options)
        self.assertIn("demo_extra_sub_Part", files["hikaripb_extra.pb.h"])
        self.assertNone("Spare", files)
        files = self.generate("type=cpp," + options)
        self.assertIn("Part", files["extra.pb.h"])
        self.assertNone("Spare", files)
        files = self.generate("type=py," + options)
        self.assertIn("class Part(", files["extra_pb.py"])
        self.assertNotIn("Spare", files["extra_pb.py"])
        files = self.generate("type=sphinxdocs,omit_conf," + options)
        self.assertIn("### Part", files["extra-protocol.md"])
        self.assertNone("Spare", files)

    def test_the_names_of_a_type_for_ignore_follow_the_namespace_override(self):
        for name in ("demo_extra_sub_Spare", "acme.extra.sub.Spare"):
            with self.subTest(name=name):
                files = self.generate("type=c,namespace_override=acme,ignore=" + name)
                self.assertIn("acme_extra_sub_Part", files["hikaripb_extra.pb.h"])
                self.assertNone("Spare", files)

    def test_ignore_of_a_configuration_file_may_use_double_colons(self):
        folder = self.tmp()
        write(os.path.join(folder, "cfg.json"), json.dumps({"ignore": ["demo::extra::sub::Spare"], "prefix": "abc"}))
        result, files = self.run_plugin("type=cpp,config_file=cfg.json", cwd=folder)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Part", files["extra.pb.h"])
        self.assertNone("Spare", files)

    def test_enums_are_left_out_as_well(self):
        # backend -> (file of the enum, enum, file of the message, message)
        tokens = {"c": ("hikaripb_core.pb.h", "demo_core_Kind", "hikaripb_extra.pb.h", "demo_extra_sub_Part"),
                  "cpp": ("core.pb.h", "Kind", "extra.pb.h", "Part"),
                  "py": ("core_pb.py", "class Kind(", "extra_pb.py", "class Part("),
                  "sphinxdocs": ("core-protocol.md", "### Kind", "extra-protocol.md", "### Part")}
        for backend, (enum_file, enum, message_file, message) in tokens.items():
            with self.subTest(backend=backend):
                files = self.generate("type=%s,ignore=demo.core.Kind|demo.extra.sub.Part%s"
                                      % (backend, ",omit_conf" if backend == "sphinxdocs" else ""))
                self.assertNotIn(enum, files[enum_file])
                self.assertNotIn(message, files[message_file])
                self.assertIn("Thing", files[enum_file])
                self.assertIn("Spare", files[message_file])

    def test_a_type_that_another_message_uses_cannot_be_left_out(self):
        for backend in ("c", "cpp", "py"):
            with self.subTest(backend=backend):
                result, _ = self.run_plugin("type=%s,ignore=demo.core.Thing" % backend)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("cannot be left out", result.stderr)

    def test_the_documentation_shows_a_type_that_is_left_out_without_a_link(self):
        files = self.generate("type=sphinxdocs,omit_conf,ignore=demo.core.Thing")
        extra = files["extra-protocol.md"]
        self.assertNotIn("#hikaripb.demo.core.Thing", extra)
        self.assertIn("**`thing`** — `demo.core.Thing`", extra)
        self.assertNotIn("### Thing", files["core-protocol.md"])
        self.assertIn("### Kind", files["core-protocol.md"])


if __name__ == "__main__":
    unittest.main()
