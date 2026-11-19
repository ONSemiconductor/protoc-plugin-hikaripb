"""Tests of the setting DEC_VARINT_UNROLL of the C and C++ decoder, also with the performance hooks.

The setting is the number of leading bytes of a varint that the decoder reads by straight-line code, the others are read by a
loop. Every level, from 0 (all in a loop) to 5 (all unrolled), must decode every length of a varint, report the end of
the input inside of a varint and a varint that is too long in the same way. The tests build a program for every level and
decode bytes that are built by hand (skipped without protoc and a compiler).
"""

import os
import shutil
import subprocess
import tempfile
import unittest

from test_tags import CC, CPP_CONFIG, CXX, C_HOOKS, EXE, MAIN_BODY, PLUGIN, PROTOC, field, varint, write

LEVELS = range(6)
# the performance hooks as a build for a small target sets them: the decoder must compile without a warning and decode alike
HOOKS = ["-DHIKARIPB_LIKELY(x)=__builtin_expect(!!(x), 1)", "-DHIKARIPB_UNLIKELY(x)=__builtin_expect(!!(x), 0)",
         "-DHIKARIPB_INLINE_ATTR=__attribute__((always_inline))", "-DHIKARIPB_OPTIMIZE_ATTR=__attribute__((hot))"]
UNEXPECTED_EOF = 2
VARINT_OVERFLOW = 7

# a value for every length of a varint, and its limits
UNSIGNED = [0, 1, 127, 128, 300, 16383, 16384, 2097151, 2097152, 268435455, 268435456, 0xFFFFFFFF]
SIGNED = [0, -1, 1, -64, 64, -8192, 8192, -2 ** 31, 2 ** 31 - 1]

PROTO = """syntax = "proto3";
package vi;
message V { uint32 a = 1; sint32 b = 2; uint32 c = 16; }
"""

HEAD = """#include <stdio.h>
#include <stdlib.h>
#include <string.h>
%(include)s
"""

C_RUN = """    if (strcmp(argv[1], "decode") == 0 && argc == 3) {
        g_len = parse_hex(argv[2], g_buf);
        vi_V msg;
        vi_V_clear(&msg);
        vi_V_decode(&msg);
        printf("a %u\\nb %d\\nc %u\\nerror %d\\n", (unsigned)msg.a, (int)msg.b, (unsigned)msg.c, (int)hikaripb_getError());
        return 0;
    }"""

CPP_RUN = """    if (strcmp(argv[1], "decode") == 0 && argc == 3) {
        g_len = parse_hex(argv[2], g_buf);
        hikaripb::InputStream is(g_buf, g_len);
        hikaripb::Decoder<> dec(is);
        vi::V msg;
        msg.decode(dec);
        printf("a %u\\nb %d\\nc %u\\nerror %d\\n", (unsigned)msg.a, (int)msg.b, (unsigned)msg.c, (int)dec.getError());
        return 0;
    }"""


def zigzag(value):
    return ((value << 1) ^ (value >> 31)) & 0xFFFFFFFF


def output(a=0, b=0, c=0, error=0):
    return [f"a {a}", f"b {b}", f"c {c}", f"error {error}"]


def cases():
    """The bytes to decode, and the output that every level gives."""
    result = []
    for value in UNSIGNED:
        result.append((f"a={value}", field(1, 0, value), output(a=value)))
        result.append((f"c={value}", field(16, 0, value), output(c=value)))
    for value in SIGNED:
        result.append((f"b={value}", field(2, 0, zigzag(value)), output(b=value)))
    # the input ends inside of the varint of the value of a, or of the tag of c
    full = varint(0xFFFFFFFF)
    for length in range(1, len(full)):
        result.append((f"cut value {length}", field(2, 0, zigzag(7)) + bytes([0x08]) + full[:length],
                       output(b=7, error=UNEXPECTED_EOF)))
    result.append(("cut tag", field(2, 0, zigzag(7)) + bytes([0x80]), output(b=7, error=UNEXPECTED_EOF)))
    # the input ends before the value: the end of the input, no error
    result.append(("no value", field(2, 0, zigzag(7)) + bytes([0x08]), output(b=7)))
    result.append(("empty", b"", output()))
    # a varint of six bytes: the highest bits are lost, the rest of it is skipped and the fields after it are decoded
    result.append(("too long", bytes([0x08, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x01]) + field(2, 0, zigzag(-3)),
                   output(a=0xFFFFFFFF, b=-3, error=VARINT_OVERFLOW)))
    # a varint of five bytes with bits above the 32nd (in the fifth byte above its lowest 4 bits) is too wide as well
    for value in (1 << 32, (1 << 35) - 1):
        result.append((f"too wide {value:#x}", field(1, 0, value) + field(2, 0, zigzag(-3)),
                       output(a=value & 0xFFFFFFFF, b=-3, error=VARINT_OVERFLOW)))
    return result


def c_program():
    head = HEAD % {"include": '#include "hikaripb_vi.pb.h"'}
    return head + C_HOOKS + MAIN_BODY % {"run": C_RUN}


def cpp_program():
    head = HEAD % {"include": '#include "vi.pb.h"'}
    return head + "\nstatic uint8_t g_buf[1024];\nstatic uint32_t g_len;\n" + MAIN_BODY % {"run": CPP_RUN}


class VarintUnrollTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which(PROTOC):
            raise unittest.SkipTest("protoc not available")
        cls.dir = tempfile.mkdtemp(prefix="hikaripb_varint_")
        cls.addClassCleanup(shutil.rmtree, cls.dir, ignore_errors=True)
        write(os.path.join(cls.dir, "vi.proto"), PROTO)
        cls.backends = [("c", CC, ".c", ["-std=c11"], c_program), ("cpp", CXX, ".cc", ["-std=c++17"], cpp_program)]
        cls.out = {}
        for backend, compiler, suffix, flags, program in cls.backends:
            out = os.path.join(cls.dir, backend)
            cfg = os.path.join(cls.dir, "cfg_" + backend)
            os.makedirs(out)
            os.makedirs(cfg)
            write(os.path.join(cfg, "hikaripb_config.h"), CPP_CONFIG if backend == "cpp" else "#pragma once\n")
            write(os.path.join(cls.dir, "main" + suffix), program())
            command = [PROTOC, "--plugin=protoc-gen-hikaripb=" + PLUGIN, "--proto_path=" + cls.dir,
                       f"--hikaripb_out=type={backend}:{out}", os.path.join(cls.dir, "vi.proto")]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            assert result.returncode == 0, f"{backend}: {result.stderr}"
            cls.out[backend] = (out, cfg)

    @classmethod
    def build(cls, backend, level, extra=()):
        """Build the program with the level and the extra flags; returns the process of the compiler and the program."""
        _, compiler, suffix, flags, _ = next(b for b in cls.backends if b[0] == backend)
        if not compiler:
            raise unittest.SkipTest("no compiler for " + backend)
        out, cfg = cls.out[backend]
        sources = [os.path.join(out, f) for f in sorted(os.listdir(out)) if f.endswith((".c", ".cc"))]
        exe = os.path.join(cls.dir, f"vi_{backend}_{level}{'_hooks' if extra else ''}{EXE}")
        command = [compiler] + flags + ["-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                                        f"-DHIKARIPB_DEC_VARINT_UNROLL={level}", *extra, "-I", out, "-I", cfg,
                                        os.path.join(cls.dir, "main" + suffix)] + sources + ["-o", exe]
        return subprocess.run(command, capture_output=True, text=True, encoding="utf-8"), exe

    def decode(self, exe, data):
        result = subprocess.run([exe, "decode", data.hex()], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        return [line.rstrip() for line in result.stdout.splitlines()]

    def test_every_level_decodes_every_length_of_a_varint(self):
        for backend, *_ in self.backends:
            for level in LEVELS:
                built, exe = self.build(backend, level)
                self.assertEqual(built.returncode, 0, f"{backend} {level}: {built.stderr}")
                for name, data, expected in cases():
                    with self.subTest(backend=backend, level=level, case=name):
                        self.assertEqual(self.decode(exe, data), expected)

    def test_every_level_decodes_the_same_with_the_performance_hooks(self):
        for backend, *_ in self.backends:
            for level in LEVELS:
                built, exe = self.build(backend, level, HOOKS)
                self.assertEqual(built.returncode, 0, f"{backend} {level}: {built.stderr}")
                for name, data, expected in cases():
                    with self.subTest(backend=backend, level=level, case=name):
                        self.assertEqual(self.decode(exe, data), expected)

    def test_a_level_that_does_not_exist_does_not_compile(self):
        for backend, *_ in self.backends:
            for level in (-1, 6):
                with self.subTest(backend=backend, level=level):
                    built, _ = self.build(backend, level)
                    self.assertNotEqual(built.returncode, 0)
                    self.assertIn("DEC_VARINT_UNROLL must be 0 to 5", built.stderr)


if __name__ == "__main__":
    unittest.main()
