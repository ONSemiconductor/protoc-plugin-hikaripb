"""Tests of the debug output of the C and C++ decoders and of the print macros of the C output.

With <PREFIX>_DEBUG and <PREFIX>_PRINT_ENABLE, the decoder prints every error that it finds with the names of the field
and the message; the C and C++ test suites leave both at 0. These tests generate a small schema, build a program that
decodes broken input and compare its output. Defining only one of <PREFIX>_PRINT and <PREFIX>_PRINTLN is a compile
error of the C output. They need protoc and a compiler (skipped otherwise).
"""

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
EXE = ".exe" if os.name == "nt" else ""

PROTO = """syntax = "proto3";
package demo;
message Inner {
  uint32 value = 1;
}
message Mid {
  Inner inner = 1;
}
message Outer {
  uint32 id = 1;
  string name = 2;
  repeated uint32 ids = 3;
  oneof choice {
    uint32 a = 4;
    uint32 b = 5;
  }
  Inner inner = 6;
  Inner streamed = 7;
  Mid mid = 8;
}
"""

SIZES = """#define demo_Outer_name_size 4U
#define demo_Outer_ids_count 2U
"""

# the root message and one level below it: the Inner of a Mid is too deep
DEBUG = """#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define HIKARIPB_DEBUG 1
#define HIKARIPB_DEC_MAX_DEPTH 2U
#define HIKARIPB_PRINT_ENABLE 1
#define HIKARIPB_PRINT(...) printf(__VA_ARGS__)
#define HIKARIPB_PRINTLN(...) do { printf(__VA_ARGS__); printf("\\n"); } while (0)
"""

C_CONFIG = "#pragma once\n" + DEBUG + SIZES + """#define HIKARIPB_CALLBACK 1
#define demo_Outer_streamed_callback_en 1
"""

CPP_CONFIG = "#pragma once\n" + DEBUG + SIZES + """
namespace hikaripb {
class InputStream {
    const uint8_t* buffer;
    uint32_t length;
    uint32_t offset = 0U;

   public:
    InputStream(const uint8_t* data, uint32_t len) : buffer(data), length(len) {}
    bool read(uint8_t* data, uint16_t len) {
        if ((offset + len) > length) {
            offset = length;
            return false;
        }
        memcpy(data, &buffer[offset], len);
        offset += len;
        return true;
    }
    bool skip(uint16_t len) {
        if ((offset + len) > length) {
            offset = length;
            return false;
        }
        offset += len;
        return true;
    }
    bool pop(uint8_t* data) {
        if (offset >= length) {
            return false;
        }
        *data = buffer[offset];
        offset++;
        return true;
    }
    void setOffset(uint32_t value) { offset = value; }
    uint32_t getOffset() const { return offset; }
};
class OutputStream {
   public:
    void write(const uint8_t*, uint16_t) {}
    void setOffset(uint32_t) {}
    uint32_t getOffset() const { return 0; }
};
}  // namespace hikaripb
"""

# the broken input of every case, decoded as an Outer; each one makes the decoder print, see EXPECTED
CASES = [
    ("unknown field", [0x78, 0x01]),
    ("unknown wire type", [0x0F]),
    ("long string", [0x12, 0x05, 0x61, 0x62, 0x63, 0x64, 0x65]),
    ("long repeated field", [0x18, 0x01, 0x18, 0x02, 0x18, 0x03]),
    ("long packed field", [0x1A, 0x03, 0x01, 0x02, 0x03]),
    ("second oneof member", [0x20, 0x01, 0x28, 0x02]),
    ("end within a message", [0x32, 0x03, 0x08, 0x01]),
    ("too deep", [0x42, 0x04, 0x0A, 0x02, 0x08, 0x01]),
]

# a callback that decodes the submessage of its field, then fails: the error is one of its own field, not of the last
# field of the submessage. Only the C test has the callback
CALLBACK_CASE = ("failed callback", [0x3A, 0x02, 0x08, 0x05])


def expected(outer, inner, mid, callback=False):
    lines = [
        "-- unknown field",
        f"HIKARIPB: received unknown tag 15 in message {outer}",
        "-- unknown wire type",
        f"HIKARIPB: received unknown tag 1 in message {outer}",
        f"HIKARIPB: received unknown wire type in message {outer}",
        "-- long string",
        f"HIKARIPB: overflow of byte array name in message {outer}",
        "-- long repeated field",
        f"HIKARIPB: overflow of repeated field ids in message {outer}",
        "-- long packed field",
        f"HIKARIPB: overflow of repeated field ids in message {outer}",
        "-- second oneof member",
        f"HIKARIPB: duplicated tag b in message {outer}",
        "-- end within a message",
        f"HIKARIPB: unexpected end of stream in message {inner}",
        "-- too deep",
        f"HIKARIPB: message nesting exceeded the maximum depth in message {mid}",
    ]
    if callback:
        lines += [
            "-- failed callback",
            f"HIKARIPB: callback error when decoding streamed in message {outer}",
        ]
    return lines


def c_array(data):
    return "{" + ", ".join(f"0x{byte:02X}U" for byte in data) + "}"


def c_main(cases):
    runs = "\n".join(f'    {{\n        static const pb_u8 bytes[] = {c_array(data)};\n'
                     f'        run("{name}", bytes, (pb_u32)sizeof(bytes));\n    }}' for name, data in cases)
    return """#include <stdio.h>
#include <string.h>
#include "hikaripb_diag.pb.h"
#include "hikaripb_decode.h"

static const pb_u8* g_data;
static pb_u32 g_length;
static pb_u32 g_offset;

pb_bool hikaripb_read(pb_u8* data, pb_u16 len) {
    if ((g_offset + len) > g_length) {
        g_offset = g_length;
        return PB_FALSE;
    }
    memcpy(data, &g_data[g_offset], len);
    g_offset += len;
    return PB_TRUE;
}
pb_bool hikaripb_skip(pb_u16 len) {
    if ((g_offset + len) > g_length) {
        g_offset = g_length;
        return PB_FALSE;
    }
    g_offset += len;
    return PB_TRUE;
}
pb_bool hikaripb_pop(pb_u8* data) {
    if (g_offset >= g_length) {
        return PB_FALSE;
    }
    *data = g_data[g_offset];
    g_offset++;
    return PB_TRUE;
}
pb_u32 hikaripb_getReadOffset(void) { return g_offset; }
void hikaripb_write(const pb_u8* data, pb_u16 len) { (void)data; (void)len; }
void hikaripb_setWriteOffset(pb_u32 offset) { (void)offset; }
pb_u32 hikaripb_getWriteOffset(void) { return 0U; }

static demo_Inner g_streamed;

pb_bool demo_Outer_streamed_callback(const struct hikaripb_ItemDescriptor* desc, pb_u16 len, void** item_data) {
    *item_data = &g_streamed;
    hikaripb_decode_item((pb_u8*)*item_data, desc, len);
    return PB_FALSE;
}

static void run(const char* name, const pb_u8* data, pb_u32 length) {
    demo_Outer message;
    printf("-- %s\\n", name);
    g_data = data;
    g_length = length;
    g_offset = 0U;
    hikaripb_decode(&message, (pb_msgid)demo_Outer_ID);
}

int main(void) {
""" + runs + """
    return 0;
}
"""


def cpp_main(cases):
    runs = "\n".join(f'    {{\n        static const uint8_t bytes[] = {c_array(data)};\n'
                     f'        run("{name}", bytes, sizeof(bytes));\n    }}' for name, data in cases)
    return """#include <stdio.h>
#include "diag.pb.h"

static void run(const char* name, const uint8_t* data, uint32_t length) {
    printf("-- %s\\n", name);
    hikaripb::InputStream stream(data, length);
    hikaripb::Decoder<> decoder(stream);
    demo::Outer message;
    message.decode(decoder);
}

int main() {
""" + runs + """
    return 0;
}
"""


# a C file that includes the decoder header
PRINT_MAIN = """#include "hikaripb_decode.h"
"""


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


class DiagnosticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which(PROTOC):
            raise unittest.SkipTest("protoc not available")
        cls.dir = tempfile.mkdtemp(prefix="hikaripb_diagnostics_")
        cls.addClassCleanup(shutil.rmtree, cls.dir, ignore_errors=True)
        write(os.path.join(cls.dir, "diag.proto"), PROTO)
        cls.out = {}
        for backend in ("c", "cpp"):
            cls.out[backend] = os.path.join(cls.dir, backend)
            os.makedirs(cls.out[backend])
            command = [PROTOC, "--plugin=protoc-gen-hikaripb=" + PLUGIN, "--proto_path=" + cls.dir,
                       f"--hikaripb_out=type={backend}:{cls.out[backend]}", os.path.join(cls.dir, "diag.proto")]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            assert result.returncode == 0, result.stderr

    def config_dir(self, name, config):
        cfg = os.path.join(self.dir, "cfg_" + name)
        os.makedirs(cfg, exist_ok=True)
        write(os.path.join(cfg, "hikaripb_config.h"), config)
        return cfg

    def run_program(self, backend, compiler, main_name, main, flags, sources, config):
        cfg = self.config_dir(backend, config)
        main_path = os.path.join(self.dir, main_name)
        write(main_path, main)
        exe = os.path.join(self.dir, "diag_" + backend + EXE)
        command = [compiler] + flags + ["-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                                        "-I", self.out[backend], "-I", cfg, main_path] + sources + ["-o", exe]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([exe], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        return [line.rstrip() for line in result.stdout.splitlines()]

    @unittest.skipUnless(CC, "no C compiler")
    def test_c_decoder_prints_every_error_with_the_names_of_the_field_and_the_message(self):
        sources = [os.path.join(self.out["c"], name) for name in sorted(os.listdir(self.out["c"])) if name.endswith(".c")]
        lines = self.run_program("c", CC, "main.c", c_main(CASES + [CALLBACK_CASE]), ["-std=c11"], sources, C_CONFIG)
        self.assertEqual(lines, expected("demo_Outer", "demo_Inner", "demo_Mid", callback=True))

    @unittest.skipUnless(CXX, "no C++ compiler")
    def test_cpp_decoder_prints_the_same_errors(self):
        sources = [os.path.join(self.out["cpp"], "hikaripb_bindings.cc")]
        lines = self.run_program("cpp", CXX, "main.cc", cpp_main(CASES), ["-std=c++17"], sources, CPP_CONFIG)
        self.assertEqual(lines, expected("Outer", "Inner", "Mid"))

    def check_error(self, name, defined, missing):
        cfg = self.config_dir(name, "#pragma once\n#include <stdio.h>\n#define HIKARIPB_PRINT_ENABLE 1\n"
                                    f"#define HIKARIPB_{defined}(...) printf(__VA_ARGS__)\n" + SIZES +
                              "#define HIKARIPB_CALLBACK 1\n#define demo_Outer_streamed_callback_en 1\n")
        main_path = os.path.join(self.dir, name + ".c")
        write(main_path, PRINT_MAIN)
        command = [CC, "-std=c11", "-fsyntax-only", "-I", self.out["c"], "-I", cfg, main_path]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"HIKARIPB_{defined} is defined, but HIKARIPB_{missing} is missing", result.stderr)

    @unittest.skipUnless(CC, "no C compiler")
    def test_c_print_without_println_is_an_error(self):
        self.check_error("print_only", "PRINT", "PRINTLN")

    @unittest.skipUnless(CC, "no C compiler")
    def test_c_println_without_print_is_an_error(self):
        self.check_error("println_only", "PRINTLN", "PRINT")


if __name__ == "__main__":
    unittest.main()
