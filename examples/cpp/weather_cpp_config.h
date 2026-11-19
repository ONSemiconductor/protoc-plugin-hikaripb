#ifndef WEATHER_CPP_CONFIG_H
#define WEATHER_CPP_CONFIG_H

/*
 * Hand-written configuration of the generated C++ codec: the generated weather_cpp_defines.h includes this
 * file, then weather_cpp_config_default.h, which defines every setting that is not defined here, and the
 * standard types and features.
 */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

// Message printing, used by Report::print(): both macros have to be defined.
#define WEATHER_CPP_PRINT_ENABLE 1
#define WEATHER_CPP_PRINT(...)   printf(__VA_ARGS__)
#define WEATHER_CPP_PRINTLN(...) \
    do {                         \
        printf(__VA_ARGS__);     \
        printf("\n");            \
    } while (0)

// Storage of strings, bytes and repeated fields: the structs have no dynamic memory, so every
// <package>_<Message>_<field>_size (bytes) and <package>_<Message>_<field>_count (elements) is required.
#define weather_Reading_label_size    16U
#define weather_Report_station_size   16U
#define weather_Report_note_size      32U
#define weather_Report_readings_count 4U

namespace weather_cpp {

// The codec only knows these two classes by name (weather_cpp_defines.h forward-declares them): it reads from
// an InputStream and writes to an OutputStream, here both work on a memory buffer.
class InputStream {
    uint8_t* buffer;
    uint32_t& length;
    uint32_t offset = 0;

   public:
    InputStream(uint8_t* buffer, uint32_t& length) : buffer(buffer), length(length) {}

    bool read(uint8_t* data, uint16_t len) {
        if ((offset + len) > length) {
            return false;
        }
        memcpy(data, &buffer[offset], len);
        offset += len;
        return true;
    }

    bool skip(uint16_t len) {
        if ((offset + len) > length) {
            return false;
        }
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

    // The encoder reserves the length of an embedded message and patches it after the message is written.
    void setOffset(uint32_t value) { offset = value; }

    uint32_t getOffset() const { return offset; }
};

}  // namespace weather_cpp

#endif  // WEATHER_CPP_CONFIG_H
