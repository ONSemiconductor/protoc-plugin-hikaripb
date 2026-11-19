# Copyright (c) 2025 Semiconductor Components Industries, LLC ("onsemi")
# SPDX-License-Identifier: GPL-3.0-or-later

import math
import os
import re
import jinja2 as jinja
import common
from config import ConfigManager
from names import Ignored, Namespaces
from google.protobuf.compiler.plugin_pb2 import CodeGeneratorResponse, CodeGeneratorRequest
from google.protobuf.descriptor_pb2 import FileDescriptorProto, FieldDescriptorProto, EnumDescriptorProto, DescriptorProto
import logging
import sys

env = jinja.Environment(
    loader=jinja.PackageLoader("c.parser"),
    trim_blocks=True,
    lstrip_blocks=True
)
# {{ comment | doc }} is the comment of a .proto item as a Doxygen comment, long lines are left to clang-format
env.filters["doc"] = common.doc_comment

naming = common.Environment(
    reserved_words=[
        "auto", "break", "case", "char", "const", "continue", "default", "do",
        "double", "else", "enum", "extern", "float", "for", "goto", "if",
        "inline", "int", "long", "register", "restrict", "return", "short", "signed",
        "sizeof", "static", "struct", "switch", "typedef", "union", "unsigned", "void",
        "volatile", "while"
    ],
    name_separator="_",
    reserved_suffix="_",
    clang_format="{BasedOnStyle: Google, TabWidth: 4, IndentWidth: 4, AlignConsecutiveMacros: true, ColumnLimit: 120, AllowShortEnumsOnASingleLine: false}"
)

# Prefix variables — overwritten by generate_c() before any parsing
_P = "HIKARIPB"   # uppercase prefix
_p = "hikaripb"   # lowercase prefix
_incpath = ""      # include path prefix for lib/ files
_cfgpath = ""      # include path prefix for config file
_doc_parent_group = ""
_doc_protocol_parent_group = ""
_doc_protocol_group_id = "hikaripb_protocol"
_doc_protocol_group_title = "Protocol"
_doc_protocol_root_header = ""

VARINT_TYPE_MAP = {
    FieldDescriptorProto.TYPE_UINT32:   ("pb_u32", f"{_P}_ITEM_VARINT_32"),
    FieldDescriptorProto.TYPE_SINT32:   ("pb_s32", f"{_P}_ITEM_VARINT_S32"),
    FieldDescriptorProto.TYPE_BOOL:     ("pb_bool", f"{_P}_ITEM_BOOL"),
}

FIXED_TYPE_MAP = {
    FieldDescriptorProto.TYPE_FLOAT:    "float",
    FieldDescriptorProto.TYPE_FIXED32:  "pb_u32",
    FieldDescriptorProto.TYPE_SFIXED32: "pb_s32",
}


def get_c_type(num: int) -> str:
    if num < 2**8 - 1:
        return "pb_u8"
    if num < 2**16 - 1:
        return "pb_u16"
    if num < 2**32 - 1:
        return "pb_u32"
    raise Exception(f"Unable to convert number {num} to type")


def unsigned_type(bits: int) -> str:
    """Get the smallest of the types `pb_u8`, `pb_u16` and `pb_u32` that has `bits` bits."""
    if bits > 32:
        raise Exception(f"Unable to convert {bits} bits to type")
    return "pb_u8" if bits <= 8 else "pb_u16" if bits <= 16 else "pb_u32"


def _prefix_generated_proto_name(name: str) -> str:
    """Prefix the basename of a generated protobuf file name."""
    directory, separator, basename = name.rpartition("/")
    if basename.startswith(f"{_p}_"):
        return name
    if separator:
        return f"{directory}/{_p}_{basename}"
    return f"{_p}_{basename}"


class ProtoEnum(common.ProtoEnum):
    """ Represents a protobuf enum definition """

    parent: "ProtoMessage" = None
    file: "ProtoFile" = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_c_type(self) -> str:
        """ Get the C type that can hold the largest enum value """
        return get_c_type(self.get_max())

    def get_item_type(self) -> str:
        """ Get the item type for this enum when it is stored in the smallest type """
        c_type = self.get_c_type()
        if c_type == "pb_u8":
            return f"{_P}_ITEM_VARINT_8"
        if c_type == "pb_u16":
            return f"{_P}_ITEM_VARINT_16"
        if c_type == "pb_u32":
            return f"{_P}_ITEM_VARINT_32"
        raise Exception(f"Unable to convert c_type {c_type} to item type")

    def get_content(self) -> str:
        """ Get the C++ code for this enum """
        return env.get_template("enum.j2").render(
            comment=self.comment,
            name=self.get_name(),
            fullname=self.get_full_name(),
            type=self.get_c_type(),
            item_type=self.get_item_type(),
            items=self.get_members(),
            p=_p, P=_P,
        )


class ProtoMessage(common.ProtoMessage):
    """ Represents a protobuf message definition """

    parent: "ProtoMessage" = None
    file: "ProtoFile" = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proxy = ProxyMessage(*args, **kwargs)

    def _process_field(self, idx: int, f: FieldDescriptorProto) -> dict:
        """ Parse field type into type information """
        res = super()._process_field(idx, f)

        if f.type == FieldDescriptorProto.TYPE_ENUM:
            enum = common.find_type(ENUMS, f.type_name)
            res["enum_type"] = enum.get_full_name()
            res["c_type"] = enum.get_full_name() + "_t"
            # a macro of the enum: its storage depends on the setting COMPRESS_ENUMS
            res["type"] = enum.get_full_name() + "_itemtype"
            res["align"] = common.member_alignment(f, enum.get_c_type(), res["rpt"])
        elif f.type in VARINT_TYPE_MAP:
            res["c_type"] = VARINT_TYPE_MAP[f.type][0]
            res["type"] = VARINT_TYPE_MAP[f.type][1]
        elif f.type in FIXED_TYPE_MAP:
            res["c_type"] = FIXED_TYPE_MAP[f.type]
            res["type"] = f"{_P}_ITEM_FIXED_32"
        elif f.type == FieldDescriptorProto.TYPE_MESSAGE:
            msg = common.find_type(MESSAGES, f.type_name)
            res["c_type"] = msg.get_full_name()
            res["type"] = f"{_P}_ITEM_MESSAGE"
            res["align"] = common.member_alignment(f, res["c_type"], res["rpt"], msg)
        elif f.type in [FieldDescriptorProto.TYPE_BYTES, FieldDescriptorProto.TYPE_STRING]:
            res["c_type"] = "pb_u8*"
            res["array_type"] = "string" if f.type == FieldDescriptorProto.TYPE_STRING else "bytes"
            res["string"] = "true" if f.type == FieldDescriptorProto.TYPE_STRING else "false"
            res["type"] = f"{_P}_ITEM_BYTES"
        if "align" not in res:
            res["align"] = common.member_alignment(f, res.get("c_type", ""), res["rpt"])

        return res

    def get_tag_groups(self):
        """ Get tag groups with zero-based indexes """
        return {k : [i - 1 for i in v] for k, v in super().get_tag_groups().items()}

    def get_content(self):
        """ Get the C header code for this message """
        return env.get_template("message.j2").render(
            fullname=self.get_full_name(),
            msgname=self.get_name(),
            comment=self.comment,
            members=self.get_grouped_members(),
            layout=self.get_layout(),
            tag_groups=self.get_tag_groups(),
            descriptors=self.get_members(),
            optionals=self.get_optional_members(),
            presence_size=self.get_presence_size(),
            proxy=self.proxy.get_content(),
            p=_p, P=_P,
        )

    def get_src_content(self):
        """ Get the C source code for this message """
        return env.get_template("message_src.j2").render(
            fullname=self.get_full_name(),
            msgname=self.get_name(),
            members=self.get_grouped_members(),
            tag_groups=self.get_tag_groups(),
            descriptors=self.get_members(),
            optionals=self.get_optional_members(),
            presence_size=self.get_presence_size(),
            p=_p, P=_P,
        )


class ProxyMessage(common.ProtoMessage):
    """ Represents a protobuf message definition for proxy generation """

    parent: "ProtoMessage" = None
    file: "ProtoFile" = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _process_field(self, idx: int, f: FieldDescriptorProto) -> dict:
        """ Parse field type into proxy type information """
        res = super()._process_field(idx, f)

        if f.type == FieldDescriptorProto.TYPE_ENUM:
            enum = common.find_type(ENUMS, f.type_name)
            temp_ctype = enum.get_full_name()
            res.update({
                "type": "varint",
                "param": temp_ctype,
                "c_type": "pb_u32",
                "enum": "true"
            })
        elif f.type in VARINT_TYPE_MAP:
            res.update({
                "type": "varint",
                "param": VARINT_TYPE_MAP[f.type][0],
                "c_type": "pb_s32" if VARINT_TYPE_MAP[f.type][0] == "pb_s32" else "pb_u32",
                "enum": "false"
            })
        elif f.type in FIXED_TYPE_MAP:
            res.update({
                "type": "fixed",
                "param": FIXED_TYPE_MAP[f.type],
                "c_type": FIXED_TYPE_MAP[f.type],
                "enum": "false"
            })
        elif f.type == FieldDescriptorProto.TYPE_MESSAGE:
            msg = common.find_type(MESSAGES, f.type_name)
            res.update({
                "type": "message",
                "c_type": msg.get_full_name(),
                "enum": "false"
            })
        elif f.type in [FieldDescriptorProto.TYPE_STRING, FieldDescriptorProto.TYPE_BYTES]:
            res.update({
                "type": "bytes",
                "c_type": "pb_u8*",
                "enum": "false"
            })
        else:
            raise Exception(f"Unsupported field type {f.type} for {f.name}")

        # the encoder functions are named after the type without the prefix: encode_varint_u32, encode_fixed_float
        res["suffix"] = res["c_type"].removeprefix("pb_")
        return res

    def get_content(self):
        """ Get the C proxy code for this message """
        return env.get_template("proxy_message.j2").render(
            msgname=self.get_name(),
            fullname=self.get_full_name(),
            comment=self.comment,
            items=self.get_members(),
            p=_p, P=_P,
        )


class ProtoFile(common.ProtoFile):
    """ Represents a protobuf file definition """

    enums: list[ProtoEnum] = []
    messages: list[ProtoMessage] = []

    def __init__(self, proto: FileDescriptorProto, namespaces: Namespaces):
        super().__init__(proto, naming, namespaces)

    def _create_enum(self, *args, **kwargs) -> ProtoEnum:
        return ProtoEnum(self, *args, **kwargs)

    def _create_message(self, *args, **kwargs) -> ProtoMessage:
        return ProtoMessage(self, *args, **kwargs)

    def get_hdr_name(self) -> str:
        """ Get the name of the header file for this proto file """
        return ProtoFile.hdr_name(self.get_name())

    def get_src_name(self) -> str:
        """ Get the name of the source file for this proto file """
        return ProtoFile.src_name(self.get_name())

    def get_protocol_file_group_id(self) -> str:
        """ Get a stable per-proto Doxygen group id under the protocol parent group """
        proto_name_no_ext = re.sub(r'\.proto$', '', self.get_name())
        safe_name = proto_name_no_ext.replace("/", "_").replace(".", "_")
        return f"{_doc_protocol_group_id}_{safe_name}"

    def get_protocol_file_topic(self) -> str:
        """ Get human-readable per-proto topic title (basename only) """
        proto_basename = self.get_name().split('/')[-1]
        proto_topic = re.sub(r'\.proto$', '', proto_basename)
        return proto_topic.replace('_', ' ').title()

    def get_hdr_content(self) -> str:
        """ Get the C header content for this proto file """
        items = []

        # put enums & embedded enums first
        for enum in self.enums:
            items.append(enum.get_content())
        # put messages & embedded messages
        for msg in self.messages:
            items.append(msg.get_content())

        return render_header(
            hdr_name=self.get_hdr_name(),
            dependencies=[ProtoFile.hdr_name(d)
                          for d in self.proto.dependency],
            items=items,
            protocol_define_root_group=(self.get_hdr_name() == _doc_protocol_root_header),
            protocol_file_group_id=self.get_protocol_file_group_id(),
            protocol_file_topic=self.get_protocol_file_topic(),
        )

    def get_src_content(self) -> str:
        """ Get the C source content for this proto file """
        # put messages & embedded messages
        return render_source(self.get_hdr_name(), [msg.get_src_content() for msg in self.messages])

    @staticmethod
    def hdr_name(proto: str) -> str:
        """ get name of header file based on the proto file name """
        return re.sub(r'(.*)\.proto', lambda match: _prefix_generated_proto_name(f"{match.group(1)}.pb.h"), proto)

    @staticmethod
    def src_name(proto: str) -> str:
        """ get name of source file based on the proto file name """
        return re.sub(r'(.*)\.proto', lambda match: _prefix_generated_proto_name(f"{match.group(1)}.pb.c"), proto)


def render_header(hdr_name: str, dependencies: list[str], items: list[str],
                  protocol_define_root_group: bool, protocol_file_group_id: str,
                  protocol_file_topic: str) -> str:
    """ Render a C header holding the pre-rendered enum/message items """
    return env.get_template("header.j2").render(
        hdr_name=hdr_name,
        hdr_guard=hdr_name.replace("/", "_").replace(".", "_").upper(),
        dependencies=dependencies,
        items=items,
        p=_p, P=_P, incpath=_incpath, cfgpath=_cfgpath,
        doc_parent_group=_doc_parent_group,
        doc_protocol_parent_group=_doc_protocol_parent_group,
        doc_protocol_group_id=_doc_protocol_group_id,
        doc_protocol_group_title=_doc_protocol_group_title,
        protocol_define_root_group=protocol_define_root_group,
        protocol_file_group_id=protocol_file_group_id,
        protocol_file_topic=protocol_file_topic,
    )


def render_source(hdr_name: str, items: list[str]) -> str:
    """ Render the C source that includes hdr_name and holds the pre-rendered message items """
    return env.get_template("source.j2").render(
        dep=hdr_name,
        items=items,
        p=_p, P=_P, incpath=_incpath, cfgpath=_cfgpath,
    )


ENUMS: list[ProtoEnum] = []
MESSAGES: list[ProtoMessage] = []
FILES: list[ProtoFile] = []


def generate_c(request: CodeGeneratorRequest,
               response: CodeGeneratorResponse,
               config: ConfigManager) -> None:
    """ Generate C code from protobuf definitions """
    global _P, _p, _incpath, _cfgpath, VARINT_TYPE_MAP
    global _doc_parent_group, _doc_protocol_parent_group, _doc_protocol_group_id, _doc_protocol_group_title, _doc_protocol_root_header
    _p = config.prefix.lower()
    _P = config.prefix.upper()
    _incpath = config.include_path
    _cfgpath = config.config_path
    _doc_parent_group = config.doc_parent_group
    _doc_protocol_parent_group = config.doc_protocol_parent_group or config.doc_parent_group
    _doc_protocol_group_id = config.doc_protocol_group_id
    _doc_protocol_group_title = config.doc_protocol_group_title
    _doc_protocol_root_header = (_prefix_generated_proto_name(config.doc_protocol_root_header)
                                 if config.doc_protocol_root_header else "")
    single_file = config.single_file
    VARINT_TYPE_MAP = {
        FieldDescriptorProto.TYPE_UINT32: ("pb_u32", f"{_P}_ITEM_VARINT_32"),
        FieldDescriptorProto.TYPE_SINT32: ("pb_s32",  f"{_P}_ITEM_VARINT_S32"),
        FieldDescriptorProto.TYPE_BOOL:   ("pb_bool", f"{_P}_ITEM_BOOL"),
    }

    # Load all proto files from request
    namespaces = Namespaces((proto.package for proto in request.proto_file), config.namespace_override)
    ignored = Ignored(config.ignore)
    for proto in sorted(request.proto_file, key=lambda file_obj: file_obj.name):
        p = ProtoFile(proto, namespaces)
        p.drop_ignored(ignored)
        ENUMS.extend(p.enums)
        MESSAGES.extend(p.messages)
        FILES.append(p)
    if not _doc_protocol_root_header and FILES:
        # without doc_protocol_root_header, the header of the first .proto file (in name order) opens the group
        _doc_protocol_root_header = FILES[0].get_hdr_name()

    # Generate message files
    if single_file:
        # Merge every .proto file (dependencies first) into one header + one source
        ordered = common.order_files_by_dependency(FILES)
        hdr_name = _prefix_generated_proto_name(f"{single_file}.pb.h")
        src_name = _prefix_generated_proto_name(f"{single_file}.pb.c")

        hdr_items = []
        for f in ordered:
            hdr_items.extend(e.get_content() for e in f.enums)
            hdr_items.extend(m.get_content() for m in f.messages)
        src_items = [m.get_src_content() for f in ordered for m in f.messages]

        file = response.file.add()
        file.name = hdr_name
        file.content = naming.format_code(render_header(
            hdr_name=hdr_name,
            dependencies=[],
            items=hdr_items,
            protocol_define_root_group=True,
            protocol_file_group_id=f"{_doc_protocol_group_id}_{single_file}",
            protocol_file_topic=single_file.replace("_", " ").title(),
        ))

        file = response.file.add()
        file.name = src_name
        file.content = naming.format_code(render_source(hdr_name, src_items))
        generated_headers = [hdr_name]
    else:
        for f in FILES:
            file = response.file.add()
            file.name = f.get_hdr_name()
            file.content = naming.format_code(f.get_hdr_content())

            file = response.file.add()
            file.name = f.get_src_name()
            file.content = naming.format_code(f.get_src_content())
        generated_headers = [f.get_hdr_name() for f in FILES]

    # Generate binding source file
    f = response.file.add()
    f.name = f"{_p}_bindings.c"
    f.content = naming.format_code(
        env.get_template("bindings.j2").render(
            data=[m.get_full_name() for m in MESSAGES],
            dependencies=generated_headers,
            p=_p, P=_P, incpath=_incpath, cfgpath=_cfgpath,
        )
    )

    # Generate binding header file
    f = response.file.add()
    f.name = f"{_p}_bindings.h"
    f.content = naming.format_code(
        env.get_template("bindings_hdr.j2").render(
            data=[m.get_full_name() for m in MESSAGES],
            p=_p, P=_P, incpath=_incpath, cfgpath=_cfgpath,
            doc_protocol_group_id=_doc_protocol_group_id,
        )
    )

    # Generate default config file
    array_items = []
    repeated_items = []
    callback_items = []
    integer_items = []
    for m in MESSAGES:
        for item in m.get_members():
            callback_items.append(f"{m.get_full_name()}_{item['name']}")
            if item["proto_type"] == FieldDescriptorProto.TYPE_UINT32:
                integer_items.append(f"{m.get_full_name()}_{item['name']}")
            if item["rpt"]:
                repeated_items.append(f"{m.get_full_name()}_{item['name']}")
            if item["proto_type"] in [FieldDescriptorProto.TYPE_STRING, FieldDescriptorProto.TYPE_BYTES]:
                array_items.append(f"{m.get_full_name()}_{item['name']}")

    f = response.file.add()
    f.name = f"{_p}_config_default.h"
    f.content = naming.format_code(
        env.get_template("default_cfg.j2").render(
            messages=[m.get_full_name() for m in MESSAGES],
            arrays=array_items,
            repeated=repeated_items,
            callbacks=callback_items,
            integers=integer_items,
            p=_p, P=_P,
        )
    )

    # the types of a field number and of a message id are the smallest ones that hold the largest of the schema
    max_tag = max((m.get_max_tag() for m in MESSAGES), default=0)
    max_msgid = max(len(MESSAGES) - 1, 0)
    common.add_runtime_files(response, os.path.join(os.path.dirname(__file__), "files"), config,
                             max_tag=max_tag, tag_type=unsigned_type(common.bits_needed(max_tag)),
                             msg_count=len(MESSAGES), msgid_type=unsigned_type(common.bits_needed(max_msgid)))