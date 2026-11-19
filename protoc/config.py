# Copyright (c) 2025 Semiconductor Components Industries, LLC ("onsemi")
# SPDX-License-Identifier: GPL-3.0-or-later

"""The options of the plugin: what protoc passes in `--hikaripb_out` and what a configuration file adds.

`ConfigManager.parse()` turns the parameter of the plugin, a comma-separated list of `key=value` pairs (a key
without a value is a flag), into typed, read-only options that the backends read as attributes
(`config.prefix`). When the parameter holds `config_file=<path>`, the options of that JSON file are read
as well; the command line wins over the file and the file over the defaults. Every option is declared once, in
`OPTIONS`, and the backends never parse a parameter themselves.
"""

import json
import logging
import os
import re
import textwrap
from dataclasses import dataclass
from typing import Any, Callable

TYPES = ("c", "cpp", "py", "sphinxdocs")

_FLAG_TRUE = ("true", "yes", "on", "1")
_FLAG_FALSE = ("false", "no", "off", "0", "")
_TYPE_REQUIRED = "type is required: type=<%s>" % "|".join(TYPES)


class ConfigError(Exception):
    """An option or a configuration file that is wrong; the message is meant for the user."""


@dataclass(frozen=True)
class Option:
    """One option. `kind` is `str`, `bool` or `list` (strings, `|`-separated on the command line)."""

    name: str
    kind: str = "str"
    default: Any = ""
    text: bool = False  # on the command line `+` and `%20` stand for a space
    placeholder: str = "<value>"  # what the option needs, for the message about a missing value
    default_from: str = ""  # the option, declared before this one, whose value is the default when this one is not set
    missing: str = ""  # message about a missing value, instead of the usual one
    check: Callable[[Any], Any] | None = None  # validates (and normalizes) a value that was set
    description: str = ""  # one or two sentences about the option, for --help


def _check_type(value: str) -> str:
    if value not in TYPES:
        raise ConfigError("Unknown type '%s': expected one of %s" % (value, ", ".join(TYPES)) if value else _TYPE_REQUIRED)
    return value


def _check_single_file(value: str) -> str:
    """The base name of the merged output file: an identifier."""
    value = value.strip()
    if not value:
        raise ConfigError("single_file needs a name for the merged output: single_file=<name>")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ConfigError(f"Invalid single_file name '{value}': expected an identifier (letters, digits, underscore)")
    return value


OPTIONS = (
    # every backend
    Option("type", placeholder="<%s>" % "|".join(TYPES), check=_check_type,
           description="The backend that generates the output: c, cpp or py (code), sphinxdocs (documentation). "
                       "Required."),
    Option("config_file", placeholder="<file>",
           description="A JSON file with options, named like the options (a path relative to the directory protoc "
                       "runs in). Options of the command line win over it."),
    Option("prefix", default="hikaripb", placeholder="<name>",
           description="Prefix of the generated runtime: the C symbols and macros, the C++ namespace and macros, the "
                       "Python runtime module, the labels of the documentation."),
    Option("single_file", placeholder="<name>", check=_check_single_file,
           missing="single_file needs a name for the merged output: single_file=<name>",
           description="Merge the output of all .proto files into one file with this name (c, cpp, py)."),
    Option("ignore", "list", (), placeholder="<name>[|...]",
           description="Messages and enums to leave out, named like a.b.Message, a_b_Message or a::b::Message. A type "
                       "that another generated message uses cannot be left out."),
    Option("namespace_override", text=True, placeholder="<namespace>",
           description="Replaces the leading part of the package names that all of them share, the packages below it "
                       "keep their names (esb.gpio is acme.gpio with acme). py: the package of the modules. "
                       "sphinxdocs: the shown names and the labels."),
    # c and cpp
    Option("include_path", placeholder="<path>",
           description="Prefix of the #include paths of the generated runtime headers (c, cpp)."),
    Option("config_path", default_from="include_path", placeholder="<path>",
           description="Prefix of the #include path of <prefix>_config.h (c, cpp)."),
    Option("doc_parent_group", placeholder="<group>",
           description="Doxygen group that the group of the generated runtime belongs to (c, cpp)."),
    Option("doc_group_id", default="hikaripb", placeholder="<id>",
           description="Id of the Doxygen group of the generated runtime (c, cpp)."),
    Option("doc_group_title", text=True, default_from="doc_group_id", placeholder="<title>",
           description="Title of the Doxygen group of the generated runtime (c, cpp)."),
    Option("doc_protocol_parent_group", default_from="doc_parent_group", placeholder="<group>",
           description="Doxygen group that the groups of the .proto files belong to (c, cpp)."),
    Option("doc_protocol_group_id", default="hikaripb_protocol", placeholder="<id>",
           description="Id of the Doxygen group that holds the groups of the .proto files (c, cpp)."),
    Option("doc_protocol_group_title", text=True, default="Protocol", placeholder="<title>",
           description="Title of the Doxygen group that holds the groups of the .proto files (c, cpp)."),
    Option("doc_protocol_root_header", placeholder="<header>",
           description="Generated header that opens the top-level Doxygen group of the protocol, by default the one "
                       "of the first .proto file in name order (c, cpp)."),
    # sphinxdocs
    Option("title", text=True, default="Protocol", placeholder="<title>",
           description="Title of the index page and name of the Sphinx project (sphinxdocs)."),
    Option("parent", placeholder="<directory>",
           description="Directory below the output directory that receives the pages, which makes them a chapter of "
                       "an existing Sphinx project (sphinxdocs)."),
    Option("image_path", placeholder="<directory>",
           description="Directory, relative to the output directory, that the image paths of the comments are "
                       "relative to (sphinxdocs)."),
    Option("pages", "list", (), placeholder="<folder>|[<name>=]<file>[|...]",
           description="Markdown folders and files that become pages in front of the pages of the .proto files "
                       "(sphinxdocs)."),
    Option("home", placeholder="<page>|<file>",
           description="Page that is the home page (index) instead of the list of the pages: a Markdown page of "
                       "pages or a Markdown file (sphinxdocs)."),
    Option("omit_conf", "bool", False,
           description="Do not write conf.py (sphinxdocs)."),
    Option("inline_protocol", "bool", False,
           description="Make the Protocol the last section of the page of its file instead of a page below it, which "
                       "a book needs (sphinxdocs)."),
)
_BY_NAME = {option.name: option for option in OPTIONS}


def options_help(width: int = 100) -> str:
    """The options with their descriptions and defaults, as `--help` lists them."""
    lines = []
    for option in OPTIONS:
        lines.append("  " + (f"{option.name}[=true|false]" if option.kind == "bool" else f"{option.name}={option.placeholder}"))
        text = option.description
        if option.default_from:
            text += f" Default: the value of {option.default_from}."
        elif option.default not in ("", (), False):
            text += f" Default: {option.default}."
        lines += textwrap.wrap(text, width, initial_indent=" " * 6, subsequent_indent=" " * 6)
    return "\n".join(lines)


def _split(parameter: str) -> dict:
    """The pairs of the parameter of the plugin: the value of a key without one is True."""
    pairs = {}
    for pair in parameter.split(","):
        key, equals, value = pair.partition("=")
        if key.strip():
            pairs[key.strip()] = value.strip() if equals else True
    return pairs


def _read_file(path: str) -> dict:
    """The top-level keys of a JSON file."""
    if os.path.splitext(path)[1].lower() != ".json":
        raise ConfigError(f"Unsupported configuration file {path}: expected a .json file")
    try:
        with open(path, "rb") as f:
            text = f.read().decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        raise ConfigError(f"Cannot read the configuration file {path}: {getattr(error, 'strerror', None) or error}")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ConfigError(f"Invalid JSON in {path}: {error}")
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected an object with the options as keys")
    for name, value in data.items():
        if isinstance(value, dict):
            raise ConfigError(f"{path}: {name} is an object, but the options are keys of the top level")
    return data


def _convert(option: Option, raw: Any, label: str, command_line: bool) -> Any:
    """The value of `option` for `raw`: a string or a flag without a value (True) on the command line, any value of
    a file. `label` starts the messages about a file."""
    name = option.name
    if option.kind == "bool":
        word = raw.strip().lower() if isinstance(raw, str) else raw
        if raw is True or word in _FLAG_TRUE:
            return True
        if raw is False or word in _FLAG_FALSE:
            return False
        raise ConfigError(f"{label}{name} is a flag: {name}, {name}=true or {name}=false")
    if raw is True and command_line:
        raise ConfigError(option.missing or f"{name} needs a value: {name}={option.placeholder}")
    if option.kind == "list":
        if isinstance(raw, str):
            raw = raw.split("|")
        if not isinstance(raw, (list, tuple)) or not all(isinstance(item, str) for item in raw):
            raise ConfigError(f"{label}{name} must be a list of strings")
        value = tuple(item.strip() for item in raw if item.strip())
    else:
        if not isinstance(raw, str):
            raise ConfigError(f"{label}{name} must be a string")
        value = raw.replace("%20", " ").replace("+", " ") if command_line and option.text else raw
    if option.check:
        try:
            value = option.check(value)
        except ConfigError as error:
            raise ConfigError(label + str(error)) from None
    return value


def _layer(items: dict, label: str, command_line: bool) -> dict:
    """The values of the options in `items`; a name that is no option is reported and left out."""
    values = {}
    for name, raw in items.items():
        if name in _BY_NAME:
            values[name] = _convert(_BY_NAME[name], raw, label, command_line)
        else:
            logging.warning("hikaripb: %sUnknown option '%s' is ignored", label, name)
    return values


def _default(option: Option, values: dict) -> Any:
    return values[option.default_from] if option.default_from else option.default


class ConfigManager:
    """The options of one run of the plugin, read-only: `config.prefix`, `config.omit_conf`, ...

    An option that no source sets has its default, which can be the value of another option (`config_path` is
    `include_path`).
    """

    __slots__ = ("_values",)

    def __init__(self, values: dict):
        object.__setattr__(self, "_values", values)

    @classmethod
    def parse(cls, parameter: str = "") -> "ConfigManager":
        """The options of the parameter of the plugin and of the file that its `config_file` names (a path relative
        to the directory in which protoc runs). A value on the command line replaces one of the file."""
        command_line = _layer(_split(parameter), "", True)
        values = {}
        path = command_line.get("config_file")
        if path:
            label = path + ": "
            from_file = _layer(_read_file(path), label, False)
            if "config_file" in from_file:
                raise ConfigError(label + "config_file cannot be set in a configuration file")
            values.update(from_file)
        values.update(command_line)
        for option in OPTIONS:
            if option.name not in values:
                values[option.name] = _default(option, values)
        if not values["type"]:
            raise ConfigError(_TYPE_REQUIRED)
        return cls(values)

    def __getattr__(self, name: str) -> Any:
        # only called for a name that is not an attribute; "_values" is missing while the object is being built
        if name != "_values" and name in self._values:
            return self._values[name]
        raise AttributeError(f"{type(self).__name__} has no option '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(f"{type(self).__name__} is read-only")

    def __repr__(self) -> str:
        changed = (f"{o.name}={self._values[o.name]!r}" for o in OPTIONS if self._values[o.name] != _default(o, self._values))
        return f"{type(self).__name__}({', '.join(changed)})"
