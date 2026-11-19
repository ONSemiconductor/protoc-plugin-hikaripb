"""Unit tests of the directory structure of the navigation of type=sphinxdocs."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "protoc"))

from sphinxdocs import parser  # noqa: E402


def pages(*names):
    """Pages that only have a name."""
    result = []
    for name in names:
        page = parser._Page.__new__(parser._Page)
        page.name = name
        result.append(page)
    return result


def shape(node):
    """Nested lists of the names of the items of a directory, directories as ("path", [...])."""
    return [(child.path, shape(child)) if isinstance(child, parser._Dir) else child.name for child in node.children]


class TreeTest(unittest.TestCase):
    def tree(self, *names):
        return parser._tree(pages(*names))

    def test_files_without_a_directory_are_on_the_top_level(self):
        self.assertEqual(shape(self.tree("a.proto", "b.proto")), ["a.proto", "b.proto"])

    def test_directory_with_several_files_is_a_level(self):
        self.assertEqual(shape(self.tree("a.proto", "d/x.proto", "d/y.proto")),
                         ["a.proto", ("d", ["d/x.proto", "d/y.proto"])])

    def test_directory_with_one_file_is_replaced_by_the_file(self):
        self.assertEqual(shape(self.tree("a.proto", "d/x.proto", "e/y.proto", "e/z.proto")),
                         ["a.proto", "d/x.proto", ("e", ["e/y.proto", "e/z.proto"])])

    def test_chain_of_directories_with_one_item_collapses(self):
        self.assertEqual(shape(self.tree("a/b/c/x.proto", "y.proto")), ["a/b/c/x.proto", "y.proto"])

    def test_directory_holding_only_a_directory_is_replaced_by_it(self):
        self.assertEqual(shape(self.tree("a/b/x.proto", "a/b/y.proto")), [("a/b", ["a/b/x.proto", "a/b/y.proto"])])

    def test_nested_directories(self):
        self.assertEqual(shape(self.tree("a/x.proto", "a/b/y.proto", "a/b/z.proto")),
                         [("a", ["a/x.proto", ("a/b", ["a/b/y.proto", "a/b/z.proto"])])])

    def test_directory_with_a_readme_is_not_replaced_by_its_file(self):
        root = parser._tree(pages("a.proto", "d/x.proto", "e/y.proto", "f/g/z.proto"),
                            {"d": ("d/readme.md", "Text"), "f/g": ("f/g/readme.md", "Text")})
        self.assertEqual(shape(root), ["a.proto", ("d", ["d/x.proto"]), "e/y.proto", ("f/g", ["f/g/z.proto"])])

    def test_items_keep_the_order_of_their_first_appearance(self):
        self.assertEqual(shape(self.tree("d/x.proto", "a.proto", "d/y.proto", "b.proto")),
                         [("d", ["d/x.proto", "d/y.proto"]), "a.proto", "b.proto"])


class TitleTest(unittest.TestCase):
    def test_titles_are_relative_to_the_directory_that_lists_them(self):
        root = parser._tree(pages("a.proto", "d/x.proto", "d/y.proto", "d/e/p.proto", "d/e/q.proto"))
        directory = root.children[1]
        # a directory has no trailing slash and a capital first letter
        self.assertEqual([parser._title(child, root) for child in root.children], ["a.proto", "D"])
        self.assertEqual([parser._title(child, directory) for child in directory.children],
                         ["x.proto", "y.proto", "E"])
        self.assertEqual(parser._title(directory.children[2].children[0], directory.children[2]), "p.proto")

    def test_a_chain_of_directories_keeps_its_path(self):
        root = parser._tree(pages("a/b/x.proto", "a/b/y.proto"))
        self.assertEqual(parser._title(root.children[0], root), "A/b")

    def test_a_page_is_listed_with_its_title(self):
        titled, plain = pages("d/x.proto", "d/y.proto")
        titled.page_id, titled.title = "x", "The X"
        root = parser._tree([titled, plain])
        self.assertEqual([parser._title(child, root.children[0]) for child in root.children[0].children],
                         ["The X", "y.proto"])


class PathTest(unittest.TestCase):
    def test_relative_paths(self):
        self.assertEqual(parser._relative("a/b.md", ""), "a/b.md")
        self.assertEqual(parser._relative("a/b.md", "a"), "b.md")
        self.assertEqual(parser._relative("a/b.md", "c/d"), "../../a/b.md")
        self.assertEqual(parser._relative("../x/y.png", "a/b"), "../../../x/y.png")
        self.assertEqual(parser._relative("a", "a"), ".")


if __name__ == "__main__":
    unittest.main()
