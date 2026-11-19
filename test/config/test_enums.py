"""Tests of the setting COMPRESS_ENUMS of the C and C++ output.

With 1 (the default) an enum is stored in the smallest of `pb_u8`, `pb_u16` and `pb_u32` that holds its largest value, so
a value that is wider than that is cut to its low bits. With 0 every enum is a `pb_u32` and the decoder stores every
value as it was sent. The tests build a program for both values of the setting, check the size of the fields, encode
the enums and decode bytes that are built by hand (skipped without protoc and a compiler).
"""

import os
import shutil
import subprocess
import tempfile
import unittest

from test_tags import CC, CPP_CONFIG, CXX, C_HOOKS, EXE, MAIN_BODY, PLUGIN, PROTOC, field, write

# the largest value of the enums: 1 fits 8 bits, 300 needs 16 bits and 70000 needs 32 bits
PROTO = """syntax = "proto3";
package en;
enum Small { SMALL_ZERO = 0; SMALL_ONE = 1; }
enum Middle { MIDDLE_ZERO = 0; MIDDLE_TOP = 300; }
enum Large { LARGE_ZERO = 0; LARGE_TOP = 70000; }
message E { Small small = 1; Middle middle = 2; Large large = 3; }
"""

HEAD = """#include <stdio.h>
#include <stdlib.h>
#include <string.h>
%(include)s
"""

C_RUN = """    if (strcmp(argv[1], "sizes") == 0) {
        en_E msg;
        printf("%u %u %u\\n", (unsigned)sizeof(msg.small), (unsigned)sizeof(msg.middle), (unsigned)sizeof(msg.large));
        return 0;
    }
    if (strcmp(argv[1], "encode") == 0) {
        en_E_WrHandle w = en_E_create();
        en_E_set_small(&w, en_Small_SMALL_ONE);
        en_E_set_middle(&w, en_Middle_MIDDLE_TOP);
        en_E_set_large(&w, en_Large_LARGE_TOP);
        g_len = g_wr;
        for (pb_u32 i = 0U; i < g_len; i++) { printf("%02X", g_buf[i]); }
        printf("\\n");
        return 0;
    }
    if (strcmp(argv[1], "decode") == 0 && argc == 3) {
        g_len = parse_hex(argv[2], g_buf);
        en_E msg;
        en_E_clear(&msg);
        en_E_decode(&msg);
        printf("small %u\\nmiddle %u\\nlarge %u\\nerror %d\\n", (unsigned)msg.small, (unsigned)msg.middle,
               (unsigned)msg.large, (int)hikaripb_getError());
        return 0;
    }"""

CPP_RUN = """    if (strcmp(argv[1], "sizes") == 0) {
        en::E msg;
        printf("%u %u %u\\n", (unsigned)sizeof(msg.small), (unsigned)sizeof(msg.middle), (unsigned)sizeof(msg.large));
        return 0;
    }
    if (strcmp(argv[1], "encode") == 0) {
        hikaripb::OutputStream os(g_buf);
        hikaripb::Encoder<> enc(os);
        {
            auto w = en::E::WrProxy<true>(enc);
            w.set_small(en::SMALL_ONE);
            w.set_middle(en::MIDDLE_TOP);
            w.set_large(en::LARGE_TOP);
        }
        g_len = os.getOffset();
        for (uint32_t i = 0U; i < g_len; i++) { printf("%02X", g_buf[i]); }
        printf("\\n");
        return 0;
    }
    if (strcmp(argv[1], "decode") == 0 && argc == 3) {
        g_len = parse_hex(argv[2], g_buf);
        hikaripb::InputStream is(g_buf, g_len);
        hikaripb::Decoder<> dec(is);
        en::E msg;
        msg.decode(dec);
        printf("small %u\\nmiddle %u\\nlarge %u\\nerror %d\\n", (unsigned)msg.small, (unsigned)msg.middle,
               (unsigned)msg.large, (int)dec.getError());
        return 0;
    }"""

SIZES = {1: "1 2 4", 0: "4 4 4"}


def c_program():
    return HEAD % {"include": '#include "hikaripb_en.pb.h"'} + C_HOOKS + MAIN_BODY % {"run": C_RUN}


def cpp_program():
    head = HEAD % {"include": '#include "en.pb.h"'}
    return head + "\nstatic uint8_t g_buf[1024];\nstatic uint32_t g_len;\n" + MAIN_BODY % {"run": CPP_RUN}


def output(small=0, middle=0, large=0):
    return [f"small {small}", f"middle {middle}", f"large {large}", "error 0"]


class CompressEnumsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which(PROTOC):
            raise unittest.SkipTest("protoc not available")
        cls.dir = tempfile.mkdtemp(prefix="hikaripb_enums_")
        cls.addClassCleanup(shutil.rmtree, cls.dir, ignore_errors=True)
        write(os.path.join(cls.dir, "en.proto"), PROTO)
        cls.backends = [("c", CC, ".c", ["-std=c11"], c_program), ("cpp", CXX, ".cc", ["-std=c++17"], cpp_program)]
        cls.out = {}
        cls.exe = {}
        for backend, compiler, suffix, flags, program in cls.backends:
            out = os.path.join(cls.dir, backend)
            cfg = os.path.join(cls.dir, "cfg_" + backend)
            os.makedirs(out)
            os.makedirs(cfg)
            write(os.path.join(cfg, "hikaripb_config.h"), CPP_CONFIG if backend == "cpp" else "#pragma once\n")
            write(os.path.join(cls.dir, "main" + suffix), program())
            command = [PROTOC, "--plugin=protoc-gen-hikaripb=" + PLUGIN, "--proto_path=" + cls.dir,
                       f"--hikaripb_out=type={backend}:{out}", os.path.join(cls.dir, "en.proto")]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            assert result.returncode == 0, f"{backend}: {result.stderr}"
            cls.out[backend] = (out, cfg)
            if not compiler:
                continue
            for compress in (0, 1):
                sources = [os.path.join(out, f) for f in sorted(os.listdir(out)) if f.endswith((".c", ".cc"))]
                exe = os.path.join(cls.dir, f"en_{backend}_{compress}{EXE}")
                command = [compiler] + flags + ["-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                                                f"-DHIKARIPB_COMPRESS_ENUMS={compress}", "-I", out, "-I", cfg,
                                                os.path.join(cls.dir, "main" + suffix)] + sources + ["-o", exe]
                result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
                assert result.returncode == 0, f"{backend} {compress}: {result.stderr}"
                cls.exe[(backend, compress)] = exe

    def run_program(self, backend, compress, *args):
        exe = self.exe.get((backend, compress))
        if exe is None:
            self.skipTest("no compiler for " + backend)
        result = subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        return [line.rstrip() for line in result.stdout.splitlines()]

    def each(self):
        for backend in ("c", "cpp"):
            for compress in (0, 1):
                with self.subTest(backend=backend, compress=compress):
                    yield backend, compress

    def test_the_storage_of_an_enum_follows_the_setting(self):
        for backend, compress in self.each():
            self.assertEqual(self.run_program(backend, compress, "sizes"), [SIZES[compress]])

    def test_every_value_of_the_enum_is_encoded_in_both_modes(self):
        expected = (field(1, 0, 1) + field(2, 0, 300) + field(3, 0, 70000)).hex().upper()
        for backend, compress in self.each():
            self.assertEqual(self.run_program(backend, compress, "encode"), [expected])

    def test_the_values_of_the_enum_are_decoded_in_both_modes(self):
        data = field(1, 0, 1) + field(2, 0, 300) + field(3, 0, 70000)
        for backend, compress in self.each():
            self.assertEqual(self.run_program(backend, compress, "decode", data.hex()), output(1, 300, 70000))

    def test_a_value_that_is_wider_than_the_storage_is_cut_only_when_the_enums_are_compressed(self):
        # a newer sender may add values to an enum: 300 does not fit the 8 bits of Small, 70000 not the 16 bits of Middle
        data = field(1, 0, 300) + field(2, 0, 70000) + field(3, 0, 0xFFFFFFFF)
        expected = {1: output(300 & 0xFF, 70000 & 0xFFFF, 0xFFFFFFFF), 0: output(300, 70000, 0xFFFFFFFF)}
        for backend, compress in self.each():
            self.assertEqual(self.run_program(backend, compress, "decode", data.hex()), expected[compress])


if __name__ == "__main__":
    unittest.main()
