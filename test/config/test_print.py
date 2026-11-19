"""Tests of the print() of the C and C++ output for repeated string and bytes fields and for float fields.

The print code is only compiled when <PREFIX>_PRINT_ENABLE is 1, which the C and C++ test suites leave at 0. These tests
generate a small schema, build a program that fills a message by hand and prints it, and compare the output (skipped
without protoc and a compiler).
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
message Lists {
  repeated string names = 1;
  repeated bytes blobs = 2;
  uint32 tail = 3;
  repeated bytes streamed = 4;
  float ratio = 5;
  repeated float ratios = 6;
}
message Nothing {
}
"""

CONFIG = """#pragma once
#include <stdint.h>
#include <stdio.h>
#define HIKARIPB_CALLBACK 1
#define HIKARIPB_PRINT_ENABLE 1
#define HIKARIPB_PRINT(...) printf(__VA_ARGS__)
#define HIKARIPB_PRINTLN(...) do { printf(__VA_ARGS__); printf("\\n"); } while (0)
#define HIKARIPB_ENABLE_REPEATED_BYTES 1
#define HIKARIPB_ENABLE_FLOAT 1
#define demo_Lists_names_size 8U
#define demo_Lists_names_count 3U
#define demo_Lists_blobs_size 4U
#define demo_Lists_blobs_count 2U
#define demo_Lists_ratios_count 2U
#define demo_Lists_streamed_callback_en 1
"""

CPP_CONFIG = CONFIG + """
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

C_MAIN = """#include <string.h>
#include "hikaripb_lists.pb.h"

pb_bool hikaripb_read(pb_u8* data, pb_u16 len) { (void)data; (void)len; return PB_FALSE; }
pb_bool hikaripb_skip(pb_u16 len) { (void)len; return PB_FALSE; }
pb_bool hikaripb_pop(pb_u8* data) { (void)data; return PB_FALSE; }
pb_u32 hikaripb_getReadOffset(void) { return 0U; }
void hikaripb_write(const pb_u8* data, pb_u16 len) { (void)data; (void)len; }
void hikaripb_setWriteOffset(pb_u32 offset) { (void)offset; }
pb_u32 hikaripb_getWriteOffset(void) { return 0U; }
pb_bool demo_Lists_streamed_callback(const struct hikaripb_ItemDescriptor* desc, pb_u16 len, void** item_data) {
    (void)desc; (void)len; (void)item_data;
    return PB_TRUE;
}

int main(void) {
    demo_Lists message;
    demo_Lists_clear(&message);
    message.names.count = 2U;
    message.names.item[0].length = 3U;
    memcpy(message.names.item[0].data, "one", 3U);
    message.names.item[1].length = 0U;
    message.blobs.count = 1U;
    message.blobs.item[0].length = 2U;
    message.blobs.item[0].data[0] = 0x0AU;
    message.blobs.item[0].data[1] = 0xFFU;
    message.tail = 7U;
    message.ratio = 1.5f;
    message.ratios.count = 2U;
    message.ratios.item[0] = 0.5f;
    message.ratios.item[1] = -2.0f;
    hikaripb_setUsed(message.presence, demo_Lists_names_TAG);
    hikaripb_setUsed(message.presence, demo_Lists_blobs_TAG);
    hikaripb_setUsed(message.presence, demo_Lists_streamed_TAG);
    hikaripb_setUsed(message.presence, demo_Lists_ratios_TAG);
    demo_Lists_print(&message);
    demo_Nothing nothing;
    demo_Nothing_clear(&nothing);
    demo_Nothing_print(&nothing);
    return 0;
}
"""

CPP_MAIN = """#include <string.h>
#include "lists.pb.h"

namespace demo {
bool Lists_streamed_callback(hikaripb::Decoder<>&, const hikaripb::ItemDescriptor*, uint16_t, void**) { return true; }
}  // namespace demo

int main() {
    demo::Lists message;
    demo::Lists::clear(&message);
    message.names.count = 2U;
    message.names.item[0].length = 3U;
    memcpy(message.names.item[0].data, "one", 3U);
    message.names.item[1].length = 0U;
    message.blobs.count = 1U;
    message.blobs.item[0].length = 2U;
    message.blobs.item[0].data[0] = 0x0AU;
    message.blobs.item[0].data[1] = 0xFFU;
    message.tail = 7U;
    message.ratio = 1.5f;
    message.ratios.count = 2U;
    message.ratios.item[0] = 0.5f;
    message.ratios.item[1] = -2.0f;
    message.setUsed(demo::Lists::TAG_NAMES);
    message.setUsed(demo::Lists::TAG_BLOBS);
    message.setUsed(demo::Lists::TAG_STREAMED);
    message.setUsed(demo::Lists::TAG_RATIOS);
    message.print();
    demo::Nothing nothing;
    demo::Nothing::clear(&nothing);
    nothing.print();
    return 0;
}
"""

# one name line for every element, the element below it; an empty element has no line; a callback-driven field is
# only named. The decoder marks the fields as used, a field that is not marked is not printed. A message without
# fields prints its name only.
EXPECTED = [
    "Lists:",
    "  names:",
    "    one",
    "  names:",
    "  blobs:",
    "    0A FF",
    "  tail: 7",
    "  streamed: callback",
    "  ratio: 1.5",
    "  ratios:",
    "    0.5",
    "    -2",
    "Nothing:",
]


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


class PrintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which(PROTOC):
            raise unittest.SkipTest("protoc not available")
        cls.dir = tempfile.mkdtemp(prefix="hikaripb_print_")
        cls.addClassCleanup(shutil.rmtree, cls.dir, ignore_errors=True)
        write(os.path.join(cls.dir, "lists.proto"), PROTO)
        cls.out = {}
        for backend in ("c", "cpp"):
            cls.out[backend] = os.path.join(cls.dir, backend)
            os.makedirs(cls.out[backend])
            command = [PROTOC, "--plugin=protoc-gen-hikaripb=" + PLUGIN, "--proto_path=" + cls.dir,
                       f"--hikaripb_out=type={backend}:{cls.out[backend]}", os.path.join(cls.dir, "lists.proto")]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            assert result.returncode == 0, result.stderr

    def run_program(self, backend, compiler, main_name, main, flags, sources):
        cfg = os.path.join(self.dir, "cfg_" + backend)
        os.makedirs(cfg, exist_ok=True)
        write(os.path.join(cfg, "hikaripb_config.h"), CPP_CONFIG if backend == "cpp" else CONFIG)
        main_path = os.path.join(self.dir, main_name)
        write(main_path, main)
        exe = os.path.join(self.dir, "print_" + backend + EXE)
        command = [compiler] + flags + ["-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                                        "-I", self.out[backend], "-I", cfg, main_path] + sources + ["-o", exe]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([exe], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        return [line.rstrip() for line in result.stdout.splitlines()]

    @unittest.skipUnless(CC, "no C compiler")
    def test_c_prints_every_element_of_a_repeated_string_and_bytes_field(self):
        sources = []
        for folder, _, files in os.walk(self.out["c"]):
            sources += [os.path.join(folder, name) for name in files if name.endswith(".c")]
        lines = self.run_program("c", CC, "main.c", C_MAIN, ["-std=c11"], sources)
        self.assertEqual(lines, EXPECTED)

    @unittest.skipUnless(CXX, "no C++ compiler")
    def test_cpp_prints_every_element_of_a_repeated_string_and_bytes_field(self):
        sources = [os.path.join(self.out["cpp"], "hikaripb_bindings.cc")]
        lines = self.run_program("cpp", CXX, "main.cc", CPP_MAIN, ["-std=c++17"], sources)
        self.assertEqual(lines, EXPECTED)


if __name__ == "__main__":
    unittest.main()
