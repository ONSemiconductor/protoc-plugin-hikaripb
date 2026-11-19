"""Tests of the option `pages` of type=sphinxdocs: Markdown files and folders become pages before the .proto pages.

The files are in `pages_md`, the schemas in `proto`. protoc runs in `pages_md`, where the entries of the option are
looked up. Needs `protoc` on PATH (skipped otherwise); the Sphinx build needs `sphinx` and `myst_parser` (skipped
otherwise).
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import test_generate as base

FILES = os.path.join(base.HERE, "pages_md")
ALL = base.PAGES | {"conf.py", "index.md", "sub/index.md"}


@unittest.skipUnless(shutil.which(base.PROTOC), "protoc not available")
class PagesFromFilesTest(unittest.TestCase):
    runs = {}  # options -> (files, standard error)

    def tmp(self):
        path = tempfile.mkdtemp(prefix="hikaripb_test_")
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        return path

    def run_protoc(self, options, out, proto_dir=base.PROTO_DIR, protos=base.PROTOS, cwd=FILES):
        command = [base.PROTOC, "--experimental_allow_proto3_optional", "--plugin=protoc-gen-hikaripb=" + base.PLUGIN,
                   "--proto_path=" + proto_dir, "--hikaripb_out=type=sphinxdocs%s:%s" % (options, out)]
        return subprocess.run(command + [os.path.join(proto_dir, name) for name in protos],
                              capture_output=True, text=True, encoding="utf-8", cwd=cwd)

    @staticmethod
    def read(directory):
        """The generated files by name (with `/`)."""
        files = {}
        for folder, _, names in os.walk(directory):
            for name in names:
                if name.endswith((".md", ".py")):
                    path = os.path.join(folder, name)
                    with open(path, encoding="utf-8", newline="") as f:  # no translation of line endings
                        files[os.path.relpath(path, directory).replace(os.sep, "/")] = f.read()
        return files

    def generate(self, options, **kwargs):
        """The generated files and the standard error of the plugin; a run with the same options is done once."""
        if not kwargs and options in self.runs:
            return self.runs[options]
        out = self.tmp()
        result = self.run_protoc(options, out, **kwargs)
        self.assertEqual(result.returncode, 0, result.stderr)
        run = self.read(out), result.stderr
        if not kwargs:
            self.runs[options] = run
        return run

    def test_a_file_becomes_the_first_page(self):
        files, _ = self.generate(",pages=introduction=intro.md")
        self.assertEqual(set(files), ALL | {"introduction.md"})
        index = files["index.md"]
        self.assertTrue(index.startswith("# Protocol\n\n- [Introduction](introduction.md) — This page is made of a "
                                         "Markdown file.\n- [single/only.proto](single/only.md)"))
        self.assertIn("\n\nIntroduction <introduction>\nsingle/only.proto <single/only>\n", index)

    def test_the_name_defaults_to_the_name_of_the_file(self):
        files, _ = self.generate(",pages=intro.md")
        self.assertTrue(files["intro.md"].startswith("(hikaripb.intro)=\n\n# Introduction\n"))
        self.assertIn("- [Introduction](intro.md)", files["index.md"])

    def test_the_file_is_converted_like_a_comment(self):
        files, stderr = self.generate(",pages=introduction=intro.md")
        page = files["introduction.md"]
        # the first heading is the title, the others keep their levels; the label makes the page a target of @ref
        self.assertTrue(page.startswith("(hikaripb.introduction)=\n\n# Introduction\n\nThis page is made"))
        self.assertIn("\n## Operating principle\n", page)
        self.assertIn("\n## Details\n", page)
        self.assertIn("88B7{sub}`H`", page)
        self.assertIn("| Field | Value |\n| :---- | ----: |\n| A     |     1 |", page)
        self.assertIn("```{figure} figures/diagram.png\n:alt: The caption\n\nThe caption\n```", page)
        self.assertIn("An image in a paragraph ![](figures/diagram.png), a link to "
                      "[`docs.base.Item`](#hikaripb.docs.base.Item) and the code span `@ref nothing`.", page)
        self.assertIn("```text\n# This is no heading\n@ref nothing\n```", page)
        self.assertNotIn("intro.md", stderr)

    def test_unresolved_references_are_reported_with_the_file(self):
        folder = self.tmp()
        with open(os.path.join(folder, "wrong.md"), "w", encoding="utf-8") as f:
            f.write("# Wrong\n\nSee @ref nosuchsymbol.\n")
        out = self.tmp()
        result = self.run_protoc(",pages=wrong.md", out, cwd=folder)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("wrong.md: cannot resolve @ref nosuchsymbol", result.stderr.replace("\r", ""))
        self.assertIn("See `nosuchsymbol`.", self.read(out)["wrong.md"])

    def test_images_are_relative_to_the_file(self):
        options = ",pages=a=intro.md|g=notes/glossary.md,image_path=../assets"
        files, _ = self.generate(options)
        self.assertIn("![](../assets/figures/diagram.png)", files["a.md"])
        self.assertIn("{figure} ../assets/figures/diagram.png", files["a.md"])
        # a file in a directory refers to the images from there
        self.assertIn("![](../assets/figures/diagram.png)", files["g.md"])
        files, _ = self.generate(",parent=chapter" + options)
        self.assertIn("![](../../assets/figures/diagram.png)", files["chapter/a.md"])
        self.assertIn("![](../../assets/figures/diagram.png)", files["chapter/g.md"])

    def test_urls_and_absolute_images_are_not_changed(self):
        folder = self.tmp()
        with open(os.path.join(folder, "urls.md"), "w", encoding="utf-8") as f:
            f.write("# Urls\n\n![](https://example.com/a.png) and ![](/figures/b.png)\n")
        out = self.tmp()
        self.assertEqual(self.run_protoc(",pages=urls.md,image_path=../assets", out, cwd=folder).returncode, 0)
        self.assertIn("![](https://example.com/a.png) and ![](/figures/b.png)", self.read(out)["urls.md"])

    def test_a_title_underlined_with_equal_signs_is_the_title_too(self):
        files, _ = self.generate(",pages=g=notes/glossary.md,image_path=../assets")
        self.assertTrue(files["g.md"].startswith("(hikaripb.g)=\n\n# Glossary\n\nA page in a directory"))
        self.assertIn("- [Glossary](g.md) — A page in a directory of its own.", files["index.md"])

    def test_the_brief_is_the_first_sentence_of_the_first_text(self):
        folder = self.tmp()
        with open(os.path.join(folder, "brief.md"), "w", encoding="utf-8") as f:
            f.write("# Brief\n\n![](a.png)\n\n- a list\n\nThe text. More text.\n")
        out = self.tmp()
        self.assertEqual(self.run_protoc(",pages=brief.md", out, cwd=folder).returncode, 0)
        self.assertIn("\n- [Brief](brief.md) — The text.\n", self.read(out)["index.md"])

    def test_the_pages_keep_the_order_of_the_option(self):
        files, _ = self.generate(",pages=g=notes/glossary.md|i=intro.md")
        self.assertIn("\n- [Glossary](g.md) — A page in a directory of its own.\n- [Introduction](i.md) — This page",
                      files["index.md"])
        self.assertIn("\n\nGlossary <g>\nIntroduction <i>\nsingle/only.proto <single/only>\n", files["index.md"])

    def test_parent_holds_the_pages(self):
        files, _ = self.generate(",parent=chapter/protocol,pages=introduction=intro.md")
        self.assertIn("chapter/protocol/introduction.md", files)
        self.assertNotIn("introduction.md", files)
        index = files["chapter/protocol/index.md"]
        self.assertIn("\n- [Introduction](introduction.md) — ", index)
        self.assertIn("\n\nIntroduction <introduction>\n", index)

    def test_a_page_is_referenced_by_its_name(self):
        folder = self.tmp()
        with open(os.path.join(folder, "one.proto"), "w", encoding="utf-8") as f:
            f.write('/*\n * @page one One\n * See @ref introduction.\n */\nsyntax = "proto3";\npackage one;\n'
                    'message M { uint32 v = 1; }\n')
        out = self.tmp()
        result = self.run_protoc(",pages=introduction=intro.md", out, proto_dir=folder, protos=["one.proto"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("See [Introduction](#hikaripb.introduction).", self.read(out)["one.md"])

    def test_a_file_without_a_heading_is_titled_with_its_name(self):
        folder = self.tmp()
        with open(os.path.join(folder, "plain.md"), "w", encoding="utf-8") as f:
            f.write("Only a paragraph.\n")
        out = self.tmp()
        self.assertEqual(self.run_protoc(",pages=plain.md", out, cwd=folder).returncode, 0)
        self.assertEqual(self.read(out)["plain.md"], "(hikaripb.plain)=\n\n# plain\n\nOnly a paragraph.\n")

    def test_a_file_may_have_a_byte_order_mark_and_windows_line_endings(self):
        folder = self.tmp()
        with open(os.path.join(folder, "win.md"), "wb") as f:
            f.write("\ufeff# Title\r\n\r\nFirst line\r\nsecond line.\r\n".encode("utf-8"))
        out = self.tmp()
        self.assertEqual(self.run_protoc(",pages=win.md", out, cwd=folder).returncode, 0)
        self.assertEqual(self.read(out)["win.md"], "(hikaripb.win)=\n\n# Title\n\nFirst line\nsecond line.\n")

    def test_wrong_options_are_reported(self):
        for options, message in (
                (",pages=nothere.md", "Cannot read the page file nothere.md"),
                (",pages=/absolute/intro.md", "Invalid pages entry '/absolute/intro.md'"),
                (",pages=my-notes.md", "Invalid page name 'my-notes' of my-notes.md"),
                (",pages=a=intro.md|a=notes/glossary.md", "The page a is defined by intro.md and by notes/glossary.md"),
                (",pages=base=intro.md", "base.proto would overwrite base.md of intro.md"),
                (",pages", "pages needs a value")):
            with self.subTest(options=options):
                result = self.run_protoc(options, self.tmp())
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    def test_a_file_with_a_name_that_is_no_identifier_needs_a_name_in_the_option(self):
        files, _ = self.generate(",pages=notes=my-notes.md")
        self.assertTrue(files["notes.md"].startswith("(hikaripb.notes)=\n\n# Notes\n"))

    def folder(self, files, name="introduction"):
        """A directory with the folder `name` that holds the files (relative path -> text); the directory."""
        root = self.tmp()
        for relative, text in files.items():
            path = os.path.join(root, name, *relative.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        return root

    def test_a_folder_is_a_menu_named_after_it(self):
        files, _ = self.generate(",pages=guide")
        self.assertEqual(set(files), ALL | {"guide/" + name for name in (
            "index.md", "overview.md", "network.md", "references.md", "more/index.md", "more/a.md", "more/b.md")})
        # the menu comes first, its pages in the order of the names, numbers compared as numbers, without the numbers
        self.assertTrue(files["index.md"].startswith(
            "# Protocol\n\n- [Guide](guide/index.md)\n"
            "  - [Overview](guide/overview.md) — The first page.\n"
            "  - [Network](guide/network.md) — The second page.\n"
            "  - [More](guide/more/index.md)\n"
            "    - [Alpha](guide/more/a.md) — The first page of a folder in the folder.\n"
            "    - [Beta](guide/more/b.md) — The second page of a folder in the folder.\n"
            "  - [References](guide/references.md) — The last page: its number has two digits, so it comes after the "
            "others.\n- [single/only.proto](single/only.md)"))
        self.assertIn("\n\nGuide <guide/index>\nsingle/only.proto <single/only>\n", files["index.md"])
        self.assertTrue(files["guide/index.md"].startswith("# Guide\n\n- [Overview](overview.md) — The first page.\n"))
        self.assertIn("\n\nOverview <overview>\nNetwork <network>\nMore <more/index>\nReferences <references>\n```",
                      files["guide/index.md"])
        self.assertTrue(files["guide/more/index.md"].startswith("# More\n\n- [Alpha](a.md) — "))
        # the name of a page is its file without the number: the label and the target of @ref
        self.assertTrue(files["guide/network.md"].startswith("(hikaripb.network)=\n\n# Network\n"))
        self.assertTrue(files["guide/more/b.md"].startswith("(hikaripb.b)=\n\n# Beta\n"))

    def test_images_of_a_folder_are_relative_to_each_file(self):
        files, _ = self.generate(",pages=guide,image_path=../assets")
        self.assertIn("![](../../assets/figures/diagram.png)", files["guide/network.md"])
        self.assertIn("![](../../../assets/figures/diagram.png)", files["guide/more/b.md"])
        files, _ = self.generate(",parent=chapter,pages=guide,image_path=../assets")
        self.assertIn("![](../../../assets/figures/diagram.png)", files["chapter/guide/network.md"])
        self.assertIn("- [Guide](guide/index.md)\n  - [Overview](guide/overview.md)", files["chapter/index.md"])

    def test_folders_and_files_keep_the_order_of_the_option(self):
        files, _ = self.generate(",pages=intro=intro.md|guide")
        self.assertIn("\n\nIntroduction <intro>\nGuide <guide/index>\nsingle/only.proto <single/only>\n", files["index.md"])

    def test_a_folder_with_a_single_page_is_no_menu(self):
        root = self.folder({"01_only.md": "# Only\n\nThe only page.\n"})
        out = self.tmp()
        self.assertEqual(self.run_protoc(",pages=introduction", out, cwd=root).returncode, 0)
        files = self.read(out)
        self.assertIn("introduction/only.md", files)
        self.assertNotIn("introduction/index.md", files)
        self.assertTrue(files["index.md"].startswith("# Protocol\n\n- [Only](introduction/only.md) — The only page.\n"))

    def readmes(self, files, options=""):
        """The generated files of the schemas with the files (relative path -> text) next to them, where protoc runs."""
        out = self.tmp()
        result = self.run_protoc(options, out, cwd=self.folder(files, name=""))
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.read(out)

    def test_a_readme_navigates_with_links_to_files(self):
        files = self.readmes({"sub/readme.md": "# Things\n\n- [Extra](extra.proto): the second file.\n"
                                               "- [Dev](device.proto): the first.\n"})
        # the links go to the pages, and the menu keeps the order of the files
        self.assertEqual(files["sub/index.md"],
                         "# Things\n\n- [Extra](extra.md): the second file.\n- [Dev](device.md): the first.\n\n"
                         "```{toctree}\n:hidden:\n:titlesonly:\n\ndevice.proto <device>\nextra.proto <extra>\n```\n")

    def test_a_link_to_a_markdown_file_goes_to_its_page(self):
        root = self.folder({"readme.md": "# Home\n\nStart with [the first](01_a.md).\n",
                            "01_a.md": '# A\n\nSee [B](02_b.md#sec "The B"), [the start](readme.md) and '
                                       '[the schema](../sub/device.proto).\n',
                            "02_b.md": "# B\n"})
        out = self.tmp()
        result = self.run_protoc(",pages=introduction", out, cwd=root)
        self.assertEqual(result.returncode, 0, result.stderr)
        files = self.read(out)
        # a page is called like its file without the number, a readme is the page of its folder
        self.assertIn("Start with [the first](a.md).", files["introduction/index.md"])
        self.assertIn('See [B](b.md#sec "The B"), [the start](index.md) and [the schema](../sub/device.md).',
                      files["introduction/a.md"])
        self.assertNotIn("cannot resolve the link", result.stderr)

    def test_a_link_to_a_file_that_is_no_page_is_reported(self):
        root = self.tmp()
        with open(os.path.join(root, "wrong.md"), "w", encoding="utf-8") as f:
            f.write("# Wrong\n\nSee [it](nothing.md).\n")
        out = self.tmp()
        result = self.run_protoc(",pages=wrong.md", out, cwd=root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("wrong.md: cannot resolve the link to nothing.md", result.stderr.replace("\r", ""))
        self.assertIn("See [it](nothing.md).", self.read(out)["wrong.md"])

    def test_a_comment_links_to_the_page_of_a_proto_file(self):
        folder = self.tmp()
        for name, header in (("one", "@page one One\n * See [Two](two.proto)."), ("two", "Two.")):
            with open(os.path.join(folder, name + ".proto"), "w", encoding="utf-8") as f:
                f.write('/*\n * %s\n */\nsyntax = "proto3";\npackage %s;\nmessage M { uint32 v = 1; }\n' % (header, name))
        out = self.tmp()
        result = self.run_protoc("", out, proto_dir=folder, protos=["one.proto", "two.proto"], cwd=folder)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("See [Two](two.md).", self.read(out)["one.md"])

    def test_the_readme_of_a_directory_is_its_page(self):
        files = self.readmes({"sub/readme.md": "# Devices\n\nThe devices of the test. More text.\n\n"
                                               "See @ref docs.base.Item and `Item`.\n\n## A heading\n\n"
                                               "![](figures/d.png)\n\n- @ref docs.base.Item: the navigation by hand.\n"})
        # the heading of the readme heads the page; the lists and the menu name the directory after its path, they
        # show the first sentence; the readme takes the place of the list of the items, the menu of the theme has them
        self.assertEqual(files["sub/index.md"],
                         "# Devices\n\nThe devices of the test. More text.\n\n"
                         "See [`docs.base.Item`](#hikaripb.docs.base.Item) and [`Item`](#hikaripb.docs.base.Item).\n\n"
                         "## A heading\n\n![](figures/d.png)\n\n"
                         "- [`docs.base.Item`](#hikaripb.docs.base.Item): the navigation by hand.\n\n"
                         "```{toctree}\n:hidden:\n:titlesonly:\n\ndevice.proto <device>\nextra.proto <extra>\n```\n")
        self.assertIn("\n- [Sub](sub/index.md) — The devices of the test.\n", files["index.md"])
        self.assertIn("\nSub <sub/index>\n", files["index.md"])
        self.assertNotIn("readme", "".join(files))

    def test_the_headings_of_a_readme_are_bold_in_a_book(self):
        text = {"sub/readme.md": "# Devices\n\nText.\n\n## A heading\n\nMore text.\n"}
        self.assertIn("\n## A heading\n", self.readmes(text)["sub/index.md"])
        # the pages below the page would end up in the last section of it
        book = self.readmes(text, ",inline_protocol")["sub/index.md"]
        self.assertIn("\n**A heading**\n", book)
        self.assertNotIn("\n## A heading\n", book)

    def test_a_readme_without_a_title_keeps_the_name_of_the_directory(self):
        files = self.readmes({"sub/README.md": "Only a paragraph.\n"})
        self.assertTrue(files["sub/index.md"].startswith("# Sub\n\nOnly a paragraph.\n\n```{toctree}"))
        self.assertIn("\n- [Sub](sub/index.md) — Only a paragraph.\n", files["index.md"])

    def test_a_directory_with_a_readme_is_a_page_even_with_a_single_file(self):
        files = self.readmes({"single/readme.md": "# Single\n\nOne file.\n"})
        self.assertEqual(files["single/index.md"],
                         "# Single\n\nOne file.\n\n```{toctree}\n:hidden:\n:titlesonly:\n\nonly.proto <only>\n```\n")
        self.assertIn("\n- [Single](single/index.md) — One file.\n  - [only.proto](single/only.md)", files["index.md"])
        self.assertIn("\nSingle <single/index>\n", files["index.md"])

    def test_a_directory_without_a_readme_has_the_generated_list(self):
        files = self.readmes({"single/readme.md": "# Single\n\nOne file.\n"})
        self.assertTrue(files["sub/index.md"].startswith("# Sub\n\n- [device.proto](device.md) — "))

    def test_the_readme_of_a_folder_of_the_pages_is_the_page_of_the_menu(self):
        root = self.folder({"readme.md": "# Welcome\n\nThe start of it. More.\n", "01_a.md": "# A\n\nFirst.\n",
                            "02_b.md": "# B\n\nSecond.\n"})
        out = self.tmp()
        result = self.run_protoc(",pages=introduction", out, cwd=root)
        self.assertEqual(result.returncode, 0, result.stderr)
        files = self.read(out)
        self.assertEqual(files["introduction/index.md"],
                         "# Welcome\n\nThe start of it. More.\n\n```{toctree}\n:hidden:\n:titlesonly:\n\n"
                         "A <a>\nB <b>\n```\n")
        self.assertEqual({name for name in files if name.startswith("introduction/")},
                         {"introduction/index.md", "introduction/a.md", "introduction/b.md"})
        self.assertTrue(files["index.md"].startswith(
            "# Protocol\n\n- [Introduction](introduction/index.md) — The start of it.\n  - [A](introduction/a.md) — First.\n"))

    def test_the_readme_of_a_folder_of_the_pages_does_not_change_the_order_of_its_files(self):
        root = self.folder({
            "readme.md": "# Welcome\n\nSee [C](03_c.md).\n\n- [B](02_b.md): second.\n- [A](01_a.md): first.\n",
            "01_a.md": "# A\n\nFirst.\n", "02_b.md": "# B\n\nSecond.\n", "03_c.md": "# C\n\nThird.\n",
            "more/readme.md": "# More\n\n- [Y](02_y.md): second.\n- [X](01_x.md): first.\n",
            "more/01_x.md": "# X\n\nFirst.\n", "more/02_y.md": "# Y\n\nSecond.\n"})
        out = self.tmp()
        result = self.run_protoc(",pages=introduction", out, cwd=root)
        self.assertEqual(result.returncode, 0, result.stderr)
        files = self.read(out)
        # the names of the files give the order, the links of a readme only navigate
        self.assertIn("\n\nA <a>\nB <b>\nC <c>\nMore <more/index>\n```\n", files["introduction/index.md"])
        self.assertIn("\n\nX <x>\nY <y>\n```\n", files["introduction/more/index.md"])
        self.assertIn("- [B](b.md): second.\n- [A](a.md): first.\n", files["introduction/index.md"])

    def test_a_folder_with_a_readme_only_has_no_pages(self):
        result = self.run_protoc(",pages=introduction", self.tmp(), cwd=self.folder({"readme.md": "# Only\n"}))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("The folder introduction of the pages has no Markdown files", result.stderr)

    def test_the_readme_of_the_top_directory_and_other_files_are_not_used(self):
        files = self.readmes({"readme.md": "# Mine\n\nNot the documentation.\n", "sub/notes.md": "# Notes\n"})
        self.assertTrue(files["index.md"].startswith("# Protocol\n\n- [single/only.proto]"))
        self.assertTrue(files["sub/index.md"].startswith("# Sub\n\n- [device.proto]"))

    def test_the_home_page_can_be_a_page_of_the_pages(self):
        files, _ = self.generate(",pages=introduction=intro.md,home=introduction")
        self.assertNotIn("introduction.md", files)
        # it is the index page: the list is replaced by the text (the menu of the theme has the pages), the label stays
        self.assertTrue(files["index.md"].startswith("(hikaripb.introduction)=\n\n# Introduction\n\nThis page is made"))
        self.assertIn("\n## Operating principle\n", files["index.md"])
        self.assertTrue(files["index.md"].endswith(
            "```{toctree}\n:hidden:\n:titlesonly:\n\nsingle/only.proto <single/only>\nSub <sub/index>\n"
            "base.proto <base>\n```\n"))
        self.assertNotIn("\n- [", files["index.md"])

    def test_a_reference_to_the_home_page_still_works(self):
        folder = self.tmp()
        with open(os.path.join(folder, "one.proto"), "w", encoding="utf-8") as f:
            f.write('/*\n * @page one One\n * See @ref introduction.\n */\nsyntax = "proto3";\npackage one;\n'
                    'message M { uint32 v = 1; }\n')
        out = self.tmp()
        result = self.run_protoc(",pages=introduction=intro.md,home=introduction", out, proto_dir=folder,
                                 protos=["one.proto"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("See [Introduction](#hikaripb.introduction).", self.read(out)["one.md"])

    def test_the_home_page_can_be_the_file_of_a_readme_too(self):
        root = self.folder({"readme.md": "# Welcome\n\nThe start of it.\n", "01_a.md": "# A\n\nFirst.\n"})
        out = self.tmp()
        result = self.run_protoc(",pages=introduction,home=introduction/readme.md", out, cwd=root)
        self.assertEqual(result.returncode, 0, result.stderr)
        files = self.read(out)
        # the same text is the home page and the page of the menu, which is named after the folder
        self.assertEqual(files["index.md"], "# Welcome\n\nThe start of it.\n\n```{toctree}\n:hidden:\n:titlesonly:\n\n"
                                            "Introduction <introduction/index>\nsingle/only.proto <single/only>\n"
                                            "Sub <sub/index>\nbase.proto <base>\n```\n")
        self.assertEqual(files["introduction/index.md"],
                         "# Welcome\n\nThe start of it.\n\n```{toctree}\n:hidden:\n:titlesonly:\n\nA <a>\n```\n")

    def test_the_home_page_can_be_a_file(self):
        files, _ = self.generate(",home=intro.md")
        self.assertNotIn("intro.md", files)
        self.assertTrue(files["index.md"].startswith("# Introduction\n\nThis page is made"))
        self.assertNotIn("(hikaripb.", files["index.md"].split("\n")[0])
        self.assertIn("```{toctree}\n:hidden:\n:titlesonly:\n\nsingle/only.proto <single/only>\n", files["index.md"])

    def test_the_home_page_leaves_the_order_of_the_menu(self):
        root = self.tmp()
        with open(os.path.join(root, "home.md"), "w", encoding="utf-8") as f:
            f.write("Start with [base](base.proto).\n")
        out = self.tmp()
        self.assertEqual(self.run_protoc(",home=home.md", out, cwd=root).returncode, 0)
        index = self.read(out)["index.md"]
        self.assertIn("Start with [base](base.md).", index)
        self.assertIn("\nsingle/only.proto <single/only>\nSub <sub/index>\nbase.proto <base>\n", index)

    def test_the_home_page_can_be_a_file_of_another_directory_tree(self):
        root = self.tmp()
        for relative, text in {"site/home.md": "# Welcome\n\nStart with [the first](../docs/introduction/01_a.md).\n",
                               "docs/introduction/01_a.md": "# A\n\nBack to [the start](../../site/home.md).\n"}.items():
            path = os.path.join(root, *relative.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        out = self.tmp()
        result = self.run_protoc(",pages=introduction,home=../site/home.md", out, cwd=os.path.join(root, "docs"))
        self.assertEqual(result.returncode, 0, result.stderr)
        files = self.read(out)
        # the links are relative to the file, and the file is the home page for the links of the other pages
        self.assertTrue(files["index.md"].startswith("# Welcome\n\nStart with [the first](introduction/a.md).\n"))
        self.assertIn("Back to [the start](../index.md).", files["introduction/a.md"])
        self.assertNotIn("cannot resolve the link", result.stderr)

    def test_the_suffixes_of_code_hosting_sites_are_dropped_from_image_paths(self):
        files = self.readmes({"sub/readme.md": "![](figures/d.png#gh-dark-mode-only)\n\n"
                                               "![](figures/l.png#gh-light-mode-only)\n"})
        self.assertIn("![](figures/d.png)\n\n![](figures/l.png)\n", files["sub/index.md"])

    def test_a_home_page_without_a_title_has_the_title_of_the_documentation(self):
        root = self.tmp()
        with open(os.path.join(root, "home.md"), "w", encoding="utf-8") as f:
            f.write("Just text.\n")
        out = self.tmp()
        self.assertEqual(self.run_protoc(",home=home.md,title=My+docs", out, cwd=root).returncode, 0)
        self.assertTrue(self.read(out)["index.md"].startswith("# My docs\n\nJust text.\n\n```{toctree}"))

    def test_the_home_page_in_a_chapter(self):
        files, _ = self.generate(",parent=chapter,home=intro.md")
        self.assertTrue(files["chapter/index.md"].startswith("# Introduction\n\nThis page is made"))

    def test_wrong_home_pages_are_reported(self):
        for options, message in ((",home=nothing", "Invalid home 'nothing'"),
                                 (",home=guide", "Invalid home 'guide'"),
                                 (",home=/absolute/home.md", "Invalid home '/absolute/home.md'")):
            with self.subTest(options=options):
                result = self.run_protoc(options, self.tmp())
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    def test_the_page_of_a_proto_file_cannot_be_the_home_page(self):
        folder = self.tmp()
        with open(os.path.join(folder, "one.proto"), "w", encoding="utf-8") as f:
            f.write('/*\n * @page one One\n * Text.\n */\nsyntax = "proto3";\npackage one;\nmessage M { uint32 v = 1; }\n')
        result = self.run_protoc(",home=one", self.tmp(), proto_dir=folder, protos=["one.proto"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("The home page one is the page of", result.stderr)

    def test_images_of_a_readme_are_relative_to_the_file(self):
        files = self.readmes({"sub/readme.md": "![](figures/d.png)\n"}, ",image_path=../assets")
        self.assertIn("![](../../assets/sub/figures/d.png)", files["sub/index.md"])
        files = self.readmes({"sub/readme.md": "![](figures/d.png)\n"}, ",parent=chapter,image_path=../assets")
        self.assertIn("![](../../../assets/sub/figures/d.png)", files["chapter/sub/index.md"])

    def test_hidden_files_and_other_files_are_ignored(self):
        root = self.folder({"a.md": "# A\n", "b.MD": "# B\n", ".hidden.md": "# Hidden\n", "c.txt": "# C\n",
                            ".git/d.md": "# D\n"})
        out = self.tmp()
        self.assertEqual(self.run_protoc(",pages=introduction", out, cwd=root).returncode, 0)
        self.assertEqual({name for name in self.read(out) if name.startswith("introduction/")},
                         {"introduction/index.md", "introduction/a.md", "introduction/b.md"})

    def test_wrong_folders_are_reported(self):
        for options, files, message in (
                (",pages=introduction", {"notes.txt": ""}, "The folder introduction of the pages has no Markdown files"),
                (",pages=name=introduction", {"a.md": "# A\n"}, "a folder is named after itself"),
                (",pages=introduction", {"1_a.md": "# A\n", "2_a.md": "# B\n"},
                 "The page a is defined by introduction/1_a.md and by introduction/2_a.md"),
                (",pages=introduction", {"01_my-notes.md": "# A\n"},
                 "Invalid page name 'my-notes' of introduction/01_my-notes.md: rename the file")):
            with self.subTest(options=options, files=sorted(files)):
                result = self.run_protoc(options, self.tmp(), cwd=self.folder(files))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    @unittest.skipUnless(base.HAVE_SPHINX, "sphinx and myst_parser not available")
    def test_sphinx_builds_the_page_without_warnings(self):
        source = os.path.join(self.tmp(), "docs")
        os.makedirs(os.path.join(source, "figures"))
        with open(os.path.join(source, "figures", "diagram.png"), "wb") as f:
            f.write(base.PNG)
        result = self.run_protoc(",pages=introduction=intro.md", source)
        self.assertEqual(result.returncode, 0, result.stderr)
        html = self.tmp()
        build = subprocess.run([sys.executable, "-m", "sphinx", "-q", "-W", "--keep-going", "-b", "html", source, html],
                               capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
        self.assertTrue(os.path.exists(os.path.join(html, "_images", "diagram.png")))
        with open(os.path.join(html, "introduction.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertIn("Operating principle", page)
        self.assertIn('href="base-protocol.html#hikaripb-docs-base-item"', page)
        self.assertIn("<sub>H</sub>", page)
        # the page is the first item of the navigation
        with open(os.path.join(html, "index.html"), encoding="utf-8") as f:
            navigation = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", f.read().split("Navigation", 1)[1]))
        self.assertRegex(navigation, r"Introduction.*single/only\.proto.*Sub.*base\.proto")

    @unittest.skipUnless(base.HAVE_SPHINX, "sphinx and myst_parser not available")
    def test_sphinx_builds_the_menu_of_a_folder_without_warnings(self):
        source = os.path.join(self.tmp(), "docs")
        os.makedirs(os.path.join(source, "figures"))
        with open(os.path.join(source, "figures", "diagram.png"), "wb") as f:
            f.write(base.PNG)
        result = self.run_protoc(",pages=guide", source)
        self.assertEqual(result.returncode, 0, result.stderr)
        html = self.tmp()
        build = subprocess.run([sys.executable, "-m", "sphinx", "-q", "-W", "--keep-going", "-b", "html", source, html],
                               capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
        for page in ("guide/index.html", "guide/network.html", "guide/more/index.html", "guide/more/b.html"):
            self.assertTrue(os.path.exists(os.path.join(html, page)), page)
        self.assertTrue(os.path.exists(os.path.join(html, "_images", "diagram.png")))
        # the menu comes first, with its pages in the order of the names
        with open(os.path.join(html, "guide", "network.html"), encoding="utf-8") as f:
            navigation = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", f.read().split("Navigation", 1)[1]))
        self.assertRegex(navigation, r"Guide.*Overview.*Network.*More.*References.*single/only\.proto")


if __name__ == "__main__":
    unittest.main()
