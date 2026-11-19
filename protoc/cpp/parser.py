# Copyright (c) 2025 Semiconductor Components Industries, LLC ("onsemi")
# SPDX-License-Identifier: GPL-3.0-or-later

import jinja2 as jinja
import os
import re
from google.protobuf.compiler.plugin_pb2 import CodeGeneratorResponse, CodeGeneratorRequest
from google.protobuf.descriptor_pb2 import FileDescriptorProto, FieldDescriptorProto, EnumDescriptorProto, DescriptorProto
import common
from config import ConfigManager
from names import Ignored, Namespaces
import sys

env = jinja.Environment(
    loader=jinja.PackageLoader("cpp.parser"),
    trim_blocks=True,
    lstrip_blocks=True
)
# {{ comment | doc }} is the comment of a .proto item as a Doxygen comment, long lines are left to clang-format
env.filters["doc"] = common.doc_comment

naming = common.Environment(
    reserved_words=[
        "alignas", "alignof", "and", "and_eq", "asm", "auto", "bitand", "bitor",
        "bool", "break", "case", "catch", "char", "char8_t", "char16_t", "char32_t",
        "class", "compl", "concept", "const", "consteval", "constexpr", "constinit", "const_cast",
        "continue", "co_await", "co_return", "co_yield", "decltype", "default", "delete", "do",
        "double", "dynamic_cast", "else", "enum", "explicit", "export", "extern", "false",
        "float", "for", "friend", "goto", "if", "inline", "int", "long",
        "mutable", "namespace", "new", "noexcept", "not", "not_eq", "nullptr", "operator",
        "or", "or_eq", "private", "protected", "public", "register", "reinterpret_cast", "requires",
        "return", "short", "signed", "sizeof", "static", "static_assert", "static_cast", "struct",
        "switch", "template", "this", "thread_local", "throw", "true", "try", "typedef",
        "typeid", "typename", "union", "unsigned", "using", "virtual", "void", "volatile",
        "wchar_t", "while", "xor", "xor_eq",
        # members of every generated message struct
        "clear", "getItemDescriptor", "getTagName", "print", "MSGID", "WrProxy"
    ],
    name_separator="::",
    reserved_suffix="_",
    clang_format="{BasedOnStyle: Google, TabWidth: 4, IndentWidth: 4, AlignConsecutiveMacros: true, ColumnLimit: 120, AllowShortEnumsOnASingleLine: false}"
)

# Prefix variables — overwritten by generate_cpp() before any parsing
_P = "HIKARIPB"   # uppercase prefix (macro prefix)
_p = "hikaripb"   # lowercase prefix (namespace + generated runtime file prefix)
_incpath = ""      # include path prefix for runtime files
_cfgpath = ""      # include path prefix for config file
_doc_parent_group = ""
_doc_protocol_parent_group = ""
_doc_protocol_group_id = "hikaripb_protocol"
_doc_protocol_group_title = "Protocol"
_doc_protocol_root_header = ""

C_TYPE_MAP = {
    "pb_u32": f"{_p}::ItemType::VARINT_32",
    "pb_u16": f"{_p}::ItemType::VARINT_16",
    "pb_u8": f"{_p}::ItemType::VARINT_8",
    "pb_s32": f"{_p}::ItemType::VARINT_S32",
    "bool": f"{_p}::ItemType::BOOL",
    "float": f"{_p}::ItemType::FIXED_32",
}

VARINT_TYPE_MAP = {
    FieldDescriptorProto.TYPE_UINT32:   ("pb_u32", C_TYPE_MAP["pb_u32"]),
    FieldDescriptorProto.TYPE_SINT32:   ("pb_s32", C_TYPE_MAP["pb_s32"]),
    FieldDescriptorProto.TYPE_BOOL:     ("bool", C_TYPE_MAP["bool"]),
}

FIXED_TYPE_MAP = {
    FieldDescriptorProto.TYPE_FLOAT:    "float",
    FieldDescriptorProto.TYPE_FIXED32:  "pb_u32",
    FieldDescriptorProto.TYPE_SFIXED32: "pb_s32",
}


def get_c_type(num: int) -> str:
    """ Get the smallest C type that can hold the given number """
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
        if c_type in C_TYPE_MAP.keys():
            return C_TYPE_MAP[c_type]
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
        # fill in item info
        if f.type == FieldDescriptorProto.TYPE_ENUM:
            enum = common.find_type(ENUMS, f.type_name)
            res["c_type"] = enum.get_name() if enum.file.get_namespace(
            ) == self.file.get_namespace() else enum.get_full_name()
            # a macro of the enum: its storage depends on the setting COMPRESS_ENUMS
            res["type"] = enum.get_full_name().replace("::", "_") + "_itemtype"
            res["align"] = common.member_alignment(f, enum.get_c_type(), res["rpt"])
        elif f.type in VARINT_TYPE_MAP:
            res["c_type"] = VARINT_TYPE_MAP[f.type][0]
            res["type"] = VARINT_TYPE_MAP[f.type][1]
        elif f.type in FIXED_TYPE_MAP:
            res["c_type"] = FIXED_TYPE_MAP[f.type]
            res["type"] = f"{_p}::ItemType::FIXED_32"
        elif f.type == FieldDescriptorProto.TYPE_MESSAGE:
            msg = common.find_type(MESSAGES, f.type_name)
            res["c_type"] = msg.get_name() if msg.file.get_namespace(
            ) == self.file.get_namespace() else msg.get_full_name()
            res["type"] = f"{_p}::ItemType::MESSAGE"
            res["align"] = common.member_alignment(f, res["c_type"], res["rpt"], msg)
        elif f.type in [FieldDescriptorProto.TYPE_BYTES, FieldDescriptorProto.TYPE_STRING]:
            res["c_type"] = "pb_u8*"
            res["array_type"] = "string" if f.type == FieldDescriptorProto.TYPE_STRING else "bytes"
            res["type"] = f"{_p}::ItemType::BYTES"
        if "align" not in res:
            res["align"] = common.member_alignment(f, res.get("c_type", ""), res["rpt"])
        return res

    def get_tag_groups(self):
        """ Get tag groups with zero-based indexes """
        return {k : [i - 1 for i in v] for k, v in super().get_tag_groups().items()}

    def get_content(self):
        """ Get the C++ code for this message """
        return env.get_template("message.j2").render(
            msgname=self.get_name(),
            fullname=self.get_full_name(),
            comment=self.comment,
            proxy=self.proxy.get_content(),
            members=self.get_grouped_members(),
            layout=self.get_layout(),
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
            res.update({
                "type": "varint",
                "param": enum.get_name() if enum.file.get_namespace() == self.file.get_namespace() else enum.get_full_name(),
                "c_type": "pb_u32",
                "encode_func": f"{_p}::Encoder<>::encode_varint32",
            })
        elif f.type in VARINT_TYPE_MAP:
            res.update({
                "type": "varint",
                "param": VARINT_TYPE_MAP[f.type][0],
                "c_type": "pb_s32" if VARINT_TYPE_MAP[f.type][0] == "pb_s32" else "pb_u32",
                "encode_func": f"{_p}::Encoder<>::encode_varint32",
            })
        elif f.type in FIXED_TYPE_MAP:
            res.update({
                "type": "fixed",
                "param": FIXED_TYPE_MAP[f.type],
                "c_type": FIXED_TYPE_MAP[f.type],
                "encode_func": f"{_p}::Encoder<>::encode_fixed32",
            })
        elif f.type == FieldDescriptorProto.TYPE_MESSAGE:
            msg = common.find_type(MESSAGES, f.type_name)
            res.update({
                "type": "handle",
                "c_type": (msg.get_name() if self.file.get_namespace() == msg.file.get_namespace() else msg.get_full_name()),
            })
        elif f.type in [FieldDescriptorProto.TYPE_STRING, FieldDescriptorProto.TYPE_BYTES]:
            res.update({
                "type": "handle",
                "c_type": f"{_p}::BytesProxy",
            })
        else:
            raise Exception(f"Unsupported field type {f.type} for {f.name}")

        # repeated fields are handled differently
        if f.label == FieldDescriptorProto.LABEL_REPEATED:
            if f.type in [FieldDescriptorProto.TYPE_MESSAGE, FieldDescriptorProto.TYPE_STRING, FieldDescriptorProto.TYPE_BYTES]:
                res["type"] = "rpt_sparse"
            else:
                res["type"] = "rpt_dense"
        return res

    def get_content(self):
        """ Get the C++ code for this proxy message """
        return env.get_template("proxy_message.j2").render(
            msgname=self.get_name(),
            fullname=self.get_full_name(),
            comment=self.comment,
            items=self.get_members(),
            p=_p, P=_P,
        )


class ProtoFile(common.ProtoFile):

    enums: list[ProtoEnum] = []
    messages: list[ProtoMessage] = []

    """ Represents a protobuf file definition """

    def __init__(self, proto: FileDescriptorProto, namespaces: Namespaces):
        super().__init__(proto, naming, namespaces)

    def _create_enum(self, *args, **kwargs) -> ProtoEnum:
        return ProtoEnum(self, *args, **kwargs)

    def _create_message(self, *args, **kwargs) -> ProtoMessage:
        return ProtoMessage(self, *args, **kwargs)

    def get_name(self) -> str:
        """get name of header file based on the proto file name"""
        return ProtoFile.hdr_name(super().get_name())

    @staticmethod
    def hdr_name(proto: str) -> str:
        """get name of header file based on the proto file name"""
        return re.sub(r'(.*)\.proto', r'\1.pb.h', proto)

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

    def get_content(self) -> str:
        """ Get the C++ code for this proto file """
        items = []
        # put enums & embedded enums first
        for enum in self.enums:
            items.append(enum.get_content())
        # put messages & embedded messages
        for msg in self.messages:
            items.append(msg.get_content())

        return render_header(
            hdr_name=self.get_name(),
            dependencies=[ProtoFile.hdr_name(d)
                          for d in self.get_deps()],
            sections=[{"namespace": self.get_namespace(), "items": items}],
            protocol_define_root_group=(self.get_name() == _doc_protocol_root_header),
            protocol_file_group_id=self.get_protocol_file_group_id(),
            protocol_file_topic=self.get_protocol_file_topic(),
        )


def render_header(hdr_name: str, dependencies: list[str], sections: list[dict],
                  protocol_define_root_group: bool, protocol_file_group_id: str,
                  protocol_file_topic: str) -> str:
    """ Render a C++ header; every section wraps its pre-rendered items in its own namespace """
    return env.get_template("header.j2").render(
        hdr_name=hdr_name,
        hdr_guard=hdr_name.replace("/", "_").replace(".", "_").upper(),
        dependencies=dependencies,
        sections=sections,
        p=_p, P=_P, incpath=_incpath, cfgpath=_cfgpath,
        doc_parent_group=_doc_parent_group,
        doc_protocol_parent_group=_doc_protocol_parent_group,
        doc_protocol_group_id=_doc_protocol_group_id,
        doc_protocol_group_title=_doc_protocol_group_title,
        protocol_define_root_group=protocol_define_root_group,
        protocol_file_group_id=protocol_file_group_id,
        protocol_file_topic=protocol_file_topic,
    )


ENUMS: list[ProtoEnum] = []
MESSAGES: list[ProtoMessage] = []
FILES: list[ProtoFile] = []


def generate_cpp(request: CodeGeneratorRequest,
                  response: CodeGeneratorResponse,
                  config: ConfigManager) -> None:
    """ Generate C++ code from protobuf definitions """
    global _P, _p, _incpath, _cfgpath, C_TYPE_MAP, VARINT_TYPE_MAP
    global _doc_parent_group, _doc_protocol_parent_group, _doc_protocol_group_id, _doc_protocol_group_title, _doc_protocol_root_header
    _p = config.prefix.lower()
    _P = config.prefix.upper()
    _incpath = config.include_path
    _cfgpath = config.config_path
    _doc_parent_group = config.doc_parent_group
    _doc_protocol_parent_group = config.doc_protocol_parent_group or config.doc_parent_group
    _doc_protocol_group_id = config.doc_protocol_group_id
    _doc_protocol_group_title = config.doc_protocol_group_title
    _doc_protocol_root_header = config.doc_protocol_root_header
    single_file = config.single_file
    C_TYPE_MAP = {
        "pb_u32": f"{_p}::ItemType::VARINT_32",
        "pb_u16": f"{_p}::ItemType::VARINT_16",
        "pb_u8": f"{_p}::ItemType::VARINT_8",
        "pb_s32": f"{_p}::ItemType::VARINT_S32",
        "bool": f"{_p}::ItemType::BOOL",
        "float": f"{_p}::ItemType::FIXED_32",
    }
    VARINT_TYPE_MAP = {
        FieldDescriptorProto.TYPE_UINT32: ("pb_u32", C_TYPE_MAP["pb_u32"]),
        FieldDescriptorProto.TYPE_SINT32: ("pb_s32", C_TYPE_MAP["pb_s32"]),
        FieldDescriptorProto.TYPE_BOOL:   ("bool", C_TYPE_MAP["bool"]),
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
        _doc_protocol_root_header = FILES[0].get_name()

    # Generate message files
    if single_file:
        # Merge every .proto file (dependencies first) into one header, one namespace block per .proto
        hdr_name = f"{single_file}.pb.h"
        sections = []
        for f in common.order_files_by_dependency(FILES):
            items = [e.get_content() for e in f.enums] + [m.get_content() for m in f.messages]
            sections.append({"namespace": f.get_namespace(), "items": items})

        file = response.file.add()
        file.name = hdr_name
        file.content = naming.format_code(render_header(
            hdr_name=hdr_name,
            dependencies=[],
            sections=sections,
            protocol_define_root_group=True,
            protocol_file_group_id=f"{_doc_protocol_group_id}_{single_file}",
            protocol_file_topic=single_file.replace("_", " ").title(),
        ))
        generated_headers = [hdr_name]
    else:
        for f in FILES:
            file = response.file.add()
            file.name = f.get_name()
            file.content = naming.format_code(f.get_content())
        generated_headers = [f.get_name() for f in FILES]

    # Generate binding source file
    f = response.file.add()
    f.name = f"{_p}_bindings.cc"
    f.content = naming.format_code(
        env.get_template("bindings.j2").render(
            data=[{"fullname": m.get_full_name(), "name": m.get_name()}
                  for m in MESSAGES],
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
        )
    )

    # Generate the default configuration: the settings, the standard types and features, and a list of what the
    # configuration of the user has to define for every message
    arrays, repeated, callbacks = [], [], []
    for m in MESSAGES:
        prefix = m.get_full_name().replace("::", "_")
        for item in m.get_members():
            callbacks.append(f"{prefix}_{item['name']}")
            if item["rpt"]:
                repeated.append(f"{prefix}_{item['name']}")
            if item["proto_type"] in [FieldDescriptorProto.TYPE_STRING, FieldDescriptorProto.TYPE_BYTES]:
                arrays.append(f"{prefix}_{item['name']}")

    f = response.file.add()
    f.name = f"{_p}_config_default.h"
    f.content = naming.format_code(
        env.get_template("default_cfg.j2").render(
            messages=[m.get_full_name().replace("::", "_") for m in MESSAGES],
            arrays=arrays, repeated=repeated, callbacks=callbacks,
            p=_p, P=_P,
        )
    )

    # the types of a field number and of a message id are the smallest ones that hold the largest of the schema
    max_tag = max((m.get_max_tag() for m in MESSAGES), default=0)
    max_msgid = max(len(MESSAGES) - 1, 0)
    common.add_runtime_files(response, os.path.join(os.path.dirname(__file__), "files"), config,
                             max_tag=max_tag, tag_type=unsigned_type(common.bits_needed(max_tag)),
                             msg_count=len(MESSAGES), msgid_type=unsigned_type(common.bits_needed(max_msgid)))
