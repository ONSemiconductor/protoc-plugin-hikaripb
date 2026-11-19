#include <criterion/criterion.h>

#include "test_io.h"
#include "sample_nested.pb.h"

// nested.proto declares Outer.Middle.Inner.Leaf and an enum in each of them: messages and enums nested up to
// three levels below a top-level message encode and decode like any other type.

Test(sample_nested, four_levels_round_trip) {
    test_io_reset();

    nestedpkg_Outer_WrHandle outer = nestedpkg_Outer_create();
    nestedpkg_Outer_set_kind(&outer, nestedpkg_OuterKind_OUTER_KIND_SECOND);

    nestedpkg_Leaf_WrHandle shortcut = nestedpkg_Outer_add_shortcut(&outer);
    nestedpkg_Leaf_set_kind(&shortcut, nestedpkg_LeafKind_LEAF_KIND_SECOND);
    nestedpkg_Leaf_set_value(&shortcut, 77U);
    nestedpkg_Leaf_destroy_submessage(&shortcut);

    nestedpkg_Middle_WrHandle middle = nestedpkg_Outer_add_middle(&outer);
    nestedpkg_Middle_set_kind(&middle, nestedpkg_MiddleKind_MIDDLE_KIND_FIRST);
    nestedpkg_Inner_WrHandle inner = nestedpkg_Middle_add_inner(&middle);
    nestedpkg_Inner_set_kind(&inner, nestedpkg_InnerKind_INNER_KIND_SECOND);
    nestedpkg_Leaf_WrHandle leaf = nestedpkg_Inner_add_leaf(&inner);
    nestedpkg_Leaf_set_kind(&leaf, nestedpkg_LeafKind_LEAF_KIND_FIRST);
    nestedpkg_Leaf_set_value(&leaf, 1234U);

    // Finalize length prefixes deepest-first; the outer handles are not touched again.
    nestedpkg_Leaf_destroy_submessage(&leaf);
    nestedpkg_Inner_destroy_submessage(&inner);
    nestedpkg_Middle_destroy_submessage(&middle);

    cr_assert(!test_io_has_write_overflow());

    test_io_set_read_buffer(test_io_get_write_buffer(), test_io_get_write_length());
    nestedpkg_Outer decoded;
    nestedpkg_Outer_clear(&decoded);
    nestedpkg_Outer_decode(&decoded);

    cr_assert(!sample_hasError(), "decode error %d", sample_getError());
    cr_assert_eq((pb_u32)decoded.kind, (pb_u32)nestedpkg_OuterKind_OUTER_KIND_SECOND);
    cr_assert(nestedpkg_Outer_has_shortcut(&decoded));
    cr_assert_eq((pb_u32)decoded.shortcut.kind, (pb_u32)nestedpkg_LeafKind_LEAF_KIND_SECOND);
    cr_assert_eq(decoded.shortcut.value, 77U);
    cr_assert(nestedpkg_Outer_has_middle(&decoded));
    cr_assert_eq((pb_u32)decoded.middle.kind, (pb_u32)nestedpkg_MiddleKind_MIDDLE_KIND_FIRST);
    cr_assert(nestedpkg_Middle_has_inner(&decoded.middle));
    cr_assert_eq((pb_u32)decoded.middle.inner.kind, (pb_u32)nestedpkg_InnerKind_INNER_KIND_SECOND);
    cr_assert(nestedpkg_Inner_has_leaf(&decoded.middle.inner));
    cr_assert_eq((pb_u32)decoded.middle.inner.leaf.kind, (pb_u32)nestedpkg_LeafKind_LEAF_KIND_FIRST);
    cr_assert_eq(decoded.middle.inner.leaf.value, 1234U);
}
