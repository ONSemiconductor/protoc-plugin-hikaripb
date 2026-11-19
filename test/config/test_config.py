"""Tests of the configuration manager (protoc/config.py): the parameter of the plugin, configuration files, the
validation and the defaults of the options, and runs of the plugin that read a configuration file.

The unit tests need nothing but Python; the runs of the plugin need `protoc` on PATH (skipped otherwise).
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "protoc"))

import config  # noqa: E402
from config import ConfigError, ConfigManager  # noqa: E402

PROTOC = os.environ.get("PROTOC", "protoc")
# protoc cannot start a Python script as a plugin on Windows
PLUGIN = os.environ.get("HIKARIPB_PLUGIN") or os.path.join(
    ROOT, "protoc", "protoc-gen-hikaripb.bat" if os.name == "nt" else "hikaripb.py")
DOCS = os.path.join(ROOT, "docs", "content")
# options.md has the options of every generator, <generator>/configuration.md the ones of each generator
OPTION_PAGES = [os.path.join(DOCS, "options.md")] + sorted(
    os.path.join(DOCS, name, "configuration.md") for name in os.listdir(DOCS)
    if os.path.isfile(os.path.join(DOCS, name, "configuration.md")))
SCRIPT = os.path.join(ROOT, "protoc", "hikaripb.py")
PROTO = 'syntax = "proto3";\npackage demo;\n\n// An item.\nmessage Item {\n   uint32 id = 1;  // Identifier.\n}\n'


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


class TempDirTest(unittest.TestCase):
    def tmp(self):
        path = tempfile.mkdtemp(prefix="hikaripb_test_")
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        return path


class ParameterTest(unittest.TestCase):
    def test_every_option_has_a_default(self):
        c = ConfigManager.parse("type=c")
        self.assertEqual((c.type, c.prefix, c.single_file, c.include_path, c.config_path, c.config_file),
                         ("c", "hikaripb", "", "", "", ""))
        self.assertEqual((c.ignore, c.pages), ((), ()))
        self.assertEqual((c.omit_conf, c.inline_protocol), (False, False))
        self.assertEqual((c.namespace_override, c.doc_parent_group, c.doc_protocol_parent_group), ("", "", ""))
        self.assertEqual((c.doc_group_id, c.doc_group_title), ("hikaripb", "hikaripb"))
        self.assertEqual((c.doc_protocol_group_id, c.doc_protocol_group_title, c.doc_protocol_root_header),
                         ("hikaripb_protocol", "Protocol", ""))
        self.assertEqual((c.title, c.parent, c.image_path), ("Protocol", "", ""))

    def test_pairs_and_flags(self):
        c = ConfigManager.parse("type=c,prefix=abc,inline_protocol,include_path=inc/")
        self.assertEqual((c.type, c.prefix, c.inline_protocol, c.include_path), ("c", "abc", True, "inc/"))

    def test_spaces_empty_pairs_and_repeated_keys(self):
        c = ConfigManager.parse(" type = c , ,prefix= x ,prefix=y,,")
        self.assertEqual((c.type, c.prefix), ("c", "y"))

    def test_a_value_may_contain_an_equals_sign(self):
        self.assertEqual(ConfigManager.parse("type=sphinxdocs,pages=intro=a.md|b.md").pages, ("intro=a.md", "b.md"))

    def test_flags(self):
        for word in ("true", "TRUE", "yes", "on", "1"):
            with self.subTest(word=word):
                self.assertIs(ConfigManager.parse("type=c,inline_protocol=" + word).inline_protocol, True)
        for word in ("false", "False", "no", "off", "0", ""):
            with self.subTest(word=word):
                self.assertIs(ConfigManager.parse("type=c,inline_protocol=" + word).inline_protocol, False)
        with self.assertRaisesRegex(ConfigError, "omit_conf is a flag: omit_conf, omit_conf=true or omit_conf=false"):
            ConfigManager.parse("type=sphinxdocs,omit_conf=maybe")

    def test_lists_are_separated_by_a_bar(self):
        c = ConfigManager.parse("type=cpp,ignore=a_B| c_D ||e_F,pages=")
        self.assertEqual((c.ignore, c.pages), (("a_B", "c_D", "e_F"), ()))

    def test_text_options_turn_plus_and_percent_20_into_spaces(self):
        c = ConfigManager.parse("type=c,title=My+Protocol%20Docs,namespace_override=a+b,doc_group_title=G+T,"
                                "doc_protocol_group_title=P%20T,prefix=a+b,doc_group_id=x+y")
        self.assertEqual((c.title, c.namespace_override, c.doc_group_title, c.doc_protocol_group_title),
                         ("My Protocol Docs", "a b", "G T", "P T"))
        self.assertEqual((c.prefix, c.doc_group_id), ("a+b", "x+y"))

    def test_defaults_follow_other_options(self):
        c = ConfigManager.parse("type=c,include_path=inc/,doc_parent_group=grp,doc_group_id=gid")
        self.assertEqual((c.config_path, c.doc_protocol_parent_group, c.doc_group_title), ("inc/", "grp", "gid"))
        c = ConfigManager.parse("type=c,include_path=inc/,config_path=,doc_parent_group=grp,doc_protocol_parent_group=,"
                                "doc_group_id=gid,doc_group_title=T")
        self.assertEqual((c.config_path, c.doc_protocol_parent_group, c.doc_group_title), ("", "", "T"))

    def test_an_option_without_a_value_is_reported(self):
        for name in ("type", "config_file", "prefix", "include_path", "ignore", "title", "parent", "image_path", "pages"):
            with self.subTest(option=name):
                with self.assertRaisesRegex(ConfigError, "^%s needs a value: %s=<" % (name, name)):
                    ConfigManager.parse("type=c," + name if name != "type" else "type")
        with self.assertRaisesRegex(ConfigError, "^pages needs a value: pages=<folder>\\|\\[<name>=\\]<file>\\[\\|\\.\\.\\.\\]$"):
            ConfigManager.parse("type=sphinxdocs,pages")

    def test_single_file_is_an_identifier(self):
        self.assertEqual(ConfigManager.parse("type=py,single_file=all_2").single_file, "all_2")
        for options in ("single_file", "single_file="):
            with self.subTest(options=options):
                with self.assertRaisesRegex(ConfigError, "^single_file needs a name for the merged output"):
                    ConfigManager.parse("type=py," + options)
        for name in ("a-b", "a/b", "1abc", "a.b"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ConfigError, "^Invalid single_file name '%s'" % name):
                    ConfigManager.parse("type=py,single_file=" + name)

    def test_the_type_is_required_and_known(self):
        for parameter in ("prefix=x", "", "type="):
            with self.subTest(parameter=parameter):
                with self.assertRaisesRegex(ConfigError, "^type is required: type=<c\\|cpp\\|py\\|sphinxdocs>$"):
                    ConfigManager.parse(parameter)
        with self.assertRaisesRegex(ConfigError, "^Unknown type 'java': expected one of c, cpp, py, sphinxdocs$"):
            ConfigManager.parse("type=java")

    def test_an_unknown_option_is_reported_and_ignored(self):
        with self.assertLogs(level="WARNING") as logs:
            c = ConfigManager.parse("type=c,bogus=1,flag")
        self.assertEqual(len(logs.output), 2)
        self.assertIn("Unknown option 'bogus' is ignored", logs.output[0])
        self.assertIn("Unknown option 'flag' is ignored", logs.output[1])
        self.assertEqual(c.type, "c")
        self.assertFalse(hasattr(c, "bogus"))

    def test_options_that_another_backend_reads_are_accepted(self):
        with self.assertNoLogs(level="WARNING"):
            c = ConfigManager.parse("type=c,title=X,omit_conf,pages=a,inline_protocol,single_file=all")
        self.assertEqual((c.title, c.omit_conf, c.pages), ("X", True, ("a",)))

    def test_the_options_are_read_only(self):
        c = ConfigManager.parse("type=c")
        with self.assertRaises(AttributeError):
            c.prefix = "x"
        with self.assertRaises(AttributeError):
            c.bogus = 1
        with self.assertRaisesRegex(AttributeError, "no option 'bogus'"):
            c.bogus

    def test_repr_lists_the_options_that_are_set(self):
        self.assertEqual(repr(ConfigManager.parse("type=c,prefix=x,inline_protocol")),
                         "ConfigManager(type='c', prefix='x', inline_protocol=True)")


class FileTest(TempDirTest):
    def load(self, name, text, parameter="type=c"):
        return ConfigManager.parse("%s,config_file=%s" % (parameter, write(os.path.join(self.tmp(), name), text)))

    def test_a_json_file_gives_the_options(self):
        c = self.load("cfg.json", json.dumps({
            "prefix": "abc", "inline_protocol": True, "ignore": ["a_B", "c_D"], "pages": "x|y", "title": "C++ docs"}))
        self.assertEqual((c.prefix, c.inline_protocol, c.ignore, c.pages), ("abc", True, ("a_B", "c_D"), ("x", "y")))
        # a space is a space in a file, + and %20 are only special on the command line
        self.assertEqual(c.title, "C++ docs")

    def test_the_command_line_wins_over_the_file(self):
        text = json.dumps({"prefix": "file", "ignore": ["a"], "inline_protocol": True, "include_path": "inc/"})
        c = self.load("cfg.json", text)
        self.assertEqual((c.prefix, c.ignore, c.inline_protocol, c.include_path), ("file", ("a",), True, "inc/"))
        c = self.load("cfg.json", text, "type=c,prefix=cli,ignore=b|c,inline_protocol=false")
        self.assertEqual((c.prefix, c.ignore, c.inline_protocol, c.include_path), ("cli", ("b", "c"), False, "inc/"))

    def test_the_file_wins_over_the_defaults(self):
        c = self.load("cfg.json", json.dumps({"include_path": "inc/", "doc_group_id": "gid"}))
        # a default that follows another option follows the value that was read
        self.assertEqual((c.include_path, c.config_path, c.doc_group_title), ("inc/", "inc/", "gid"))

    def test_the_type_may_come_from_the_file(self):
        path = write(os.path.join(self.tmp(), "cfg.json"), json.dumps({"type": "py", "prefix": "abc"}))
        self.assertEqual(ConfigManager.parse("config_file=" + path).type, "py")
        self.assertEqual(ConfigManager.parse("type=c,config_file=" + path).type, "c")

    def test_a_relative_path_is_relative_to_the_working_directory(self):
        folder = self.tmp()
        write(os.path.join(folder, "cfg.json"), '{"prefix": "abc"}')
        previous = os.getcwd()
        os.chdir(folder)
        try:
            self.assertEqual(ConfigManager.parse("type=c,config_file=cfg.json").prefix, "abc")
        finally:
            os.chdir(previous)

    def test_a_byte_order_mark_is_skipped(self):
        path = os.path.join(self.tmp(), "cfg.json")
        with open(path, "wb") as f:
            f.write(b"\xef\xbb\xbf" + b'{"prefix": "abc"}')
        self.assertEqual(ConfigManager.parse("type=c,config_file=" + path).prefix, "abc")

    def test_a_file_that_cannot_be_used_is_reported(self):
        # (file name, text, the options of the command line, message)
        cases = [
            ("cfg.yaml", "prefix: abc\n", "type=c", "^Unsupported configuration file .*cfg\\.yaml: expected a \\.json file$"),
            ("cfg.toml", 'prefix = "abc"\n', "type=c", "^Unsupported configuration file .*cfg\\.toml: expected a \\.json file$"),
            ("cfg.json", "{", "type=c", "^Invalid JSON in .*cfg\\.json: "),
            ("cfg.json", "[1, 2]", "type=c", "cfg\\.json: expected an object with the options as keys"),
            ("cfg.json", '{"c": {"prefix": "x"}}', "type=c", "cfg\\.json: c is an object, but the options are keys of the top level"),
            ("cfg.json", '{"config_file": "other.json"}', "type=c", "cfg\\.json: config_file cannot be set in a configuration file"),
            ("cfg.json", '{"prefix": 5}', "type=c", "cfg\\.json: prefix must be a string"),
            ("cfg.json", '{"prefix": true}', "type=c", "cfg\\.json: prefix must be a string"),
            ("cfg.json", '{"omit_conf": "maybe"}', "type=c", "cfg\\.json: omit_conf is a flag"),
            ("cfg.json", '{"omit_conf": 2}', "type=c", "cfg\\.json: omit_conf is a flag"),
            ("cfg.json", '{"pages": 3}', "type=c", "cfg\\.json: pages must be a list of strings"),
            ("cfg.json", '{"ignore": [1]}', "type=c", "cfg\\.json: ignore must be a list of strings"),
            ("cfg.json", '{"single_file": "a-b"}', "type=c", "cfg\\.json: Invalid single_file name 'a-b'"),
            ("cfg.json", '{"type": "java"}', "type=c", "cfg\\.json: Unknown type 'java'"),
            ("cfg.json", '{"prefix": "abc"}', "", "^type is required"),
        ]
        folder = self.tmp()
        for name, text, parameter, message in cases:
            with self.subTest(name=name, text=text):
                path = write(os.path.join(folder, name), text)
                with self.assertRaisesRegex(ConfigError, message):
                    ConfigManager.parse(",".join(part for part in (parameter, "config_file=" + path) if part))

    def test_a_missing_file_is_reported(self):
        with self.assertRaisesRegex(ConfigError, "^Cannot read the configuration file nothere\\.json: "):
            ConfigManager.parse("type=c,config_file=nothere.json")

    def test_an_unknown_key_is_reported_with_the_file(self):
        path = write(os.path.join(self.tmp(), "cfg.json"), '{"bogus": 1, "prefix": "abc"}')
        with self.assertLogs(level="WARNING") as logs:
            c = ConfigManager.parse("type=c,config_file=" + path)
        self.assertEqual(c.prefix, "abc")
        self.assertIn("%s: Unknown option 'bogus' is ignored" % path, logs.output[0])


class DeclarationTest(unittest.TestCase):
    def test_the_names_are_unique_and_the_kinds_known(self):
        names = [option.name for option in config.OPTIONS]
        self.assertEqual(len(names), len(set(names)))
        for option in config.OPTIONS:
            with self.subTest(option=option.name):
                self.assertIn(option.kind, ("str", "bool", "list"))
                expected = {"str": str, "bool": bool, "list": tuple}[option.kind]
                self.assertIsInstance(option.default, expected)

    def test_a_default_follows_an_option_declared_before_it(self):
        names = [option.name for option in config.OPTIONS]
        for option in config.OPTIONS:
            if option.default_from:
                self.assertLess(names.index(option.default_from), names.index(option.name), option.name)

    def test_every_option_is_in_the_documentation(self):
        pages = []
        for path in OPTION_PAGES:
            with open(path, encoding="utf-8") as f:
                pages.append(f.read())
        for option in config.OPTIONS:
            self.assertTrue(any("`%s`" % option.name in page for page in pages), option.name)

    def test_every_option_has_a_short_description(self):
        for option in config.OPTIONS:
            with self.subTest(option=option.name):
                self.assertTrue(option.description.strip())
                self.assertLess(len(option.description), 250)

    def test_the_help_lists_every_option_with_its_description(self):
        text = config.options_help(width=10000)
        for option in config.OPTIONS:
            with self.subTest(option=option.name):
                self.assertIn(option.name, text)
                self.assertIn(option.description, text)
        self.assertIn("  prefix=<name>\n      Prefix of the generated runtime", text)
        self.assertIn("Default: hikaripb.", text)
        self.assertIn("  omit_conf[=true|false]\n", text)
        self.assertIn("Default: the value of include_path.", text)


class PluginScriptTest(unittest.TestCase):
    """hikaripb.py itself: without arguments it is the plugin, --help describes it."""

    def run_script(self, *arguments, stdin=b""):
        return subprocess.run([sys.executable, SCRIPT, *arguments], input=stdin, capture_output=True, timeout=120)

    def test_help_lists_the_options(self):
        for argument in ("--help", "-h"):
            with self.subTest(argument=argument):
                result = self.run_script(argument)
                self.assertEqual(result.returncode, 0, result.stderr)
                text = result.stdout.decode("utf-8")
                self.assertIn("--hikaripb_out", text)
                self.assertIn("wins over the file", text)
                for option in config.OPTIONS:
                    self.assertIn(option.name, text)
                    self.assertIn(" ".join(option.description.split()[:3]), text)

    def test_an_unknown_argument_is_an_error(self):
        result = self.run_script("--bogus")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized arguments: --bogus", result.stderr.decode("utf-8"))

    def test_without_arguments_it_is_the_plugin(self):
        from google.protobuf.compiler.plugin_pb2 import CodeGeneratorRequest, CodeGeneratorResponse
        result = self.run_script(stdin=CodeGeneratorRequest(parameter="type=py,prefix=abc").SerializeToString())
        self.assertEqual(result.returncode, 0, result.stderr)
        names = sorted(file.name for file in CodeGeneratorResponse.FromString(result.stdout).file)
        self.assertEqual(names, ["abc_build_ext.py", "abc_codec.pxd", "abc_codec.py"])

    def test_the_options_of_the_request_are_read_by_process_request(self):
        import hikaripb
        from google.protobuf.compiler.plugin_pb2 import CodeGeneratorRequest
        response = hikaripb.process_request(CodeGeneratorRequest(parameter="type=py,prefix=xyz"))
        self.assertEqual(sorted(file.name for file in response.file),
                         ["xyz_build_ext.py", "xyz_codec.pxd", "xyz_codec.py"])
        with self.assertRaisesRegex(ConfigError, "^type is required"):
            hikaripb.process_request(CodeGeneratorRequest(parameter="prefix=xyz"))


@unittest.skipUnless(shutil.which(PROTOC), "protoc not available")
class PluginTest(TempDirTest):
    def setUp(self):
        self.proto_dir = self.tmp()
        write(os.path.join(self.proto_dir, "demo.proto"), PROTO)

    def run_plugin(self, options, cwd=None, protos=("demo.proto",)):
        """The result of protoc and the generated files by name."""
        out = self.tmp()
        command = [PROTOC, "--experimental_allow_proto3_optional", "--plugin=protoc-gen-hikaripb=" + PLUGIN,
                   "--proto_path=" + self.proto_dir, "--hikaripb_out=%s:%s" % (options, out),
                   *(os.path.join(self.proto_dir, name) for name in protos)]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", cwd=cwd)
        files = {}
        for folder, _, names in os.walk(out):
            for name in names:
                with open(os.path.join(folder, name), "rb") as f:
                    files[os.path.relpath(os.path.join(folder, name), out).replace(os.sep, "/")] = f.read()
        return result, files

    def test_a_configuration_file_gives_the_options_of_the_command_line(self):
        folder = self.tmp()
        write(os.path.join(folder, "cfg.json"), '{"prefix": "abc", "single_file": "everything"}')
        result, from_file = self.run_plugin("type=py,config_file=cfg.json", folder)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(from_file), {"everything_pb.py", "abc_codec.py", "abc_codec.pxd", "abc_build_ext.py"})
        result, from_command_line = self.run_plugin("type=py,prefix=abc,single_file=everything")
        self.assertEqual(from_file, from_command_line)

    def test_the_command_line_wins_over_the_file(self):
        folder = self.tmp()
        write(os.path.join(folder, "cfg.json"), '{"prefix": "abc"}')
        result, files = self.run_plugin("type=py,prefix=xyz,config_file=cfg.json", folder)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("xyz_codec.py", files)
        self.assertNotIn("abc_codec.py", files)

    def test_the_documentation_options_of_a_file(self):
        folder = self.tmp()
        write(os.path.join(folder, "intro.md"), "# Intro\n\nHello.\n")
        write(os.path.join(folder, "docs.json"), json.dumps(
            {"title": "My Docs", "omit_conf": True, "pages": ["intro.md"], "inline_protocol": True}))
        result, from_file = self.run_plugin("type=sphinxdocs,config_file=docs.json", folder)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(from_file), {"index.md", "intro.md", "demo.md"})
        self.assertTrue(from_file["index.md"].startswith(b"# My Docs\n"))
        result, from_command_line = self.run_plugin("type=sphinxdocs,title=My+Docs,omit_conf,pages=intro.md,"
                                                    "inline_protocol", folder)
        self.assertEqual(from_file, from_command_line)

    def test_a_title_with_a_plus_sign_is_kept_in_a_file(self):
        folder = self.tmp()
        write(os.path.join(folder, "docs.json"), '{"title": "C++ protocol"}')
        result, files = self.run_plugin("type=sphinxdocs,config_file=docs.json", folder)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(files["index.md"].startswith(b"# C++ protocol\n"))
        self.assertIn(b'project = "C++ protocol"', files["conf.py"])

    def test_the_runtime_templates_read_the_options(self):
        options = "prefix=abc,include_path=inc/,config_path=cfg/,doc_parent_group=grp,doc_group_id=gid,doc_group_title=G+T"
        expected = {
            "abc_defines.h": (b'#include "cfg/abc_config.h"', b"@defgroup gid G T", b"@ingroup grp", b"@ingroup gid"),
            "abc_encode.h": (b'#include "inc/abc_defines.h"', b"@ingroup gid"),
            "abc_decode.h": (b'#include "inc/abc_bindings.h"', b'#include "inc/abc_defines.h"', b"@ingroup gid"),
        }
        for backend in ("c", "cpp"):
            with self.subTest(backend=backend):
                result, files = self.run_plugin("type=%s,%s" % (backend, options))
                self.assertEqual(result.returncode, 0, result.stderr)
                for name, texts in expected.items():
                    for text in texts:
                        self.assertIn(text, files[name], name)
                if backend == "c":
                    self.assertIn(b"@defgroup gid G T", files["abc_encode.c"])

    def test_the_first_proto_file_opens_the_protocol_group(self):
        write(os.path.join(self.proto_dir, "alpha.proto"),
              'syntax = "proto3";\npackage alpha;\n\nmessage A {\n   uint32 x = 1;\n}\n')
        group = b"@defgroup hikaripb_protocol Protocol"
        for backend, prefix in (("c", "hikaripb_"), ("cpp", "")):
            alpha, demo = prefix + "alpha.pb.h", prefix + "demo.pb.h"
            # alpha.proto comes first in name order, not on the command line
            for option, opener, other in (("", alpha, demo), (",doc_protocol_root_header=demo.pb.h", demo, alpha)):
                with self.subTest(backend=backend, option=option):
                    result, files = self.run_plugin("type=" + backend + option, protos=("demo.proto", "alpha.proto"))
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(group, files[opener])
                    self.assertNotIn(group, files[other])

    def test_an_error_is_a_message_without_a_traceback(self):
        for options, message in (("type=c,single_file=a-b", "Invalid single_file name 'a-b'"),
                                 ("type=py,config_file=nothere.json", "Cannot read the configuration file nothere.json"),
                                 ("prefix=x", "type is required")):
            with self.subTest(options=options):
                result, files = self.run_plugin(options)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("hikaripb: " + message, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(files, {})

    def test_an_unknown_option_is_reported_on_stderr(self):
        result, files = self.run_plugin("type=py,bogus")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Unknown option 'bogus' is ignored", result.stderr)
        self.assertIn("demo_pb.py", files)


if __name__ == "__main__":
    unittest.main()
