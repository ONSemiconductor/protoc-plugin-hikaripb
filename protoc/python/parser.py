# Copyright (c) 2025 Semiconductor Components Industries, LLC ("onsemi")
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import re
import jinja2 as jinja
from google.protobuf.compiler.plugin_pb2 import CodeGeneratorResponse, CodeGeneratorRequest
from google.protobuf.descriptor_pb2 import FileDescriptorProto, FieldDescriptorProto
import common
from config import ConfigManager
from names import Ignored, Namespaces

env = jinja.Environment(
    loader=jinja.PackageLoader("python.parser"),
    trim_blocks=True,
    lstrip_blocks=True
)

naming = common.Environment(
    reserved_words=[
        "False", "None", "True", "and", "as", "assert", "async",
        "await", "break", "class", "continue", "def", "del", "elif",
        "else", "except", "finally", "for", "from", "global", "if",
        "import", "in", "is", "lambda", "nonlocal", "not", "or", "pass",
        "raise", "return", "try", "while", "with", "yield",
        "self", "serialize", "deserialize", "init", "clear", "print"],
    name_separator="_",
    reserved_suffix="_",
)

# Prefix of the generated runtime module ({prefix}_codec) - overwritten by generate_py()
_p = "hikaripb"

# proto scalar type -> (codec kind, python annotation, default of a field without presence)
SCALAR_TYPE_MAP = {
    FieldDescriptorProto.TYPE_UINT32:   ("uint32", "int", "0"),
    FieldDescriptorProto.TYPE_SINT32:   ("sint32", "int", "0"),
    FieldDescriptorProto.TYPE_FIXED32:  ("fixed32", "int", "0"),
    FieldDescriptorProto.TYPE_SFIXED32: ("sfixed32", "int", "0"),
    FieldDescriptorProto.TYPE_BOOL:     ("bool", "bool", "False"),
    FieldDescriptorProto.TYPE_FLOAT:    ("float", "float", "0.0"),
    FieldDescriptorProto.TYPE_BYTES:    ("bytes", "bytes", None),
    FieldDescriptorProto.TYPE_STRING:   ("string", "str", None),
}


def _doc(text: str) -> str:
    """ Make a proto comment safe to embed in a python docstring """
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _identifier(name: str) -> str:
    """ Turn a proto file name component into a valid python module name component """
    name = re.sub(r"\W", "_", name)
    return name if not name[:1].isdigit() else "_" + name


def module_name(proto_name: str) -> str:
    """ Dotted module path generated for a .proto file, e.g. a/b/c.proto -> a.b.c_pb """
    parts = [_identifier(part) for part in re.sub(r"\.proto$", "", proto_name).split("/")]
    parts[-1] += "_pb"
    return ".".join(parts)


class ProtoEnum(common.ProtoEnum):
    """ Represents a protobuf enum definition """

    file: "ProtoFile" = None

    def get_zero_name(self) -> str:
        """ Name of the member with value 0 (proto3 enums always have one) """
        return next((m["name"] for m in self.get_members() if m["number"] == 0), "")

    def get_content(self) -> str:
        """ Get the py code for this enum """
        items = self.get_members()
        for item in items:
            item["comment"] = _doc(item["comment"])
        return env.get_template("enum.j2").render(
            comment=_doc(self.comment),
            name=self.get_name(),
            items=items
        )


class ProtoMessage(common.ProtoMessage):
    """ Represents a protobuf message definition """

    parent: "ProtoMessage" = None
    file: "ProtoFile" = None
    _view: "ProtoFile" = None  # file whose module names the types, see get_params()

    def _process_field(self, idx: int, f: FieldDescriptorProto) -> dict:
        """ Parse the field into the information the class template needs """
        res = super()._process_field(idx, f)
        res["comment"] = _doc(res["comment"])
        res["number"] = f.number
        res["msg"] = f.type == FieldDescriptorProto.TYPE_MESSAGE
        res["ref"] = ""
        res["zero"] = None

        if f.type in (FieldDescriptorProto.TYPE_ENUM, FieldDescriptorProto.TYPE_MESSAGE):
            target = TYPES.get(f.type_name)
            if target is None:
                raise Exception(f"Unknown type {f.type_name} of field {self.get_name()}.{f.name}; "
                                "a type that a generated message uses cannot be left out")
            res["ref"] = (self._view or self.file).ref(target)
            if f.type == FieldDescriptorProto.TYPE_ENUM:
                res["kind"] = "enum"
                res["pytype"] = res["ref"]
                res["zero"] = f"{res['ref']}.{target.get_zero_name()}" if target.get_zero_name() else "0"
            else:
                res["kind"] = "message"
                res["pytype"] = res["ref"]
                res["target"] = target
        elif f.type in SCALAR_TYPE_MAP:
            res["kind"], res["pytype"], res["zero"] = SCALAR_TYPE_MAP[f.type]
        else:
            raise ValueError(f"Unsupported field type: {f.type}")

        # presence follows the C/C++ generators: bytes/string/message/oneof/optional fields own a presence bit
        explicit = bool(res["group"]) or f.proto3_optional
        res["explicit"] = explicit
        if res["rpt"]:
            res["label"] = "repeated"
            res["pytype"] = f"list[{res['pytype']}]"
        elif res["kind"] in ("bytes", "string", "message") or explicit:
            res["label"] = "optional"
        else:
            res["label"] = "single"

        # everything but plain proto3 scalars is read/written through a property that maintains the presence bit
        res["prop"] = res["label"] != "single"
        res["attr"] = "_" + res["name"] if res["prop"] else res["name"]
        # unset members read as None, except message/bytes/string fields of the plain kind
        nullable = res["label"] == "optional" and ((explicit and not res["msg"]) or (res["msg"] and bool(res["group"])))
        res["optional_type"] = res["pytype"] + " | None" if nullable else res["pytype"]
        res["doc"] = ((f"Oneof({res['group']}) " if res["group"] else "") + res["comment"]).strip()
        return res

    def get_members(self) -> list[dict]:
        """ Members in declaration order, with the presence bit and the oneof masks assigned """
        members = super().get_members()
        bit = 0
        group_masks: dict[str, int] = {}
        for m in members:
            m["bit"], m["mask"] = -1, 0
            if m["label"] == "optional":
                m["bit"], m["mask"] = bit, 1 << bit
                bit += 1
            if m["group"]:
                group_masks[m["group"]] = group_masks.get(m["group"], 0) | m["mask"]
        for m in members:
            m["group_mask"] = group_masks[m["group"]] & ~m["mask"] if m["group"] else 0
        return members

    def get_groups(self) -> list[dict]:
        """ The oneof groups with the mask of all their presence bits """
        groups: dict[str, int] = {}
        for m in self.get_members():
            if m["group"]:
                groups[m["group"]] = groups.get(m["group"], 0) | m["mask"]
        return [{"name": name, "mask": mask} for name, mask in groups.items()]

    def get_content(self) -> str:
        """ Get the py code for this message """
        fields = self.get_members()
        for f in fields:
            # the add() of a repeated message field takes the fields of its element as parameters
            f["params"] = f["target"].get_params(self.file) if f["rpt"] and f["msg"] else []
        return env.get_template("class.j2").render(
            name=self.get_name(),
            comment=_doc(self.comment),
            fields=fields,
            groups=self.get_groups(),
        )

    def get_params(self, view: "ProtoFile") -> list[dict]:
        """ The members with their types named as the module of `view` imports them """
        self._view = view
        try:
            return self.get_members()
        finally:
            self._view = None

    def get_registration(self) -> str:
        """ Get the py code that attaches the codec field table to the class """
        return env.get_template("register.j2").render(
            name=self.get_name(),
            fields=self.get_members(),
        )


class ProtoFile(common.ProtoFile):
    """ Represents a protobuf file definition """

    module: str = ""

    def __init__(self, proto: FileDescriptorProto, namespaces: Namespaces):
        super().__init__(proto, naming, namespaces)
        self.imports: dict[str, str] = {}

    def _create_enum(self, *args, **kwargs) -> ProtoEnum:
        return ProtoEnum(self, *args, **kwargs)

    def _create_message(self, *args, **kwargs) -> ProtoMessage:
        return ProtoMessage(self, *args, **kwargs)

    def ref(self, target) -> str:
        """ Python expression naming a type defined in `target`'s file, as seen from this file's module """
        if target.file.module == self.module:
            return target.get_name()
        alias = "_" + target.file.module.replace(".", "_")
        self.imports[target.file.module] = alias
        return f"{alias}.{target.get_name()}"


ENUMS: list[ProtoEnum] = []
MESSAGES: list[ProtoMessage] = []
FILES: list[ProtoFile] = []
TYPES: dict[str, ProtoEnum | ProtoMessage] = {}


def generate_py(request: CodeGeneratorRequest,
                response: CodeGeneratorResponse,
                config: ConfigManager) -> None:
    """ Generate py code from protobuf definitions: one {name}_pb module per .proto file, or a single one """
    global _p
    _p = config.prefix.lower()
    single_file = config.single_file
    ENUMS.clear()
    MESSAGES.clear()
    FILES.clear()
    TYPES.clear()

    # Load all proto files from request
    namespaces = Namespaces((proto.package for proto in request.proto_file), config.namespace_override)
    ignored = Ignored(config.ignore)
    for proto in sorted(request.proto_file, key=lambda file_obj: file_obj.name):
        f = ProtoFile(proto, namespaces)
        f.drop_ignored(ignored)
        f.module = f"{single_file}_pb" if single_file else module_name(f.get_name())
        FILES.append(f)
    # Python has no namespaces but its modules: the override replaces the package that all of them share
    packages = Namespaces((f.module.rpartition(".")[0] for f in FILES), config.namespace_override)
    for f in FILES:
        package, _, name = f.module.rpartition(".")
        f.module = ".".join([*(_identifier(part) for part in packages.parts(package)), name])
    FILES[:] = common.order_files_by_dependency(FILES)

    for f in FILES:
        ENUMS.extend(f.enums)
        MESSAGES.extend(f.messages)
        for t in f.enums + f.messages:
            TYPES[t.get_fq_name()] = t

    # every class lives at module level, so names must be unique within one module
    seen: dict[tuple[str, str], str] = {}
    for t in ENUMS + MESSAGES:
        key = (t.file.module, t.get_name())
        if key in seen:
            raise Exception(f"{t.get_fq_name()} and {seen[key]} would both generate class {t.get_name()} in module {key[0]}")
        seen[key] = t.get_fq_name()

    # Generate one module per proto file (or the one merged module)
    modules: dict[str, list[ProtoFile]] = {}
    for f in FILES:
        modules.setdefault(f.module, []).append(f)

    for module, files in modules.items():
        enums = [e.get_content() for f in files for e in f.enums]
        messages = [m.get_content() for f in files for m in f.messages]
        registrations = [m.get_registration() for f in files for m in f.messages]
        imports = {}
        for f in files:
            imports.update(f.imports)

        file = response.file.add()
        file.name = module.replace(".", "/") + ".py"
        file.content = env.get_template("source.j2").render(
            p=_p,
            sources=[f.get_name() for f in files],
            imports=sorted(imports.items()),
            enums=enums,
            messages=messages,
            registrations=registrations,
        )

    common.add_runtime_files(response, os.path.join(os.path.dirname(__file__), "files"), config)
