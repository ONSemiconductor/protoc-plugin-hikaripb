"""Generator tests of type=sphinxdocs: layout of the output, options, references, images and a real Sphinx build.

Runs protoc with the plugin of this repository, so it needs `protoc` on PATH (skipped otherwise). The Sphinx
build needs `sphinx` and `myst_parser` for the interpreter running the tests (skipped otherwise).
"""

import base64
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
PROTOC = os.environ.get("PROTOC", "protoc")
# protoc cannot start a Python script as a plugin on Windows
PLUGIN = os.environ.get("HIKARIPB_PLUGIN") or os.path.join(
    ROOT, "protoc", "protoc-gen-hikaripb.bat" if os.name == "nt" else "hikaripb.py")
PROTO_DIR = os.path.join(HERE, "proto")
PROTOS = ["base.proto", "single/only.proto", "sub/device.proto", "sub/extra.proto"]
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
HAVE_SPHINX = bool(importlib.util.find_spec("sphinx") and importlib.util.find_spec("myst_parser"))
# two pages per file: the file, which shows its header, and its Protocol
PAGES = {"%s%s.md" % (name, suffix) for name in ("base", "single/only", "sub/device", "sub/extra")
         for suffix in ("", "-protocol")}


@unittest.skipUnless(shutil.which(PROTOC), "protoc not available")
class SphinxDocsTest(unittest.TestCase):
    runs = {}  # options -> (files, standard error): every run starts a Python process, which is slow on Windows

    def tmp(self):
        path = tempfile.mkdtemp(prefix="hikaripb_test_")
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        return path

    def run_protoc(self, options, out, proto_dir=PROTO_DIR, protos=PROTOS):
        command = [PROTOC, "--experimental_allow_proto3_optional", "--plugin=protoc-gen-hikaripb=" + PLUGIN,
                   "--proto_path=" + proto_dir, "--hikaripb_out=type=sphinxdocs%s:%s" % (options, out)]
        return subprocess.run(command + [os.path.join(proto_dir, name) for name in protos],
                              capture_output=True, text=True, encoding="utf-8")

    def generate(self, options="", out=None):
        """The generated files by name (with `/`) and the standard error of the plugin."""
        if out is None and options in self.runs:
            return self.runs[options]
        directory = out or self.tmp()
        result = self.run_protoc(options, directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        files = {}
        for folder, _, names in os.walk(directory):
            for name in names:
                if not name.endswith((".md", ".py")):  # the images of the test are no output
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8") as f:
                    files[os.path.relpath(path, directory).replace(os.sep, "/")] = f.read()
        if out is None:
            self.runs[options] = files, result.stderr
        return files, result.stderr

    def test_the_documentation_is_the_root_by_default(self):
        files, _ = self.generate()
        self.assertEqual(set(files), PAGES | {"conf.py", "index.md", "sub/index.md"})
        self.assertIn('extensions = ["myst_parser"]', files["conf.py"])
        self.assertTrue(files["index.md"].startswith("# Protocol\n"))

    def test_omit_conf(self):
        files, _ = self.generate(",omit_conf")
        self.assertEqual(set(files), PAGES | {"index.md", "sub/index.md"})

    def test_parent_makes_the_documentation_a_chapter(self):
        files, _ = self.generate(",parent=chapter/protocol")
        self.assertEqual(set(files), {"chapter/protocol/" + name for name in PAGES | {"index.md", "sub/index.md"}})
        # the lists and toctrees are relative to the page
        index = files["chapter/protocol/index.md"]
        self.assertIn("- [single/only.proto](single/only.md)", index)
        self.assertIn("\nSub <sub/index>\n", index)

    def test_parent_must_stay_below_the_output_directory(self):
        for value in ("../outside", "a/../../b", "/absolute"):
            with self.subTest(parent=value):
                result = self.run_protoc(",parent=" + value, self.tmp())
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Invalid parent", result.stderr)

    def test_options_need_a_value(self):
        for option in ("parent", "image_path"):
            with self.subTest(option=option):
                result = self.run_protoc("," + option, self.tmp())
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("%s needs a value" % option, result.stderr)

    def test_image_path_must_be_relative(self):
        result = self.run_protoc(",image_path=/absolute", self.tmp())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid image_path", result.stderr)

    def test_title(self):
        files, _ = self.generate(",title=My+Protocol%20Docs")
        self.assertTrue(files["index.md"].startswith("# My Protocol Docs\n"))
        self.assertIn('project = "My Protocol Docs"', files["conf.py"])

    def test_single_file_is_not_supported(self):
        result = self.run_protoc(",single_file=all", self.tmp())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("single_file is not supported", result.stderr)

    def test_pages_must_not_overwrite_each_other(self):
        folder = self.tmp()
        os.makedirs(os.path.join(folder, "a"))
        for name, package in (("a/index.proto", "one"), ("a/b.proto", "two")):
            with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
                f.write('syntax = "proto3";\npackage %s;\nmessage M { uint32 v = 1; }\n' % package)
        result = self.run_protoc("", self.tmp(), proto_dir=folder, protos=["a/index.proto", "a/b.proto"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("would overwrite a/index.md", result.stderr)

    def test_navigation_follows_the_directories(self):
        files, _ = self.generate()
        # a file nobody imports comes first, then the files it imports; a directory with one file is no level
        self.assertIn("""- [single/only.proto](single/only.md) — The only file of its directory: it is listed at the top level.
- [Sub](sub/index.md)
  - [device.proto](sub/device.md) — Device messages, built on the [`Item`](#hikaripb.docs.base.Item) of the base schema.
  - [extra.proto](sub/extra.md) — More device messages: the second file of the directory, so that the directory is listed on its own page.
- [base.proto](base.md) — Test schema of the Sphinx documentation generator.
""", files["index.md"])
        self.assertIn("```{toctree}\n:hidden:\n:titlesonly:\n\nsingle/only.proto <single/only>\nSub <sub/index>\n"
                      "base.proto <base>\n```", files["index.md"])
        self.assertNotIn("single/index.md", files)
        # the page of the directory lists its files relative to itself
        self.assertTrue(files["sub/index.md"].startswith("# Sub\n\n- [device.proto](device.md) — Device messages"))
        self.assertIn("\ndevice.proto <device>\nextra.proto <extra>\n```", files["sub/index.md"])

    def test_every_file_has_a_page_and_a_protocol(self):
        files, _ = self.generate()
        # the page of the file shows the header, the Protocol is the only page below it, listed by the navigation only
        self.assertTrue(files["base.md"].startswith("# base.proto\n\n**Package:** `docs.base`\n\n"
                                                     "Test schema of the Sphinx documentation generator.\n\n"))
        self.assertTrue(files["base.md"].endswith("```{toctree}\n:hidden:\n:titlesonly:\n\nbase-protocol\n```\n"))
        self.assertIn("\ndevice-protocol\n```\n", files["sub/device.md"])
        self.assertTrue(files["base-protocol.md"].startswith("# Protocol\n\n## Messages\n\n"))
        self.assertFalse([name for name in files if name.endswith("-overview.md")])

    def test_inline_protocol_ends_the_page_of_the_file(self):
        files, _ = self.generate(",inline_protocol")
        # one page per file: the Protocol is its last section, not a page of its own
        self.assertEqual(set(files), {name for name in PAGES if not name.endswith("-protocol.md")}
                         | {"conf.py", "index.md", "sub/index.md"})
        base = files["base.md"]
        self.assertNotIn("toctree", base)
        self.assertTrue(base.endswith("\n") and not base.endswith("\n\n"))
        self.assertLess(base.index("\n## Anchored section\n"), base.index("\n## Protocol\n\n### Messages\n\n"))
        self.assertLess(base.index("\n### Messages\n"), base.index("\n### Enumerations\n"))
        # everything is one level deeper than on the page below the page of the file
        for heading in ("Item", "Item.Kind", "Result"):
            self.assertIn("\n#### %s\n" % heading, base)
        self.assertNotIn("\n### Item\n", base)
        self.assertIn("(hikaripb.docs.base.Item)=\n\n#### Item\n\n*Message* `docs.base.Item`", base)
        # the Protocol of a file without enums has no section for them
        self.assertNotIn("Enumerations", files["single/only.md"])
        self.assertIn("\n## Protocol\n\n### Messages\n\n(hikaripb.docs.single.Lone)=\n\n#### Lone\n", files["single/only.md"])

    def test_inline_protocol_changes_nothing_else(self):
        inline, _ = self.generate(",inline_protocol")
        pages, _ = self.generate()
        self.assertEqual(inline["index.md"], pages["index.md"])
        self.assertEqual(inline["sub/index.md"], pages["sub/index.md"])
        # the header of a file is the same; the messages of the Protocol page are the ones that end the page
        self.assertEqual(inline["base.md"].split("\n## Protocol\n")[0].rstrip("\n"),
                         pages["base.md"].split("```{toctree}")[0].rstrip("\n"))
        self.assertIn("see [`Result`](#hikaripb.docs.base.Result)", inline["sub/device.md"])
        self.assertIn("**`mode`** — *oneof*", inline["sub/device.md"])
        self.assertEqual(inline["sub/device.md"].count("(hikaripb.docs.base.device.Config.mode)="), 1)

    def test_the_page_of_a_file_is_its_header(self):
        base = self.generate()[0]["base.md"]
        # the headings of the comment go below the title of the page
        self.assertIn("\n## Details\n", base)
        self.assertIn("\n## Anchored section\n", base)
        self.assertNotIn("## Messages", base)
        self.assertIn("```c\nint x = 1;\n\nint y = 2;\n```", base)
        self.assertIn("{math}`t_B` = 1 / {math}`f` and\n13{sub}`H`", base)
        self.assertIn("![](figures/diagram.png)", base)
        self.assertTrue(base.endswith("\n") and not base.endswith("\n\n"))
        # the comments in front of `syntax` and `package` make up the header
        device = self.generate()[0]["sub/device.md"]
        self.assertEqual(device, "# sub/device.proto\n\n**Package:** `docs.base.device`\n\n"
                         "Device messages, built on the [`Item`](#hikaripb.docs.base.Item) of the base schema.\n\n"
                         "Package of the device messages: its comment belongs to the file as well.\n\n"
                         "```{toctree}\n:hidden:\n:titlesonly:\n\ndevice-protocol\n```\n")

    def test_protocol_documents_messages_fields_and_enums(self):
        files = self.generate()[0]
        base = files["base-protocol.md"]
        self.assertIn("\n## Messages\n", base)
        self.assertIn("\n## Enumerations\n", base)
        self.assertIn("```{note}\nItems are small.\n```", base)
        self.assertIn("**`resOk`** — Success.", base)
        self.assertIn("**`resUnsupported`**\\\n  Not supported.\n\n  ```{warning}\n  Do not rely on it.\n  ```", base)
        # the numbers of enum values are not shown
        self.assertNotIn("** = ", base)
        self.assertIn("**`result`** — *optional* [`Result`](#hikaripb.docs.base.Result)\n", base)
        self.assertIn("### Item.Kind\n", base)
        device = files["sub/device-protocol.md"]
        self.assertIn("### Config\n\n*Message* `docs.base.device.Config`\n\nConfiguration of a device.", device)
        self.assertIn("**`handle`** — `uint32`\\\n  Handle of the device,", device)
        self.assertIn("**`items`** — *repeated* [`Item`](#hikaripb.docs.base.Item)\\\n", device)
        self.assertIn("**`counters`** — `map<string, uint32>`\\\n", device)
        self.assertNotIn("*repeated* `map", device)
        self.assertIn("**`mode`** — *oneof*", device)
        self.assertIn("  - (hikaripb.docs.base.device.Config.fast)=\n\n    **`fast`** — `bool`\\\n", device)
        self.assertIn("**`nested`** — [`Nested`](#hikaripb.docs.base.device.Config.Nested)\n", device)
        self.assertIn("### Config.Nested\n", device)

    def test_tag_numbers_are_not_documented(self):
        for name, text in self.generate()[0].items():
            self.assertIsNone(re.search(r"\btags? \d", text), name)
        device = self.generate()[0]["sub/device-protocol.md"]
        # reserved names stay, reserved tags go
        self.assertIn("- **reserved** — name `old`\\\n  Name of a removed field.", device)
        self.assertEqual(device.count("reserved"), 1)

    def test_references_resolve_like_protobuf_names(self):
        files, _ = self.generate()
        base, device = files["base.md"] + files["base-protocol.md"], files["sub/device-protocol.md"]
        # parent package, absolute name from another file, enum value, field of the own message
        self.assertIn("see [`Result`](#hikaripb.docs.base.Result)", device)
        self.assertIn("see [`docs.base.device.Config.handle`](#hikaripb.docs.base.device.Config.handle)", base)
        self.assertIn("[`resOk`](#hikaripb.docs.base.Result.resOk)", base)
        self.assertIn("[`Item.kind`](#hikaripb.docs.base.Item.kind-2)", base)
        self.assertIn("[`kindA`](#hikaripb.docs.base.Item.Kind.kindA)", base)
        self.assertIn("[`kindB`](#hikaripb.docs.base.Item.Kind.kindB)", base)
        self.assertIn("see [`Status`](#hikaripb.docs.base.extra.Status)", files["sub/extra-protocol.md"])
        # section of a comment
        self.assertIn("(hikaripb.anchored)=\n\n## Anchored section", base)
        self.assertIn("Linked from [`anchored`](#hikaripb.anchored).", base)

    def test_labels_differ_when_only_the_case_differs(self):
        base = self.generate()[0]["base-protocol.md"]
        self.assertIn("(hikaripb.docs.base.Item.Kind)=", base)
        self.assertIn("(hikaripb.docs.base.Item.kind-2)=", base)

    def test_unresolved_reference_is_reported(self):
        files, stderr = self.generate()
        self.assertIn("sub/device.proto: handle: cannot resolve @ref nosuchsymbol", stderr)
        self.assertIn("Unknown: `nosuchsymbol`.", files["sub/device-protocol.md"])

    def test_prefix_names_the_labels(self):
        files, _ = self.generate(",prefix=abc")
        self.assertIn("(abc.docs.base.Item)=", files["base-protocol.md"])
        self.assertNotIn("hikaripb.", files["base-protocol.md"])

    def test_image_paths_are_relative_to_the_page(self):
        files, _ = self.generate()
        # the references of the comments are relative to the output directory
        self.assertIn("![](figures/diagram.png)", files["base.md"])
        self.assertIn("```{figure} ../figures/diagram.png\n  :alt: Diagram caption\n  :width: 50%",
                      files["sub/device-protocol.md"])
        files, _ = self.generate(",parent=chapter")
        self.assertIn("![](../figures/diagram.png)", files["chapter/base.md"])
        self.assertIn("{figure} ../../figures/diagram.png", files["chapter/sub/device-protocol.md"])

    def test_image_path_moves_the_images(self):
        files, _ = self.generate(",image_path=../assets")
        self.assertIn("![](../assets/figures/diagram.png)", files["base.md"])
        self.assertIn("{figure} ../../assets/figures/diagram.png", files["sub/device-protocol.md"])

    def test_nothing_mentions_the_old_default_name(self):
        old = "on" + "cp"
        for options in ("", ",parent=chapter"):
            for name, text in self.generate(options)[0].items():
                self.assertNotIn(old, name.lower())
                self.assertNotIn(old, text.lower(), name)

    def build(self, source, builder="html"):
        out = self.tmp()
        command = [sys.executable, "-m", "sphinx", "-q", "-W", "--keep-going", "-b", builder, source, out]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return out

    def write_images(self, folder):
        os.makedirs(os.path.join(folder, "figures"))
        with open(os.path.join(folder, "figures", "diagram.png"), "wb") as f:
            f.write(PNG)

    @unittest.skipUnless(HAVE_SPHINX, "sphinx and myst_parser not available")
    def test_sphinx_builds_the_documentation_without_warnings(self):
        source = os.path.join(self.tmp(), "docs")
        os.makedirs(source)
        self.write_images(source)
        self.generate(out=source)
        html = self.build(source)
        for page in ("index.html", "sub/index.html", "sub/device.html",
                     "sub/device-protocol.html", "base-protocol.html"):
            self.assertTrue(os.path.exists(os.path.join(html, page)), page)
        with open(os.path.join(html, "sub", "device-protocol.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertIn('id="hikaripb-docs-base-device-config-handle"', page)
        self.assertIn('href="../base-protocol.html#hikaripb-docs-base-item"', page)
        self.assertTrue(os.path.exists(os.path.join(html, "_images", "diagram.png")))
        # the navigation: the directory, its file and the Protocol below the file
        with open(os.path.join(html, "sub", "device.html"), encoding="utf-8") as f:
            navigation = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", f.read().split("Navigation", 1)[1]))
        self.assertRegex(navigation, r"single/only\.proto.*Sub.*device\.proto.*Protocol.*extra\.proto.*base\.proto")

    @unittest.skipUnless(HAVE_SPHINX, "sphinx and myst_parser not available")
    def test_sphinx_builds_the_inline_protocol_without_warnings(self):
        source = os.path.join(self.tmp(), "docs")
        os.makedirs(source)
        self.write_images(source)
        self.generate(",inline_protocol", out=source)
        html = self.build(source)
        self.assertFalse(os.path.exists(os.path.join(html, "base-protocol.html")))
        with open(os.path.join(html, "sub", "device.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertIn('id="hikaripb-docs-base-device-config-handle"', page)
        self.assertIn('href="../base.html#hikaripb-docs-base-item"', page)

    @unittest.skipUnless(HAVE_SPHINX, "sphinx and myst_parser not available")
    def test_inline_protocol_is_a_section_like_the_ones_of_the_header_in_latex(self):
        # A page below a page ends up in the last section of the page in a single document, so the Protocol of the
        # page-below structure is a subsection of whatever section the header ends with. Inline, it is a sibling.
        headings = {}
        for options in ("", ",inline_protocol"):
            source = os.path.join(self.tmp(), "docs")
            os.makedirs(source)
            self.write_images(source)
            self.generate(options, out=source)
            with open(os.path.join(self.build(source, "latex"), "protocol.tex"), encoding="utf-8") as f:
                tex = f.read()
            headings[options] = re.findall(r"^\\(chapter|section|subsection|subsubsection)\{([^}]*)\}", tex, re.M)
        details = ("section", "Anchored section")
        self.assertIn(details, headings[""])
        self.assertEqual(headings[""][headings[""].index(details) + 1], ("subsection", "Protocol"))
        self.assertEqual(headings[",inline_protocol"][headings[",inline_protocol"].index(details) + 1],
                         ("section", "Protocol"))
        self.assertIn(("subsection", "Messages"), headings[",inline_protocol"])

    @unittest.skipUnless(HAVE_SPHINX, "sphinx and myst_parser not available")
    def test_sphinx_builds_the_documentation_as_a_chapter(self):
        workspace = self.tmp()
        source = os.path.join(workspace, "docs")
        os.makedirs(source)
        self.write_images(os.path.join(workspace, "assets"))
        with open(os.path.join(source, "conf.py"), "w", encoding="utf-8") as f:
            f.write('project = "Host"\nextensions = ["myst_parser"]\n')
        with open(os.path.join(source, "index.md"), "w", encoding="utf-8") as f:
            f.write("# Host\n\n```{toctree}\nprotocol/index\n```\n")
        self.generate(",parent=protocol,image_path=../assets", out=source)
        html = self.build(source)
        self.assertTrue(os.path.exists(os.path.join(html, "protocol", "sub", "device-protocol.html")))
        self.assertTrue(os.path.exists(os.path.join(html, "_images", "diagram.png")))


if __name__ == "__main__":
    unittest.main()
