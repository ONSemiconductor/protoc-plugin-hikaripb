#ifndef WEATHER_C_CONFIG_H
#define WEATHER_C_CONFIG_H

/*
 * Hand-written configuration of the generated C runtime: the generated weather_c_defines.h includes this
 * file, then weather_c_config_default.h, which defines every setting that is not defined here, and the
 * standard types and features. That file also lists the settings of every message.
 */

#include <stdio.h>

/* Message printing, used by weather_Report_print(): both macros have to be defined. */
#define WEATHER_C_PRINT_ENABLE 1
#define WEATHER_C_PRINT(...)   printf(__VA_ARGS__)
#define WEATHER_C_PRINTLN(...) \
    do {                       \
        printf(__VA_ARGS__);   \
        printf("\n");          \
    } while (0)

/*
 * Storage of strings, bytes and repeated fields: the C structs have no dynamic memory, so every
 * <package>_<Message>_<field>_size (bytes) and <package>_<Message>_<field>_count (elements) is required.
 */
#define weather_Reading_label_size    16U
#define weather_Report_station_size   16U
#define weather_Report_note_size      32U
#define weather_Report_readings_count 4U

#endif /* WEATHER_C_CONFIG_H */
