# Copyright (c) 2025 Semiconductor Components Industries, LLC ("onsemi")
# SPDX-License-Identifier: GPL-3.0-or-later

# Common utilities for protobuf code generation

import os
import re
import sys
import textwrap
import jinja2
from config import ConfigManager
from names import Ignored, Namespaces, type_names
from google.protobuf.compiler.plugin_pb2 import CodeGeneratorResponse
from google.protobuf.descriptor_pb2 import FileDescriptorProto, FieldDescriptorProto, EnumDescriptorProto, DescriptorProto
import subprocess

# the C and C++ descriptors address a field with a 16-bit offset in the message, which starts with its presence bitmap
MAX_PRESENCE_SIZE = 0xFFFF


class Environment:
    """Class representing the code generation environment."""

    def __init__(self, reserved_words: list = [], name_separator: str = "_", reserved_suffix: str = "_", clang_format: str = ""):
        """
        reserved_words: list - List of reserved words in the target language
        name_separator: str - Separator to use in names
        """
        self.reserved = reserved_words
        self.separator = name_separator
        self.reserved_suffix = reserved_suffix
        self.clang_format = clang_format
        self._style_checked = False

    def _check_style(self):
        """Without clang-format, or with one that rejects the style (a key it does not know, e.g., before version 11 for
        `AllowShortEnumsOnASingleLine`), the code is not formatted. The style is tried once, on the first code to
        format, so that the backends that need no formatter neither run it nor complain about it. An empty input is
        not enough: clang-format does not read the style then."""
        self._style_checked = True
        try:
            probe = subprocess.run(["clang-format", f"-style={self.clang_format}"], input="int a;\n", capture_output=True, text=True)
        except OSError:
            self.clang_format = ""
            return
        if probe.returncode != 0:
            print(f"hikaripb: the generated code is not formatted, clang-format rejects the style: {probe.stderr.strip()}",
                  file=sys.stderr)
            self.clang_format = ""

    def format_name(self, name: str) -> str:
        """Format a name to avoid reserved words."""
        if name in self.reserved:
            return name + self.reserved_suffix
        return name

    def format_code(self, text: str):
        """Format text according to clang_format if specified."""
        if self.clang_format and not self._style_checked:
            self._check_style()
        if self.clang_format:
            process = subprocess.Popen(
                ["clang-format", f"-style={self.clang_format}"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=text)
            if process.returncode != 0:
                raise Exception(f"Clang format failed: {stderr}")
            return stdout
        return text


# The Doxygen commands that start a paragraph of their own: the admonitions, the descriptions and the labelled
# paragraphs (see "Write the comments" in the documentation of the sphinxdocs generator). The other commands (`@ref`,
# `@c`, ...) belong to the text around them.
_BLOCK_COMMANDS = (r"note|remark|warning|attention|important|hint|tip|caution|danger|error|see|sa|todo|bug|deprecated|"
                   r"pre|post|invariant|brief|details|par|since|version|author|date|copyright|return|retval|param|li")
_COMMAND_START = re.compile(r"(?<!\S)(?=[@\\](?:%s)\b)" % _BLOCK_COMMANDS)
_LIST_ITEM = re.compile(r"(?:[-+*]|\d+[.)])\s")
_BLOCK_START = re.compile(r"[@\\](?:%s)\b|%s" % (_BLOCK_COMMANDS, _LIST_ITEM.pattern))
_CODE_START = re.compile(r"```|~~~|[@\\](?:code|verbatim)\b")


def _code_end(line: str):
    """The pattern that ends the code that the line starts, None if it starts none."""
    start = _CODE_START.match(line)
    if not start:
        return None
    if start.group()[0] in "`~":
        return re.compile("^" + re.escape(start.group()))
    return re.compile(r"[@\\]end" + start.group()[1:] + r"\b")


def doc_comment(text: str) -> str:
    """Render the text of a `.proto` comment as a Doxygen comment for `clang-format` to wrap.

    A paragraph, a list item and a Doxygen command that starts a paragraph (`@note`, `@warning`, ...) are one line each,
    however long: the formatter splits them where its column limit asks for it. A comment of one line is
    `/** text */`, any other one has a line ` * text` for each, and ` *` for a blank line between two paragraphs. A line
    that is indented less than the text of the list item before it starts a paragraph after the list, and nested lists
    are flat. The lines of code (a fence, `@code`, `@verbatim`) stay as they are. A text without content gives "".
    """
    lines = []  # the lines of the comment, "" is the blank line between two paragraphs
    paragraph = False  # the last line is text that the next line of the paragraph continues
    item = None  # the indentation of the lines that continue the list item that is the last line
    code_end = None  # ends the code that is being copied
    code = []
    for raw in text.expandtabs(4).splitlines():
        if code_end:
            code.append(raw.rstrip())
            if code_end.search(raw.strip()):
                lines.extend(textwrap.dedent("\n".join(code)).splitlines())
                code_end, code = None, []
            continue
        line = raw.strip()
        if not line:
            if lines and lines[-1]:
                lines.append("")
            paragraph = False
            continue
        code_end = _code_end(line)
        if code_end:
            lines.append(line)
            paragraph = False
            continue
        indent = len(raw) - len(raw.lstrip())
        for part in _COMMAND_START.split(line):
            part = " ".join(part.split())
            if not part:
                continue
            text_line = not _BLOCK_START.match(part)
            if paragraph and text_line and (item is None or indent >= item):
                lines[-1] += " " + part
                continue
            if paragraph and text_line:
                lines.append("")  # a paragraph after a list, a blank line keeps the formatter from joining it to the item
            lines.append(re.sub(r"^\*\s", "- ", part))
            paragraph = True
            item = indent + 2 if _LIST_ITEM.match(part) else None
    while lines and not lines[-1]:
        lines.pop()
    # the comment must not end early, and a nested start is a warning of the compiler
    lines = [line.replace("*/", "* /").replace("/*", "/ *") for line in lines]
    if not lines:
        return ""
    if len(lines) == 1:
        return f"/** {lines[0]} */"
    return "\n".join(["/**", *(f" * {line}" if line else " *" for line in lines), " */"])


def order_files_by_dependency(files: list) -> list:
    """Order proto files so that every file comes after the files it imports."""
    by_name = {f.proto.name: f for f in files}
    ordered = []
    seen = set()

    def visit(f):
        if f.proto.name in seen:
            return
        seen.add(f.proto.name)
        for dep in f.proto.dependency:
            if dep in by_name:
                visit(by_name[dep])
        ordered.append(f)

    for f in files:
        visit(f)
    return ordered


def bits_needed(max_value: int) -> int:
    """Get the number of bits that hold every value from 0 to `max_value` (one at least)."""
    return max(max_value.bit_length(), 1)


# the alignment of the storage types of the C and C++ structs that are smaller than a pb_u32
SMALL_ALIGNMENTS = {"pb_u8": 1, "pb_bool": 1, "bool": 1, "pb_u16": 2}


def member_alignment(field: FieldDescriptorProto, c_type: str, rpt: bool, message=None) -> int:
    """Get the alignment of the struct member of a field as the generator knows it: a repeated field, a string and bytes
    start with a pb_u32 (count, length), an embedded message is aligned like its struct, an enum and a scalar like their
    storage type (`c_type`, the one of a compressed enum). A setting can change a type afterwards (`COMPRESS_ENUMS`, a
    `_ctype` or a callback), the order of the members is then not the best one, the offsets of the descriptors stay right."""
    if rpt or field.type in [FieldDescriptorProto.TYPE_BYTES, FieldDescriptorProto.TYPE_STRING]:
        return 4
    if field.type == FieldDescriptorProto.TYPE_MESSAGE and message is not None:
        return message.get_alignment()
    return SMALL_ALIGNMENTS.get(c_type, 4)


def add_runtime_files(response: CodeGeneratorResponse, files_dir: str, config: ConfigManager, **context) -> None:
    """Add the runtime of a backend, the files that no message changes: every template (`*.j2`) of `files_dir` is
    rendered with `config`, `p` and `P` (its prefix in lower and upper case) and the keyword arguments `context` into
    `<p>_<name>`, any other file is copied."""
    p = config.prefix.lower()
    P = config.prefix.upper()
    j2_env = jinja2.Environment(keep_trailing_newline=True)
    for file_name in sorted(os.listdir(files_dir)):
        file_path = os.path.join(files_dir, file_name)
        if not os.path.isfile(file_path):
            continue
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        new_file = response.file.add()
        if file_name.endswith(".j2"):
            new_file.name = f"{p}_{file_name[:-3]}"
            new_file.content = j2_env.from_string(content).render(p=p, P=P, config=config, **context)
        else:
            new_file.name = file_name
            new_file.content = content


def is_optional(field: FieldDescriptorProto) -> bool:
    """Determine if a field is optional."""
    if field.label == FieldDescriptorProto.LABEL_REQUIRED:
        return False
    if field.HasField('oneof_index'):
        return True
    if field.proto3_optional:
        return True
    if field.type in [FieldDescriptorProto.TYPE_BYTES, FieldDescriptorProto.TYPE_MESSAGE, FieldDescriptorProto.TYPE_STRING]:
        return True
    if field.label == FieldDescriptorProto.LABEL_REPEATED:
        return True
    return False


def find_type(types: list, type_name: str):
    """Find the message or enum a field refers to by the fully qualified `type_name` of its descriptor."""
    found = next((t for t in types if t.get_fq_name() == type_name), None)
    if found is None:
        raise Exception(f"Unable to find type {type_name}; a type that a generated message uses cannot be left out")
    return found


class ProtoEnum:
    """Class representing a protobuf enum."""

    def __init__(self, file: "ProtoFile", id, enum: EnumDescriptorProto,
                 comment: str = "", item_comments: list = [], parent: "ProtoMessage" = None):
        """
        enum: EnumDescriptorProto - The protobuf enum descriptor
        file: ProtoFile - The protobuf file containing the enum
        comment: str - The comment for the enum
        item_comments: list - List of comments for each enum value
        parent: ProtoMessage - The parent message if the enum is nested
        """
        self.id = id
        self.enum = enum
        self.comment = comment
        self.item_comments = item_comments
        self.parent = parent
        self.file = file

    def get_name(self) -> str:
        """Get the formatted name of the enum."""
        return self.file.env.format_name(self.enum.name)
    
    def get_full_name(self) -> str:
        """Get the full name of the enum including namespace."""
        return self.file.get_namespace() + self.file.env.separator + self.get_name()

    def get_fq_name(self) -> str:
        """Get the fully qualified proto name, e.g. .package.Message.Enum."""
        return (self.parent.get_fq_name() if self.parent else self.file.get_fq_prefix()) + "." + self.enum.name

    def get_max(self) -> int:
        """Get the maximum value of the enum."""
        return max([v.number for v in self.enum.value])

    def get_members(self) -> list:
        """Get list of enum members."""
        members = []
        for idx, v in enumerate(self.enum.value):
            members.append({
                "name": self.file.env.format_name(v.name),
                "number": v.number,
                "comment": self.item_comments[idx] if len(self.item_comments) else "",
            })
        return sorted(members, key=lambda x: x["number"])


class ProtoMessage:
    """Class representing a protobuf message."""

    def __init__(self, file: "ProtoFile", id, msg: DescriptorProto, comment: str = "", field_comments: list[str] = [], parent: "ProtoMessage" = None):
        """
        msg: DescriptorProto - The protobuf message descriptor
        file: ProtoFile - The protobuf file containing the message
        comment: str - The comment for the message
        field_comments: list - List of comments for each field in the message
        parent: ProtoMessage - The parent message if this message is nested
        """
        self.id = id
        self.msg = msg
        self.file = file
        self.parent = parent
        self.comment = comment
        self.field_comments = field_comments

    def get_name(self) -> str:
        """Get the formatted name of the message."""
        return self.file.env.format_name(self.msg.name)

    def get_full_name(self) -> str:
        """Get the full name of the message including namespace."""
        return self.file.get_namespace() + self.file.env.separator + self.get_name()

    def get_fq_name(self) -> str:
        """Get the fully qualified proto name, e.g. .package.Message.Nested."""
        return (self.parent.get_fq_name() if self.parent else self.file.get_fq_prefix()) + "." + self.msg.name

    def get_max_tag(self) -> int:
        """Get the largest field number of the message (0 for a message without fields)."""
        return max((f.number for f in self.msg.field), default=0)

    def get_presence_size(self) -> int:
        """Get the size in bytes of the presence bitmap for the message (one bit per field number up to the largest, one
        byte at least, as an array cannot be empty)."""
        size = self.get_max_tag() // 8 + 1
        if size > MAX_PRESENCE_SIZE:
            raise Exception(f"Message {self.get_full_name()}: the field number {self.get_max_tag()} needs a presence bitmap of "
                            f"{size} bytes, but the descriptors address the fields with 16-bit offsets; use field numbers "
                            f"up to {MAX_PRESENCE_SIZE * 8 - 1}")
        return size

    def get_tag_groups(self) -> dict:
        """
        Get groups of consecutive tags in the message.
        Returns a dictionary where keys are offsets and values are lists of tags.
        """
        tags = sorted([f.number for f in self.msg.field])
        if len(tags) == 0:
            return {}

        groups = [[tags[0]]]

        for tag in tags[1:]:
            if tag == groups[-1][-1] + 1:
                groups[-1].append(tag)
            else:
                groups.append([tag])

        res = {}
        offset = 0
        for g in groups:
            res[offset] = g
            offset += len(g)

        return res

    def _process_field(self, idx: int, field: FieldDescriptorProto) -> dict:
        """Process a field and return its information as a dictionary."""
        # get group name from oneof_index
        group = ""
        if field.HasField('oneof_index') and not self.msg.oneof_decl[field.oneof_index].name.startswith("_"):
            group = self.file.env.format_name(
                self.msg.oneof_decl[field.oneof_index].name)

        # fill in item info
        res = {
            "tag": field.number,
            "name": self.file.env.format_name(field.name),
            "group": group,
            "rpt": field.label == FieldDescriptorProto.LABEL_REPEATED,
            "comment": self.field_comments[idx] if len(self.field_comments) else "",
            "proto_type": field.type,
            "optional": is_optional(field),
        }
        return res

    def get_members(self) -> list[dict]:
        """Get list of members"""
        memebers = []
        for idx, f in enumerate(self.msg.field):
            memebers.append(self._process_field(idx, f))
        return memebers

    def get_grouped_members(self) -> dict:
        """Get members of the message grouped by oneof fields."""
        members = self.get_members()
        groups = {}
        for m in members:
            if m["group"] not in groups:
                groups[m["group"]] = []
            groups[m["group"]].append(m)
        return groups

    def get_layout(self) -> list[dict]:
        """Get the members of the struct of the message in the order of the struct, as units: a field that is not in a
        oneof, or a oneof (its tag and its union). The presence bitmap of one-byte entries starts the struct, so the
        units are sorted by alignment, smallest first: the members of one byte follow the bitmap without padding, then
        those of two bytes, then the others. Within an alignment the order of the .proto file is kept. The backend gives
        every member its alignment as "align"; a oneof is aligned by its pb_u32 tag."""
        units = []
        for group, items in self.get_grouped_members().items():
            if group == "":
                units.extend({"group": "", "fields": [item], "align": item.get("align", 4)} for item in items)
            else:
                units.append({"group": group, "fields": items, "align": 4})
        return sorted(units, key=lambda unit: unit["align"])

    def get_alignment(self) -> int:
        """Get the alignment of the struct of the message: the largest of its members, 1 for the presence bitmap."""
        if not hasattr(self, "_alignment"):
            # a message that contains itself (only possible through a callback) must not recurse forever
            self._alignment = 4
            self._alignment = max([1] + [unit["align"] for unit in self.get_layout()])
        return self._alignment

    def get_optional_members(self) -> list[dict]:
        """Get a list of optional fields in the message."""
        return list(filter(lambda f: f["optional"], self.get_members()))


class Comment:
    """Enum for comment path types."""
    FIELD = 2
    MESSAGE = 4
    ENUM = 5
    NESTED_TYPE = 3
    NESTED_ENUM = 4


class ProtoFile:
    enums: list["ProtoEnum"]
    messages: list["ProtoMessage"]
    comments: dict

    """Class representing a protobuf file."""

    def __init__(self, proto: FileDescriptorProto, env: Environment, namespaces: Namespaces | None = None):
        if proto.syntax != "proto3":
            raise Exception("Unsupported proto syntax")
        self.proto = proto
        self.env = env
        self.namespaces = namespaces or Namespaces()

        self.load_comments()
        self.load_messages()
        self.load_enums()

        # resolve parent references for messages and enums
        for msg in self.messages:
            if msg.parent is not None:
                parent = next(
                    (m for m in self.messages if m.id == msg.parent), None)
                msg.parent = parent
        for enum in self.enums:
            if enum.parent is not None:
                parent = next(
                    (m for m in self.messages if m.id == enum.parent), None)
                enum.parent = parent

    def _create_message(self, id, msg: DescriptorProto, comment: str = "", field_comments: list[str] = [], parent: "ProtoMessage" = None) -> ProtoMessage:
        """Create a ProtoMessage instance."""
        return ProtoMessage(self, id, msg, comment, field_comments, parent)

    def _create_enum(self, id, enum: EnumDescriptorProto, comment: str = "", item_comments: list[str] = [], parent: "ProtoMessage" = None) -> ProtoEnum:
        """Create a ProtoEnum instance."""
        return ProtoEnum(self, id, enum, comment, item_comments, parent)

    def _load_enum(self, enum: EnumDescriptorProto, id: tuple, parentid: tuple | None) -> None:
        """Add one enum; `id` is its path in the file descriptor, `parentid` the path of its message."""
        comm = [self.comments.get((*id, Comment.FIELD, vidx), "") for vidx, _ in enumerate(enum.value)]
        self.enums.append(self._create_enum(id, enum, self.comments.get(id, ""), comm, parentid))

    def _load_nested_enums(self, msg: DescriptorProto, id: tuple) -> None:
        """Add the enums declared in a message and in the messages nested in it, at any depth."""
        for eidx, enum in enumerate(msg.enum_type):
            self._load_enum(enum, (*id, Comment.NESTED_ENUM, eidx), id)
        for nidx, nested in enumerate(msg.nested_type):
            self._load_nested_enums(nested, (*id, Comment.NESTED_TYPE, nidx))

    def load_enums(self) -> None:
        """Load enums from the proto file."""
        self.enums = []
        for idx, enum in enumerate(self.proto.enum_type):
            self._load_enum(enum, (Comment.ENUM, idx), None)
        for midx, msg in enumerate(self.proto.message_type):
            self._load_nested_enums(msg, (Comment.MESSAGE, midx))

    def _load_message(self, msg: DescriptorProto, id: tuple, parentid: tuple | None) -> None:
        """Add a message after the messages nested in it, at any depth; `parentid` is the path of its message."""
        for nidx, nested in enumerate(msg.nested_type):
            self._load_message(nested, (*id, Comment.NESTED_TYPE, nidx), id)
        comm = [self.comments.get((*id, Comment.FIELD, fidx), "") for fidx, _ in enumerate(msg.field)]
        self.messages.append(self._create_message(id, msg, self.comments.get(id, ""), comm, parentid))

    def load_messages(self) -> None:
        """Load messages from the proto file."""
        self.messages = []
        for idx, msg in enumerate(self.proto.message_type):
            self._load_message(msg, (Comment.MESSAGE, idx), None)

    def load_comments(self) -> None:
        """Load comments from source_code_info."""
        self.comments = {}
        if self.proto.HasField("source_code_info"):
            for loc in self.proto.source_code_info.location:
                if loc.leading_comments or loc.trailing_comments:
                    cmt = loc.trailing_comments.removeprefix("*").strip()
                    cmt += "\n"
                    cmt += loc.leading_comments.removeprefix("*").strip()
                    self.comments[tuple(loc.path)] = cmt.strip()

    def get_namespace(self) -> str:
        """get namespace based on the proto package, as the namespace override leaves it"""
        return self.env.separator.join([self.env.format_name(n) for n in self.namespaces.parts(self.proto.package)])

    def get_fq_prefix(self) -> str:
        """Get the fully qualified proto name of the package ("" without one)."""
        return "." + self.proto.package if self.proto.package else ""

    def get_type_names(self, item: "ProtoMessage | ProtoEnum") -> list[str]:
        """The names with which the option `ignore` can name a message or enum of the file."""
        package = self.proto.package
        chain = item.get_fq_name()[len(self.get_fq_prefix()) + 1:]
        return [item.get_full_name(), *type_names(package, self.namespaces.package(package), chain)]

    def drop_ignored(self, ignored: Ignored) -> None:
        """Leave out the enums and messages that the option `ignore` names."""
        self.enums = [e for e in self.enums if not ignored.matches(self.get_type_names(e))]
        self.messages = [m for m in self.messages if not ignored.matches(self.get_type_names(m))]

    def get_name(self) -> str:
        """ Get the name of this proto file"""
        return self.proto.name

    def get_deps(self) -> list[str]:
        """ Get the dependencies of this proto file """
        return self.proto.dependency