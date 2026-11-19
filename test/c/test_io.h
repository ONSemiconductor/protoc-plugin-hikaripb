#ifndef TEST_C_TEST_IO_H
#define TEST_C_TEST_IO_H

#include "sample_defines.h"

// Simple in-memory reader/writer implementing the generated sample_read/sample_write
// family of functions required by protoc/c's generated defines.h (see sample_defines.h).

#ifdef __cplusplus
extern "C" {
#endif

void         test_io_reset(void);
void         test_io_set_read_buffer(const pb_u8* data, pb_u32 len);
void*        test_io_writer_context(void);
const pb_u8* test_io_get_write_buffer(void);
pb_u32       test_io_get_write_length(void);
pb_bool      test_io_has_write_overflow(void);

#ifdef __cplusplus
}
#endif

#endif
