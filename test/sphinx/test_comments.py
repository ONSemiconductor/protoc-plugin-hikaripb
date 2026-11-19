"""Unit tests of the conversion of .proto comments (Markdown + Doxygen commands) to MyST Markdown."""

import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "protoc"))

from sphinxdocs import comments  # noqa: E402

SYMBOLS = {"Item": "p.Item", "Item.kind": "p.Item.kind", "resOk": "p.resOk", "anchored": "p.anchored",
           "uart": "p.Config.uart"}
PAGES = {"uart": ("p.uart", "UART Driver"), "gpio": ("p.gpio", "GPIO [Driver]")}
FILES = {"a.md": "../x/a.md", "b.proto": "b.md"}


def convert(text, headings=2):
    ctx = comments.Context(resolve=lambda name: SYMBOLS.get(name.lstrip(".")) or PAGES.get(name),
                           symbol=lambda name: SYMBOLS.get(name.lstrip(".")), link=FILES.get,
                           anchor_label=lambda name: "p." + name, image=lambda path: "img/" + path, where="test")
    return comments.convert(text, ctx, headings)


class ReferenceTest(unittest.TestCase):
    def test_ref_becomes_a_link_to_the_label(self):
        self.assertEqual(convert("Use @ref Item.kind."), "Use [`Item.kind`](#p.Item.kind).")

    def test_ref_with_text(self):
        self.assertEqual(convert('See @ref Item "the item".'), "See [the item](#p.Item).")

    def test_backslash_form(self):
        self.assertEqual(convert("See \\ref Item"), "See [`Item`](#p.Item)")

    def test_separators_of_other_languages(self):
        self.assertEqual(convert("@ref Item::kind and @ref Item#kind"),
                         "[`Item.kind`](#p.Item.kind) and [`Item.kind`](#p.Item.kind)")

    def test_unresolved_ref_is_reported_and_kept_as_code(self):
        with self.assertLogs(level=logging.WARNING) as logs:
            self.assertEqual(convert("See @ref nothing here"), "See `nothing` here")
        self.assertIn("cannot resolve @ref nothing", logs.output[0])

    def test_code_spans_and_escapes_are_left_alone(self):
        self.assertEqual(convert("`@ref Item` and \\@ref Item"), "`@ref Item` and @ref Item")

    def test_leading_dot_is_not_shown(self):
        self.assertEqual(convert("@ref .Item"), "[`Item`](#p.Item)")


class CodeSpanReferenceTest(unittest.TestCase):
    def test_a_code_span_with_a_name_is_a_link(self):
        self.assertEqual(convert("Set `Item.kind` and `resOk`."),
                         "Set [`Item.kind`](#p.Item.kind) and [`resOk`](#p.resOk).")

    def test_the_text_stays_as_written(self):
        self.assertEqual(convert("The `.Item` and ``Item``."), "The [`.Item`](#p.Item) and [``Item``](#p.Item).")

    def test_unknown_names_stay_code_without_a_warning(self):
        with self.assertNoLogs(level=logging.WARNING):
            self.assertEqual(convert("Use `nothing` and `a.b`."), "Use `nothing` and `a.b`.")

    def test_a_name_of_a_page_or_an_anchor_stays_code(self):
        self.assertEqual(convert("The `gpio` page and `target`."), "The `gpio` page and `target`.")

    def test_what_is_more_than_a_name_stays_code(self):
        text = "`Item.kind = 1`, `Item()`, `Item.`, `1Item`, `@ref Item` and ` Item `"
        self.assertEqual(convert(text), text)

    def test_headings_are_not_linked(self):
        self.assertEqual(convert("# The `Item`\n\ntext `Item`"), "## The `Item`\n\ntext [`Item`](#p.Item)")

    def test_commands_and_tables_are_linked(self):
        self.assertEqual(convert("@note See `Item`."), "```{note}\nSee [`Item`](#p.Item).\n```")
        self.assertEqual(convert("| `Item` | b |"), "| [`Item`](#p.Item) | b |")

    def test_code_blocks_are_not_linked(self):
        text = "```text\n`Item`\n```"
        self.assertEqual(convert(text), text)
        self.assertEqual(convert("@code\n`Item`\n@endcode"), "```\n`Item`\n```")

    def test_no_link_inside_a_link_or_a_role(self):
        self.assertEqual(convert("[`Item`](x.html) and [the `Item`][x]"), "[`Item`](x.html) and [the `Item`][x]")
        self.assertEqual(convert("13:sub:`Item`"), "13{sub}`Item`")

    def test_a_context_without_a_symbol_hook_links_nothing(self):
        ctx = comments.Context(resolve=lambda name: SYMBOLS.get(name))
        self.assertEqual(comments.convert("`Item`", ctx), "`Item`")


class FileLinkTest(unittest.TestCase):
    def test_a_link_to_a_file_goes_to_its_page(self):
        self.assertEqual(convert("See [the page](a.md) and [b](b.proto)."),
                         "See [the page](../x/a.md) and [b](b.md).")

    def test_fragment_and_title_are_kept(self):
        self.assertEqual(convert('[x](a.md#sec "The title") and [y]( b.proto )'),
                         '[x](../x/a.md#sec "The title") and [y]( b.md )')

    def test_the_text_of_the_link_is_kept(self):
        # a code span in the text of a link is no link of its own
        self.assertEqual(convert("[the `Item` and *more*](a.md)"), "[the `Item` and *more*](../x/a.md)")

    def test_a_file_that_is_no_page_is_reported_and_kept(self):
        with self.assertLogs(level=logging.WARNING) as logs:
            self.assertEqual(convert("See [it](c.md)."), "See [it](c.md).")
        self.assertIn("cannot resolve the link to c.md", logs.output[0])

    def test_other_links_are_left_alone(self):
        text = "[a](https://example.com/c.md), [b](/c.md), [c](#c), [d](c.html) and [e](c.txt)"
        with self.assertNoLogs(level=logging.WARNING):
            self.assertEqual(convert(text), text)

    def test_code_is_left_alone(self):
        text = "`[a](a.md)`\n\n```text\n[a](a.md)\n```"
        self.assertEqual(convert(text), text)

    def test_images_are_no_links(self):
        self.assertEqual(convert("![](a.md)"), "![](img/a.md)")

    def test_a_context_without_a_hook_keeps_the_links(self):
        ctx = comments.Context()
        self.assertEqual(comments.convert("[a](a.md)", ctx), "[a](a.md)")


class PageTest(unittest.TestCase):
    def test_ref_to_a_page_shows_its_title(self):
        self.assertEqual(convert("See @ref gpio."), "See [GPIO \\[Driver\\]](#p.gpio).")

    def test_ref_to_a_page_with_text(self):
        self.assertEqual(convert('See @ref gpio "the pins".'), "See [the pins](#p.gpio).")

    def test_ref_to_a_symbol_is_not_affected_by_pages(self):
        self.assertEqual(convert("@ref uart and @ref Item.kind"),
                         "[`uart`](#p.Config.uart) and [`Item.kind`](#p.Item.kind)")

    def test_subpage_is_not_a_command(self):
        with self.assertLogs(level=logging.WARNING) as logs:
            self.assertEqual(convert("See @subpage uart"), "See @subpage uart")
        self.assertIn("unsupported Doxygen command @subpage", logs.output[0])

    def test_page_is_not_a_command_of_a_comment_that_is_converted(self):
        with self.assertLogs(level=logging.WARNING) as logs:
            self.assertEqual(convert("@page x Title"), "@page x Title")
        self.assertIn("unsupported Doxygen command @page", logs.output[0])


class SplitTitleTest(unittest.TestCase):
    def test_a_heading_of_level_one_at_the_start_is_the_title(self):
        self.assertEqual(comments.split_title("# Title\n\nText\n\n## Sub"), ("Title", "Text\n\n## Sub"))
        self.assertEqual(comments.split_title("\n\n# The *title* with `code` #\nText"),
                         ("The title with code", "Text"))

    def test_a_title_underlined_with_equal_signs(self):
        self.assertEqual(comments.split_title("Title\n=====\n\nText"), ("Title", "Text"))

    def test_nothing_else_is_a_title(self):
        for text in ("## Sub\n\nText", "Title\n-----\n\nText", "Text\n\n# Title", "Text", ""):
            with self.subTest(text=text):
                self.assertEqual(comments.split_title(text), ("", text))

    def test_a_title_alone_leaves_nothing(self):
        self.assertEqual(comments.split_title("# Title\n"), ("Title", ""))


class PageCommandTest(unittest.TestCase):
    def test_name_title_and_the_rest(self):
        self.assertEqual(comments.page_command("@page uart UART Driver\nSummary.\n\nMore."),
                         ("uart", "UART Driver", "Summary.\n\nMore."))

    def test_the_line_can_be_anywhere_and_with_a_backslash(self):
        self.assertEqual(comments.page_command("Summary.\n  \\page uart  UART Driver  \nMore."),
                         ("uart", "UART Driver", "Summary.\nMore."))

    def test_a_page_without_a_title(self):
        self.assertEqual(comments.page_command("@page uart\nSummary."), ("uart", "", "Summary."))

    def test_only_the_first_line_is_taken(self):
        self.assertEqual(comments.page_command("@page a A\n@page b B\nText"), ("a", "A", "@page b B\nText"))

    def test_the_blank_line_behind_the_command_goes_too(self):
        self.assertEqual(comments.page_command("@page a A\n\nText"), ("a", "A", "Text"))

    def test_no_command_no_change(self):
        self.assertEqual(comments.page_command("Text about @page a and @pages"), (None, "", "Text about @page a and @pages"))
        self.assertEqual(comments.page_command(""), (None, "", ""))


class BlockCommandTest(unittest.TestCase):
    def test_admonitions(self):
        for command, directive in (("note", "note"), ("warning", "warning"), ("hint", "hint"),
                                   ("attention", "attention"), ("important", "important"), ("sa", "seealso")):
            with self.subTest(command=command):
                self.assertEqual(convert("@%s Text of it." % command), "```{%s}\nText of it.\n```" % directive)

    def test_generic_admonitions_have_a_title(self):
        self.assertEqual(convert("@todo Write it."), "```{admonition} To do\nWrite it.\n```")

    def test_admonition_ends_at_the_blank_line(self):
        self.assertEqual(convert("@note first\nsecond\n\nplain"), "```{note}\nfirst\nsecond\n```\n\nplain")

    def test_command_in_the_middle_of_a_paragraph(self):
        self.assertEqual(convert("Before.\n@warning Danger.\n@note Remark."),
                         "Before.\n\n```{warning}\nDanger.\n```\n\n```{note}\nRemark.\n```")

    def test_inline_commands_work_inside_admonitions(self):
        self.assertEqual(convert("@note Uses @ref Item and @c code."),
                         "```{note}\nUses [`Item`](#p.Item) and `code`.\n```")

    def test_brief_and_details_are_plain_text(self):
        self.assertEqual(convert("@brief Short.\n\n@details Long."), "Short.\n\nLong.")

    def test_labelled_paragraphs(self):
        self.assertEqual(convert("@since 1.2\n@return The value."), "**Since:** 1.2\n\n**Returns:** The value.")
        self.assertEqual(convert("@param[in] size The size."), "**Parameter `size`:** The size.")

    def test_par_gives_a_bold_title(self):
        self.assertEqual(convert("@par Remark\nBody."), "**Remark**\n\nBody.")

    def test_structural_commands_are_dropped(self):
        self.assertEqual(convert("@ingroup protocol\nText."), "Text.")

    def test_hidden_sections(self):
        self.assertEqual(convert("Visible\n\n@cond\nHidden\n@endcond\n\nVisible too"), "Visible\n\nVisible too")
        self.assertEqual(convert("A\n\n@internal\nSecret\n@endinternal"), "A")

    def test_unknown_command_is_reported_and_kept(self):
        with self.assertLogs(level=logging.WARNING) as logs:
            self.assertEqual(convert("Text with @foo inside."), "Text with @foo inside.")
        self.assertIn("unsupported Doxygen command @foo", logs.output[0])

    def test_digits_after_the_at_sign_are_no_command(self):
        with self.assertNoLogs(level=logging.WARNING):
            self.assertEqual(convert("at @23us and user@host"), "at @23us and user@host")


class InlineCommandTest(unittest.TestCase):
    def test_font_commands(self):
        self.assertEqual(convert("@c code, @p param, @b bold, @e em and @a arg."),
                         "`code`, `param`, **bold**, *em* and *arg*.")

    def test_trailing_punctuation_stays_outside(self):
        self.assertEqual(convert("(@b bold)."), "(**bold**).")

    def test_single_letter_commands_with_a_backslash_are_text(self):
        self.assertEqual(convert("the escape \\n in text and \\b"), "the escape \\n in text and \\b")

    def test_html(self):
        self.assertEqual(convert("H<sub>2</sub>O, x<sup>2</sup>, <b>bold</b>, <tt>code</tt>"),
                         "H{sub}`2`O, x{sup}`2`, **bold**, `code`")

    def test_restructured_text_roles(self):
        self.assertEqual(convert("13:sub:`H`"), "13{sub}`H`")

    def test_line_break(self):
        self.assertEqual(convert("one @n two"), "one \\\n two")

    def test_list_items(self):
        self.assertEqual(convert("@li first\n@li second"), "- first\n- second")


class MathTest(unittest.TestCase):
    def test_inline_math(self):
        self.assertEqual(convert("$t_B$ = 1 / $f$ and @f$x^2@f$"), "{math}`t_B` = 1 / {math}`f` and {math}`x^2`")

    def test_prices_are_no_math(self):
        # escaped, so that dollarmath of the project does not turn them into math either
        self.assertEqual(convert("costs $5 and $10"), "costs \\$5 and \\$10")
        self.assertEqual(convert("`$5` and \\$10"), "`$5` and \\$10")

    def test_display_math(self):
        self.assertEqual(convert("$$ a + b $$"), "```{math}\na + b\n```")
        self.assertEqual(convert("@f[\n x = 1\n@f]"), "```{math}\nx = 1\n```")
        self.assertEqual(convert("inline $$a$$ here"), "inline {math}`a` here")

    def test_math_is_not_scanned_for_commands(self):
        self.assertEqual(convert("$\\ref Item$"), "{math}`\\ref Item`")


class CodeTest(unittest.TestCase):
    def test_code_block(self):
        self.assertEqual(convert("@code{.cpp}\nint x;\n\nint y;\n@endcode"), "```cpp\nint x;\n\nint y;\n```")

    def test_verbatim(self):
        self.assertEqual(convert("@verbatim\n@ref Item\n@endverbatim"), "```text\n@ref Item\n```")

    def test_fence_is_longer_than_the_backticks_inside(self):
        self.assertEqual(convert("@code\n```\n@endcode"), "````\n```\n````")

    def test_markdown_fences_are_copied(self):
        text = "```c\n@ref Item\n\nint x;\n```"
        self.assertEqual(convert(text), text)

    def test_html_only(self):
        self.assertEqual(convert("@htmlonly\n<b>x</b>\n@endhtmlonly"), "```{raw} html\n<b>x</b>\n```")


class HeadingTest(unittest.TestCase):
    TEXT = "Intro\n\nTitle\n=====\n\ntext\n\nSub\n---\n\n### Third"

    def test_headings_are_moved_below_the_given_level(self):
        self.assertEqual(convert(self.TEXT, headings=2), "Intro\n\n## Title\n\ntext\n\n### Sub\n\n#### Third")
        self.assertEqual(convert(self.TEXT, headings=4), "Intro\n\n#### Title\n\ntext\n\n##### Sub\n\n###### Third")

    def test_levels_are_consecutive(self):
        self.assertEqual(convert("# A\n\n#### B", headings=2), "## A\n\n### B")

    def test_headings_become_bold_text_inside_lists(self):
        self.assertEqual(convert("Title\n=====\n\ntext", headings=None), "**Title**\n\ntext")

    def test_sections_with_an_id_get_a_label(self):
        self.assertEqual(convert("@section anchored The @b title\ntext"), "(p.anchored)=\n\n## The **title**\n\ntext")

    def test_anchor(self):
        self.assertEqual(convert("@anchor target\nText"), "(p.target)=\n\nText")

    def test_ids_of_anchors_are_found(self):
        self.assertEqual(comments.anchor_ids("@anchor a\n@section b Title\n\\subsection c Title"), ["a", "b", "c"])


class FirstHeadingTest(unittest.TestCase):
    def test_the_title_of_a_heading_is_plain_text(self):
        self.assertEqual(comments.first_heading("# The *title* with `code`, [a link](x.md) and <b>tags</b>\n\ntext"),
                         "The title with code, a link and tags")

    def test_an_underlined_heading(self):
        self.assertEqual(comments.first_heading("Some text.\n\nTitle of\ntwo lines\n=====\n\ntext"),
                         "Title of two lines")

    def test_code_is_skipped(self):
        self.assertEqual(comments.first_heading("```\n# no heading\n```\n\n## Real"), "Real")

    def test_the_first_heading_wins_whatever_its_level(self):
        self.assertEqual(comments.first_heading("Text\n\n## First\n\n# Second"), "First")

    def test_a_text_without_a_heading(self):
        self.assertEqual(comments.first_heading("Just text.\n\n- a list\n\nAnd more."), "")
        self.assertEqual(comments.first_heading(""), "")


class ImageTest(unittest.TestCase):
    def test_path_of_markdown_images(self):
        self.assertEqual(convert("![](fig/a.png)"), "![](img/fig/a.png)")
        self.assertEqual(convert("Text ![alt](fig/a.png) text"), "Text ![alt](img/fig/a.png) text")

    def test_image_with_alt_text_on_its_own_is_a_figure(self):
        self.assertEqual(convert("![The caption](a.png)"), "```{figure} img/a.png\n:alt: The caption\n\nThe caption\n```")

    def test_doxygen_image(self):
        self.assertEqual(convert('@image html a.png "The caption" width=50%'),
                         "```{figure} img/a.png\n:alt: The caption\n:width: 50%\n\nThe caption\n```")
        self.assertEqual(convert("@image html a.png"), "```{image} img/a.png\n```")

    def test_other_formats_of_doxygen_images_are_ignored(self):
        self.assertEqual(convert("@image latex a.eps\n@image html a.png"), "```{image} img/a.png\n```")


class CleanTest(unittest.TestCase):
    def test_indentation_and_blank_lines_are_removed(self):
        self.assertEqual(comments.clean("\n  first\n    second\n\n"), "first\n  second")

    def test_doc_comments(self):
        self.assertEqual(comments.clean("* Text"), "Text")

    def test_tabs_and_windows_line_endings(self):
        self.assertEqual(comments.clean(" a\r\n\tb\r\n"), "a\n   b")


if __name__ == "__main__":
    unittest.main()
