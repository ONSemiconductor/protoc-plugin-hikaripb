# Copyright (c) 2025 Semiconductor Components Industries, LLC ("onsemi")
# SPDX-License-Identifier: GPL-3.0-or-later

"""Conversion of .proto comments (Markdown with Doxygen commands) to MyST Markdown for Sphinx.

`convert()` turns one comment into Markdown that Sphinx renders with nothing but the `myst_parser`
extension:

- Doxygen block commands (`@note`, `@warning`, `@code`, `@image`, `@par`, `@section`, ...) become
  admonitions, code blocks, figures, headings or labelled paragraphs; `@ref` becomes a link to the
  label of the referenced symbol. Every command can also be written with a backslash.
- Markdown headings are renumbered to fit below the heading the comment belongs to.
- Relative image paths are rewritten to be relative to the generated page.
- A code span that is nothing but the name of a symbol (`esb.net.fldConfig.vlanIds`) links to it like `@ref`.
- A link to a Markdown or .proto file (`[text](other.md)`) goes to the page of that file, see `Context.link`.
- Math (`$..$`, `@f$..@f$`, `@f[..@f]`) becomes the `{math}` role/directive, which needs no extension.
- `@page <name> <title>` in the header of a file names its page (`page_command()` takes the line out of the
  text); `@ref <name>` links to a page with its title.

The module knows nothing about protobuf: `sphinxdocs.parser` passes a `Context` that resolves the
references and the image paths of the place the comment belongs to.
"""

import logging
import re
import textwrap

# Private-use characters delimiting the tokens that stand in for text no later step may touch
_OPEN, _CLOSE = "\ue000", "\ue001"
_TOKEN = re.compile("%s(\\d+)%s" % (_OPEN, _CLOSE))

# command -> (MyST directive, title of a generic admonition)
_ADMONITIONS = {
    "note": ("note", ""), "remark": ("admonition", "Remark"), "remarks": ("admonition", "Remarks"),
    "warning": ("warning", ""), "attention": ("attention", ""), "important": ("important", ""),
    "hint": ("hint", ""), "tip": ("tip", ""), "caution": ("caution", ""), "danger": ("danger", ""),
    "error": ("error", ""), "see": ("seealso", ""), "sa": ("seealso", ""), "seealso": ("seealso", ""),
    "bug": ("admonition", "Bug"), "todo": ("admonition", "To do"),
    "deprecated": ("admonition", "Deprecated"), "pre": ("admonition", "Precondition"),
    "post": ("admonition", "Postcondition"), "invariant": ("admonition", "Invariant"),
}
# command -> label of the paragraph it starts
_LABELED = {
    "since": "Since", "version": "Version", "author": "Author", "authors": "Authors", "date": "Date",
    "copyright": "Copyright", "return": "Returns", "returns": "Returns", "result": "Returns",
}
# commands whose text is regular text: the command itself disappears
_PLAIN = {"brief", "short", "details", "detail"}
# commands that take the rest of the line, command -> heading level
_SECTIONS = {"section": 1, "subsection": 2, "subsubsection": 3}
# structural commands of Doxygen (grouping, member documentation) that have no meaning here
_IGNORED = {
    "file", "ingroup", "defgroup", "addtogroup", "weakgroup", "headerfile", "class", "struct", "union",
    "enum", "fn", "var", "typedef", "namespace", "package", "relates", "relatedalso", "memberof", "public",
    "private", "protected", "static", "dir", "interface", "protocol", "category", "def", "overload",
    "showinitializer", "hideinitializer", "name",
}
_LINE_COMMANDS = set(_SECTIONS) | _IGNORED | {"anchor", "image"}
_BLOCK_COMMANDS = set(_ADMONITIONS) | set(_LABELED) | _PLAIN | _LINE_COMMANDS | {"param", "retval", "par"}

_BLOCK = re.compile(r"(?<![\w@\\])[@\\](%s)(?!\w)" % "|".join(sorted(_BLOCK_COMMANDS, key=len, reverse=True)))
_IDENT = r"[A-Za-z_]\w*"
_NAME = r"\.?%s(?:(?:\.|::|#)%s)*" % (_IDENT, _IDENT)
_REF = re.compile(r'(?<![\w@\\])[@\\]ref\s+(%s)(?:\s+"([^"\n]*)")?' % _NAME)
_SYMBOL_NAME = re.compile(r"\.?%s(?:\.%s)*" % (_IDENT, _IDENT))
# what makes a code span a role argument (`:sub:`x``, ``{sub}`x```) or the text of a link (`[`x`](url)`)
_ROLE_BEFORE = re.compile(r"(?::[A-Za-z][\w.+-]*:|\})$")
_LINK_BEFORE = re.compile(r"\[[^\[\]]*$")
_LINK_AFTER = re.compile(r"[^\[\]]*\][(\[]")
_PAGE = re.compile(r"^[ \t]*[@\\]page[ \t]+(%s)[ \t]*(.*?)[ \t]*(?:\n|$)" % _IDENT, re.M)
_WORD = re.compile(r"(?<![\w@\\])([@\\])(c|p|a|e|em|b)\s+(\S+)")
_LIST_ITEM = re.compile(r"^([ \t]*)[@\\](?:li|arg)\s+", re.M)
_BREAK = re.compile(r"(?<![\w@\\])@n(?!\w)|<br\s*/?>", re.I)
_GROUP_MARK = re.compile(r"(?<![\w@\\])[@\\][{}]")
_UNKNOWN = re.compile(r"(?<![\w@\\])@([A-Za-z]\w*)")
_IMAGE = re.compile(r'!\[([^\]]*)\]\(\s*([^)\s]+)(\s+"[^"]*")?\s*\)')
# a link to a Markdown or .proto file: (before the path, path, #fragment, after the path)
_FILE_LINK = re.compile(r'(?<!!)(\[[^\]\n]*\]\(\s*)([^)\s#]+\.(?:md|proto))(#[^)\s]*)?(\s+"[^"]*")?(\s*\))', re.I)
_NOT_RELATIVE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:|/")
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.S)
_MATH = re.compile(r"(?<![\\$])\$(?![\s$])((?:[^$\\]|\\.)+?)(?<![\s\\])\$(?!\d)")
_MATH_BLOCK = re.compile(r"\$\$(.+?)\$\$", re.S)
_FORMULA = re.compile(r"[@\\]f\$(.+?)[@\\]f\$", re.S)
_ROLE = re.compile(r":([A-Za-z][\w.+-]*):(%s\d+%s)" % (_OPEN, _CLOSE))
_HTML_ROLE = re.compile(r"<(sub|sup)>(.*?)</\1>", re.S | re.I)
_HTML_STYLE = [(re.compile(r"<%s>(.*?)</%s>" % (tag, tag), re.S | re.I), mark)
               for tags, mark in ((("b", "strong"), "**"), (("i", "em"), "*"), (("tt", "code"), "`"))
               for tag in tags]

_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
_BEGIN = re.compile(r"^\s*[@\\](code|verbatim|htmlonly|latexonly|cond|internal)(?!\w)(?:\{([^}]*)\})?(.*)$")
_BEGIN_FORMULA = re.compile(r"^\s*[@\\]f\[(.*)$")
_ATX = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
_SETEXT = re.compile(r"^\s{0,3}(=+|-+)\s*$")
_ANCHOR = re.compile(r"(?<![\w@\\])[@\\](?:anchor|section|subsection|subsubsection)\s+(%s)" % _IDENT)


class Context:
    """What a comment needs to know about the place it is rendered in."""

    def __init__(self, resolve=None, anchor_label=None, image=None, where="", rename=None, symbol=None, link=None):
        # symbol name (`fldConfig.field`, `pkg.Message`, an anchor) -> label of its target, None if unknown;
        # a page is (label, title)
        self.resolve = resolve or (lambda name: None)
        # name in a code span -> label of the symbol it names, None if it names none (no page, no anchor)
        self.symbol = symbol or (lambda name: None)
        # path of a link to a Markdown or .proto file as written -> path of its page, None if it is no page
        self.link = link or (lambda path: path)
        # name of a symbol as written in a `@ref` -> name to show (differs when the namespace is overridden)
        self.rename = rename or (lambda name: name)
        # name of a `@anchor`/`@section` -> label that defines it
        self.anchor_label = anchor_label or (lambda name: name)
        # image path as written in the comment -> path to use in the page
        self.image = image or (lambda path: path)
        self.where = where

    def warn(self, message: str) -> None:
        logging.warning("%s: %s", self.where, message)


class _Mask:
    """Text that must not be touched by the next steps; a token stands in for it until restore()."""

    def __init__(self):
        self.parts = []

    def add(self, text: str) -> str:
        self.parts.append(text)
        return "%s%d%s" % (_OPEN, len(self.parts) - 1, _CLOSE)

    def restore(self, text: str) -> str:
        previous = None
        while previous != text:
            previous = text
            text = _TOKEN.sub(lambda m: self.parts[int(m.group(1))], text)
        return text


def clean(raw: str) -> str:
    """Text of a comment as protoc delivers it, without the common indentation and surrounding blank lines."""
    text = raw.expandtabs(4)
    if text.startswith("*"):  # doc comment: /** ... */
        text = text[1:]
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return textwrap.dedent("\n".join(lines))


def anchor_ids(text: str) -> list:
    """Names defined by `@anchor`, `@section`, `@subsection` and `@subsubsection` in a comment."""
    return _ANCHOR.findall(text)


def first_heading(text: str) -> str:
    """The title of the first heading of a Markdown text (outside of code), as plain text; "" without a heading."""
    for kind, *data in _blocks(clean(text).split("\n")):
        if kind != "para":
            continue
        run = []
        for line in [*data[0], None]:
            atx = _ATX.match(line) if line is not None else None
            if line is None or atx:
                # the same rules as convert(): a run of lines that ends with an underline is a heading
                if len(run) > 1 and _SETEXT.match(run[-1]):
                    return _plain(" ".join(part.strip() for part in run[:-1]))
                if atx:
                    return _plain(atx.group(2))
                run = []
            else:
                run.append(line)
    return ""


def _plain(markdown: str) -> str:
    """Text of a short piece of Markdown without its markup (links keep their text)."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", markdown)
    return " ".join(re.sub(r"<[^>]+>|[`*]", "", text).split())


def split_title(text: str) -> tuple:
    """(title, rest) of a Markdown text that starts with a `#` heading of level 1 (or a line underlined with `=`).

    The title is plain text. A text that does not start with such a heading gives ("", text).
    """
    lines = clean(text).split("\n")
    atx = _ATX.match(lines[0])
    if atx and len(atx.group(1)) == 1:
        return _plain(atx.group(2)), "\n".join(lines[1:]).strip("\n")
    if len(lines) > 1 and lines[0].strip() and _SETEXT.match(lines[1]) and lines[1].strip()[0] == "=":
        return _plain(lines[0]), "\n".join(lines[2:]).strip("\n")
    return "", text


def page_command(text: str) -> tuple:
    """
    The first `@page <name> <title>` line of a cleaned comment: (name, title, the text without the line).

    A comment without one gives (None, "", text).
    """
    found = _PAGE.search(text)
    if not found:
        return None, "", text
    return found.group(1), found.group(2), (text[:found.start()] + text[found.end():]).strip("\n")


def convert(text: str, ctx: Context, headings=None) -> str:
    """
    Markdown for a comment.

    headings: the Markdown level the topmost heading of the comment is given (the others keep their
              distance); None turns the headings into bold paragraphs, for comments inside a list.
    """
    items = []
    for kind, *data in _blocks(clean(text).split("\n")):
        if kind == "para":
            items += _paragraph(data[0], ctx)
        elif kind == "fence":
            items.append(("md", data[0]))
        elif kind == "code":
            items.append(("md", _code_block(data[0], data[1])))
        elif kind == "math":
            items.append(("md", _directive("math", data[0])))
        elif kind == "raw":
            items.append(("md", _directive("raw", data[1], data[0])))
    levels = sorted({item[1] for item in items if item[0] == "h"})
    out = []
    for item in items:
        if item[0] == "md":
            out.append(item[1])
            continue
        _, level, title, label = item
        if label:
            out.append("(%s)=" % label)
        if headings is None:
            out.append("**%s**" % title)
        else:
            out.append("#" * min(6, headings + levels.index(level)) + " " + title)
    return "\n\n".join(part for part in out if part.strip())


def _blocks(lines: list) -> list:
    """Split the lines into paragraphs and the blocks that are copied (code, fences, math) or dropped."""
    blocks, paragraph, i = [], [], 0

    def flush():
        if paragraph:
            blocks.append(("para", list(paragraph)))
            paragraph.clear()

    while i < len(lines):
        line = lines[i]
        fence, begin, formula = _FENCE.match(line), _BEGIN.match(line), _BEGIN_FORMULA.match(line)
        if not line.strip():
            flush()
            i += 1
        elif fence:
            flush()
            mark = fence.group(1)
            closing = re.compile(r"^\s*%s{%d,}\s*$" % (re.escape(mark[0]), len(mark)))
            end = i + 1
            while end < len(lines) and not closing.match(lines[end]):
                end += 1
            blocks.append(("fence", "\n".join(lines[i:end + 1])))
            i = end + 1
        elif begin:
            flush()
            name, option, rest = begin.groups()
            body, i = _until(lines, i, rest, re.compile(r"[@\\]end%s(?!\w)" % name))
            if name == "code":
                blocks.append(("code", body, _language(option)))
            elif name == "verbatim":
                blocks.append(("code", body, "text"))
            elif name in ("htmlonly", "latexonly"):
                blocks.append(("raw", name[:-4], body))
        elif formula:
            flush()
            body, i = _until(lines, i, formula.group(1), re.compile(r"[@\\]f\]"))
            blocks.append(("math", body))
        else:
            paragraph.append(line)
            i += 1
    flush()
    return blocks


def _until(lines: list, start: int, rest: str, closing) -> tuple:
    """Text from `rest` (on line `start`) up to the line matching `closing`, and the index of the next line."""
    chunk, i = [rest], start
    while True:
        found = closing.search(chunk[-1])
        if found:
            chunk[-1] = chunk[-1][:found.start()]
            break
        i += 1
        if i >= len(lines):
            break
        chunk.append(lines[i])
    return textwrap.dedent("\n".join(chunk)).strip("\n"), i + 1


def _language(option) -> str:
    """Language of `@code{.cpp}`: the name Pygments knows."""
    name = (option or "").strip().lstrip(".")
    return {"unparsed": "text", "txt": "text"}.get(name, name)


def _paragraph(lines: list, ctx: Context) -> list:
    """Items of a paragraph: ("md", text) or ("h", level, text, label)."""
    items, run = [], []

    def end_run():
        if len(run) > 1 and _SETEXT.match(run[-1]):
            level = 1 if run[-1].strip()[0] == "=" else 2
            mask = _Mask()
            title = _inline(_mask_literals(" ".join(line.strip() for line in run[:-1]), mask), ctx, mask)
            items.append(("h", level, mask.restore(title), None))
        elif run:
            items.extend(_text_items("\n".join(run), ctx))
        run.clear()

    for line in lines:
        atx = _ATX.match(line)
        if atx:
            end_run()
            mask = _Mask()
            title = _inline(_mask_literals(atx.group(2), mask), ctx, mask)
            items.append(("h", len(atx.group(1)), mask.restore(title), None))
        else:
            run.append(line)
    end_run()
    return items


def _text_items(text: str, ctx: Context) -> list:
    """Items of a paragraph without headings: text, admonitions, figures, labelled paragraphs."""
    stripped = text.strip()
    block_math = _MATH_BLOCK.fullmatch(stripped)
    if block_math:
        return [("md", _directive("math", block_math.group(1).strip()))]

    mask = _Mask()
    text = _mask_literals(text, mask, ctx)
    items = []
    for event in _events(text):
        if event[0] == "text":
            if event[1].strip():
                items.append(("md", _text(event[1].strip(), ctx, mask)))
            continue
        _, name, arg = event
        if name in _ADMONITIONS:
            directive, title = _ADMONITIONS[name]
            if arg:
                items.append(("md", _directive(directive, _inline(arg, ctx, mask), title)))
        elif name in _LABELED:
            items.append(("md", "**%s:** %s" % (_LABELED[name], _inline(arg, ctx, mask))))
        elif name == "param":
            found = re.match(r"(?:\[[^\]]*\])?\s*(\S+)\s*(.*)", arg, re.S)
            if found:
                items.append(("md", "**Parameter `%s`:** %s" % (mask.restore(found.group(1)),
                                                               _inline(found.group(2), ctx, mask))))
        elif name == "retval":
            found = re.match(r"(\S+)\s*(.*)", arg, re.S)
            if found:
                items.append(("md", "**Return value `%s`:** %s" % (mask.restore(found.group(1)),
                                                                  _inline(found.group(2), ctx, mask))))
        elif name == "par":
            title, _, rest = arg.partition("\n")
            items.append(("md", "**%s**" % _inline(title.strip(), ctx, mask)))
            if rest.strip():
                items.append(("md", _inline(rest.strip(), ctx, mask)))
        elif name == "anchor":
            if re.fullmatch(_IDENT, arg):
                items.append(("md", "(%s)=" % ctx.anchor_label(arg)))
        elif name in _SECTIONS:
            ident, _, title = arg.partition(" ")
            if ident and title.strip():
                items.append(("h", _SECTIONS[name], _inline(title.strip(), ctx, mask), ctx.anchor_label(ident)))
        elif name == "image":
            figure = _doxygen_image(arg, ctx, mask)
            if figure:
                items.append(("md", figure))
        # the remaining commands only structure the Doxygen documentation
    return [("md", mask.restore(item[1])) if item[0] == "md" else ("h", item[1], mask.restore(item[2]), item[3])
            for item in items]


def _events(text: str) -> list:
    """Split a paragraph at its block commands: ("text", text) and ("command", name, argument)."""
    events, pos = [], 0
    while True:
        found = _BLOCK.search(text, pos)
        if not found:
            events.append(("text", text[pos:]))
            return events
        events.append(("text", text[pos:found.start()]))
        name = found.group(1)
        if name in _LINE_COMMANDS:
            end = text.find("\n", found.end())
            end = len(text) if end < 0 else end
        else:
            following = _BLOCK.search(text, found.end())
            end = following.start() if following else len(text)
        argument = text[found.end():end].strip()
        events.append(("text", argument) if name in _PLAIN else ("command", name, argument))
        pos = end


def _text(text: str, ctx: Context, mask: _Mask) -> str:
    """Text of a paragraph; a paragraph that is only an image with an alt text becomes a figure."""
    image = _IMAGE.fullmatch(text)
    if image and image.group(1).strip():
        alt = image.group(1).strip()
        return _figure(ctx.image(image.group(2)), caption=_inline(alt, ctx, mask), alt=mask.restore(alt))
    return _inline(text, ctx, mask)


def _doxygen_image(arg: str, ctx: Context, mask: _Mask) -> str:
    """`@image html file.png "caption" width=50%`; only the html variant is used, the others duplicate it."""
    found = re.fullmatch(r'(\w+)\s+(\S+)(?:\s+"([^"]*)")?\s*(.*)', arg, re.S)
    if not found or found.group(1).lower() != "html":
        return ""
    size = dict(re.findall(r"(width|height)\s*=\s*(\S+)", found.group(4)))
    caption = found.group(3) or ""
    return _figure(ctx.image(mask.restore(found.group(2))), caption=_inline(caption, ctx, mask),
                   alt=mask.restore(caption), width=size.get("width", ""), height=size.get("height", ""))


def _figure(uri: str, caption: str = "", alt: str = "", width: str = "", height: str = "") -> str:
    options = []
    if alt:
        options.append(":alt: " + " ".join(alt.split()))
    if width:
        options.append(":width: " + width)
    if height:
        options.append(":height: " + height)
    if caption:
        return _directive("figure", "\n".join(options + ["", caption]), uri)
    return _directive("image", "\n".join(options), uri)


def _ticks(body: str, minimum: int = 3) -> str:
    """A run of backticks that is longer than any run of backticks in the body."""
    return "`" * max(minimum, max([len(run) for run in re.findall(r"`+", body)] + [0]) + 1)


def _directive(name: str, body: str, argument: str = "") -> str:
    """A MyST directive."""
    fence = _ticks(body)
    head = "%s{%s}%s" % (fence, name, " " + argument if argument else "")
    return "%s\n%s\n%s" % (head, body, fence) if body else "%s\n%s" % (head, fence)


def _code_block(body: str, language: str) -> str:
    fence = _ticks(body)
    return "%s%s\n%s\n%s" % (fence, language, body, fence)


def _math(source: str) -> str:
    """The role that renders `source` as math."""
    ticks = _ticks(source, 1)
    return "{math}%s%s%s" % (ticks, source.strip(), ticks)


def _symbol_label(span, ctx: Context):
    """Label of the symbol that a code span names, None if the span is anything else or cannot hold a link."""
    name = span.group(2)
    if not _SYMBOL_NAME.fullmatch(name):
        return None
    before, after = span.string[:span.start()], span.string[span.end():]
    if _ROLE_BEFORE.search(before) or (_LINK_BEFORE.search(before) and _LINK_AFTER.match(after)):
        return None
    return ctx.symbol(name)


def _mask_literals(text: str, mask: _Mask, ctx: Context = None) -> str:
    """
    Hide what the commands must not touch: code spans, escaped command prefixes and math.

    With a context, a code span that is only the name of a symbol becomes a link to it (headings pass none).
    """

    def code_span(m):
        label = _symbol_label(m, ctx) if ctx else None
        return mask.add("[%s](#%s)" % (m.group(0), label) if label else m.group(0))

    text = _CODE_SPAN.sub(code_span, text)
    text = text.replace("\\@", mask.add("@"))
    text = _FORMULA.sub(lambda m: mask.add(_math(m.group(1))), text)
    text = _MATH_BLOCK.sub(lambda m: mask.add(_math(m.group(1))), text)
    text = _MATH.sub(lambda m: mask.add(_math(m.group(1))), text)
    # a dollar sign that is no math must not become one in a project that enables dollarmath
    text = re.sub(r"(?<!\\)\$", lambda m: mask.add("\\$"), text)

    def role(m):
        # :sub:`x` written the reStructuredText way is the role of MyST: {sub}`x`
        is_code = mask.parts[int(_TOKEN.fullmatch(m.group(2)).group(1))].startswith("`")
        return "{%s}%s" % (m.group(1), m.group(2)) if is_code else m.group(0)

    return _ROLE.sub(role, text)


def _inline(text: str, ctx: Context, mask: _Mask) -> str:
    """Inline commands and HTML of a masked text; the result is still masked."""

    def ref(m):
        name = m.group(1).replace("::", ".").replace("#", ".")
        found = ctx.resolve(name)
        if found is None:
            ctx.warn("cannot resolve @ref %s" % name)
            return mask.add(m.group(2) if m.group(2) is not None else "`%s`" % name.lstrip("."))
        if isinstance(found, tuple):  # a page: (label, title), shown with its title unless the command gives a text
            label, title = found
            return mask.add("[%s](#%s)" % (re.sub(r"([\[\]])", r"\\\1", title if m.group(2) is None else m.group(2)),
                                           label))
        shown = m.group(2) if m.group(2) is not None else "`%s`" % ctx.rename(name.lstrip("."))
        return mask.add("[%s](#%s)" % (shown.replace("]", "\\]"), found))

    def word(m):
        command, argument = m.group(2), m.group(3)
        if m.group(1) == "\\" and len(command) == 1:  # `\n`, `\e`, ... are too likely to be plain text
            return m.group(0)
        trailing = re.search(r"[.,;:!?)\]]*$", argument).group(0)
        argument = argument[:len(argument) - len(trailing)]
        if not argument:
            return m.group(0)
        mark = {"c": "`", "p": "`", "b": "**"}.get(command, "*")
        return mask.add(mark + argument + mark) + trailing

    def image(m):
        title = m.group(3) or ""
        return mask.add("![%s](%s%s)" % (m.group(1), ctx.image(mask.restore(m.group(2))), title))

    def file_link(m):
        before, path, fragment, title, after = (group or "" for group in m.groups())
        if _NOT_RELATIVE.match(path):
            return m.group(0)
        page = ctx.link(path.replace("\\", "/"))
        if page is None:
            ctx.warn("cannot resolve the link to %s: it is no file of the documentation" % path)
            return m.group(0)
        return before + page + fragment + title + after

    text = _REF.sub(ref, text)
    text = _WORD.sub(word, text)
    text = _BREAK.sub(lambda m: mask.add("\\\n"), text)
    text = _LIST_ITEM.sub(lambda m: m.group(1) + "- ", text)
    text = _GROUP_MARK.sub("", text)
    text = _HTML_ROLE.sub(lambda m: mask.add("{%s}`%s`" % (m.group(1).lower(), m.group(2))), text)
    for pattern, mark in _HTML_STYLE:
        text = pattern.sub(lambda m, mark=mark: mask.add(mark + m.group(1) + mark), text)
    text = _FILE_LINK.sub(file_link, text)
    text = _IMAGE.sub(image, text)
    for name in sorted(set(_UNKNOWN.findall(text))):
        ctx.warn("unsupported Doxygen command @%s" % name)
    return text
