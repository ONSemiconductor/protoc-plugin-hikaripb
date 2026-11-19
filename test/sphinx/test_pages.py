"""Tests of the pages of type=sphinxdocs: `@page` names the page of a file, the directories make the submenus.

The schemas are in `proto_pages`. Runs protoc with the plugin of this repository, so it needs `protoc` on PATH
(skipped otherwise); the Sphinx build needs `sphinx` and `myst_parser` (skipped otherwise).
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import test_generate as base

PROTO_DIR = os.path.join(base.HERE, "proto_pages")
PROTOS = ["nopkg.proto", "overview.proto", "plain.proto", "sub/devices.proto", "sub/leaf.proto", "sub/tools.proto",
          "titled/a.proto", "titled/b.proto"]


@unittest.skipUnless(shutil.which(base.PROTOC), "protoc not available")
class PagesTest(unittest.TestCase):
    runs = {}  # options -> (files, standard error)

    def tmp(self):
        path = tempfile.mkdtemp(prefix="hikaripb_test_")
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        return path

    def run_protoc(self, options, out, proto_dir=PROTO_DIR, protos=PROTOS, cwd=None):
        command = [base.PROTOC, "--plugin=protoc-gen-hikaripb=" + base.PLUGIN, "--proto_path=" + proto_dir,
                   "--hikaripb_out=type=sphinxdocs%s:%s" % (options, out)]
        return subprocess.run(command + [os.path.join(proto_dir, name) for name in protos],
                              capture_output=True, text=True, encoding="utf-8", cwd=cwd)

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
                if name.endswith((".md", ".py")):
                    path = os.path.join(folder, name)
                    with open(path, encoding="utf-8") as f:
                        files[os.path.relpath(path, directory).replace(os.sep, "/")] = f.read()
        if out is None:
            self.runs[options] = files, result.stderr
        return files, result.stderr

    def schemas(self, **headers):
        """Run the generator on files with the given headers (name -> header comment), return the result."""
        folder = self.tmp()
        for name, header in headers.items():
            with open(os.path.join(folder, name + ".proto"), "w", encoding="utf-8") as f:
                f.write('/*\n%s\n*/\nsyntax = "proto3";\npackage %s;\nmessage M { uint32 v = 1; }\n' % (header, name))
        return self.run_protoc("", self.tmp(), proto_dir=folder, protos=[name + ".proto" for name in headers])

    def single(self, text):
        """Run the generator on the file one.proto with the text (and a message); (result, output directory)."""
        folder, out = self.tmp(), self.tmp()
        with open(os.path.join(folder, "one.proto"), "w", encoding="utf-8") as f:
            f.write(text + ("" if "message" in text else "\nmessage M { uint32 v = 1; }\n"))
        return self.run_protoc("", out, proto_dir=folder, protos=["one.proto"]), out

    @staticmethod
    def read(directory, name):
        with open(os.path.join(directory, name), encoding="utf-8") as f:
            return f.read()

    def test_the_title_replaces_the_path_in_the_navigation(self):
        files, _ = self.generate()
        self.assertEqual(files["index.md"], """# Protocol

- [nopkg.proto](nopkg.md) — A file without a package: its message has the name of a page.
- [Protocol Overview](overview.md) — The top page of the page test.
- [plain.proto](plain.md) — A file without a page: it is listed with its path.
- [Sub](sub/index.md)
  - [Devices](sub/devices.md) — The devices: the first titled file of a directory.
  - [Leaf Page](sub/leaf.md) — The leaf: the second titled file of a directory.
  - [Tools](sub/tools.md) — The tools: the last titled file of a directory.
- [Titled](titled/index.md)
  - [Alpha](titled/a.md) — The first titled file of a directory.
  - [Beta](titled/b.md) — The second titled file of a directory.

```{toctree}
:hidden:
:titlesonly:

nopkg.proto <nopkg>
Protocol Overview <overview>
plain.proto <plain>
Sub <sub/index>
Titled <titled/index>
```
""")

    def test_a_directory_is_a_submenu_that_lists_the_titles_of_its_files(self):
        files, _ = self.generate()
        self.assertIn("\n- [Alpha](a.md) — The first titled file of a directory.\n", files["titled/index.md"])
        self.assertIn("\n\nAlpha <a>\nBeta <b>\n```", files["titled/index.md"])
        self.assertTrue(files["sub/index.md"].startswith("# Sub\n\n- [Devices](devices.md) — The devices"))
        self.assertIn("\n\nDevices <devices>\nLeaf Page <leaf>\nTools <tools>\n```", files["sub/index.md"])

    def test_the_page_of_a_file_has_the_title_and_the_header(self):
        files, _ = self.generate()
        self.assertEqual(files["overview.md"], """(hikaripb.overview)=

# Protocol Overview

**File:** `overview.proto`

**Package:** `pages`

The top page of the page test.

The [Tools](#hikaripb.tools) page, the same with [a text](#hikaripb.tools) and the message [`devices`](#hikaripb.pages.devices), which is named like
a page.

```{toctree}
:hidden:
:titlesonly:

overview-protocol
```
""")

    def test_a_file_without_a_page_shows_its_path_as_title(self):
        files, _ = self.generate()
        self.assertEqual(files["plain.md"], "# plain.proto\n\n**Package:** `pages`\n\n"
                         "A file without a page: it is listed with its path.\n\n"
                         "```{toctree}\n:hidden:\n:titlesonly:\n\nplain-protocol\n```\n")

    def test_the_page_command_is_not_part_of_the_page(self):
        files, _ = self.generate()
        self.assertFalse([name for name in files if name.endswith("-overview.md")])
        for name, text in files.items():
            self.assertNotIn("@page", text, name)

    def test_ref_links_to_a_page_with_its_title(self):
        files, _ = self.generate()
        self.assertIn("Number of devices, see the [Tools](#hikaripb.tools) page.", files["overview-protocol.md"])
        self.assertIn("Another one, see [Alpha](#hikaripb.alpha).", files["plain-protocol.md"])

    def test_protobuf_scoping_comes_before_a_page(self):
        files, _ = self.generate()
        # `devices` is a message of the package pages and a page: the message is in scope in overview.proto ...
        self.assertIn("the message [`devices`](#hikaripb.pages.devices)", files["overview.md"])
        # ... the message `overview` of the root package is in scope everywhere, so it hides the page of that name ...
        self.assertIn("Identifier, see [`overview`](#hikaripb.overview-2).", files["plain-protocol.md"])
        # ... and in a file without a package the message of the package pages is not, so the page is found
        self.assertIn("Here [Devices](#hikaripb.devices) is the page", files["nopkg.md"])

    def test_labels_of_pages_are_not_shared_with_symbols(self):
        files, _ = self.generate()
        self.assertIn("(hikaripb.overview)=", files["overview.md"])
        self.assertIn("(hikaripb.overview-2)=", files["nopkg-protocol.md"])

    def test_prefix_names_the_labels_of_the_pages(self):
        files, _ = self.generate(",prefix=abc")
        self.assertIn("(abc.overview)=", files["overview.md"])
        self.assertIn("[Tools](#abc.tools)", files["overview.md"])
        self.assertNotIn("hikaripb.", files["overview.md"])

    def test_pages_work_in_a_chapter(self):
        files, _ = self.generate(",parent=chapter/protocol")
        self.assertIn("  - [Devices](sub/devices.md)", files["chapter/protocol/index.md"])
        self.assertIn("Sub <sub/index>", files["chapter/protocol/index.md"])
        self.assertIn("\n\nDevices <devices>\n", files["chapter/protocol/sub/index.md"])

    def test_the_title_of_the_index_page_is_not_a_page(self):
        files, _ = self.generate(",title=Test+pages")
        self.assertTrue(files["index.md"].startswith("# Test pages\n"))

    def test_a_code_span_that_names_a_symbol_is_a_link(self):
        result, out = self.single(
            '/*\n @page Inner The page\n The header names `Other.x`.\n*/\nsyntax = "proto3";\npackage one;\n'
            'message Other {\n  uint32 x = 1;\n  message Inner {}\n}\n'
            'message M {\n  // Like `Other.x` and `one.Other`, but `Inner`, `Other.nothing`, `v = 1` and `Item()` are code.\n'
            '  uint32 v = 1;\n}\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("cannot resolve", result.stderr)
        self.assertIn("The header names [`Other.x`](#hikaripb.one.Other.x).", self.read(out, "one.md"))
        # `Inner` is a page, which does not make plain code a link (`@ref Inner` would link to the page)
        self.assertIn("Like [`Other.x`](#hikaripb.one.Other.x) and [`one.Other`](#hikaripb.one.Other), "
                      "but `Inner`, `Other.nothing`, `v = 1` and `Item()` are code.", self.read(out, "one-protocol.md"))

    def test_a_name_needs_a_single_hit_to_be_a_link(self):
        folder, out = self.tmp(), self.tmp()
        for name, text in (("a", 'package pa;\nmessage Outer {\n  message Dup {}\n  uint32 only = 1;\n}\nmessage M {\n'
                                 '  // `Dup`, `Outer.Dup`, `only`, `Outer.only` and @ref Dup.\n  uint32 v = 1;\n}\n'),
                           ("b", 'package pb;\nmessage Dup {}\n')):
            with open(os.path.join(folder, name + ".proto"), "w", encoding="utf-8") as f:
                f.write('syntax = "proto3";\n' + text)
        result = self.run_protoc("", out, proto_dir=folder, protos=["a.proto", "b.proto"])
        self.assertEqual(result.returncode, 0, result.stderr)
        # `Dup` has two hits: plain code, while the `@ref` prefers the hit of its own file
        self.assertIn("`Dup`, [`Outer.Dup`](#hikaripb.pa.Outer.Dup), [`only`](#hikaripb.pa.Outer.only), "
                      "[`Outer.only`](#hikaripb.pa.Outer.only) and [`Dup`](#hikaripb.pa.Outer.Dup).",
                      self.read(out, "a-protocol.md"))

    def test_the_links_of_a_readme_do_not_change_the_order_of_the_menu(self):
        cwd, out = self.tmp(), self.tmp()
        os.makedirs(os.path.join(cwd, "sub"))
        with open(os.path.join(cwd, "sub", "readme.md"), "w", encoding="utf-8") as f:
            f.write("# Things\n\n- @ref tools: the last file.\n- @ref leaf: the second one.\n")
        result = self.run_protoc("", out, cwd=cwd)
        self.assertEqual(result.returncode, 0, result.stderr)
        index = self.read(out, "sub/index.md")
        # the readme is the navigation: the list of the files is not generated, the menu keeps the order of the files
        self.assertEqual(index, "# Things\n\n- [Tools](#hikaripb.tools): the last file.\n"
                                "- [Leaf Page](#hikaripb.leaf): the second one.\n\n"
                                "```{toctree}\n:hidden:\n:titlesonly:\n\nDevices <devices>\nLeaf Page <leaf>\n"
                                "Tools <tools>\n```\n")

    def test_a_page_without_a_title_is_named_by_its_id(self):
        result, out = self.single('/*\n @page first\n A page without a title.\n*/\nsyntax = "proto3";\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.read(out, "one.md").startswith("(hikaripb.first)=\n\n# first\n\n**File:** `one.proto`\n"))

    def test_two_files_cannot_define_the_same_page(self):
        result = self.schemas(one="@page same One\nFirst.", two="@page same Two\nSecond.")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("The page same is defined by one.proto and by two.proto", result.stderr)

    def test_page_belongs_in_the_header(self):
        result, out = self.single('/*\n @page one One\n Text.\n*/\nsyntax = "proto3";\n'
                                  'message M {\n  uint32 a = 1;  // Is @page two Two.\n}\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("unsupported Doxygen command @page", result.stderr)
        self.assertIn("Is @page two Two.", self.read(out, "one-protocol.md"))

    @unittest.skipUnless(base.HAVE_SPHINX, "sphinx and myst_parser not available")
    def test_sphinx_builds_the_pages_without_warnings(self):
        source = os.path.join(self.tmp(), "docs")
        os.makedirs(source)
        self.generate(out=source)
        html = self.tmp()
        command = [sys.executable, "-m", "sphinx", "-q", "-W", "--keep-going", "-b", "html", source, html]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for page in ("overview.html", "sub/index.html", "sub/devices.html", "sub/leaf.html", "titled/a.html"):
            self.assertTrue(os.path.exists(os.path.join(html, page)), page)
        with open(os.path.join(html, "overview.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertIn("<title>Protocol Overview", page)
        # the page of the file shows its header right away; the Protocol is the only page below it and only the
        # navigation links to it, no list in the text
        self.assertRegex(page, r'(?s)The top page of the page test.*href="overview-protocol\.html"')
        self.assertRegex(page, r'toctree-wrapper compound">\s*</div>')
        self.assertNotIn("Subpages", page)
        # a link to a page lands on the title of the page, with the title of the page as text
        with open(os.path.join(html, "plain-protocol.html"), encoding="utf-8") as f:
            self.assertIn('href="titled/a.html#hikaripb-alpha"', f.read())
        # the navigation: a directory is a submenu with the pages of its files
        with open(os.path.join(html, "sub", "devices.html"), encoding="utf-8") as f:
            navigation = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", f.read().split("Navigation", 1)[1]))
        self.assertRegex(navigation, r"Protocol Overview.*plain\.proto.*Sub.*Devices.*Protocol.*Leaf Page.*Tools.*Titled")


if __name__ == "__main__":
    unittest.main()
