/*
 * C++ example: encode a weather.Report with the generated writer proxies, decode it again and print it.
 *
 * The code generated from proto/weather.proto lives in build/examples/generated/cpp, run
 * examples/build first (see ../README.md).
 */
#include <stdio.h>
#include <string.h>

#include "weather.pb.h"  // <proto file>.pb.h, not prefixed

namespace {

// Writes one reading; the humidity is optional and only written when a value is given.
void add_reading(weather::Report::WrProxy<true>& report, uint32_t sensor_id, int32_t temperature, const char* label,
                 const uint32_t* humidity) {
    // an embedded message is finished when its proxy goes out of scope
    auto reading = report.rpt_readings();
    reading.set_sensor_id(sensor_id);
    reading.set_temperature(temperature);
    reading.set_unit(weather::Unit::UNIT_CELSIUS);
    if (humidity != nullptr) {
        reading.set_humidity(*humidity);
    }

    // strings are written as bytes
    auto text = reading.add_label();
    text.write(reinterpret_cast<const uint8_t*>(label), static_cast<uint16_t>(strlen(label)));
}

}  // namespace

int main() {
    uint8_t buffer[256];

    // Encode: the message is written to the buffer while it is built.
    weather_cpp::OutputStream os(buffer);
    weather_cpp::Encoder<> enc(os);
    {
        auto report = weather::Report::WrProxy<true>(enc);
        {
            auto station = report.add_station();
            station.write(reinterpret_cast<const uint8_t*>("roof-1"), 6U);
        }

        const uint32_t humidity = 48U;
        add_reading(report, 1U, 215, "roof", &humidity);
        add_reading(report, 2U, -35, "shed", nullptr);

        // A oneof: setting one member replaces the other, here the note of an operator.
        auto note = report.add_note();
        note.write(reinterpret_cast<const uint8_t*>("calibrated"), 10U);
    }
    uint32_t length = os.getOffset();
    printf("encoded %u bytes\n", static_cast<unsigned>(length));

    // Decode: the fixed-size struct is filled from the buffer.
    weather_cpp::InputStream is(buffer, length);
    weather_cpp::Decoder<> dec(is);
    weather::Report decoded;
    decoded.decode(dec);
    if (dec.hasError()) {
        fprintf(stderr, "decode error %d\n", static_cast<int>(dec.getError()));
        return 1;
    }

    printf("station %.*s\n", static_cast<int>(decoded.station.length),
           reinterpret_cast<const char*>(decoded.station.data));
    for (uint32_t i = 0U; i < decoded.readings.count; i++) {
        const weather::Reading& reading = decoded.readings.item[i];
        printf("sensor %u (%.*s): %d tenths", static_cast<unsigned>(reading.sensor_id),
               static_cast<int>(reading.label.length), reinterpret_cast<const char*>(reading.label.data),
               static_cast<int>(reading.temperature));
        if (reading.has_humidity()) {
            printf(", humidity %u%%", static_cast<unsigned>(reading.humidity));
        }
        printf("\n");
    }
    if (decoded.has_note()) {
        printf("note %.*s\n", static_cast<int>(decoded.status.note.length),
               reinterpret_cast<const char*>(decoded.status.note.data));
    }

    // Every message can print itself (see WEATHER_CPP_PRINT in weather_cpp_config.h).
    printf("\n");
    decoded.print();
    return 0;
}
