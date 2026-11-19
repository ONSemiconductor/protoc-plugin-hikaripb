# Configuration options of the documentation generator

The documentation generator produces Sphinx sources and has no library to configure: its output is controlled
entirely by the options of `--hikaripb_out`. The syntax of the options, on the command line and in a configuration
file, is described in [Generator options](../options.md).

## Generator options

`type=sphinxdocs` selects this generator, and `config_file` names a
[configuration file](../options.md#configuration-file). The generator also reads the following options:

| Option | Default | Description |
|--------|---------|-------------|
| `prefix` | `hikaripb` | Prefix of the labels of the link targets: `<prefix>.<full name>` for every message, field, oneof, enum and enum value, and `<prefix>.<name>` for a page. Use a different prefix for each protocol that shares a Sphinx project. |
| `ignore` | *(none)* | Messages and enums to exclude: the section of the message or enum in the Protocol of its file and its labels are omitted. A field whose type is excluded shows the type without a link. See [ignore](../options.md#ignore). |
| `namespace_override` | *(none)* | Replaces the leading part of the package names in the full names, in the package shown on a page and in the labels. See [namespace_override](../options.md#namespace_override). |
| `title` | `Protocol` | Title of the index page and name of the Sphinx project in `conf.py`. |
| `parent` | *(empty)* | Directory below the output directory that receives the pages. Without this option, the output is a standalone Sphinx project; with it, the output is a chapter of an existing project. See [Standalone project or chapter](#standalone-project-or-chapter). |
| `image_path` | *(empty)* | Directory, relative to the output directory, to which the relative image paths in the comments refer. |
| `pages` | *(none)* | Markdown folders and `[<name>=]<file>` files, relative to the directory in which `protoc` runs, that become pages preceding the pages of the `.proto` files, for example an introduction. See [Pages from Markdown files](#pages-from-markdown-files). |
| `home` | *(empty)* | The page that replaces the list of pages as the home page: the name of a Markdown page of `pages`, or a Markdown file. See [Home page](#home-page). |
| `omit_conf` | *(off)* | Flag. Suppresses the generation of `conf.py`. |
| `inline_protocol` | *(off)* | Flag. Places the Protocol in the last section of the page of its file instead of on a separate subpage, as required for a book (LaTeX, PDF). See [Books](#books-latex-pdf). |

`single_file` is rejected, because the pages always follow the `.proto` files. The other options of the plugin have no
effect on `type=sphinxdocs`.

## Pages from Markdown files

`pages=<entry>[|<entry>...]` adds Markdown files to the documentation, for example an introduction that is not part of
any `.proto` file. An entry is either a folder or a file, `[<name>=]<file>`:

```sh
cd project/pbuf
protoc ... --hikaripb_out=type=sphinxdocs,image_path=../../pbuf,pages=../introduction:../generated/docs *.proto
```

- A **folder** becomes a menu named after the folder (`introduction` becomes *Introduction*). Every `.md` file below
  it becomes a page of the menu, and every subfolder a submenu; hidden files and folders are skipped. The entries are
  ordered by the names of the files and folders, with numbers compared numerically. A numeric prefix with its
  separator (`01_`, `2-`) only determines the order: `02_network.md` becomes the page `network`. A `readme.md` in a
  folder does not become a page of the menu but the page of the menu itself, as for the directories of the `.proto`
  files. A folder must contain at least one other file.
- A **file** becomes a separate page, named `<name>` (the name before the `=`) or, without a name, after the file
  without its extension and numeric prefix.
- The pages precede the pages of the `.proto` files, in the order given in the option. A page name is an identifier
  that must be unique within the documentation: the page is written to `<name>.md`, `@ref <name>` links to it and its
  label is `<prefix>.<name>`. The first heading of the file is its title in the navigation.
- The entries are resolved relative to the directory in which `protoc` runs and read as UTF-8 text. Entries are
  separated by `|`; a `:` cannot be used because `protoc` splits the parameter at the first colon. An entry that cannot
  be read, an absolute path, a folder without Markdown files and a page that would overwrite another page are errors.
- The text is processed in the same way as a comment, so a page can also link to messages and fields with `@ref`. The
  headings keep their levels; the first heading is the title of the page.
- Relative image paths are relative to the Markdown file. The generator locates the file from the output directory
  through `image_path`, which must therefore point from the output directory to the directory in which `protoc` runs.

## Home page

Without `home`, the `index` page lists the top level of the navigation. `home=<value>` designates another page as the
home page; its text replaces the list, and the top level remains in the menu of the theme. The value is interpreted in
the following order:

- As the name of a Markdown page of `pages` (`home=overview` for `overview.md`). That page becomes the `index` page and
  is not generated separately; its label is retained.
- As a Markdown file relative to the directory in which `protoc` runs (`home=../home.md`). The file is not used as a
  page otherwise, unless it is also a file of `pages` or the `readme.md` of a folder. In that case, its text appears on
  two pages, and an `@anchor` or `@section` in it would define its label twice.

A leading `#` heading of the text becomes the title of the home page; without one, the value of the `title` option is
used. Any other value is an error.

## Standalone project or chapter

Without `parent`, the output directory is a standalone Sphinx project, see
[Generate and build](overview.md#generate-and-build). With `parent=<dir>`, the output directory is the source
directory of an existing project, the pages are written to `<dir>` below it, and no `conf.py` is generated. The
project includes the chapter in one of its `toctree` directives:

```sh
protoc ... --hikaripb_out=type=sphinxdocs,parent=reference/protocol,title=Protocol+reference:docs ...
```

````markdown
```{toctree}
reference/protocol/index
```
````

Labels are global in Sphinx, so the references remain valid wherever the chapter is placed. Use a different `prefix`
for each protocol that shares a Sphinx project.

## Books (LaTeX, PDF)

When the LaTeX builder combines the pages into a single document, the Protocol page of a file ends up inside the last
section of the page of that file. `inline_protocol` avoids this by placing the Protocol in the last section of the page
of its file instead of on a separate subpage:

```sh
protoc ... --hikaripb_out=type=sphinxdocs,inline_protocol:book ...   # for the LaTeX/PDF builder
protoc ... --hikaripb_out=type=sphinxdocs:html ...                   # for HTML, with separate Protocol pages
```

In this mode, the pages `<file>-protocol.md` are not generated; the lists, labels and references remain the same.
