"""Tests of the standard types and features of the C and C++ output.

The generated runtime takes nothing from the C library: the integer types (the macros pb_u8, pb_u32, ...), the boolean
type, NULL and offsetof are defined in <prefix>_types.h, behind the <prefix>_config.h of the user, which can change any
of them. The tests generate a small schema and compile the output without the headers of the C library
(-nostdinc -ffreestanding), with a config that maps the types to those of the C library, and with other types of the
user (skipped without protoc and a compiler).
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

PROTO = """syntax = "proto3";
package demo;
message Inner {
  uint32 a = 1;
  sint32 b = 2;
  fixed32 c = 3;
  sfixed32 d = 4;
  bool e = 5;
}
message Outer {
  uint32 id = 1;
  string name = 2;
  repeated uint32 ids = 3;
  Inner inner = 4;
  oneof pick {
    uint32 x = 5;
    Inner y = 6;
  }
}
"""

SIZES = """#define demo_Outer_name_size 8U
#define demo_Outer_ids_count 4U
"""

# the config of the user needs no header of the C library: the streams of C++ use the plain types
C_CONFIG = "#pragma once\n" + SIZES
CPP_CONFIG = "#pragma once\n" + SIZES + """
namespace hikaripb {
class InputStream {
   public:
    bool read(unsigned char*, unsigned short) { return false; }
    bool skip(unsigned short) { return false; }
    bool pop(unsigned char*) { return false; }
    void setOffset(unsigned int) {}
    unsigned int getOffset() const { return 0; }
};
class OutputStream {
   public:
    void write(const unsigned char*, unsigned short) {}
    void setOffset(unsigned int) {}
    unsigned int getOffset() const { return 0; }
};
}  // namespace hikaripb
"""

C_USE = """#include "hikaripb_msg.pb.h"
void use(void) {
    demo_Outer_WrHandle root = demo_Outer_create();
    demo_Outer_set_id(&root, 1U);
    demo_Inner_WrHandle inner = demo_Outer_add_inner(&root);
    demo_Inner_set_e(&inner, PB_TRUE);
    demo_Inner_destroy_submessage(&inner);
    demo_Outer decoded;
    demo_Outer_clear(&decoded);
    demo_Outer_decode(&decoded);
}
"""

CPP_USE = """#include "msg.pb.h"
void use(hikaripb::Encoder<>& e, hikaripb::Decoder<>& d) {
    {
        auto root = demo::Outer::WrProxy<true>(e);
        root.set_id(1U);
        auto inner = root.add_inner();
        inner.set_e(true);
    }
    demo::Outer message;
    message.decode(d);
}
"""

# a config that takes the types and macros from the headers of the C library
C_STD_TYPES = """#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define pb_s8   int8_t
#define pb_s16  int16_t
#define pb_s32  int32_t
#define pb_s64  int64_t
#define pb_u8   uint8_t
#define pb_u16  uint16_t
#define pb_u32  uint32_t
#define pb_u64  uint64_t
#define pb_size size_t
#define pb_bool bool
#define PB_NULL NULL
#define PB_OFFSETOF(type, member) offsetof(type, member)
"""
CPP_STD_TYPES = """#include <stddef.h>
#include <stdint.h>
#define pb_s8  int8_t
#define pb_s16 int16_t
#define pb_s32 int32_t
#define pb_s64 int64_t
#define pb_u8  uint8_t
#define pb_u16 uint16_t
#define pb_u32 uint32_t
#define pb_u64 uint64_t
#define PB_OFFSETOF(type, member) offsetof(type, member)
"""

# a type of the user is the type in the generated code: unsigned long is wider than a 32-bit integer
C_USER_TYPES = """#define pb_u32 unsigned long
#define pb_bool unsigned short
"""
C_USER_CHECK = """
_Static_assert(sizeof(pb_u32) == sizeof(unsigned long), "the config defines pb_u32");
_Static_assert(sizeof(pb_bool) == sizeof(unsigned short), "the config defines pb_bool");
"""
CPP_USER_TYPES = "#define pb_u32 unsigned long\n"
CPP_USER_CHECK = """
static_assert(sizeof(pb_u32) == sizeof(unsigned long), "the config defines pb_u32");
"""


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


class StdCases:
    """The tests, run once for the C and once for the C++ output."""

    backend = compiler = sources = config = use = user_types = user_check = freestanding = std_flags = None
    std_types = use_name = None

    @classmethod
    def setUpClass(cls):
        if not shutil.which(PROTOC):
            raise unittest.SkipTest("protoc not available")
        if not cls.compiler:
            raise unittest.SkipTest("no compiler for " + cls.backend)
        cls.dir = tempfile.mkdtemp(prefix="hikaripb_std_")
        cls.addClassCleanup(shutil.rmtree, cls.dir, ignore_errors=True)
        cls.out = os.path.join(cls.dir, "out")
        os.makedirs(cls.out)
        write(os.path.join(cls.dir, "msg.proto"), PROTO)
        command = [PROTOC, "--plugin=protoc-gen-hikaripb=" + PLUGIN, "--proto_path=" + cls.dir,
                   f"--hikaripb_out=type={cls.backend}:{cls.out}", os.path.join(cls.dir, "msg.proto")]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0, result.stderr

    def compile(self, case, flags, config, check=""):
        """Compile the generated sources and a use of the API; `check` is added to the file that uses the API."""
        cfg = os.path.join(self.dir, "cfg_" + case)
        os.makedirs(cfg, exist_ok=True)
        write(os.path.join(cfg, "hikaripb_config.h"), config)
        use = os.path.join(cfg, self.use_name)
        write(use, self.use + check)
        for source in [*self.sources(self.out), use]:
            obj = os.path.join(cfg, os.path.basename(source) + ".o")
            command = [self.compiler, *self.std_flags, *flags, "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                       "-I", self.out, "-I", cfg, "-c", source, "-o", obj]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, "%s\n%s" % (" ".join(command), result.stderr))

    def test_compiles_without_the_headers_of_the_c_library(self):
        self.compile("freestanding", self.freestanding, self.config)

    def test_compiles_with_the_types_of_the_c_library(self):
        self.compile("std", [], self.config + self.std_types)

    def test_the_types_of_the_user_are_used(self):
        self.compile("user", self.freestanding, self.config + self.user_types, self.user_check)

    def test_no_generated_file_includes_a_header_of_the_c_library(self):
        found = {}
        for folder, _, names in os.walk(self.out):
            for name in names:
                with open(os.path.join(folder, name), encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("#include <"):
                            found.setdefault(name, []).append(line.strip())
        self.assertEqual(found, {})


@unittest.skipUnless(CC, "no C compiler")
class CTest(StdCases, unittest.TestCase):
    backend, compiler, config, use, use_name = "c", CC, C_CONFIG, C_USE, "use.c"
    user_types, user_check, std_types = C_USER_TYPES, C_USER_CHECK, C_STD_TYPES
    std_flags = ["-std=c11"]
    freestanding = ["-nostdinc", "-ffreestanding"]

    @staticmethod
    def sources(out):
        return sorted(os.path.join(out, name) for name in os.listdir(out) if name.endswith(".c"))


@unittest.skipUnless(CXX, "no C++ compiler")
class CppTest(StdCases, unittest.TestCase):
    backend, compiler, config, use, use_name = "cpp", CXX, CPP_CONFIG, CPP_USE, "use.cc"
    user_types, user_check, std_types = CPP_USER_TYPES, CPP_USER_CHECK, CPP_STD_TYPES
    std_flags = ["-std=c++17"]
    freestanding = ["-nostdinc", "-nostdinc++", "-ffreestanding", "-fno-exceptions", "-fno-rtti"]

    @staticmethod
    def sources(out):
        return [os.path.join(out, "hikaripb_bindings.cc")]


if __name__ == "__main__":
    unittest.main()
