# Copyright (c) 2025 Semiconductor Components Industries, LLC ("onsemi")
# SPDX-License-Identifier: GPL-3.0-or-later

"""Sphinx documentation generator: MyST Markdown pages for the .proto files, navigable by directory.

A .proto file gets a page that shows its header, with a page below it for its Protocol (the messages and
enums, in the order of the file, with the comments converted by `sphinxdocs.comments`); with `inline_protocol`
the Protocol is the last section of the page of the file instead, which is what a book (LaTeX, PDF) needs.
The directories of the files become pages that list their items; a directory with a single item is
replaced by that item. The header of a file can name its page (`@page <name> <title>`). All symbols get a
label `<prefix>.<full name>` so references (`@ref`) work across pages. The pages are written under the
optional `parent` directory, which is how the documentation becomes a chapter of a bigger Sphinx project
instead of the root of its own. The option `pages` adds Markdown files and folders as pages in front of the others.
"""

import os
import posixpath
import re

import jinja2 as jinja
from google.protobuf.compiler.plugin_pb2 import CodeGeneratorResponse, CodeGeneratorRequest
from google.protobuf.descriptor_pb2 import FieldDescriptorProto

from sphinxdocs import comments
from config import ConfigManager
from names import Ignored, Namespaces, type_names

env = jinja.Environment(
    loader=jinja.PackageLoader("sphinxdocs.parser"),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)

SCALAR_TYPES = {
    FieldDescriptorProto.TYPE_DOUBLE: "double", FieldDescriptorProto.TYPE_FLOAT: "float",
    FieldDescriptorProto.TYPE_INT64: "int64", FieldDescriptorProto.TYPE_UINT64: "uint64",
    FieldDescriptorProto.TYPE_INT32: "int32", FieldDescriptorProto.TYPE_FIXED64: "fixed64",
    FieldDescriptorProto.TYPE_FIXED32: "fixed32", FieldDescriptorProto.TYPE_BOOL: "bool",
    FieldDescriptorProto.TYPE_STRING: "string", FieldDescriptorProto.TYPE_BYTES: "bytes",
    FieldDescriptorProto.TYPE_UINT32: "uint32", FieldDescriptorProto.TYPE_SFIXED32: "sfixed32",
    FieldDescriptorProto.TYPE_SFIXED64: "sfixed64", FieldDescriptorProto.TYPE_SINT32: "sint32",
    FieldDescriptorProto.TYPE_SINT64: "sint64", FieldDescriptorProto.TYPE_GROUP: "group",
}

# Markdown that opens a block of its own: a paragraph cannot be joined with it
_BLOCK_START = re.compile(r"^(#{1,6}\s|[-*+]\s|\d+[.)]\s|>|\||`{3,}|~{3,}|\(.+\)=$|<)")


class _Symbol:
    def __init__(self, fqn: str, label: str, file: str, original: str = ""):
        self.fqn = fqn
        self.label = label
        self.file = file
        self.original = original or fqn  # the protobuf name, which differs from `fqn` after a namespace override


class _Symbols:
    """The symbols of all generated files, looked up with the scoping rules of protobuf."""

    def __init__(self, prefix: str):
        self.prefix = prefix
        self.names = {}
        self.suffixes = {}
        self.labels = set()

    def label(self, name: str) -> str:
        """A label `<prefix>.<name>` that differs from every other one in lower case, as Sphinx compares them."""
        label, count = "%s.%s" % (self.prefix, name), 1
        while label.lower() in self.labels:
            count += 1
            label = "%s.%s-%d" % (self.prefix, name, count)
        self.labels.add(label.lower())
        return label

    def add(self, fqn: str, file: str, aliases=(), original: str = "") -> None:
        symbol = _Symbol(fqn, self.label(fqn), file, original)
        for key in (fqn, *aliases):
            self.names.setdefault(key, symbol)
            parts = key.split(".")
            for i in range(len(parts)):
                self.suffixes.setdefault(".".join(parts[i:]), []).append(symbol)

    def display(self, fqn: str) -> str:
        """The name of a symbol as it is shown; `fqn` can be its protobuf name, which differs after the override."""
        symbol = self.names.get(fqn)
        return symbol.fqn if symbol else fqn

    def lookup(self, name: str, scope: str):
        """The innermost scope that has the name wins; a leading dot makes the name absolute."""
        if name.startswith("."):
            return self.names.get(name[1:])
        parts = scope.split(".") if scope else []
        for i in range(len(parts), -1, -1):
            found = self.names.get(".".join(parts[:i] + [name]))
            if found:
                return found
        return None

    def resolve(self, name: str, scope: str, file: str, in_file: bool = True):
        """Like lookup(), then the one symbol that ends with the name (with `in_file`, one in the file wins first)."""
        found = self.lookup(name, scope)
        if found:
            return found
        candidates = list({id(s): s for s in self.suffixes.get(name, [])}.values())
        same_file = [s for s in candidates if s.file == file] if in_file else []
        if len(same_file) == 1:
            return same_file[0]
        return candidates[0] if len(candidates) == 1 else None

    def short_name(self, fqn: str, scope: str, package: str) -> str:
        """The shortest name that resolves to `fqn` inside `scope`."""
        parts = fqn.split(".")
        for i in range(len(parts) - 1, -1, -1):
            name = ".".join(parts[i:])
            found = self.lookup(name, scope)
            if found and found.fqn == fqn:
                return name
        if fqn in self.names:  # hidden by a nearer symbol of the same name
            return "." + fqn
        return fqn.removeprefix(package + ".") if package else fqn


def _relative(target: str, start: str) -> str:
    """Path from the directory `start` to `target`; both are relative to the same directory."""
    t = [p for p in target.split("/") if p not in ("", ".")]
    s = [p for p in start.split("/") if p not in ("", ".")]
    i = 0
    while i < len(t) and i < len(s) and t[i] == s[i]:
        i += 1
    return "/".join([".."] * (len(s) - i) + t[i:]) or "."


def _is_text(chunk: str) -> bool:
    """True for a plain paragraph."""
    return bool(chunk) and not _BLOCK_START.match(chunk)


def _bullet(blocks: list) -> str:
    """A list item holding the blocks."""
    lines = "\n\n".join(block for block in blocks if block).split("\n")
    return "- " + lines[0] + "".join("\n" + ("  " + line if line else "") for line in lines[1:])


def _brief(markdown: str) -> str:
    """The first sentence of the first paragraph of the documentation of a file."""
    first = markdown.split("\n\n")[0]
    if not _is_text(first):
        return ""
    return re.split(r"(?<=[.!?])\s+(?=[A-Z])", " ".join(first.split()), maxsplit=1)[0]


def _document_brief(markdown: str) -> str:
    """The first sentence of the first paragraph of text of a page made of a file (headings and figures come first)."""
    for chunk in markdown.split("\n\n"):
        if _is_text(chunk.strip()) and not chunk.lstrip().startswith("!"):
            return _brief(chunk.strip())
    return ""


def _image_path(docs: "_Docs", directory: str, path: str, page: str) -> str:
    """Path of an image as seen from `page`; `path` is relative to `directory` below the image directory of the run.

    The suffixes `#gh-light-mode-only` and `#gh-dark-mode-only`, which make a code hosting site show an image in one
    color mode only, are dropped: a project that shows two drawings by mode does that with the style sheet of its theme.
    """
    path = re.sub(r"#gh-(light|dark)-mode-only$", "", path)
    if re.match(r"^([A-Za-z][A-Za-z0-9+.-]*:|/)", path):  # URL or path from the Sphinx source directory
        return path
    target = posixpath.normpath(posixpath.join(docs.image_path, directory, path.replace("\\", "/")))
    return _relative(target, posixpath.dirname(page))


class _Page:
    """The documentation of one .proto file: a page that shows the header of the file, with the page Protocol below it
    (or, with `inline_protocol`, ending with the section Protocol).

    The header of the file may start a page of its own with `@page <name> <title>`: the title replaces the path of
    the file in the navigation and `@ref <name>` links to the page.
    """

    # defaults for a page that has no `@page` (and for the tests, which create pages without __init__)
    page_id = None
    title = None
    label = ""
    brief = ""

    def __init__(self, docs: "_Docs", proto):
        self.docs = docs
        self.proto = proto
        self.name = proto.name
        self.package = docs.namespaces.package(proto.package)  # as shown: the symbols are named after it
        self.docname = posixpath.join(docs.parent, re.sub(r"\.proto$", "", proto.name))
        self.path = self.docname + ".md"
        self.protocol_path = self.docname + "-protocol.md"
        self.locations = {}
        for location in proto.source_code_info.location:
            commented = location.leading_comments or location.trailing_comments or location.leading_detached_comments
            if tuple(location.path) not in self.locations or commented:
                self.locations[tuple(location.path)] = location
        self.page_id, title, self.header_text = comments.page_command(self.header())
        self.title = title or self.page_id or self.name

    def qualify(self, name: str) -> str:
        return self.package + "." + name if self.package else name

    def original(self, fqn: str) -> str:
        """The protobuf name of a symbol of the file; `fqn` has the namespace after the override."""
        if self.package == self.proto.package:
            return fqn
        return ".".join(part for part in (self.proto.package, fqn[len(self.package):].lstrip(".")) if part)

    def aliases(self, fqn: str, *extra: str) -> tuple:
        """The other names of a symbol, which the comments and the fields use: `extra` and the protobuf names."""
        names = [name for given in (fqn, *extra) for name in (given, self.original(given))]
        return tuple(dict.fromkeys(name for name in names if name != fqn))

    def is_ignored(self, name: str) -> bool:
        """True if the option `ignore` names the message or enum `name`, which is its name in the file."""
        return self.docs.ignored.matches(type_names(self.proto.package, self.package, name))

    @property
    def source(self) -> str:
        """The file the page is made of, as the messages name it."""
        return self.name

    def comment(self, path: tuple) -> str:
        """The comment of the declaration at `path`: the one before it, then the one behind it."""
        location = self.locations.get(tuple(path))
        if location is None:
            return ""
        return "\n\n".join(comments.clean(text) for text in (location.leading_comments, location.trailing_comments)
                           if text.strip())

    def header(self) -> str:
        """The comments in front of the `syntax` and the `package` statements."""
        parts = []
        for path in ((12,), (2,)):
            location = self.locations.get(path)
            if location is not None:
                parts += [*location.leading_detached_comments, location.leading_comments]
        return "\n\n".join(comments.clean(text) for text in parts if text.strip())

    def all_messages(self):
        """(descriptor, path, full name, name in the file) of every message, nested ones behind their parent."""
        def walk(message, path, fqn, name):
            yield message, path, fqn, name
            for j, nested in enumerate(message.nested_type):
                if not nested.options.map_entry:
                    yield from walk(nested, path + (3, j), fqn + "." + nested.name, name + "." + nested.name)

        for i, message in enumerate(self.proto.message_type):
            yield from walk(message, (4, i), self.qualify(message.name), message.name)

    def messages(self):
        """(descriptor, path, full name, name in the file) of every message that `ignore` does not name."""
        return (item for item in self.all_messages() if not self.is_ignored(item[3]))

    def enums(self):
        """(descriptor, path, full name, name in the file, full name of the scope) of every enum."""
        for i, enum in enumerate(self.proto.enum_type):
            if not self.is_ignored(enum.name):
                yield enum, (5, i), self.qualify(enum.name), enum.name, self.package
        for message, path, fqn, name in self.all_messages():
            for j, enum in enumerate(message.enum_type):
                if not self.is_ignored(name + "." + enum.name):
                    yield enum, path + (4, j), fqn + "." + enum.name, name + "." + enum.name, fqn

    def declare_types(self, symbols: _Symbols) -> None:
        """Register the messages and enums of the file."""
        for _, _, fqn, _ in self.messages():
            symbols.add(fqn, self.name, aliases=self.aliases(fqn), original=self.original(fqn))
        for _, _, fqn, _, _ in self.enums():
            symbols.add(fqn, self.name, aliases=self.aliases(fqn), original=self.original(fqn))
        for map_entry in self.map_entries():
            self.docs.map_entries[map_entry[0]] = map_entry[1:]

    def declare_members(self, symbols: _Symbols) -> None:
        """Register the fields, oneofs and enum values of the file."""
        for message, _, fqn, _ in self.messages():
            for field in message.field:
                name = fqn + "." + field.name
                symbols.add(name, self.name, aliases=self.aliases(name), original=self.original(name))
            for oneof in message.oneof_decl:
                if not oneof.name.startswith("_"):
                    name = fqn + "." + oneof.name
                    symbols.add(name, self.name, aliases=self.aliases(name), original=self.original(name))
        for enum, _, fqn, _, scope in self.enums():
            for value in enum.value:
                # enum values live in the scope of their enum, like in C++: `Enum.value` and `value` both work
                name = fqn + "." + value.name
                symbols.add(name, self.name, original=self.original(name),
                            aliases=self.aliases(name, scope + "." + value.name if scope else value.name))

    def map_entries(self):
        """(full name, key field, value field) of every map field type of the file."""
        def walk(message, fqn):
            for nested in message.nested_type:
                if nested.options.map_entry:
                    yield (fqn + "." + nested.name, nested.field[0], nested.field[1])
                yield from walk(nested, fqn + "." + nested.name)

        for message in self.proto.message_type:
            yield from walk(message, self.original(self.qualify(message.name)))

    def context(self, scope: str, where: str) -> comments.Context:
        return self.docs.context(scope, self.name, "%s: %s" % (self.name, where), self.image,
                                 self.docs.link("", self.path))

    def image(self, path: str) -> str:
        """Path of an image of a comment as seen from this page."""
        return _image_path(self.docs, "", path, self.path)

    def is_map(self, field) -> bool:
        return field.type == FieldDescriptorProto.TYPE_MESSAGE and field.type_name.lstrip(".") in self.docs.map_entries

    def type_markdown(self, field, scope: str) -> str:
        """The type of a field; message and enum types link to their definition."""
        if field.type not in (FieldDescriptorProto.TYPE_MESSAGE, FieldDescriptorProto.TYPE_ENUM):
            return "`%s`" % SCALAR_TYPES.get(field.type, "unknown")
        fqn = field.type_name.lstrip(".")
        if self.is_map(field):
            key, value = self.docs.map_entries[fqn]
            return "`map<%s, %s>`" % tuple(self.type_name(f, scope) for f in (key, value))
        name = self.docs.symbols.short_name(self.docs.symbols.display(fqn), scope, self.package)
        symbol = self.docs.symbols.names.get(fqn)
        return "[`%s`](#%s)" % (name, symbol.label) if symbol else "`%s`" % name

    def type_name(self, field, scope: str) -> str:
        if field.type in (FieldDescriptorProto.TYPE_MESSAGE, FieldDescriptorProto.TYPE_ENUM):
            fqn = self.docs.symbols.display(field.type_name.lstrip("."))
            return self.docs.symbols.short_name(fqn, scope, self.package)
        return SCALAR_TYPES.get(field.type, "unknown")

    def entry(self, label: str, header: str, comment: str, scope: str, where: str, children: str = "",
              inline: bool = False) -> str:
        """A list item: the header, below it the comment and the items it contains."""
        description = comments.convert(comment, self.context(scope, where)) if comment.strip() else ""
        blocks = ["(%s)=" % label if label else ""]
        first, _, rest = description.partition("\n\n")
        if _is_text(first):
            if inline and not rest:
                blocks.append("%s — %s" % (header, first))
            else:
                blocks += ["%s\\\n%s" % (header, first), rest]
        else:
            blocks += [header, description]
        return _bullet(blocks + [children])

    def field_entry(self, message, path: tuple, fqn: str, index: int) -> str:
        field = message.field[index]
        syntax = self.proto.syntax or "proto2"
        flags = []
        if field.label == FieldDescriptorProto.LABEL_REPEATED and not self.is_map(field):
            flags.append("repeated")
        elif field.label == FieldDescriptorProto.LABEL_REQUIRED:
            flags.append("required")
        elif field.proto3_optional or (syntax == "proto2" and field.label == FieldDescriptorProto.LABEL_OPTIONAL):
            flags.append("optional")
        if field.options.deprecated:
            flags.append("deprecated")
        header = "**`%s`** — %s%s" % (field.name, "".join("*%s* " % flag for flag in flags),
                                      self.type_markdown(field, fqn))
        return self.entry(self.docs.symbols.names[fqn + "." + field.name].label, header,
                          self.comment(path + (2, index)), fqn, field.name)

    def oneof_entry(self, message, path: tuple, fqn: str, index: int) -> str:
        members = [self.field_entry(message, path, fqn, i) for i, field in enumerate(message.field)
                   if field.HasField("oneof_index") and field.oneof_index == index and not field.proto3_optional]
        name = message.oneof_decl[index].name
        return self.entry(self.docs.symbols.names[fqn + "." + name].label, "**`%s`** — *oneof*" % name,
                          self.comment(path + (8, index)), fqn, name, children="\n\n".join(members))

    def reserved_entries(self, message, path: tuple, fqn: str) -> list:
        """The reserved names; reserved tag numbers are not documented."""
        entries = []
        # the comment of a `reserved` statement belongs to the statement, which is its first name
        statement = self.comment(path + (10,))
        for i, name in enumerate(message.reserved_name):
            comment = self.comment(path + (10, i)) or statement
            statement = ""
            entries.append(self.entry("", "**reserved** — name `%s`" % name, comment, fqn, "reserved"))
        return entries

    def message_section(self, message, path: tuple, fqn: str, name: str, level: int = 3) -> str:
        """The documentation of a message, `level` is the Markdown level of its heading."""
        entries, seen = [], set()
        for i, field in enumerate(message.field):
            if field.HasField("oneof_index") and not field.proto3_optional:
                if field.oneof_index not in seen:
                    seen.add(field.oneof_index)
                    entries.append(self.oneof_entry(message, path, fqn, field.oneof_index))
            else:
                entries.append(self.field_entry(message, path, fqn, i))
        entries += self.reserved_entries(message, path, fqn)
        parts = ["(%s)=" % self.docs.symbols.names[fqn].label, "#" * level + " " + name, "*Message* `%s`" % fqn,
                 comments.convert(self.comment(path), self.context(fqn, name), headings=level + 1)]
        if entries:
            parts += ["**Fields**", "\n\n".join(entries)]
        return "\n\n".join(part for part in parts if part)

    def enum_section(self, enum, path: tuple, fqn: str, name: str, scope: str, level: int = 3) -> str:
        """The documentation of an enum, `level` is the Markdown level of its heading."""
        entries = []
        for i, value in enumerate(enum.value):
            entries.append(self.entry(self.docs.symbols.names[fqn + "." + value.name].label,
                                      "**`%s`**" % value.name, self.comment(path + (2, i)),
                                      fqn, value.name, inline=True))
        parts = ["(%s)=" % self.docs.symbols.names[fqn].label, "#" * level + " " + name, "*Enumeration* `%s`" % fqn,
                 comments.convert(self.comment(path), self.context(fqn, name), headings=level + 1),
                 "\n\n".join(entries)]
        return "\n\n".join(part for part in parts if part)

    def render(self) -> list:
        """(path, content) of the page of the file, which shows its header, and of its Protocol, which is the page
        below it or, with `inline_protocol`, the last section of the page."""
        header = comments.convert(self.header_text, self.context(self.package, "header"), headings=2)
        self.brief = _brief(header)
        inline = self.docs.inline_protocol
        top = 2 if inline else 1  # the Markdown level of the heading Protocol
        protocol = env.get_template("protocol.md.j2").render(
            top="#" * top, messages=[self.message_section(*item, level=top + 2) for item in self.messages()],
            enums=[self.enum_section(*item, level=top + 2) for item in self.enums()])
        page = env.get_template("file.md.j2").render(
            title=self.title, label=self.label, file=self.name if self.page_id else "", package=self.package,
            header=header, protocol=posixpath.basename(self.docname) + "-protocol",
            inline_protocol=protocol if inline else "")
        if inline:
            return [(self.path, page.rstrip() + "\n")]
        return [(path, text.rstrip() + "\n") for path, text in zip((self.path, self.protocol_path), (page, protocol))]


class _Document:
    """A page made of a Markdown file that is written like a comment: Markdown with Doxygen commands.

    `name` is the place of the page in the navigation, like the name of a .proto file without its extension: the
    folders of the file, then the name of the page (`@ref` uses it, and it is the name of the page file). The first
    heading of the file is the title. The images are relative to the file, which `source` locates relative to the
    directory protoc runs in.
    """

    def __init__(self, docs: "_Docs", name: str, source: str, text: str):
        self.docs = docs
        self.name = name
        self.page_id = posixpath.basename(name)
        self.source = source
        self.text = text
        self.heading = comments.first_heading(text)
        self.title = self.heading or self.page_id
        self.path = posixpath.join(docs.parent, name + ".md")
        self.label = ""
        self.brief = ""

    def image(self, path: str) -> str:
        """Path of an image of the file as seen from this page."""
        return _image_path(self.docs, posixpath.dirname(self.source), path, self.path)

    def render(self) -> list:
        """(path, content) of the page."""
        context = self.docs.context("", self.source, self.source, self.image,
                                    self.docs.link(posixpath.dirname(self.source), self.path))
        body = comments.convert(self.text, context, headings=1)
        if not self.heading:
            body = "# %s\n\n%s" % (self.title, body)
        self.brief = _document_brief(body)
        text = env.get_template("document.md.j2").render(label=self.label, body=body)
        return [(self.path, text.rstrip() + "\n")]


class _Dir:
    """A directory of the pages that holds more than one item or has a readme: a page that lists them.

    The readme is `(file, text)` of its readme.md, which takes the place of the list of the items: describe() makes
    the description, the heading of the page (otherwise the name of the directory is used; the lists and the menu
    name the directory after its path) and the brief that the list of the parent directory shows from it. The root
    directory has a readme if the home page is set.
    """

    def __init__(self, path: str, readme=None):
        self.path = path
        self.children = []
        self.readme = readme
        self.label = ""
        self.title = ""
        self.description = ""
        self.brief = ""

    def index_path(self, parent: str) -> str:
        return posixpath.join(parent, self.path, "index.md")

    def describe(self, docs: "_Docs", parent: str) -> None:
        """Convert the readme: a leading heading of level 1 is the title, the rest the description.

        The headings of the description are bold text in a book (LaTeX), because the pages below this one end up in
        the last section of it.
        """
        source, text = self.readme
        page = self.index_path(parent)
        self.title, text = comments.split_title(text)
        context = docs.context("", source, source, lambda path: _image_path(docs, posixpath.dirname(source), path, page),
                               docs.link(posixpath.dirname(source), page))
        self.description = comments.convert(text, context, headings=None if docs.inline_protocol else 2)
        chunks = [chunk for chunk in self.description.split("\n\n") if not re.fullmatch(r"\*\*[^*\n]+\*\*", chunk.strip())]
        self.brief = _document_brief("\n\n".join(chunks))


def _tree(pages: list, readmes: dict = None) -> _Dir:
    """The directories of the files as nested nodes; a directory with a single item is replaced by that item.

    `readmes` maps the path of a directory to its readme; a directory that has one stays a page.
    """
    readmes = readmes or {}
    root = _Dir("")
    for page in pages:
        parts = page.name.split("/")[:-1]
        node = root
        for i in range(len(parts)):
            path = "/".join(parts[:i + 1])
            child = next((c for c in node.children if isinstance(c, _Dir) and c.path == path), None)
            if child is None:
                child = _Dir(path, readmes.get(path))
                node.children.append(child)
            node = child
        node.children.append(page)

    def collapse(node):
        node.children = [collapse(child) if isinstance(child, _Dir) else child for child in node.children]
        return node.children[0] if len(node.children) == 1 and node.path and not node.readme else node

    collapse(root)
    return root


def _read_readme(path: str):
    """(file, text) of the readme.md (in any case) of the directory `path`, None without one."""
    if not os.path.isdir(path):
        return None
    for entry in sorted(os.listdir(path)):
        source = posixpath.join(path, entry)
        if entry.lower() == "readme.md" and os.path.isfile(source):
            return source, _read_text(source)
    return None


def _readmes(pages: list) -> dict:
    """The readmes of the directories of the files of `pages`, by the path of the directory; the paths are relative to
    the directory protoc runs in, like the names of the files."""
    found = {}
    for page in pages:
        parts = page.name.split("/")[:-1]
        for i in range(len(parts)):
            path = "/".join(parts[:i + 1])
            if path not in found:
                found[path] = _read_readme(path)
    return {path: readme for path, readme in found.items() if readme}


def _title(node, directory: _Dir) -> str:
    """Name of a page or directory as listed in `directory`.

    A page that has a title is listed with it, a page without one with the path of its file below `directory`, a
    directory with the path below `directory` without a trailing slash and with a capital first letter.
    """
    if isinstance(node, (_Page, _Document)) and node.page_id:
        return node.title
    name = node.name if isinstance(node, _Page) else node.path
    name = name[len(directory.path) + 1:] if directory.path else name
    return name if isinstance(node, _Page) else name[:1].upper() + name[1:]


def _listing(directory: _Dir, parent: str, base: str, level: int = 0) -> list:
    """Markdown list of the items of a directory (below it the directories it holds), links relative to `base`."""
    lines = []
    for node in directory.children:
        indent = "  " * level
        if isinstance(node, _Dir):
            lines.append("%s- [%s](%s)%s" % (indent, _title(node, directory), _relative(node.index_path(parent), base),
                                              " — " + node.brief if node.brief else ""))
            lines += _listing(node, parent, base, level + 1)
        else:
            lines.append("%s- [%s](%s)%s" % (indent, _title(node, directory), _relative(node.path, base),
                                              " — " + node.brief if node.brief else ""))
    return lines


def _toctree(directory: _Dir, parent: str, base: str) -> list:
    """The entries of the toctree of a directory page; `base` is the directory of the page."""
    entries = []
    for node in directory.children:
        docname = node.index_path(parent) if isinstance(node, _Dir) else node.path
        entries.append("%s <%s>" % (_title(node, directory), re.sub(r"\.md$", "", _relative(docname, base))))
    return entries


class _Docs:
    """The options of the run and what all pages share."""

    def __init__(self, prefix: str, parent: str, image_path: str, inline_protocol: bool = False,
                 namespaces: Namespaces | None = None, ignored: Ignored | None = None):
        self.symbols = _Symbols(prefix)
        self.parent = parent
        self.image_path = image_path
        self.inline_protocol = inline_protocol
        self.namespaces = namespaces or Namespaces()
        self.ignored = ignored or Ignored()
        self.anchors = set()
        self.map_entries = {}
        self.page_ids = {}
        self.sources = {}  # key of a source file -> its page

    def add_source(self, source: str, page: str) -> None:
        """Make `page` the page that a link to the file `source` (relative to the directory protoc runs in) goes to."""
        self.sources.setdefault(os.path.normcase(os.path.abspath(source)), page)

    def link(self, directory: str, page: str):
        """The `link` of a Context: paths are relative to `directory` (where protoc runs), `page` is the page that
        holds the link."""
        def resolve(path):
            target = self.sources.get(os.path.normcase(os.path.abspath(posixpath.join(directory, path))))
            return _relative(target, posixpath.dirname(page)) if target else None
        return resolve

    def anchor_label(self, name: str) -> str:
        return "%s.%s" % (self.symbols.prefix, name)

    def context(self, scope: str, file: str, where: str, image, link=None) -> comments.Context:
        """What a comment or a page needs to resolve its references; `scope` and `file` are the place it belongs to."""
        def resolve(name):
            # protobuf's scoping first, then a page, then the one symbol that ends with the name, then an anchor
            symbol = self.symbols.lookup(name, scope)
            if symbol:
                return symbol.label
            if name in self.page_ids:
                return self.page_ids[name].label, self.page_ids[name].title
            symbol = self.symbols.resolve(name, scope, file)
            if symbol:
                return symbol.label
            return self.anchor_label(name) if name in self.anchors else None

        def named_symbol(name):
            # what a code span may name: no page, no anchor, and only a name that has a single hit
            found = self.symbols.lookup(name, scope)
            if not found and name not in self.page_ids:
                found = self.symbols.resolve(name, scope, file, in_file=False)
            return found.label if found else None

        def rename(name):
            # a full protobuf name that the namespace override changed is shown as the symbols are named now
            symbol = self.symbols.names.get(name)
            return symbol.fqn if symbol and symbol.original == name else name

        return comments.Context(resolve=resolve, anchor_label=self.anchor_label, image=image, where=where,
                                rename=rename, symbol=named_symbol, link=link)


def _sorted_files(files: list) -> list:
    """Top-level files first: every file is followed by the files it imports, in the order of its imports."""
    by_name = {f.name: f for f in files}
    imported = {dependency for f in files for dependency in f.dependency}
    ordered, seen = [], set()

    def visit(f):
        if f.name in seen:
            return
        seen.add(f.name)
        ordered.append(f)
        for dependency in f.dependency:
            if dependency in by_name:
                visit(by_name[dependency])

    for f in sorted(files, key=lambda f: f.name):
        if f.name not in imported:
            visit(f)
    for f in sorted(files, key=lambda f: f.name):
        visit(f)
    return ordered


def _parent_dir(value: str) -> str:
    value = value.replace("\\", "/")
    parts = [part for part in value.split("/") if part not in ("", ".")]
    if ".." in parts or value.startswith("/"):
        raise Exception("Invalid parent '%s': expected a directory below the output directory" % value)
    return "/".join(parts)


_NUMBER = re.compile(r"^\d+[-_. ]+(?=\S)")


def _unnumbered(name: str) -> str:
    """A name of a file or folder without the number in front of it, which only orders it: `02_network` is `network`."""
    return _NUMBER.sub("", name, count=1)


def _natural(name: str) -> list:
    """Sort key that compares the numbers of a name as numbers: `2_a` comes before `10_a`."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def _folder(path: str) -> list:
    """(folders, file) of the Markdown files below the folder `path`, in the order of their names.

    `folders` are the names of the folders from `path` itself down to the one that holds the file, without numbers.
    """
    def walk(directory, folders):
        found = []
        for entry in sorted(os.listdir(directory), key=_natural):
            full = posixpath.join(directory, entry)
            if entry.startswith("."):
                continue
            if os.path.isdir(full):
                found += walk(full, folders + [_unnumbered(entry)])
            elif entry.lower().endswith(".md"):
                found.append((folders, full))
        return found

    name = _unnumbered(os.path.basename(os.path.abspath(path)))
    if not name:
        raise Exception("Invalid pages entry '%s': the folder has no name" % path)
    return walk(path, [name])


def _read_text(source: str) -> str:
    try:
        with open(source, encoding="utf-8-sig") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as error:
        raise Exception("Cannot read the page file %s: %s" % (source, getattr(error, "strerror", None) or error))


def _read_pages(entries: tuple) -> tuple:
    """(pages, readmes) of the Markdown files of the option `pages`: entries `[<name>=]<file>` or `<folder>`.

    A page is (name, file, text): `name` is the place of the page in the navigation, its folders then its name. The
    readme.md of a folder is no page: `readmes` maps the path of the folder in the navigation to its (file, text).
    """
    found, readmes = [], {}
    for entry in entries:
        named = re.fullmatch(r"([A-Za-z_]\w*)=(.+)", entry)
        name, path = named.groups() if named else (None, entry)
        path = posixpath.normpath(path.strip().replace("\\", "/"))
        if path.startswith("/") or re.match(r"[A-Za-z]:", path):
            raise Exception("Invalid pages entry '%s': expected a path relative to the directory protoc runs in" % entry)
        if os.path.isdir(path):
            if name:
                raise Exception("Invalid pages entry '%s': a folder is named after itself, only a file can be given "
                                "a name" % entry)
            files = _folder(path)
            for item in [item for item in files if posixpath.basename(item[1]).lower() == "readme.md"]:
                readmes["/".join(item[0])] = (item[1], _read_text(item[1]))
                files.remove(item)
            if not files:
                raise Exception("The folder %s of the pages has no Markdown files" % path)
        else:
            files = [([], path)]
        for folders, source in files:
            page = name or _unnumbered(posixpath.splitext(posixpath.basename(source))[0])
            if not re.fullmatch(r"[A-Za-z_]\w*", page):
                raise Exception("Invalid page name '%s' of %s: %s" % (
                    page, source, "rename the file" if folders else "name the page with pages=<name>=%s" % source))
            found.append(("/".join(folders + [page]), source, _read_text(source)))
    return found, readmes


def _home(value: str, docs: "_Docs"):
    """What the home page is: a Markdown page of `pages` (its _Document) or a Markdown file as (file, text)."""
    value = value.strip().replace("\\", "/")
    page = docs.page_ids.get(value)
    if isinstance(page, _Document):
        return page
    if page:
        raise Exception("The home page %s is the page of %s, which is no Markdown page" % (value, page.source))
    if value.startswith("/") or re.match(r"[A-Za-z]:", value):
        raise Exception("Invalid home '%s': expected a path relative to the directory protoc runs in" % value)
    path = posixpath.normpath(value)
    try:
        text = _read_text(path)
    except Exception:
        raise Exception("Invalid home '%s': it is neither a Markdown page of the documentation nor a Markdown file"
                        % value) from None
    return path, text


def generate_sphinxdocs(request: CodeGeneratorRequest, response: CodeGeneratorResponse, config: ConfigManager) -> None:
    """Add the pages of the .proto files and of the Markdown files and folders of `pages`, the pages of the
    directories and, for documentation of its own, conf.py."""
    if config.single_file:
        raise Exception("single_file is not supported by type=sphinxdocs: every .proto file is its own page")
    image_path = config.image_path
    if image_path.startswith(("/", "\\")):
        raise Exception("Invalid image_path '%s': expected a directory relative to the output directory" % image_path)
    parent = _parent_dir(config.parent)
    protos = [proto for proto in request.proto_file if proto.name in request.file_to_generate]
    docs = _Docs(config.prefix, parent, posixpath.normpath(image_path.replace("\\", "/")) if image_path else ".",
                 config.inline_protocol, Namespaces((proto.package for proto in protos), config.namespace_override),
                 Ignored(config.ignore))
    page_files, page_readmes = _read_pages(config.pages)
    documents = [_Document(docs, *item) for item in page_files]
    files = [_Page(docs, proto) for proto in _sorted_files(protos)]
    everything = [*documents, *files]
    readmes = {**_readmes(files), **page_readmes}

    # the pages come first, so that a symbol with the name of a page gets the other label
    for page in everything:
        if page.page_id:
            if page.page_id in docs.page_ids:
                raise Exception("The page %s is defined by %s and by %s"
                                % (page.page_id, docs.page_ids[page.page_id].source, page.source))
            docs.page_ids[page.page_id] = page
            page.label = docs.symbols.label(page.page_id)
    home = _home(config.home, docs) if config.home else None
    for text in [document.text for document in documents] + [text for _, text in readmes.values()] + (
            [home[1]] if isinstance(home, tuple) else []):
        docs.anchors.update(comments.anchor_ids(text))
    for page in files:
        page.declare_types(docs.symbols)
        for location in page.locations.values():
            for text in (location.leading_comments, location.trailing_comments, *location.leading_detached_comments):
                docs.anchors.update(comments.anchor_ids(text))
    for page in files:
        page.declare_members(docs.symbols)

    outputs = {}

    def add(path: str, content: str, source: str) -> None:
        if path in outputs:
            raise Exception("%s would overwrite %s of %s" % (source, path, outputs[path][0]))
        outputs[path] = (source, content)

    def add_index(directory: _Dir, heading: str) -> None:
        path = directory.index_path(parent)
        base = posixpath.dirname(path)
        # a readme takes the place of the list of the items
        listing = "" if directory.readme else "\n".join(_listing(directory, parent, base))
        add(path, env.get_template("index.md.j2").render(
            label=directory.label, title=directory.title or heading, description=directory.description,
            listing=listing, entries=_toctree(directory, parent, base)),
            directory.path + "/" if directory.path else heading)
        for child in directory.children:
            if isinstance(child, _Dir):
                add_index(child, _title(child, directory))

    def describe(directory: _Dir) -> None:
        if directory.readme:
            directory.describe(docs, parent)
        for child in directory.children:
            if isinstance(child, _Dir):
                describe(child)

    home_page = home if isinstance(home, _Document) else None  # its page is the root, not a page of its own
    pages = [page for page in everything if page is not home_page]
    # a link to a file goes to its page; a readme is the page of its directory
    index = posixpath.join(parent, "index.md")
    for page in files:
        docs.add_source(page.name, page.path)
    for document in documents:
        docs.add_source(document.source, index if document is home_page else document.path)
    for path, (source, _) in readmes.items():
        docs.add_source(source, posixpath.join(parent, path, "index.md"))
    if isinstance(home, tuple):
        docs.add_source(home[0], index)
    for page in pages:
        for path, content in page.render():
            add(path, content, page.source)
    root = _tree(pages, readmes)
    if home_page:
        root.readme, root.label = (home_page.source, home_page.text), home_page.label
    elif isinstance(home, tuple):
        root.readme = home
    describe(root)
    add_index(root, config.title)
    if not parent and not config.omit_conf:
        add("conf.py", env.get_template("conf.py.j2").render(title=config.title), "the configuration")

    for path, (_, content) in outputs.items():
        file = response.file.add()
        file.name = path
        file.content = content
