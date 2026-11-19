"""Tests of the decoding of fixed32, sfixed32 and float fields in the C and C++ output.

Every value of the wire must be decoded, and a field that is cut by the end of the input must be reported (skipped
without protoc and a compiler).
"""

import os
import shutil
import struct
import subprocess
import tempfile
import unittest

from test_tags import CC, CPP_CONFIG, CXX, C_HOOKS, EXE, MAIN_BODY, PLUGIN, PROTOC, field, write

UNEXPECTED_EOF = 2

PROTO = """syntax = "proto3";
package fx;
message F { fixed32 a = 1; sfixed32 b = 2; float c = 3; }
"""

HEAD = """#include <stdio.h>
#include <stdlib.h>
#include <string.h>
%(include)s
"""

C_RUN = """    if (strcmp(argv[1], "decode") == 0 && argc == 3) {
        g_len = parse_hex(argv[2], g_buf);
        fx_F msg;
        pb_u32 bits;
        fx_F_clear(&msg);
        fx_F_decode(&msg);
        memcpy(&bits, &msg.c, sizeof(bits));
        printf("a %u\\nb %d\\nc %08X\\nerror %d\\n", (unsigned)msg.a, (int)msg.b, (unsigned)bits,
               (int)hikaripb_getError());
        return 0;
    }"""

CPP_RUN = """    if (strcmp(argv[1], "decode") == 0 && argc == 3) {
        g_len = parse_hex(argv[2], g_buf);
        hikaripb::InputStream is(g_buf, g_len);
        hikaripb::Decoder<> dec(is);
        fx::F msg;
        uint32_t bits;
        msg.decode(dec);
        memcpy(&bits, &msg.c, sizeof(bits));
        printf("a %u\\nb %d\\nc %08X\\nerror %d\\n", (unsigned)msg.a, (int)msg.b, (unsigned)bits, (int)dec.getError());
        return 0;
    }"""

UNSIGNED = [0, 1, 0x01020304, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF]
SIGNED = [0, 1, -1, -2, 0x01020304, -0x01020304, -2 ** 31, 2 ** 31 - 1]
FLOATS = [0.0, 1.0, -2.5, 3.4028234663852886e38]


def fixed(number, data):
    return field(number, 5, data)


def output(a=0, b=0, c=0, error=0):
    return [f"a {a}", f"b {b}", f"c {c:08X}", f"error {error}"]


def bits(value):
    return struct.unpack("<I", struct.pack("<f", value))[0]


def cases():
    """The bytes to decode and the output that the program gives."""
    result = []
    for value in UNSIGNED:
        result.append((f"a={value}", fixed(1, struct.pack("<I", value)), output(a=value)))
    for value in SIGNED:
        result.append((f"b={value}", fixed(2, struct.pack("<i", value)), output(b=value)))
    for value in FLOATS:
        result.append((f"c={value}", fixed(3, struct.pack("<f", value)), output(c=bits(value))))
    everything = fixed(1, struct.pack("<I", 0xA1B2C3D4)) + fixed(2, struct.pack("<i", -77)) + fixed(3, struct.pack("<f", 1.0))
    result.append(("all three", everything, output(a=0xA1B2C3D4, b=-77, c=bits(1.0))))
    result.append(("empty", b"", output()))
    return result


def c_program():
    return HEAD % {"include": '#include "hikaripb_fx.pb.h"'} + C_HOOKS + MAIN_BODY % {"run": C_RUN}


def cpp_program():
    head = HEAD % {"include": '#include "fx.pb.h"'}
    return head + "\nstatic uint8_t g_buf[1024];\nstatic uint32_t g_len;\n" + MAIN_BODY % {"run": CPP_RUN}


class Fixed32Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which(PROTOC):
            raise unittest.SkipTest("protoc not available")
        cls.dir = tempfile.mkdtemp(prefix="hikaripb_fixed32_")
        cls.addClassCleanup(shutil.rmtree, cls.dir, ignore_errors=True)
        write(os.path.join(cls.dir, "fx.proto"), PROTO)
        cls.exe = {}
        for backend, compiler, suffix, flags, program in [("c", CC, ".c", ["-std=c11"], c_program),
                                                            ("cpp", CXX, ".cc", ["-std=c++17"], cpp_program)]:
            out = os.path.join(cls.dir, backend)
            cfg = os.path.join(cls.dir, "cfg_" + backend)
            os.makedirs(out)
            os.makedirs(cfg)
            write(os.path.join(cfg, "hikaripb_config.h"), CPP_CONFIG if backend == "cpp" else "#pragma once\n")
            write(os.path.join(cls.dir, "main" + suffix), program())
            command = [PROTOC, "--plugin=protoc-gen-hikaripb=" + PLUGIN, "--proto_path=" + cls.dir,
                       f"--hikaripb_out=type={backend}:{out}", os.path.join(cls.dir, "fx.proto")]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            assert result.returncode == 0, f"{backend}: {result.stderr}"
            if not compiler:
                continue
            sources = [os.path.join(out, f) for f in sorted(os.listdir(out)) if f.endswith((".c", ".cc"))]
            exe = os.path.join(cls.dir, f"fx_{backend}{EXE}")
            command = [compiler] + flags + ["-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                                            "-DHIKARIPB_ENABLE_FLOAT=1", "-I", out, "-I", cfg,
                                            os.path.join(cls.dir, "main" + suffix)] + sources + ["-o", exe]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            assert result.returncode == 0, f"{backend}: {result.stderr}"
            cls.exe[backend] = exe

    def decode(self, backend, data):
        exe = self.exe.get(backend)
        if exe is None:
            self.skipTest("no compiler for " + backend)
        result = subprocess.run([exe, "decode", data.hex()], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        return [line.rstrip() for line in result.stdout.splitlines()]

    def each(self):
        for backend in ("c", "cpp"):
            with self.subTest(backend=backend):
                yield backend

    def test_every_value_is_decoded(self):
        for backend in self.each():
            for name, data, expected in cases():
                with self.subTest(case=name):
                    self.assertEqual(self.decode(backend, data), expected)

    def test_a_field_that_is_cut_by_the_end_of_the_input_is_reported(self):
        whole = fixed(1, struct.pack("<I", 0xA1B2C3D4))
        for backend in self.each():
            for length in range(1, 5):
                # a field with 0 to 3 bytes of its value, after a whole one
                data = fixed(2, struct.pack("<i", -77)) + whole[:-4] + whole[-4:][:length - 1]
                with self.subTest(case=f"fixed32 with {length - 1} bytes"):
                    lines = self.decode(backend, data)
                    self.assertEqual(lines[-1], f"error {UNEXPECTED_EOF}")
                    self.assertEqual(lines[1], "b -77")

    def test_an_unknown_field_that_is_cut_by_the_end_of_the_input_is_reported(self):
        data = fixed(2, struct.pack("<i", -77)) + fixed(9, b"\x01\x02")
        for backend in self.each():
            self.assertEqual(self.decode(backend, data)[-1], f"error {UNEXPECTED_EOF}")


if __name__ == "__main__":
    unittest.main()
