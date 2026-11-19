"""Tests of the switches HIKARIPB_ENABLE_FLOAT and HIKARIPB_ENABLE_REPEATED_BYTES of the C and C++ output.

Both are 0 by default: a message with a float or a repeated string or bytes field is a compile error then, and the
decoder leaves the code for repeated string or bytes out. The tests generate small schemas and compile the output;
they need `protoc` on PATH and a C and a C++ compiler (skipped otherwise).
"""

import itertools
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

PROTOC = os.environ.get("PROTOC", "protoc")
# protoc cannot start a Python script as a plugin on Windows
PLUGIN = os.environ.get("HIKARIPB_PLUGIN") or os.path.join(
    ROOT, "protoc", "protoc-gen-hikaripb.bat" if os.name == "nt" else "hikaripb.py")
CC = os.environ.get("CC") or shutil.which("cc") or shutil.which("gcc")
CXX = os.environ.get("CXX") or shutil.which("c++") or shutil.which("g++")

HEAD = 'syntax = "proto3";\npackage demo;\n'
PROTOS = {
    "plain": "message Plain { uint32 id = 1; string name = 2; repeated uint32 ids = 3; }",
    "float": "message WithFloat { float value = 1; }",
    "list": "message WithList { repeated bytes chunks = 1; }",
}

SIZES = """#define demo_Plain_name_size 8U
#define demo_Plain_ids_count 4U
#define demo_WithList_chunks_size 8U
#define demo_WithList_chunks_count 2U
"""
C_CONFIG = "#pragma once\n" + SIZES
CPP_CONFIG = """#pragma once
#include <stdint.h>
""" + SIZES + """
namespace hikaripb {
class InputStream {
   public:
    bool read(uint8_t*, uint16_t) { return false; }
    bool skip(uint16_t) { return false; }
    bool pop(uint8_t*) { return false; }
    void setOffset(uint32_t) {}
    uint32_t getOffset() const { return 0; }
};
class OutputStream {
   public:
    void write(const uint8_t*, uint16_t) {}
    void setOffset(uint32_t) {}
    uint32_t getOffset() const { return 0; }
};
}  // namespace hikaripb
"""

C_USES = {
    "plain": """#include "hikaripb_plain.pb.h"
void use(void) {
    demo_Plain_WrHandle root = demo_Plain_create();
    demo_Plain_set_id(&root, 1U);
    demo_Plain_name_WrHandle name = demo_Plain_add_name(&root);
    demo_Plain_name_done(&name);
}
""",
    "float": """#include "hikaripb_float.pb.h"
void use(void) {
    demo_WithFloat_WrHandle root = demo_WithFloat_create();
    demo_WithFloat_set_value(&root, 1.5f);
}
""",
    "list": """#include "hikaripb_list.pb.h"
void use(void) {
    demo_WithList_WrHandle root = demo_WithList_create();
    demo_WithList_chunks_WrHandle chunk = demo_WithList_add_chunks(&root);
    demo_WithList_chunks_done(&chunk);
}
""",
}

CPP_USES = {
    "plain": """#include "plain.pb.h"
void use(hikaripb::Encoder<>& e, hikaripb::Decoder<>& d) {
    { auto root = demo::Plain::WrProxy<true>(e); root.set_id(1U); }
    demo::Plain message;
    message.decode(d);
}
""",
    "float": """#include "float.pb.h"
void use(hikaripb::Encoder<>& e) {
    auto root = demo::WithFloat::WrProxy<true>(e);
    root.set_value(1.5f);
}
""",
    "list": """#include "list.pb.h"
void use(hikaripb::Encoder<>& e, hikaripb::Decoder<>& d) {
    { auto root = demo::WithList::WrProxy<true>(e); auto chunk = root.rpt_chunks(); chunk.write(nullptr, 0); }
    demo::WithList message;
    message.decode(d);
}
""",
}

FLOAT = "-DHIKARIPB_ENABLE_FLOAT=1"
LIST = "-DHIKARIPB_ENABLE_REPEATED_BYTES=1"


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


class SwitchCases:
    """The tests, run once for the C and once for the C++ output (backend, compiler, flags, uses, config)."""

    backend = compiler = flags = uses = config = None

    @classmethod
    def setUpClass(cls):
        if not shutil.which(PROTOC):
            raise unittest.SkipTest("protoc not available")
        if not cls.compiler:
            raise unittest.SkipTest("no compiler for " + cls.backend)
        cls.dir = tempfile.mkdtemp(prefix="hikaripb_switch_")
        cls.addClassCleanup(shutil.rmtree, cls.dir, ignore_errors=True)
        cls.out = os.path.join(cls.dir, "out")
        cls.cfg = os.path.join(cls.dir, "cfg")
        os.makedirs(cls.out)
        os.makedirs(cls.cfg)
        write(os.path.join(cls.cfg, "hikaripb_config.h"), cls.config)
        protos = []
        for name, body in PROTOS.items():
            protos.append(os.path.join(cls.dir, name + ".proto"))
            write(protos[-1], HEAD + body + "\n")
        command = [PROTOC, "--plugin=protoc-gen-hikaripb=" + PLUGIN, "--proto_path=" + cls.dir,
                   f"--hikaripb_out=type={cls.backend}:{cls.out}"] + protos
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0, result.stderr
        cls.sources = {}
        for name, text in cls.uses.items():
            cls.sources[name] = os.path.join(cls.dir, "use_" + name + (".c" if cls.backend == "c" else ".cc"))
            write(cls.sources[name], text)

    def compile(self, source, *switches, output=None):
        command = [self.compiler] + self.flags + ["-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                                                  "-I", self.out, "-I", self.cfg] + list(switches)
        command += ["-c", source, "-o", output] if output else ["-fsyntax-only", source]
        return subprocess.run(command, capture_output=True, text=True, encoding="utf-8")

    def assertCompiles(self, source, *switches):
        result = self.compile(source, *switches)
        self.assertEqual(result.returncode, 0, result.stderr)

    def assertFails(self, source, switch_name, *switches):
        result = self.compile(source, *switches)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(switch_name, result.stderr)

    def test_a_schema_without_float_and_repeated_bytes_needs_no_switch(self):
        self.assertCompiles(self.sources["plain"])

    def test_a_float_field_needs_the_switch(self):
        self.assertFails(self.sources["float"], "HIKARIPB_ENABLE_FLOAT")
        self.assertFails(self.sources["float"], "HIKARIPB_ENABLE_FLOAT", LIST)
        self.assertCompiles(self.sources["float"], FLOAT)

    def test_a_repeated_bytes_field_needs_the_switch(self):
        self.assertFails(self.sources["list"], "HIKARIPB_ENABLE_REPEATED_BYTES")
        self.assertFails(self.sources["list"], "HIKARIPB_ENABLE_REPEATED_BYTES", FLOAT)
        self.assertCompiles(self.sources["list"], LIST)

    def test_a_switch_set_to_0_is_the_default(self):
        self.assertFails(self.sources["float"], "HIKARIPB_ENABLE_FLOAT", "-DHIKARIPB_ENABLE_FLOAT=0")
        self.assertFails(self.sources["list"], "HIKARIPB_ENABLE_REPEATED_BYTES", "-DHIKARIPB_ENABLE_REPEATED_BYTES=0")

    def test_the_output_compiles_with_every_combination_of_the_switches(self):
        for switches in itertools.product([(), (FLOAT,)], [(), (LIST,)]):
            switches = switches[0] + switches[1]
            with self.subTest(switches=switches):
                self.assertCompiles(self.sources["plain"], *switches)


@unittest.skipUnless(CC, "no C compiler")
class CSwitchTest(SwitchCases, unittest.TestCase):
    backend, compiler, flags, uses, config = "c", CC, ["-std=c11"], C_USES, C_CONFIG

    def test_the_sources_compile_with_every_combination_of_the_switches(self):
        sources = ["hikaripb_decode.c", "hikaripb_encode.c", "hikaripb_plain.pb.c"]
        for switches in itertools.product([(), (FLOAT,)], [(), (LIST,)]):
            switches = switches[0] + switches[1]
            extra = (["hikaripb_float.pb.c"] if FLOAT in switches else []) + (["hikaripb_list.pb.c"] if LIST in switches else [])
            for name in sources + extra:
                with self.subTest(source=name, switches=switches):
                    self.assertCompiles(os.path.join(self.out, name), *switches)

    def test_the_decoder_is_smaller_without_repeated_bytes(self):
        sizes = {}
        for switches in ((), (LIST,)):
            output = os.path.join(self.dir, "decode%d.o" % len(switches))
            result = self.compile(os.path.join(self.out, "hikaripb_decode.c"), *switches, output=output)
            self.assertEqual(result.returncode, 0, result.stderr)
            sizes[len(switches)] = os.path.getsize(output)
        self.assertLess(sizes[0], sizes[1])


@unittest.skipUnless(CXX, "no C++ compiler")
class CppSwitchTest(SwitchCases, unittest.TestCase):
    backend, compiler, flags, uses, config = "cpp", CXX, ["-std=c++17"], CPP_USES, CPP_CONFIG


if __name__ == "__main__":
    unittest.main()
