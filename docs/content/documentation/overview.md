# Using the documentation generator

`type=sphinxdocs` generates documentation instead of code: [Sphinx](https://www.sphinx-doc.org) pages written in
[MyST](https://myst-parser.readthedocs.io) Markdown. The text is derived from the comments of the `.proto` files, so
the quality of the documentation of a message, a field or an enum value depends directly on its comment.

The Sphinx project that builds the pages requires only the `myst_parser` extension
(`pip install sphinx myst-parser`). The pages contain no markup specific to a theme or another extension and adopt the
appearance of the theme used by the project.

## Generate and build

```sh
mkdir -p docs
protoc --experimental_allow_proto3_optional \
    --plugin=protoc-gen-hikaripb=protoc/hikaripb.py \
    --proto_path=examples/proto \
    --hikaripb_out=type=sphinxdocs,prefix=weather_docs,title=Weather+station+protocol:docs \
    examples/proto/weather.proto
sphinx-build -b html docs build/html
```

The options are described in [Configuration options](configuration.md). They include `parent`, which makes the pages a
chapter of an existing Sphinx project; `pages` and `home`, which add custom pages; and `inline_protocol`, which
prepares the output for a book (LaTeX, PDF).

| Generated file | Content |
|----------------|---------|
| `index.md` | The home page, which lists the top level of the navigation. |
| `<file>.md` | One page per `.proto` file, titled with its path (`a/b.proto` becomes `a/b.md`) or with its `@page` title. The page shows the header of the file, which consists of the comments before `syntax` and `package`. |
| `<file>-protocol.md` | The Protocol of the file, a subpage of the file's page, with a *Messages* and an *Enumerations* section. Each message lists its fields in the order of the file, with name, type, `optional`/`repeated`/`required` and comment; a `oneof` groups its members, and message and enum types link to their definitions. Nested types follow their parent as `Parent.Nested`. |
| `<dir>/index.md` | A page for every directory with several files, listing its files and subdirectories. |
| `conf.py` | A minimal Sphinx configuration (`project`, the `myst_parser` extension and the default theme). It is rewritten on every run; `omit_conf` preserves a custom configuration. |

The navigation follows the directory structure of the `.proto` files:

- A directory with several files forms a separate navigation entry (`server/` becomes *Server*). A directory with a
  single entry does not form a level of its own; its entry moves up one level, recursively.
- The lists show the first sentence of the header of each file.
- Files that no other file imports come first, each followed by the files it imports; the entries of a directory
  appear in the order in which this traversal reaches them. The pages added with
  [`pages`](configuration.md#pages-from-markdown-files) precede all of them.
- Field numbers (of fields and `reserved` ranges) and the numeric values of enum values are not documented.

## Write the comments

The comments of the `.proto` files are Markdown (CommonMark and MyST) with Doxygen commands, written with a leading
`@` or `\` (`\ref`). Commands within code spans and code blocks are not interpreted; `\@` produces a literal `@`.

```proto
// Measurement of one sensor, see @ref Report.
message Reading {
  // Temperature in tenths of a degree.
  // @note Negative below zero. The unit is in @ref Reading.unit.
  sint32 temperature = 2;
}
```

| Command | Result |
|---------|--------|
| `@ref name ["text"]` | A link to the message, field, oneof, enum, enum value, `@anchor`, `@section` or page `name`. The name is resolved according to the protobuf scoping rules: relative to the comment (its message, then the package, then the parent packages); a leading `.` makes it absolute; `Message.field`, `pkg.Message` and `Enum.value` are supported. If no symbol of that name is in scope, a page of that name is used. A name that protobuf cannot resolve is accepted if exactly one symbol ends with it (searching the same file first). Otherwise, the name is reported on stderr and rendered as code. |
| `@page name Title` | In a file header: the title and the name of the page of the file, see [Pages](#pages). |
| `@note`, `@remark`, `@warning`, `@attention`, `@important`, `@hint`, `@tip`, `@caution`, `@danger`, `@error`, `@see`/`@sa`, `@todo`, `@bug`, `@deprecated`, `@pre`, `@post`, `@invariant` | An admonition containing the paragraph that follows the command (up to the next blank line or command). |
| `@brief`, `@details` | Plain text. |
| `@par Title`, `@since`, `@version`, `@author`, `@date`, `@copyright`, `@return`, `@retval`, `@param` | A paragraph with a bold title or label. |
| `@c word`/`@p word`, `@b word`, `@a word`/`@e word`/`@em word` | Code, bold, emphasis. |
| `@code{.lang}` ... `@endcode`, `@verbatim` ... `@endverbatim` | A code block. |
| `@image html file "caption" width=50%` | A figure (only the `html` variant is used; the other variants duplicate it). |
| `@section id Title`, `@subsection`, `@subsubsection`, `@anchor id` | A heading with a label; a label. |
| `@f$` ... `@f$`, `@f[` ... `@f]` | Mathematical notation. |
| `@li`, `@n` | A list item; a line break. |
| `@htmlonly`, `@latexonly` | Raw HTML; raw LaTeX. |
| `@cond` ... `@endcond`, `@internal` ... `@endinternal` | Omitted. |
| `@file`, `@ingroup`, `@defgroup`, `@addtogroup`, ... | No effect (the grouping and member commands of Doxygen). |

Any other command is reported on stderr and left in the text. The remaining Markdown is passed through unchanged, with
the following exceptions:

- **Headings** in comments (`#` or underlined) are placed below the heading to which they belong. Within a field, a
  oneof or an enum value, they are rendered as bold text.
- **Symbol names.** A code span that contains only the name of a symbol, `` `weather.Reading.humidity` ``, links to the
  symbol in the same way as `@ref` and is displayed as written. The name is resolved according to the protobuf scoping
  rules, and a name that protobuf cannot resolve is accepted if exactly one symbol ends with it (`humidity`,
  `Reading.humidity`). A name that matches several symbols or none leaves the code span unchanged, without a message.
  Code spans in headings, in code blocks, in link text and after a role are not linked, and any code span that is not
  a plain name (`` `name()` ``) remains plain code.
- **Labels.** Every message, field, oneof, enum and enum value is a link target with the label `<prefix>.<full name>`,
  so other pages can link to it with `[text](#weather_docs.weather.Reading)` or
  `` {ref}`text <weather_docs.weather.Reading>` ``. A label that differs from a previous one only in letter case (for
  example a field `unit` and a type `Unit`) receives the suffix `-2`, because Sphinx compares labels case-insensitively.
- **Links to files.** A link to a Markdown or `.proto` file, `[text](04_network.md)` or
  `[text](net_dev.proto#fragment)`, points to the page generated from that file, so the sources also link correctly in
  a Markdown viewer or on a code hosting platform. A file is located by its path, relative to the Markdown file or, in
  a comment of a `.proto` file, relative to the directory in which `protoc` runs. Eligible files are the `.proto`
  files, the files of `pages`, the readme files of directories and the file of `home`. A link to any other file is
  reported and kept; URLs and absolute paths are not modified.
- **Mathematical notation** written as `$...$` or `@f$...@f$` is converted to the `{math}` role, and display math
  (`$$...$$` as a paragraph, or `@f[...@f]`) to the `math` directive, so the `dollarmath` extension is not required.
  reStructuredText roles such as `:sub:` and the HTML tags `<sub>`, `<sup>`, `<b>`, `<i>` and `<tt>` are converted as
  well.
- **Images.** `![](path)` and `@image` embed images, and a paragraph that contains only an image with alternative text
  becomes a figure with that text as its caption. A `protoc` plugin can only return text and cannot copy files, so the
  pages reference the image files at their original location: a relative path in a comment is interpreted relative to
  the output directory, or to [`image_path`](configuration.md#generator-options) below it, and is rewritten relative to
  the page so that Sphinx locates and copies the file. URLs and paths beginning with `/` are not modified, and the
  suffixes `#gh-light-mode-only` and `#gh-dark-mode-only` are removed.
- **Block comments.** `protoc` removes the leading whitespace and the first `*` of every line of a `/* ... */`
  comment. In such comments, use `-` for bullet lists, and begin every line with ` * ` where indentation is
  significant.

## Pages

The header of a file can assign a name and a title to its page:

```proto
/*
 * @page uart UART Driver
 * Configuration and action messages for UART endpoints.
 */
```

- `@page <name> <title>` on a separate line gives the page of the file a title, which replaces the path of the file in
  the navigation (the page then also displays the path), and a name that `@ref` uses to link to the page. The line
  itself is not displayed. Names are identifiers and must be unique within the documentation; the title is the rest of
  the line, or the name if the title is omitted. `@page` is accepted only in a file header.
- A directory can be described by a `readme.md` file (in any letter case), which is searched for in the directory
  itself and below the directory in which `protoc` runs. The readme replaces the generated list of entries and can
  define the navigation manually, for example with a list of links to the files. The menu of the theme still contains
  all entries, with the pages linked from the readme first, in the order of the links. A leading level-1 heading
  becomes the heading of the page, and the first sentence of the first paragraph is shown in the list of the parent
  directory. A directory with a readme always has a page of its own, even if it contains only one file.
- `@ref <name>` links to a page only if no symbol of that name is in scope, so a field `uart` is not hidden by a page
  named `uart`.

## Limitations

- Services are not documented.
- Field numbers and the numeric values of enum values are not shown.
- `single_file` is rejected; the pages always follow the `.proto` files.
- A command in a comment that is not listed above is reported on stderr and left in the text.
