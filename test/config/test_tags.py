"""Tests of field numbers above 255 in the C and C++ output.

The generator picks the type of a field number (`pb_tag`) from the largest field number of the schema, and the decoder
reads the whole field number of the wire: a number that is not a field of the schema must not wrap around to one
that is. The tests generate a schema for every width of the type, build a program that encodes and decodes it, and
check the bytes against a small wire format reader, and the decoder against bytes built by hand (skipped without
protoc and a compiler).
"""

import os
import re
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

# the field numbers of the message Wide: plain, optional and in the oneof (only the last two of it are written by
# the encoder test, the decoder gets one), and the number of the embedded message Inner
CASES = {
    "u8": {"plain": [1], "optional": [15, 254], "oneof": [2, 255], "inner": 100, "type": "pb_u8", "size": 1},
    "u16": {"plain": [1], "optional": [255, 256, 4000], "oneof": [300, 5000], "inner": 3000, "type": "pb_u16", "size": 2},
    "u32": {"plain": [1], "optional": [256, 70000], "oneof": [65536, 100000], "inner": 80000, "type": "pb_u32", "size": 4},
}
MAX_FIELD_NUMBER = 536870911  # 2^29 - 1
UNEXPECTED_EOF = 2  # the value of DECODER_UNEXPECTED_EOF in C and C++


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def proto_text(case):
    lines = ['syntax = "proto3";', "package tags;", "message Inner { uint32 value = 1; }", "message Wide {"]
    lines += [f"  uint32 f{n} = {n};" for n in case["plain"]]
    lines += [f"  optional uint32 f{n} = {n};" for n in case["optional"]]
    lines += ["  oneof choice {"] + [f"    uint32 c{n} = {n};" for n in case["oneof"]] + ["  }"]
    lines += [f"  Inner inner = {case['inner']};", "}"]
    return "\n".join(lines) + "\n"


def value(number):
    return number % 200 + 1


# the wire format, as a reader and a writer that know nothing of the generated code

def varint(number):
    out = bytearray()
    while True:
        byte = number & 0x7F
        number >>= 7
        if number:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def field(number, wire_type, payload):
    """A field: the key, and for a varint the value, for the other wire types the payload (with its length)."""
    key = varint((number << 3) | wire_type)
    if wire_type == 0:
        return key + varint(payload)
    if wire_type == 2:
        return key + varint(len(payload)) + payload
    return key + payload


def parse(data):
    """The fields of a message as (number, wire type, value); a varint can be longer than needed."""
    fields = []
    pos = 0

    def read_varint():
        nonlocal pos
        result = shift = 0
        while True:
            byte = data[pos]
            pos += 1
            result |= (byte & 0x7F) << shift
            shift += 7
            if not byte & 0x80:
                return result

    while pos < len(data):
        key = read_varint()
        number, wire_type = key >> 3, key & 7
        if wire_type == 0:
            fields.append((number, 0, read_varint()))
        elif wire_type == 2:
            length = read_varint()
            fields.append((number, 2, data[pos:pos + length]))
            pos += length
        else:
            raise AssertionError(f"unexpected wire type {wire_type}")
    return fields


def unknown_fields(case):
    """Fields of the wire that are not in the schema, with numbers that wrap around to one that is when the number is
    cut to 8 or to 16 bits."""
    known = set(case["plain"] + case["optional"] + case["oneof"] + [case["inner"]])
    numbers = []
    for number in sorted(known):
        for other in (number + 256, number + 65536):
            if other not in known and other not in numbers:
                numbers.append(other)
    numbers.append(MAX_FIELD_NUMBER)
    payloads = [(0, 99), (2, b"abc"), (5, b"\x01\x02\x03\x04"), (1, b"\x01\x02\x03\x04\x05\x06\x07\x08")]
    return [field(number, *payloads[i % len(payloads)]) for i, number in enumerate(numbers)]


def expected_output(case, values, selected=None, inner=None):
    """What the programs print for a decoded message: the fields that were on the wire, zero and not set for the rest."""
    lines = [f"f{n} {values.get(n, 0)}" for n in case["plain"]]
    lines += [f"f{n} {values.get(n, 0)} {int(n in values)}" for n in case["optional"]]
    lines.append(f"choice {selected or 0}")
    if selected:
        lines.append(f"c{selected} {values[selected]}")
    lines.append(f"inner {int(inner is not None)} {inner or 0}")
    lines.append("error 0")
    return lines


C_HOOKS = """
static pb_u8 g_buf[1024];
static pb_u32 g_len;
static pb_u32 g_wr;
static pb_u32 g_rd;

void hikaripb_write(const pb_u8* data, pb_u16 len) { memcpy(&g_buf[g_wr], data, len); g_wr += len; }
void hikaripb_setWriteOffset(pb_u32 offset) { g_wr = offset; }
pb_u32 hikaripb_getWriteOffset(void) { return g_wr; }
pb_bool hikaripb_read(pb_u8* data, pb_u16 len) {
    if ((g_rd + len) > g_len) { return PB_FALSE; }
    memcpy(data, &g_buf[g_rd], len);
    g_rd += len;
    return PB_TRUE;
}
pb_bool hikaripb_skip(pb_u16 len) {
    if ((g_rd + len) > g_len) { return PB_FALSE; }
    g_rd += len;
    return PB_TRUE;
}
pb_bool hikaripb_pop(pb_u8* data) { return hikaripb_read(data, 1U); }
pb_u32 hikaripb_getReadOffset(void) { return g_rd; }
"""

CPP_CONFIG = """#pragma once
#include <stdint.h>
#include <string.h>

namespace hikaripb {
class InputStream {
    const uint8_t* buffer;
    uint32_t length;
    uint32_t offset = 0;

   public:
    InputStream(const uint8_t* buffer, uint32_t length) : buffer(buffer), length(length) {}
    bool read(uint8_t* data, uint16_t len) {
        if ((offset + len) > length) { return false; }
        memcpy(data, &buffer[offset], len);
        offset += len;
        return true;
    }
    bool skip(uint16_t len) {
        if ((offset + len) > length) { return false; }
        offset += len;
        return true;
    }
    bool pop(uint8_t* data) { return read(data, 1U); }
    void setOffset(uint32_t value) { offset = value; }
    uint32_t getOffset() const { return offset; }
};
class OutputStream {
    uint8_t* buffer;
    uint32_t offset = 0;

   public:
    explicit OutputStream(uint8_t* buffer) : buffer(buffer) {}
    void write(const uint8_t* data, uint16_t len) {
        memcpy(&buffer[offset], data, len);
        offset += len;
    }
    void setOffset(uint32_t value) { offset = value; }
    uint32_t getOffset() const { return offset; }
};
}  // namespace hikaripb
"""

# the hex of the message goes in as the second argument of "decode", comes out of "encode"
MAIN_HEAD = """#include <stdio.h>
#include <stdlib.h>
#include <string.h>
%(include)s

/* the type of a field number must be the one of the case: a negative array size is a compile error */
typedef char tag_type_is_%(type)s[(sizeof(pb_tag) == %(size)uU) ? 1 : -1];
"""

MAIN_BODY = """
static pb_u32 parse_hex(const char* text, pb_u8* out) {
    pb_u32 count = 0U;
    for (; text[0] != '\\0' && text[1] != '\\0'; text += 2) {
        char pair[3] = {text[0], text[1], '\\0'};
        out[count++] = (pb_u8)strtoul(pair, NULL, 16);
    }
    return count;
}

int main(int argc, char** argv) {
    if (argc < 2) { return 2; }
%(run)s
    return 2;
}
"""


def c_program(case):
    encode = ["tags_Wide_WrHandle w = tags_Wide_create();"]
    encode += [f"tags_Wide_set_f{n}(&w, {value(n)}U);" for n in case["plain"] + case["optional"]]
    encode += [f"tags_Wide_set_c{case['oneof'][-1]}(&w, {value(case['oneof'][-1])}U);"]
    encode += ["tags_Inner_WrHandle in = tags_Wide_add_inner(&w);", "tags_Inner_set_value(&in, 4U);",
               "tags_Inner_destroy_submessage(&in);", "g_len = g_wr;",
               'for (pb_u32 i = 0U; i < g_len; i++) { printf("%02X", g_buf[i]); }', 'printf("\\n");', "return 0;"]
    decode = ["g_len = parse_hex(argv[2], g_buf);", "tags_Wide msg;", "tags_Wide_clear(&msg);", "tags_Wide_decode(&msg);"]
    decode += [f'printf("f{n} %u\\n", (unsigned)msg.f{n});' for n in case["plain"]]
    decode += [f'printf("f{n} %u %d\\n", (unsigned)msg.f{n}, (int)tags_Wide_has_f{n}(&msg));' for n in case["optional"]]
    decode += ['printf("choice %u\\n", (unsigned)msg.choice_tag);']
    decode += [f'if (tags_Wide_has_c{n}(&msg)) {{ printf("c{n} %u\\n", (unsigned)msg.choice.c{n}); }}'
               for n in case["oneof"]]
    decode += ['printf("inner %d %u\\n", (int)tags_Wide_has_inner(&msg), (unsigned)msg.inner.value);',
               'printf("error %d\\n", (int)hikaripb_getError());', "return 0;"]
    run = ('    if (strcmp(argv[1], "encode") == 0) {\n        ' + "\n        ".join(encode) + "\n    }\n"
           '    if (strcmp(argv[1], "decode") == 0 && argc == 3) {\n        ' + "\n        ".join(decode) + "\n    }")
    head = MAIN_HEAD % {"include": '#include "hikaripb_tags.pb.h"', "type": case["type"], "size": case["size"]}
    return head + C_HOOKS + MAIN_BODY % {"run": run}


def cpp_program(case):
    encode = ["hikaripb::OutputStream os(g_buf);", "hikaripb::Encoder<> enc(os);", "{",
              "    auto w = tags::Wide::WrProxy<true>(enc);"]
    encode += [f"    w.set_f{n}({value(n)}U);" for n in case["plain"] + case["optional"]]
    encode += [f"    w.set_c{case['oneof'][-1]}({value(case['oneof'][-1])}U);",
               "    auto in = w.add_inner();", "    in.set_value(4U);", "}", "g_len = os.getOffset();",
               'for (uint32_t i = 0U; i < g_len; i++) { printf("%02X", g_buf[i]); }', 'printf("\\n");', "return 0;"]
    decode = ["g_len = parse_hex(argv[2], g_buf);", "hikaripb::InputStream is(g_buf, g_len);",
              "hikaripb::Decoder<> dec(is);", "tags::Wide msg;", "msg.decode(dec);"]
    decode += [f'printf("f{n} %u\\n", (unsigned)msg.f{n});' for n in case["plain"]]
    decode += [f'printf("f{n} %u %d\\n", (unsigned)msg.f{n}, (int)msg.has_f{n}());' for n in case["optional"]]
    decode += ['printf("choice %u\\n", (unsigned)msg.choice_tag);']
    decode += [f'if (msg.has_c{n}()) {{ printf("c{n} %u\\n", (unsigned)msg.choice.c{n}); }}' for n in case["oneof"]]
    decode += ['printf("inner %d %u\\n", (int)msg.has_inner(), (unsigned)msg.inner.value);',
               'printf("error %d\\n", (int)dec.getError());', "return 0;"]
    run = ('    if (strcmp(argv[1], "encode") == 0) {\n        ' + "\n        ".join(encode) + "\n    }\n"
           '    if (strcmp(argv[1], "decode") == 0 && argc == 3) {\n        ' + "\n        ".join(decode) + "\n    }")
    head = MAIN_HEAD % {"include": '#include "tags.pb.h"', "type": case["type"], "size": case["size"]}
    buffer = "\nstatic uint8_t g_buf[1024];\nstatic uint32_t g_len;\n"
    return head + buffer + MAIN_BODY % {"run": run}


class TagTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which(PROTOC):
            raise unittest.SkipTest("protoc not available")
        cls.dir = tempfile.mkdtemp(prefix="hikaripb_tags_")
        cls.addClassCleanup(shutil.rmtree, cls.dir, ignore_errors=True)
        cls.out = {}
        cls.programs = {}
        backends = [("c", CC, ".c", ["-std=c11"], c_program), ("cpp", CXX, ".cc", ["-std=c++17"], cpp_program)]
        for name, case in CASES.items():
            proto_dir = os.path.join(cls.dir, name)
            os.makedirs(proto_dir)
            write(os.path.join(proto_dir, "tags.proto"), proto_text(case))
            for backend, compiler, suffix, flags, program in backends:
                out = os.path.join(proto_dir, backend)
                cfg = os.path.join(proto_dir, "cfg_" + backend)
                os.makedirs(out)
                os.makedirs(cfg)
                cls.out[(backend, name)] = out
                cls.generate(backend, proto_dir, out)
                if not compiler:
                    continue
                write(os.path.join(cfg, "hikaripb_config.h"), CPP_CONFIG if backend == "cpp" else "#pragma once\n")
                main = os.path.join(proto_dir, "main" + suffix)
                write(main, program(case))
                sources = [os.path.join(out, f) for f in sorted(os.listdir(out)) if f.endswith((".c", ".cc"))]
                exe = os.path.join(proto_dir, "tags_" + backend + EXE)
                command = [compiler] + flags + ["-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                                                "-I", out, "-I", cfg, main] + sources + ["-o", exe]
                result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
                assert result.returncode == 0, f"{backend} {name}: {result.stderr}"
                cls.programs[(backend, name)] = exe

    @staticmethod
    def generate(backend, proto_dir, out, proto="tags.proto"):
        command = [PROTOC, "--plugin=protoc-gen-hikaripb=" + PLUGIN, "--proto_path=" + proto_dir,
                   f"--hikaripb_out=type={backend}:{out}", os.path.join(proto_dir, proto)]
        return subprocess.run(command, capture_output=True, text=True, encoding="utf-8")

    def run_program(self, backend, name, *arguments):
        exe = self.programs.get((backend, name))
        if exe is None:
            self.skipTest("no compiler for " + backend)
        result = subprocess.run([exe, *arguments], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        return [line.rstrip() for line in result.stdout.splitlines()]

    def decode(self, backend, name, data):
        return self.run_program(backend, name, "decode", data.hex())

    def test_the_type_of_a_field_number_is_the_smallest_that_holds_the_largest_one(self):
        for (backend, name), out in self.out.items():
            with self.subTest(backend=backend, case=name):
                with open(os.path.join(out, "hikaripb_types.h"), encoding="utf-8") as f:
                    found = re.search(r"^#define pb_tag (\w+)$", f.read(), re.M)
                self.assertEqual(found.group(1), CASES[name]["type"])

    def test_the_encoder_writes_every_field_number(self):
        for name, case in CASES.items():
            numbers = case["plain"] + case["optional"] + [case["oneof"][-1]]
            scalars = b"".join(field(n, 0, value(n)) for n in numbers)
            for backend in ("c", "cpp"):
                with self.subTest(backend=backend, case=name):
                    (line,) = self.run_program(backend, name, "encode")
                    data = bytes.fromhex(line)
                    # a scalar is its key and its value, nothing is padded
                    self.assertTrue(data.startswith(scalars), data.hex())
                    # the length of an embedded message is padded to the bytes that the encoder reserves
                    self.assertEqual(parse(data)[len(numbers):], [(case["inner"], 2, field(1, 0, 4))])

    def test_the_decoder_reads_every_field_number(self):
        for name, case in CASES.items():
            numbers = case["plain"] + case["optional"]
            values = {n: value(n) for n in numbers}
            selected = case["oneof"][0]
            values[selected] = value(selected)
            data = b"".join(field(n, 0, value(n)) for n in numbers) + field(selected, 0, value(selected))
            data += field(case["inner"], 2, field(1, 0, 4))
            for backend in ("c", "cpp"):
                with self.subTest(backend=backend, case=name):
                    self.assertEqual(self.decode(backend, name, data), expected_output(case, values, selected, 4))

    def test_a_message_that_is_encoded_is_decoded(self):
        for name, case in CASES.items():
            for backend in ("c", "cpp"):
                with self.subTest(backend=backend, case=name):
                    (line,) = self.run_program(backend, name, "encode")
                    selected = case["oneof"][-1]
                    values = {n: value(n) for n in case["plain"] + case["optional"] + [selected]}
                    self.assertEqual(self.decode(backend, name, bytes.fromhex(line)),
                                     expected_output(case, values, selected, 4))

    def test_a_field_number_that_is_not_in_the_schema_is_not_taken_for_one_that_is(self):
        for name, case in CASES.items():
            numbers = case["plain"] + case["optional"]
            known = [field(n, 0, value(n)) for n in numbers] + [field(case["oneof"][0], 0, value(case["oneof"][0]))]
            known.append(field(case["inner"], 2, field(1, 0, 4)))
            unknown = unknown_fields(case)
            values = {n: value(n) for n in numbers + [case["oneof"][0]]}
            # the unknown fields come before, between and after the known ones
            data = b"".join(unknown[:2] + known[:1] + unknown[2:-1] + known[1:] + unknown[-1:])
            for backend in ("c", "cpp"):
                with self.subTest(backend=backend, case=name):
                    self.assertEqual(self.decode(backend, name, data),
                                     expected_output(case, values, case["oneof"][0], 4))

    def test_an_unknown_field_that_the_input_cuts_off_is_an_error(self):
        # a field that is skipped must be complete as well: cut inside its value, the end of the input is an error, and
        # the known fields in front of it are decoded
        for name, case in CASES.items():
            numbers = case["plain"] + case["optional"]
            values = {n: value(n) for n in numbers}
            known = b"".join(field(n, 0, value(n)) for n in numbers) + field(case["inner"], 2, field(1, 0, 4))
            expected = expected_output(case, values, inner=4)[:-1] + [f"error {UNEXPECTED_EOF}"]
            for wire_type, payload in ((0, 300), (1, bytes(8)), (2, b"abc"), (5, bytes(4))):
                cut = field(MAX_FIELD_NUMBER, wire_type, payload)[:-1]
                for backend in ("c", "cpp"):
                    with self.subTest(backend=backend, case=name, wire_type=wire_type):
                        self.assertEqual(self.decode(backend, name, known + cut), expected)

    def test_the_generator_stops_at_a_field_number_that_the_descriptors_cannot_address(self):
        # the presence bitmap holds a bit for every field number up to the largest: 65535 bytes at most
        for number, ok in ((524279, True), (524280, False)):
            proto_dir = os.path.join(self.dir, f"limit_{number}")
            os.makedirs(proto_dir)
            write(os.path.join(proto_dir, "limit.proto"),
                  f'syntax = "proto3";\npackage limit;\nmessage Big {{ uint32 value = {number}; }}\n')
            for backend in ("c", "cpp"):
                with self.subTest(backend=backend, number=number):
                    out = os.path.join(proto_dir, backend)
                    os.makedirs(out)
                    result = self.generate(backend, proto_dir, out, "limit.proto")
                    if ok:
                        self.assertEqual(result.returncode, 0, result.stderr)
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn("presence bitmap", result.stderr)


if __name__ == "__main__":
    unittest.main()
