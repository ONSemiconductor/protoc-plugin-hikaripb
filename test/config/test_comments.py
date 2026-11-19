"""Tests of the comments of the generated C and C++ code.

`doc_comment` (protoc/common.py) renders the comment of a `.proto` item as one Doxygen comment, one line for each
paragraph, list item and Doxygen command like `@note`, and clang-format wraps the long lines. The c backend documents
its functions with the comments of the fields.

The unit tests need nothing but Python; the runs of the plugin need `protoc` on PATH (skipped otherwise), a few
tests need `clang-format`.
"""

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "protoc"))

import common  # noqa: E402

doc = common.doc_comment

PROTOC = os.environ.get("PROTOC", "protoc")
# protoc cannot start a Python script as a plugin on Windows
PLUGIN = os.environ.get("HIKARIPB_PLUGIN") or os.path.join(
    ROOT, "protoc", "protoc-gen-hikaripb.bat" if os.name == "nt" else "hikaripb.py")

PROTO = """syntax = "proto3";
package demo.docs;

/*
 * A thing that has a note.
 * The second line of the paragraph.
 *
 * @note Remember this.
 */
message Thing {
   // The identifier of the thing.
   uint32 id = 1;

   /*
    * The label of the thing.
    * @warning Keep it short.
    */
   optional string label = 2;

   // The parts of the thing.
   repeated uint32 parts = 3;

   // The kind of the thing.
   Kind kind = 4;

   // The first part.
   Part part = 5;

   oneof choice {
      uint32 number = 6;  // A number.
      string text = 7;    // A text.
   }
}

message Part {
   uint32 value = 1;  // The value of the part.
}

// The kinds of things.
enum Kind {
   // Nothing at all.
   kindNone = 0;

   /*
    * Something that comes
    * in pieces:
    * - the first piece
    * - the second piece
    */
   kindSome = 1;
}
"""


class DocCommentTest(unittest.TestCase):
    def test_a_text_of_one_line_is_a_comment_of_one_line(self):
        self.assertEqual(doc("The sequence number."), "/** The sequence number. */")

    def test_a_text_without_content_gives_no_comment(self):
        for text in ("", "  ", "\n \n"):
            with self.subTest(text=text):
                self.assertEqual(doc(text), "")

    def test_the_lines_of_a_paragraph_are_one_line(self):
        self.assertEqual(doc("First line,\n second   line\n\tthird line."), "/** First line, second line third line. */")

    def test_a_blank_line_separates_paragraphs(self):
        self.assertEqual(doc("One\n two\n\n\n Three"), "/**\n * One two\n *\n * Three\n */")

    def test_a_doxygen_command_starts_a_line(self):
        self.assertEqual(doc("The text.\n @note The note\n goes on.\n @warning Careful."),
                         "/**\n * The text.\n * @note The note goes on.\n * @warning Careful.\n */")

    def test_every_paragraph_command_starts_a_line(self):
        for command in ("note", "remark", "warning", "attention", "important", "hint", "tip", "caution", "danger",
                        "error", "see", "sa", "todo", "bug", "deprecated", "pre", "post", "invariant", "brief",
                        "details", "par", "since", "version", "author", "date", "copyright", "return", "retval",
                        "param", "li"):
            for prefix in ("@", "\\"):
                with self.subTest(command=prefix + command):
                    self.assertEqual(doc(f"Text {prefix}{command} more."), f"/**\n * Text\n * {prefix}{command} more.\n */")

    def test_a_command_in_the_middle_of_a_line_starts_a_line(self):
        self.assertEqual(doc("Text. @note A note."), "/**\n * Text.\n * @note A note.\n */")

    def test_a_reference_stays_in_the_text(self):
        self.assertEqual(doc("The @ref seq field,\n @c code and @p param."), "/** The @ref seq field, @c code and @p param. */")

    def test_text_that_only_looks_like_a_command_stays(self):
        for text in ("at @23us --> now", "mail me@note.com", "a \\@note is escaped", "an @notebook", "@refer to"):
            with self.subTest(text=text):
                self.assertEqual(doc(text), f"/** {text} */")

    def test_a_command_may_be_the_first_line(self):
        self.assertEqual(doc("@brief Short.\n\n@details Long."), "/**\n * @brief Short.\n *\n * @details Long.\n */")

    def test_a_list_item_is_a_line(self):
        self.assertEqual(doc("The items:\n - first\n   item\n - second\n + third\n 1. fourth\n 2) fifth"),
                         "/**\n * The items:\n * - first item\n * - second\n * + third\n * 1. fourth\n * 2) fifth\n */")

    def test_a_star_is_a_dash_in_a_list(self):
        self.assertEqual(doc("* one\n * two"), "/**\n * - one\n * - two\n */")

    def test_a_paragraph_after_a_list_is_separated_by_a_blank_line(self):
        self.assertEqual(doc("Items:\n - one\n   more\n Done.\n @note Note."),
                         "/**\n * Items:\n * - one more\n *\n * Done.\n * @note Note.\n */")

    def test_the_text_of_a_list_item_may_be_indented_like_the_item(self):
        self.assertEqual(doc("- first\n  item\n- second"), "/**\n * - first item\n * - second\n */")

    def test_a_dash_without_blank_is_not_a_list_item(self):
        self.assertEqual(doc("a -1 value\n -2 more"), "/** a -1 value -2 more */")

    def test_code_stays_as_it_is(self):
        self.assertEqual(doc("Example:\n```c\n  int  x;\n    y();\n```\nDone."),
                         "/**\n * Example:\n * ```c\n *   int  x;\n *     y();\n * ```\n * Done.\n */")
        self.assertEqual(doc("A.\n @code\n   one\n    two\n @endcode\n B.\n @verbatim\n x  y\n @endverbatim"),
                         "/**\n * A.\n * @code\n *   one\n *    two\n * @endcode\n * B.\n * @verbatim\n * x  y\n * @endverbatim\n */")

    def test_a_blank_line_in_code_stays(self):
        self.assertEqual(doc("```\na\n\nb\n```"), "/**\n * ```\n * a\n *\n * b\n * ```\n */")

    def test_the_comment_cannot_end_early(self):
        self.assertEqual(doc("ends */ here and /* starts"), "/** ends * / here and / * starts */")

    def test_a_tab_is_a_blank(self):
        self.assertEqual(doc("a\tb"), "/** a b */")


@unittest.skipUnless(shutil.which("clang-format"), "clang-format not available")
class FormatterTest(unittest.TestCase):
    """What clang-format makes of the comments (the exact wrapping differs between its versions)."""

    LIMIT = 40
    STYLE = "{BasedOnStyle: Google, TabWidth: 4, IndentWidth: 4, ColumnLimit: %d, AllowShortEnumsOnASingleLine: false}" % LIMIT
    WORDS = "One two three four five six seven eight nine ten eleven twelve."

    def comment(self, code, next_line):
        """The lines of the comment that the formatter leaves above the line `next_line` of the code."""
        lines = common.Environment(clang_format=self.STYLE).format_code(code).splitlines()
        end = lines.index(next_line)
        start = end
        while not lines[start - 1].endswith("{"):
            start -= 1
        return lines[start:end]

    def check_wrapped(self, lines):
        self.assertGreater(len(lines), 1)
        self.assertTrue(lines[0].lstrip().startswith("/**"), lines)
        self.assertTrue(all(line.lstrip().startswith("* ") for line in lines[1:]), lines)
        self.assertTrue(lines[-1].endswith("*/"), lines)
        self.assertLessEqual(max(len(line) for line in lines), self.LIMIT, lines)
        words = " ".join(line.strip().removeprefix("/**").removeprefix("*").removesuffix("*/") for line in lines).split()
        self.assertEqual(words, self.WORDS.split())

    def test_a_long_line_is_wrapped_with_stars(self):
        code = "struct a {\n" + doc(self.WORDS) + "\n    int b;\n};\n"
        self.check_wrapped(self.comment(code, "    int b;"))

    def test_the_comment_of_an_enumerator_is_wrapped_with_stars_as_well(self):
        code = "enum e {\n" + doc(self.WORDS) + "\n    a = 0,\n    b = 1\n};\n"
        self.check_wrapped(self.comment(code, "    a = 0,"))

    def test_a_command_stays_on_its_own_line_and_a_paragraph_after_a_list_is_apart(self):
        code = ("struct a {\n"
                + doc("One two three.\n@note Four five six seven eight nine ten.\n- item one two three four five six seven\n"
                      "Last words after the list.") + "\n    int b;\n};\n")
        lines = [line.strip() for line in self.comment(code, "    int b;")]
        self.assertEqual(lines[:2], ["/**", "* One two three."])
        self.assertTrue(lines[2].startswith("* @note Four five"), lines)
        item = next(i for i, line in enumerate(lines) if line.startswith("* - item"))
        self.assertEqual(lines[item - 1].split()[-1], "ten.")
        self.assertEqual(lines[-3:], ["*", "* Last words after the list.", "*/"], lines)

    def test_a_style_that_clang_format_does_not_know_leaves_the_code_as_it_is(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            environment = common.Environment(clang_format="{BasedOnStyle: Google, NoSuchOption: 1}")
            self.assertEqual(stderr.getvalue(), "", "the style is tried when there is code to format")
            self.assertEqual(environment.format_code("int   a;"), "int   a;")
            self.assertEqual(environment.format_code("int   b;"), "int   b;")
        self.assertEqual(environment.clang_format, "")
        self.assertEqual(stderr.getvalue().count("not formatted"), 1, stderr.getvalue())
        self.assertIn("NoSuchOption", stderr.getvalue())


class EnvironmentTest(unittest.TestCase):
    """The formatting of the code is optional."""

    def test_no_style_is_no_formatting(self):
        stderr = io.StringIO()
        with mock.patch.object(common.subprocess, "run") as run, mock.patch.object(common.subprocess, "Popen") as popen, \
                contextlib.redirect_stderr(stderr):
            environment = common.Environment()
            self.assertEqual(environment.format_code("int   a;"), "int   a;")
        run.assert_not_called()
        popen.assert_not_called()
        self.assertEqual(stderr.getvalue(), "")

    def test_without_clang_format_the_code_is_not_formatted(self):
        stderr = io.StringIO()
        with mock.patch.object(common.subprocess, "run", side_effect=FileNotFoundError("clang-format")), \
                contextlib.redirect_stderr(stderr):
            environment = common.Environment(clang_format="{BasedOnStyle: Google}")
            self.assertEqual(environment.format_code("int   a;"), "int   a;")
        self.assertEqual(stderr.getvalue(), "")

    def test_a_backend_that_needs_no_formatter_does_not_start_it(self):
        with mock.patch.object(common.subprocess, "run") as run, mock.patch.object(common.subprocess, "Popen") as popen:
            common.Environment(clang_format="{BasedOnStyle: Google}")
        run.assert_not_called()
        popen.assert_not_called()


def comment_before(content, declaration):
    """The lines of the comment right in front of the line with the declaration, without indentation ([] if none)."""
    lines = [line.strip() for line in content.splitlines()]
    index = next(i for i, line in enumerate(lines) if declaration in line)
    end = index - 1
    if not lines[end].endswith("*/"):
        return []
    start = end
    while not lines[start].startswith("/**"):
        start -= 1
    return lines[start:end + 1]


@unittest.skipUnless(shutil.which(PROTOC), "protoc not available")
class GeneratedCodeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="hikaripb_test_")
        cls.addClassCleanup(shutil.rmtree, cls.dir, ignore_errors=True)
        proto = os.path.join(cls.dir, "docs.proto")
        with open(proto, "w", encoding="utf-8", newline="\n") as f:
            f.write(PROTO)
        cls.files = {}
        for backend in ("c", "cpp"):
            out = os.path.join(cls.dir, backend)
            os.makedirs(out)
            command = [PROTOC, "--experimental_allow_proto3_optional", "--plugin=protoc-gen-hikaripb=" + PLUGIN,
                       "--proto_path=" + cls.dir, f"--hikaripb_out=type={backend}:{out}", proto]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            assert result.returncode == 0, result.stderr
            with open(os.path.join(out, "hikaripb_docs.pb.h" if backend == "c" else "docs.pb.h"), encoding="utf-8") as f:
                cls.files[backend] = f.read()

    def c(self, declaration):
        return comment_before(self.files["c"], declaration)

    def cpp(self, declaration):
        return comment_before(self.files["cpp"], declaration)

    def test_the_comment_of_a_message_has_a_line_for_the_note(self):
        expected = ["/**", "* A thing that has a note. The second line of the paragraph.", "*", "* @note Remember this.", "*/"]
        self.assertEqual(self.c("typedef struct demo_docs_Thing {"), expected)
        self.assertEqual(self.cpp("struct Thing : public"), expected)

    def test_the_comment_of_a_field_is_one_line(self):
        self.assertEqual(self.c("demo_docs_Thing_id_ctype id;"), ["/** The identifier of the thing. */"])
        self.assertEqual(self.cpp("demo_docs_Thing_id_ctype id;"), ["/** The identifier of the thing. */"])

    def test_the_comment_of_an_enum_and_its_values(self):
        for files, declaration in ((self.c, "typedef enum demo_docs_Kind {"), (self.cpp, "enum Kind : ")):
            with self.subTest(declaration=declaration):
                self.assertEqual(files(declaration), ["/** The kinds of things. */"])
        self.assertEqual(self.c("demo_docs_Kind_kindNone = 0"), ["/** Nothing at all. */"])
        expected = ["/**", "* Something that comes in pieces:", "* - the first piece", "* - the second piece", "*/"]
        self.assertEqual(self.c("demo_docs_Kind_kindSome = 1"), expected)
        self.assertEqual(self.cpp("kindSome = 1"), expected)

    def test_c_documents_the_setter_of_a_field(self):
        self.assertEqual(self.c("static inline void demo_docs_Thing_set_id("), ["/** The identifier of the thing. */"])
        self.assertEqual(self.c("static inline void demo_docs_Thing_set_kind("), ["/** The kind of the thing. */"])
        self.assertEqual(self.c("static inline void demo_docs_Thing_set_number("), ["/** A number. */"])

    def test_c_documents_the_adder_of_a_field(self):
        label = ["/**", "* The label of the thing.", "* @warning Keep it short.", "*/"]
        self.assertEqual(self.c("demo_docs_Thing_add_part("), ["/** The first part. */"])
        self.assertEqual(self.c("demo_docs_Thing_add_parts("), ["/** The parts of the thing. */"])
        self.assertEqual(self.c("demo_docs_Thing_add_label("), label)
        self.assertEqual(self.c("demo_docs_Thing_add_text("), ["/** A text. */"])

    def test_c_documents_the_functions_of_a_bytes_field_and_of_a_repeated_field(self):
        self.assertEqual(self.c("static inline void demo_docs_Thing_label_addBytes("), ["/** Append bytes to the label field */"])
        self.assertEqual(self.c("static inline void demo_docs_Thing_label_done("), ["/** Finish and clean up the label field */"])
        self.assertEqual(self.c("static inline void demo_docs_Thing_parts_add("), ["/** Add an element to the repeated parts field */"])
        self.assertEqual(self.c("static inline void demo_docs_Thing_parts_done("),
                         ["/** Finish and clean up the repeated parts field */"])

    def test_c_documents_the_functions_of_a_message(self):
        self.assertEqual(self.c("static inline void demo_docs_Thing_destroy_submessage("),
                         ["/** Finish and clean up the demo_docs_Thing submessage */"])
        self.assertEqual(self.c("demo_docs_Thing_create("), ["/** Start writing a new top-level message of type demo_docs_Thing */"])
        self.assertEqual(self.c("demo_docs_Thing_submessage("),
                         ["/** Start writing a submessage of type demo_docs_Thing as the field with the given tag of the parent message */"])
        self.assertEqual(self.c("static inline pb_bool demo_docs_Thing_has_label("), ["/** Check if the field label is set */"])
        self.assertEqual(self.c("static inline pb_bool demo_docs_Thing_has_number("),
                         ["/** Check if the oneof choice holds the member number */"])
        self.assertEqual(self.c("static inline pb_bool demo_docs_Thing_has_choice("),
                         ["/** Check if any member of the oneof choice is set */"])
        self.assertEqual(self.c("static inline const char* demo_docs_Kind_to_string("),
                         ["/** Get the name of a value of the enum demo_docs_Kind, for printing */"])

    def test_the_macros_of_a_message_have_its_comment(self):
        thing = ["/**", "* A thing that has a note. The second line of the paragraph.", "*", "* @note Remember this.", "*/"]
        self.assertEqual(self.c("#define demo_docs_Thing_Wr("), thing)
        self.assertEqual(self.c("#define demo_docs_Thing_WrTop(VAR, CTX)"), thing)
        self.assertEqual(self.c("#define demo_docs_Thing_WrTop(VAR) "), thing)

    def test_the_macros_of_a_message_are_defined_once(self):
        header = self.files["c"]
        self.assertEqual(header.count("#define demo_docs_Thing_Wr("), 1)
        self.assertEqual(header.count("#define demo_docs_Thing_WrTop(VAR, CTX)"), 1)

    def test_cpp_documents_the_setters_and_adders_of_the_proxy(self):
        self.assertEqual(self.cpp("void set_id("), ["/** The identifier of the thing. */"])
        self.assertEqual(self.cpp("auto add_part("), ["/** The first part. */"])
        self.assertEqual(self.cpp("void set_number("), ["/** A number. */"])


if __name__ == "__main__":
    unittest.main()
