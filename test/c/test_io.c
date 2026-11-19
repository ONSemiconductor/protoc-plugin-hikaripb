#include "test_io.h"

#include <string.h>

#define TEST_IO_BUFFER_SIZE 2048U

static pb_u8   g_write_buffer[TEST_IO_BUFFER_SIZE];
static pb_u8   g_read_buffer[TEST_IO_BUFFER_SIZE];
static pb_u32  g_write_offset;
static pb_u32  g_read_offset;
static pb_u32  g_read_length;
static pb_bool g_write_overflow;
static pb_u8   g_writer_context_token;

void test_io_reset(void) {
    g_write_offset = 0U;
    g_read_offset = 0U;
    g_read_length = 0U;
    g_write_overflow = false;
}

void test_io_set_read_buffer(const pb_u8* data, pb_u32 len) {
    pb_u32 copy_len = len;

    if (copy_len > TEST_IO_BUFFER_SIZE) {
        copy_len = TEST_IO_BUFFER_SIZE;
    }

    if ((data != (const pb_u8*)0) && (copy_len > 0U)) {
        memcpy(g_read_buffer, data, copy_len);
    }

    g_read_length = copy_len;
    g_read_offset = 0U;
}

void* test_io_writer_context(void) {
    return &g_writer_context_token;
}

const pb_u8* test_io_get_write_buffer(void) {
    return g_write_buffer;
}

pb_u32 test_io_get_write_length(void) {
    return g_write_offset;
}

pb_bool test_io_has_write_overflow(void) {
    return g_write_overflow;
}

pb_bool sample_read(pb_u8* data, pb_u16 len) {
    if ((g_read_offset + len) > g_read_length) {
        return false;
    }

    memcpy(data, &g_read_buffer[g_read_offset], len);
    g_read_offset += len;
    return true;
}

pb_bool sample_skip(pb_u16 len) {
    if ((g_read_offset + len) > g_read_length) {
        return false;
    }

    g_read_offset += len;
    return true;
}

pb_bool sample_pop(pb_u8* data) {
    return sample_read(data, 1U);
}

pb_u32 sample_getReadOffset(void) {
    return g_read_offset;
}

void sample_write(const pb_u8* data, pb_u16 len) {
    if ((g_write_offset + len) > TEST_IO_BUFFER_SIZE) {
        g_write_overflow = true;
        return;
    }

    memcpy(&g_write_buffer[g_write_offset], data, len);
    g_write_offset += len;
}

void sample_setWriteOffset(pb_u32 offset) {
    if (offset <= TEST_IO_BUFFER_SIZE) {
        g_write_offset = offset;
    } else {
        g_write_overflow = true;
    }
}

pb_u32 sample_getWriteOffset(void) {
    return g_write_offset;
}
