"""Tests of the struct of a message in the C and C++ output and of the values that the decoder stores in it.

The members of the struct are in the order of their alignment, smallest first, so that the one-byte members (bool, small
enums, messages of one-byte members) follow the presence bitmap without padding. A bool is true for every value but 0,
also for one whose low byte is 0, and a varint wider than 32 bits is an error instead of being cut. The tests build a
program for each backend that prints the offsets of the members and decodes bytes that are built by hand (skipped
without protoc and a compiler).
"""

import os
import shutil
import subprocess
import tempfile
import unittest

from test_tags import CC, CPP_CONFIG, CXX, C_HOOKS, EXE, MAIN_BODY, PLUGIN, PROTOC, field, varint, write

# the members in the order of the .proto file: their alignments are 4, 1, 2, 4, 1, 1, 1 (Inner has a bool only), 4 (a
# repeated field starts with its count), 4 (a oneof starts with its tag) and 1
PROTO = """syntax = "proto3";
package lay;
enum Small { SMALL_ZERO = 0; SMALL_ONE = 1; }
enum Middle { MIDDLE_ZERO = 0; MIDDLE_TOP = 300; }
message Inner { bool on = 1; }
message Mixed {
  uint32 a = 1;
  bool b1 = 2;
  Middle m = 3;
  fixed32 c = 4;
  bool b2 = 5;
  Small e = 6;
  Inner inner = 7;
  repeated bool flags = 8;
  oneof pick { uint32 x = 9; bool y = 10; }
  bool b3 = 11;
}
"""

COUNT = 4
CONFIG = f"#define lay_Mixed_flags_count {COUNT}\n"
# the members in the order that the struct must have, the presence bitmap of 11 field numbers first, with their
# alignment and their size (the one of Inner is printed by the program)
ORDER = ["presence", "b1", "b2", "e", "inner", "b3", "m", "a", "c", "flags", "pick_tag", "pick"]
ALIGNMENTS = {"presence": 1, "b1": 1, "b2": 1, "e": 1, "inner": 1, "b3": 1, "m": 2, "a": 4, "c": 4, "flags": 4,
              "pick_tag": 4, "pick": 4}
SIZES = {"presence": 2, "b1": 1, "b2": 1, "e": 1, "b3": 1, "m": 2, "a": 4, "c": 4, "flags": 4 + COUNT, "pick_tag": 4,
         "pick": 4}

HEAD = """#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
%(include)s
"""

# the offsets of the members and the sizes of the structs, then the decoded values
LAYOUT = """    if (strcmp(argv[1], "layout") == 0) {
%(offsets)s
        printf("sizeof %%u %%u\\n", (unsigned)sizeof(%(mixed)s), (unsigned)sizeof(%(inner)s));
        return 0;
    }"""

VALUES = """        printf("a %%u\\nb1 %%u\\nb2 %%u\\nb3 %%u\\ne %%u\\ninner %%u\\nm %%u\\nc %%u\\n", (unsigned)msg.a, (unsigned)msg.b1,
               (unsigned)msg.b2, (unsigned)msg.b3, (unsigned)msg.e, (unsigned)msg.inner.on, (unsigned)msg.m, (unsigned)msg.c);
        printf("flags");
        for (unsigned i = 0U; i < (unsigned)msg.flags.count; i++) { printf(" %%u", (unsigned)msg.flags.item[i]); }
        printf("\\npick %%u %%u\\n", (unsigned)msg.pick_tag, (msg.pick_tag == 10U) ? (unsigned)msg.pick.y : 0U);
        printf("error %%s\\n", (%(error)s == %(ok)s) ? "ok" : (%(error)s == %(overflow)s) ? "overflow" : "other");
        return 0;"""

C_DECODE = """    if (strcmp(argv[1], "decode") == 0 && argc == 3) {
        g_len = parse_hex(argv[2], g_buf);
        lay_Mixed msg;
        lay_Mixed_clear(&msg);
        lay_Mixed_decode(&msg);
""" + VALUES % {"error": "hikaripb_getError()", "ok": "HIKARIPB_DECODER_OK",
                "overflow": "HIKARIPB_DECODER_VARINT_OVERFLOW"} + "\n    }"

CPP_DECODE = """    if (strcmp(argv[1], "decode") == 0 && argc == 3) {
        g_len = parse_hex(argv[2], g_buf);
        hikaripb::InputStream is(g_buf, g_len);
        hikaripb::Decoder<> dec(is);
        lay::Mixed msg;
        msg.decode(dec);
""" + VALUES % {"error": "dec.getError()", "ok": "hikaripb::DecodeError::DECODER_OK",
                "overflow": "hikaripb::DecodeError::DECODER_VARINT_OVERFLOW"} + "\n    }"


def layout(mixed, inner):
    lines = [f'        printf("{name} %u\\n", (unsigned)offsetof({mixed}, {name}));' for name in ORDER]
    return LAYOUT % {"offsets": "\n".join(lines), "mixed": mixed, "inner": inner}


def c_program():
    run = layout("lay_Mixed", "lay_Inner") + "\n" + C_DECODE
    return HEAD % {"include": '#include "hikaripb_lay.pb.h"'} + C_HOOKS + MAIN_BODY % {"run": run}


def cpp_program():
    run = layout("lay::Mixed", "lay::Inner") + "\n" + CPP_DECODE
    head = HEAD % {"include": '#include "lay.pb.h"'}
    return head + "\nstatic uint8_t g_buf[1024];\nstatic uint32_t g_len;\n" + MAIN_BODY % {"run": run}


def output(a=0, b1=0, b2=0, b3=0, e=0, inner=0, m=0, c=0, flags=(), pick=(0, 0), error="ok"):
    return [f"a {a}", f"b1 {b1}", f"b2 {b2}", f"b3 {b3}", f"e {e}", f"inner {inner}", f"m {m}", f"c {c}",
            "flags" + "".join(f" {flag}" for flag in flags), f"pick {pick[0]} {pick[1]}", f"error {error}"]


def align(offset, alignment):
    return (offset + alignment - 1) // alignment * alignment


class LayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which(PROTOC):
            raise unittest.SkipTest("protoc not available")
        cls.dir = tempfile.mkdtemp(prefix="hikaripb_layout_")
        cls.addClassCleanup(shutil.rmtree, cls.dir, ignore_errors=True)
        write(os.path.join(cls.dir, "lay.proto"), PROTO)
        backends = [("c", CC, ".c", ["-std=c11"], c_program), ("cpp", CXX, ".cc", ["-std=c++17"], cpp_program)]
        cls.exe = {}
        for backend, compiler, suffix, flags, program in backends:
            out = os.path.join(cls.dir, backend)
            cfg = os.path.join(cls.dir, "cfg_" + backend)
            os.makedirs(out)
            os.makedirs(cfg)
            write(os.path.join(cfg, "hikaripb_config.h"), (CPP_CONFIG if backend == "cpp" else "#pragma once\n") + CONFIG)
            write(os.path.join(cls.dir, "main" + suffix), program())
            command = [PROTOC, "--plugin=protoc-gen-hikaripb=" + PLUGIN, "--proto_path=" + cls.dir,
                       f"--hikaripb_out=type={backend}:{out}", os.path.join(cls.dir, "lay.proto")]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            assert result.returncode == 0, f"{backend}: {result.stderr}"
            if not compiler:
                continue
            sources = [os.path.join(out, f) for f in sorted(os.listdir(out)) if f.endswith((".c", ".cc"))]
            exe = os.path.join(cls.dir, f"lay_{backend}{EXE}")
            command = [compiler] + flags + ["-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-I", out, "-I", cfg,
                                            os.path.join(cls.dir, "main" + suffix)] + sources + ["-o", exe]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            assert result.returncode == 0, f"{backend}: {result.stderr}"
            cls.exe[backend] = exe

    def run_program(self, backend, *args):
        exe = self.exe.get(backend)
        if exe is None:
            self.skipTest("no compiler for " + backend)
        result = subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        return [line.rstrip() for line in result.stdout.splitlines()]

    def decode(self, data):
        """The lines that the program of every backend prints for the decoded data."""
        if not self.exe:
            self.skipTest("no compiler")
        return {backend: self.run_program(backend, "decode", data.hex()) for backend in self.exe}

    def check(self, data, expected, last=False):
        for backend, lines in self.decode(data).items():
            with self.subTest(backend=backend):
                self.assertEqual(lines[-1] if last else lines, expected)

    def test_the_members_are_ordered_by_their_alignment_without_padding(self):
        for backend in ("c", "cpp"):
            with self.subTest(backend=backend):
                lines = self.run_program(backend, "layout")
                offsets = {name: int(number) for name, number in (line.split() for line in lines[:-1])}
                mixed, inner = (int(number) for number in lines[-1].split()[1:])
                self.assertEqual(sorted(ORDER, key=lambda name: offsets[name]), ORDER)
                # every member at the first offset that its alignment allows
                sizes = dict(SIZES, inner=inner)
                expected = {}
                offset = 0
                for name in ORDER:
                    offset = align(offset, ALIGNMENTS[name])
                    expected[name] = offset
                    offset += sizes[name]
                self.assertEqual(offsets, expected)
                self.assertEqual(mixed, align(offset, 4))
                self.assertEqual(inner, 2)

    def test_every_member_is_decoded_at_its_offset(self):
        # the members are not in the order of the field numbers, the descriptors must still find each of them
        data = field(1, 0, 70000) + field(2, 0, 1) + field(3, 0, 300) + field(4, 5, (0x12345678).to_bytes(4, "little"))
        data += field(5, 0, 1) + field(6, 0, 1) + field(7, 2, field(1, 0, 1))
        data += field(8, 2, b"".join(varint(number) for number in (1, 0, 1))) + field(10, 0, 1) + field(11, 0, 1)
        self.check(data, output(a=70000, b1=1, b2=1, b3=1, e=1, inner=1, m=300, c=0x12345678, flags=(1, 0, 1),
                                pick=(10, 1)))

    def test_a_bool_is_true_for_every_value_but_zero(self):
        for number in (1, 2, 0x80, 0x100, 0x10000, 0xFF000000, 0x80000000, 0xFFFFFFFF):
            with self.subTest(value=hex(number)):
                data = field(2, 0, number) + field(11, 0, number) + field(7, 2, field(1, 0, number))
                self.check(data + field(10, 0, number), output(b1=1, b3=1, inner=1, pick=(10, 1)))

    def test_a_bool_that_is_zero_in_a_longer_varint_is_false(self):
        zero = b"\x80\x80\x80\x80\x00"
        data = bytes([2 << 3]) + zero + bytes([5 << 3]) + b"\x80\x00" + bytes([10 << 3]) + zero
        self.check(data, output(pick=(10, 0)))

    def test_every_element_of_a_packed_bool_field_is_true_for_every_value_but_zero(self):
        data = field(8, 2, b"".join(varint(number) for number in (0, 0x100, 0xFF000000))) + field(8, 0, 0x200)
        self.check(data, output(flags=(0, 1, 1, 1)))

    def test_a_varint_wider_than_32_bits_is_an_error(self):
        # 2^32 has a fifth byte of 0x10: its bit 32 must not be dropped, which would make the bool false and a uint32 0
        for name, number in (("b1", 2), ("a", 1)):
            for value in (1 << 32, (1 << 35) - 1):
                with self.subTest(field=name, value=hex(value)):
                    self.check(field(number, 0, value), "error overflow", last=True)

    def test_a_varint_of_ten_bytes_is_an_error(self):
        # a negative int64 has ten bytes on the wire
        self.check(field(1, 0, (1 << 64) - 1), "error overflow", last=True)

    def test_the_largest_32_bit_value_is_decoded(self):
        self.check(field(1, 0, 0xFFFFFFFF) + field(2, 0, 0xFFFFFFFF), output(a=0xFFFFFFFF, b1=1))


if __name__ == "__main__":
    unittest.main()
