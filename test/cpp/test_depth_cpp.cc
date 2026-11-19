#include <criterion/criterion.h>

#include "depth.pb.h"

// C++ mirror of test_depth.c: a 10-level DepthL0..DepthL9 chain must decode
// successfully under the bumped HIKARIPB_DEC_MAX_DEPTH (12), while a 14-level
// chain must be rejected with DecodeError::DECODER_DEPTH_EXCEEDED.

Test(sample_depth_cpp, ten_levels_decodes_successfully) {
    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);

    {
        auto root = depthpkg::DepthL0::WrProxy<true>(enc);
        root.set_value(0U);
        auto n1 = root.add_next();
        n1.set_value(1U);
        auto n2 = n1.add_next();
        n2.set_value(2U);
        auto n3 = n2.add_next();
        n3.set_value(3U);
        auto n4 = n3.add_next();
        n4.set_value(4U);
        auto n5 = n4.add_next();
        n5.set_value(5U);
        auto n6 = n5.add_next();
        n6.set_value(6U);
        auto n7 = n6.add_next();
        n7.set_value(7U);
        auto n8 = n7.add_next();
        n8.set_value(8U);
        auto n9 = n8.add_next();
        n9.set_value(9U);
        // Leaf: no further nesting. Destructors below finalize deepest-first.
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    depthpkg::DepthL0 decoded;
    decoded.decode(dec);

    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(decoded.value, 0U);
    cr_assert(decoded.has_next());
    cr_assert_eq(decoded.next.value, 1U);
    cr_assert_eq(decoded.next.next.value, 2U);
    cr_assert_eq(decoded.next.next.next.value, 3U);
    cr_assert_eq(decoded.next.next.next.next.value, 4U);
    cr_assert_eq(decoded.next.next.next.next.next.value, 5U);
    cr_assert_eq(decoded.next.next.next.next.next.next.value, 6U);
    cr_assert_eq(decoded.next.next.next.next.next.next.next.value, 7U);
    cr_assert_eq(decoded.next.next.next.next.next.next.next.next.value, 8U);
    cr_assert_eq(decoded.next.next.next.next.next.next.next.next.next.value, 9U);
    cr_assert(!decoded.next.next.next.next.next.next.next.next.next.has_next());
}

Test(sample_depth_cpp, fourteen_levels_exceeds_max_depth) {
    static uint8_t buffer[2048];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);

    {
        auto root = depthpkg::DepthL0::WrProxy<true>(enc);
        auto n1 = root.add_next();
        auto n2 = n1.add_next();
        auto n3 = n2.add_next();
        auto n4 = n3.add_next();
        auto n5 = n4.add_next();
        auto n6 = n5.add_next();
        auto n7 = n6.add_next();
        auto n8 = n7.add_next();
        auto n9 = n8.add_next();
        auto n10 = n9.add_next();
        auto n11 = n10.add_next();
        auto n12 = n11.add_next();
        auto n13 = n12.add_next();
        n13.set_value(13U);
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    depthpkg::DepthL0 decoded;
    decoded.decode(dec);

    cr_assert(dec.hasError());
    cr_assert_eq(dec.getError(), hikaripb::DecodeError::DECODER_DEPTH_EXCEEDED);
}
