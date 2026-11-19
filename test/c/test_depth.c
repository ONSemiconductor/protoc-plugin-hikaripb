#include <criterion/criterion.h>

#include "test_io.h"
#include "sample_depth.pb.h"

// Exercises the generated iterative decoder's message-nesting depth limit
// (SAMPLE_DEC_MAX_DEPTH, bumped to 12 in sample_config.h): a 10-level chain
// (at least 10 embedded messages) must decode successfully, while a deeper
// 14-level chain must be rejected with DECODER_DEPTH_EXCEEDED.

Test(sample_depth, ten_levels_decodes_successfully) {
    test_io_reset();

    depthpkg_DepthL0_WrHandle h0 = depthpkg_DepthL0_create();
    depthpkg_DepthL0_set_value(&h0, 0U);
    depthpkg_DepthL1_WrHandle h1 = depthpkg_DepthL0_add_next(&h0);
    depthpkg_DepthL1_set_value(&h1, 1U);
    depthpkg_DepthL2_WrHandle h2 = depthpkg_DepthL1_add_next(&h1);
    depthpkg_DepthL2_set_value(&h2, 2U);
    depthpkg_DepthL3_WrHandle h3 = depthpkg_DepthL2_add_next(&h2);
    depthpkg_DepthL3_set_value(&h3, 3U);
    depthpkg_DepthL4_WrHandle h4 = depthpkg_DepthL3_add_next(&h3);
    depthpkg_DepthL4_set_value(&h4, 4U);
    depthpkg_DepthL5_WrHandle h5 = depthpkg_DepthL4_add_next(&h4);
    depthpkg_DepthL5_set_value(&h5, 5U);
    depthpkg_DepthL6_WrHandle h6 = depthpkg_DepthL5_add_next(&h5);
    depthpkg_DepthL6_set_value(&h6, 6U);
    depthpkg_DepthL7_WrHandle h7 = depthpkg_DepthL6_add_next(&h6);
    depthpkg_DepthL7_set_value(&h7, 7U);
    depthpkg_DepthL8_WrHandle h8 = depthpkg_DepthL7_add_next(&h7);
    depthpkg_DepthL8_set_value(&h8, 8U);
    depthpkg_DepthL9_WrHandle h9 = depthpkg_DepthL8_add_next(&h8);
    depthpkg_DepthL9_set_value(&h9, 9U);
    // Leaf: no further nesting.

    // Finalize length prefixes deepest-first; none of the outer handles are
    // touched again once their nested "next" handle has been opened.
    depthpkg_DepthL9_destroy_submessage(&h9);
    depthpkg_DepthL8_destroy_submessage(&h8);
    depthpkg_DepthL7_destroy_submessage(&h7);
    depthpkg_DepthL6_destroy_submessage(&h6);
    depthpkg_DepthL5_destroy_submessage(&h5);
    depthpkg_DepthL4_destroy_submessage(&h4);
    depthpkg_DepthL3_destroy_submessage(&h3);
    depthpkg_DepthL2_destroy_submessage(&h2);
    depthpkg_DepthL1_destroy_submessage(&h1);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    depthpkg_DepthL0 decoded;
    depthpkg_DepthL0_clear(&decoded);
    depthpkg_DepthL0_decode(&decoded);

    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq(decoded.value, 0U);
    cr_assert(depthpkg_DepthL0_has_next(&decoded));
    cr_assert_eq(decoded.next.value, 1U);
    cr_assert(depthpkg_DepthL1_has_next(&decoded.next));
    cr_assert_eq(decoded.next.next.value, 2U);
    cr_assert_eq(decoded.next.next.next.value, 3U);
    cr_assert_eq(decoded.next.next.next.next.value, 4U);
    cr_assert_eq(decoded.next.next.next.next.next.value, 5U);
    cr_assert_eq(decoded.next.next.next.next.next.next.value, 6U);
    cr_assert_eq(decoded.next.next.next.next.next.next.next.value, 7U);
    cr_assert_eq(decoded.next.next.next.next.next.next.next.next.value, 8U);
    cr_assert_eq(decoded.next.next.next.next.next.next.next.next.next.value, 9U);
    cr_assert(!depthpkg_DepthL9_has_next(&decoded.next.next.next.next.next.next.next.next.next));
}

Test(sample_depth, fourteen_levels_exceeds_max_depth) {
    test_io_reset();

    depthpkg_DepthL0_WrHandle h0 = depthpkg_DepthL0_create();
    depthpkg_DepthL1_WrHandle h1 = depthpkg_DepthL0_add_next(&h0);
    depthpkg_DepthL2_WrHandle h2 = depthpkg_DepthL1_add_next(&h1);
    depthpkg_DepthL3_WrHandle h3 = depthpkg_DepthL2_add_next(&h2);
    depthpkg_DepthL4_WrHandle h4 = depthpkg_DepthL3_add_next(&h3);
    depthpkg_DepthL5_WrHandle h5 = depthpkg_DepthL4_add_next(&h4);
    depthpkg_DepthL6_WrHandle h6 = depthpkg_DepthL5_add_next(&h5);
    depthpkg_DepthL7_WrHandle h7 = depthpkg_DepthL6_add_next(&h6);
    depthpkg_DepthL8_WrHandle h8 = depthpkg_DepthL7_add_next(&h7);
    depthpkg_DepthL9_WrHandle h9 = depthpkg_DepthL8_add_next(&h8);
    depthpkg_DepthL10_WrHandle h10 = depthpkg_DepthL9_add_next(&h9);
    depthpkg_DepthL11_WrHandle h11 = depthpkg_DepthL10_add_next(&h10);
    depthpkg_DepthL12_WrHandle h12 = depthpkg_DepthL11_add_next(&h11);
    depthpkg_DepthL13_WrHandle h13 = depthpkg_DepthL12_add_next(&h12);
    depthpkg_DepthL13_set_value(&h13, 13U);

    depthpkg_DepthL12_destroy_submessage(&h12);
    depthpkg_DepthL11_destroy_submessage(&h11);
    depthpkg_DepthL10_destroy_submessage(&h10);
    depthpkg_DepthL9_destroy_submessage(&h9);
    depthpkg_DepthL8_destroy_submessage(&h8);
    depthpkg_DepthL7_destroy_submessage(&h7);
    depthpkg_DepthL6_destroy_submessage(&h6);
    depthpkg_DepthL5_destroy_submessage(&h5);
    depthpkg_DepthL4_destroy_submessage(&h4);
    depthpkg_DepthL3_destroy_submessage(&h3);
    depthpkg_DepthL2_destroy_submessage(&h2);
    depthpkg_DepthL1_destroy_submessage(&h1);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    depthpkg_DepthL0 decoded;
    depthpkg_DepthL0_clear(&decoded);
    depthpkg_DepthL0_decode(&decoded);

    cr_assert(sample_hasError());
    cr_assert_eq(sample_getError(), SAMPLE_DECODER_DEPTH_EXCEEDED);
}
