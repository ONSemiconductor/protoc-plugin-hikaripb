"""Tests of the type of a message identifier in the C and C++ output.

The generator picks the type of a message identifier (`pb_msgid`) from the number of messages of the schema: with more
than 256 messages an identifier does not fit 8 bits, and the decoder must not take a message for another one. The tests
generate a schema of 256 messages (the largest one with 8 bits) and one of 258, build a program that decodes it, and check
the decoder against bytes built by hand (skipped without protoc and a compiler).
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "protoc"))

import common  # noqa: E402
from c import parser as c_parser  # noqa: E402
from cpp import parser as cpp_parser  # noqa: E402
from test_tags import CC, CPP_CONFIG, CXX, C_HOOKS, EXE, MAIN_BODY, PLUGIN, PROTOC, field, write  # noqa: E402

# the number of messages is the one of the largest schema whose identifiers fit the type
CASES = {
    "u8": {"count": 256, "type": "pb_u8", "size": 1},
    "u16": {"count": 258, "type": "pb_u16", "size": 2},
}

HEAD = """#include <stdio.h>
#include <stdlib.h>
#include <string.h>
%(include)s

/* the type of a message identifier must be the one of the case: a negative array size is a compile error */
typedef char msgid_type_is_%(type)s[(sizeof(pb_msgid) == %(size)uU) ? 1 : -1];
"""


def proto_text(count):
    """`count` messages: fillers, then Leaf and Root, which get the two highest identifiers. Leaf has its field number
    of its own, so the descriptor of another message does not decode it."""
    lines = ['syntax = "proto3";', "package ids;"]
    lines += [f"message M{i} {{ uint32 value = 1; }}" for i in range(count - 2)]
    lines += ["message Leaf { uint32 value = 2; }", "message Root { Leaf leaf = 1; M0 first = 2; }"]
    return "\n".join(lines) + "\n"


def c_program(case):
    run = """    if (strcmp(argv[1], "decode") == 0 && argc == 3) {
        g_len = parse_hex(argv[2], g_buf);
        ids_Root msg;
        ids_Root_clear(&msg);
        ids_Root_decode(&msg);
        printf("leaf %u\\n", (unsigned)msg.leaf.value);
        printf("first %u\\n", (unsigned)msg.first.value);
        printf("error %d\\n", (int)hikaripb_getError());
        return 0;
    }"""
    head = HEAD % {"include": '#include "hikaripb_ids.pb.h"', "type": case["type"], "size": case["size"]}
    return head + C_HOOKS + MAIN_BODY % {"run": run}


def cpp_program(case):
    run = """    if (strcmp(argv[1], "decode") == 0 && argc == 3) {
        g_len = parse_hex(argv[2], g_buf);
        hikaripb::InputStream is(g_buf, g_len);
        hikaripb::Decoder<> dec(is);
        ids::Root msg;
        msg.decode(dec);
        printf("leaf %u\\n", (unsigned)msg.leaf.value);
        printf("first %u\\n", (unsigned)msg.first.value);
        printf("error %d\\n", (int)dec.getError());
        return 0;
    }"""
    head = HEAD % {"include": '#include "ids.pb.h"', "type": case["type"], "size": case["size"]}
    buffer = "\nstatic uint8_t g_buf[1024];\nstatic uint32_t g_len;\n"
    return head + buffer + MAIN_BODY % {"run": run}


class MessageIdTypeTest(unittest.TestCase):
    def test_the_bits_hold_every_value_up_to_the_largest(self):
        for largest, bits in ((0, 1), (1, 1), (255, 8), (256, 9), (65535, 16), (65536, 17), (2 ** 32 - 1, 32)):
            with self.subTest(largest=largest):
                self.assertEqual(common.bits_needed(largest), bits)

    def test_the_type_is_the_smallest_that_has_the_bits(self):
        for backend in (c_parser, cpp_parser):
            for bits, expected in ((1, "pb_u8"), (8, "pb_u8"), (9, "pb_u16"), (16, "pb_u16"), (17, "pb_u32"), (32, "pb_u32")):
                with self.subTest(backend=backend.__name__, bits=bits):
                    self.assertEqual(backend.unsigned_type(bits), expected)
            with self.assertRaises(Exception):
                backend.unsigned_type(33)

    def test_the_type_of_a_message_identifier_follows_the_number_of_messages(self):
        for backend in (c_parser, cpp_parser):
            cases = ((0, "pb_u8"), (1, "pb_u8"), (256, "pb_u8"), (257, "pb_u16"), (65536, "pb_u16"), (65537, "pb_u32"))
            for count, expected in cases:
                with self.subTest(backend=backend.__name__, count=count):
                    self.assertEqual(backend.unsigned_type(common.bits_needed(max(count - 1, 0))), expected)


class MessageIdTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which(PROTOC):
            raise unittest.SkipTest("protoc not available")
        cls.dir = tempfile.mkdtemp(prefix="hikaripb_msgid_")
        cls.addClassCleanup(shutil.rmtree, cls.dir, ignore_errors=True)
        cls.out = {}
        cls.programs = {}
        backends = [("c", CC, ".c", ["-std=c11"], c_program), ("cpp", CXX, ".cc", ["-std=c++17"], cpp_program)]
        for name, case in CASES.items():
            proto_dir = os.path.join(cls.dir, name)
            os.makedirs(proto_dir)
            write(os.path.join(proto_dir, "ids.proto"), proto_text(case["count"]))
            for backend, compiler, suffix, flags, program in backends:
                out = os.path.join(proto_dir, backend)
                cfg = os.path.join(proto_dir, "cfg_" + backend)
                os.makedirs(out)
                os.makedirs(cfg)
                cls.out[(backend, name)] = out
                command = [PROTOC, "--plugin=protoc-gen-hikaripb=" + PLUGIN, "--proto_path=" + proto_dir,
                           f"--hikaripb_out=type={backend}:{out}", os.path.join(proto_dir, "ids.proto")]
                result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
                assert result.returncode == 0, f"{backend} {name}: {result.stderr}"
                if not compiler:
                    continue
                write(os.path.join(cfg, "hikaripb_config.h"), CPP_CONFIG if backend == "cpp" else "#pragma once\n")
                main = os.path.join(proto_dir, "main" + suffix)
                write(main, program(case))
                sources = [os.path.join(out, f) for f in sorted(os.listdir(out)) if f.endswith((".c", ".cc"))]
                exe = os.path.join(proto_dir, "ids_" + backend + EXE)
                command = [compiler] + flags + ["-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                                                "-I", out, "-I", cfg, main] + sources + ["-o", exe]
                result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
                assert result.returncode == 0, f"{backend} {name}: {result.stderr}"
                cls.programs[(backend, name)] = exe

    def decode(self, backend, name, data):
        exe = self.programs.get((backend, name))
        if exe is None:
            self.skipTest("no compiler for " + backend)
        result = subprocess.run([exe, "decode", data.hex()], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        return [line.rstrip() for line in result.stdout.splitlines()]

    def test_the_type_of_a_message_identifier_is_the_smallest_that_holds_the_largest_one(self):
        for (backend, name), out in self.out.items():
            with self.subTest(backend=backend, case=name):
                with open(os.path.join(out, "hikaripb_types.h"), encoding="utf-8") as f:
                    found = re.search(r"^#define pb_msgid (\w+)$", f.read(), re.M)
                self.assertEqual(found.group(1), CASES[name]["type"])

    def test_the_decoder_finds_the_message_of_every_identifier(self):
        # Leaf and Root have the highest identifiers: cut to 8 bits, they would be the ones of two filler messages
        data = field(1, 2, field(2, 0, 7)) + field(2, 2, field(1, 0, 5))
        for name in CASES:
            for backend in ("c", "cpp"):
                with self.subTest(backend=backend, case=name):
                    self.assertEqual(self.decode(backend, name, data), ["leaf 7", "first 5", "error 0"])


if __name__ == "__main__":
    unittest.main()
