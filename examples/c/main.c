/*
 * C example: encode a weather.Report with the generated writer API, decode it again and print it.
 *
 * The code generated from proto/weather.proto lives in build/examples/generated/c, run
 * examples/build first (see ../README.md).
 */
#include <stdio.h>
#include <string.h>

#include "weather_c_weather.pb.h" /* <prefix>_<proto file>.pb.h */

/*
 * The generated runtime does no I/O of its own, it calls the hooks declared in weather_c_defines.h.
 * Here they work on one memory buffer that is written by the encoder and read by the decoder.
 */
#define BUFFER_SIZE 256U

static pb_u8 g_buffer[BUFFER_SIZE];
static pb_u32 g_write_offset;
static pb_u32 g_read_offset;
static pb_bool g_overflow;

void weather_c_write(const pb_u8* data, pb_u16 len) {
    if ((g_write_offset + len) > BUFFER_SIZE) {
        g_overflow = PB_TRUE;
        return;
    }
    memcpy(&g_buffer[g_write_offset], data, len);
    g_write_offset += len;
}

/* The encoder reserves the length of an embedded message and patches it after the message is written. */
void weather_c_setWriteOffset(pb_u32 offset) {
    g_write_offset = offset;
}

pb_u32 weather_c_getWriteOffset(void) {
    return g_write_offset;
}

pb_bool weather_c_read(pb_u8* data, pb_u16 len) {
    if ((g_read_offset + len) > g_write_offset) {
        return PB_FALSE;
    }
    memcpy(data, &g_buffer[g_read_offset], len);
    g_read_offset += len;
    return PB_TRUE;
}

pb_bool weather_c_skip(pb_u16 len) {
    if ((g_read_offset + len) > g_write_offset) {
        return PB_FALSE;
    }
    g_read_offset += len;
    return PB_TRUE;
}

pb_bool weather_c_pop(pb_u8* data) {
    return weather_c_read(data, 1U);
}

pb_u32 weather_c_getReadOffset(void) {
    return g_read_offset;
}

/*
 * The functions of the generated header: <message>_create() starts a message, <message>_set_<field>(&handle, value)
 * writes a scalar and <message>_add_<field>(&handle) opens an embedded message or a string.
 * This one writes a reading; the humidity is optional and only written when a value is given.
 */
static void add_reading(weather_Report_WrHandle* report, pb_u32 sensor_id, pb_s32 temperature, const char* label,
                        const pb_u32* humidity) {
    weather_Reading_WrHandle reading = weather_Report_add_readings(report);
    weather_Reading_set_sensor_id(&reading, sensor_id);
    weather_Reading_set_temperature(&reading, temperature);
    weather_Reading_set_unit(&reading, weather_Unit_UNIT_CELSIUS);
    if (humidity != NULL) {
        weather_Reading_set_humidity(&reading, *humidity);
    }

    /* strings are written as bytes */
    weather_Reading_label_WrHandle text = weather_Reading_add_label(&reading);
    weather_Reading_label_addBytes(&text, (const pb_u8*)label, (pb_u16)strlen(label));
    weather_Reading_label_done(&text);

    weather_Reading_destroy_submessage(&reading);
}

static void encode_with_functions(void) {
    weather_Report_WrHandle report = weather_Report_create();

    weather_Report_station_WrHandle station = weather_Report_add_station(&report);
    weather_Report_station_addBytes(&station, (const pb_u8*)"roof-1", 6U);
    weather_Report_station_done(&station);

    const pb_u32 humidity = 48U;
    add_reading(&report, 1U, 215, "roof", &humidity);
    add_reading(&report, 2U, -35, "shed", NULL);

    /* A oneof: setting one member replaces the other, here the note of an operator. */
    weather_Report_note_WrHandle note = weather_Report_add_note(&report);
    weather_Report_note_addBytes(&note, (const pb_u8*)"calibrated", 10U);
    weather_Report_note_done(&note);
}

/*
 * The same message with the macros and the structs of function pointers of the generated header. <message>_WrTop(name)
 * defines the write handle `name_hdl` of a top-level message and `name`, a pointer to a const struct that holds the
 * functions of the message; <message>_Wr(name, handle) does the same for an embedded message, and
 * <message>_<field>_Wr(name, handle) for a string or bytes field. A call reads name->set_<field>(&name_hdl, value),
 * and the embedded ones are finished with name->done(&name_hdl). The bytes are the same as the ones of the functions.
 */
static void encode_with_macros(void) {
    weather_Report_WrTop(report);

    weather_Report_station_Wr(station, report->add_station(&report_hdl));
    station->write(&station_hdl, (const pb_u8*)"roof-1", 6U);
    station->done(&station_hdl);

    {
        weather_Reading_Wr(reading, report->add_readings(&report_hdl));
        reading->set_sensor_id(&reading_hdl, 1U);
        reading->set_temperature(&reading_hdl, 215);
        reading->set_unit(&reading_hdl, weather_Unit_UNIT_CELSIUS);
        reading->set_humidity(&reading_hdl, 48U);
        weather_Reading_label_Wr(label, reading->add_label(&reading_hdl));
        label->write(&label_hdl, (const pb_u8*)"roof", 4U);
        label->done(&label_hdl);
        reading->done(&reading_hdl);
    }
    {
        weather_Reading_Wr(reading, report->add_readings(&report_hdl));
        reading->set_sensor_id(&reading_hdl, 2U);
        reading->set_temperature(&reading_hdl, -35);
        reading->set_unit(&reading_hdl, weather_Unit_UNIT_CELSIUS);
        weather_Reading_label_Wr(label, reading->add_label(&reading_hdl));
        label->write(&label_hdl, (const pb_u8*)"shed", 4U);
        label->done(&label_hdl);
        reading->done(&reading_hdl);
    }

    weather_Report_note_Wr(note, report->add_note(&report_hdl));
    note->write(&note_hdl, (const pb_u8*)"calibrated", 10U);
    note->done(&note_hdl);
}

int main(void) {
    /* Encode: the message is written to the buffer while it is built. */
    encode_with_functions();

    if (g_overflow) {
        fprintf(stderr, "buffer too small\n");
        return 1;
    }
    printf("encoded %u bytes\n", (unsigned)g_write_offset);

    /* The macros write the same bytes: encode again and compare. */
    static pb_u8 first[BUFFER_SIZE];
    const pb_u32 length = g_write_offset;
    memcpy(first, g_buffer, length);
    g_write_offset = 0U;
    encode_with_macros();
    if (g_overflow || g_write_offset != length || memcmp(first, g_buffer, length) != 0) {
        fprintf(stderr, "the macros write other bytes\n");
        return 1;
    }
    printf("the macros write the same bytes\n");

    /* Decode: the fixed-size struct is filled from the buffer. */
    weather_Report decoded;
    weather_Report_clear(&decoded);
    weather_Report_decode(&decoded);
    if (weather_c_hasError()) {
        fprintf(stderr, "decode error %d\n", (int)weather_c_getError());
        return 1;
    }

    printf("station %.*s\n", (int)decoded.station.length, (const char*)decoded.station.data);
    for (pb_u32 i = 0U; i < decoded.readings.count; i++) {
        const weather_Reading* reading = &decoded.readings.item[i];
        printf("sensor %u (%.*s): %d tenths", (unsigned)reading->sensor_id, (int)reading->label.length,
               (const char*)reading->label.data, (int)reading->temperature);
        if (weather_Reading_has_humidity(reading)) {
            printf(", humidity %u%%", (unsigned)reading->humidity);
        }
        printf("\n");
    }
    if (weather_Report_has_note(&decoded)) {
        printf("note %.*s\n", (int)decoded.status.note.length, (const char*)decoded.status.note.data);
    }

    /* Every message can print itself (see WEATHER_C_PRINT in weather_c_config.h). */
    printf("\n");
    weather_Report_print(&decoded);
    return 0;
}
