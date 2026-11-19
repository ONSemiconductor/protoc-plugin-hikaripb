#include <criterion/criterion.h>

#include "nested.pb.h"

// C++ mirror of test_nested.c: messages and enums nested up to three levels below a top-level message
// (nested.proto: Outer.Middle.Inner.Leaf) encode and decode like any other type.

Test(sample_nested_cpp, four_levels_round_trip) {
    static uint8_t buffer[256];
    hikaripb::OutputStream os(buffer);
    hikaripb::Encoder<> enc(os);

    {
        auto outer = nestedpkg::Outer::WrProxy<true>(enc);
        outer.set_kind(nestedpkg::OUTER_KIND_SECOND);
        {
            auto shortcut = outer.add_shortcut();
            shortcut.set_kind(nestedpkg::LEAF_KIND_SECOND);
            shortcut.set_value(77U);
        }
        auto middle = outer.add_middle();
        middle.set_kind(nestedpkg::MIDDLE_KIND_FIRST);
        auto inner = middle.add_inner();
        inner.set_kind(nestedpkg::INNER_KIND_SECOND);
        auto leaf = inner.add_leaf();
        leaf.set_kind(nestedpkg::LEAF_KIND_FIRST);
        leaf.set_value(1234U);
        // Destructors below finalize deepest-first.
    }

    uint32_t len = os.getOffset();
    hikaripb::InputStream is(buffer, len);
    hikaripb::Decoder<> dec(is);
    nestedpkg::Outer decoded;
    decoded.decode(dec);

    cr_assert(!dec.hasError(), "decode error %d", dec.getError());
    cr_assert_eq(decoded.kind, nestedpkg::OUTER_KIND_SECOND);
    cr_assert(decoded.has_shortcut());
    cr_assert_eq(decoded.shortcut.kind, nestedpkg::LEAF_KIND_SECOND);
    cr_assert_eq(decoded.shortcut.value, 77U);
    cr_assert(decoded.has_middle());
    cr_assert_eq(decoded.middle.kind, nestedpkg::MIDDLE_KIND_FIRST);
    cr_assert(decoded.middle.has_inner());
    cr_assert_eq(decoded.middle.inner.kind, nestedpkg::INNER_KIND_SECOND);
    cr_assert(decoded.middle.inner.has_leaf());
    cr_assert_eq(decoded.middle.inner.leaf.kind, nestedpkg::LEAF_KIND_FIRST);
    cr_assert_eq(decoded.middle.inner.leaf.value, 1234U);
}
