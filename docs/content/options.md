# Generator options

Options are passed in the parameter of `--hikaripb_out`, between `type=` and the output directory:

```sh
protoc --experimental_allow_proto3_optional \
    --plugin=protoc-gen-hikaripb=protoc/hikaripb.py \
    --proto_path=protos \
    --hikaripb_out=type=c,prefix=sample:out/dir \
    protos/message.proto
```

- The parameter is a comma-separated list of `key=value` pairs, followed by `:` and the output directory. Because
  `protoc` splits the parameter at the first `:`, a value cannot contain a colon; use `.` or `_` in names, or a
  configuration file.
- A **flag** is written as `name`, `name=true` or `name=false`. The values `1`, `yes`, `on` and `0`, `no`, `off` are
  accepted as well.
- The entries of a **list** are separated by `|`: `ignore=esb.gpio.fldConfig|esb.gpio.fldNotif`.
- In a **text** value (`title`, `doc_group_title`, `namespace_override`, ...), a space is written as `+` or `%20` on
  the command line: `title=My+protocol`.
- An option that the selected generator does not read is accepted and has no effect, so the same set of options can
  be used for every generator. An unknown option name is reported on stderr and ignored. A missing value or a value of
  the wrong kind aborts the run with an error message.
- `hikaripb.py --help` describes the plugin and lists every option with its description and default value.

This page describes the options that all generators read. The options specific to a generator, and the effect of the
shared options on its output, are described on the configuration page of that generator:

- [C](c/configuration.md#generator-options)
- [C++](cpp/configuration.md#generator-options)
- [Python](python/configuration.md#generator-options)
- [Documentation](documentation/configuration.md#generator-options)

## Options of all generators

| Option | Default | Description |
|--------|---------|-------------|
| `type` | *(required)* | The generator: `c`, `cpp`, `py` or `sphinxdocs`. |
| `config_file` | *(none)* | A JSON file containing options, see [Configuration file](#configuration-file). |
| `prefix` | `hikaripb` | Prefix of the generated runtime: the C symbols and macros (`<prefix>_defines.h`, `<PREFIX>_ASSERT`), the C++ namespace and macros, the Python runtime modules (`<prefix>_codec.py`) and the labels of the documentation. |
| `single_file` | *(off)* | Merges the output of all `.proto` files into a single file with this name, see [single_file](#single_file). Supported by `c`, `cpp` and `py` only. |
| `ignore` | *(none)* | Messages and enums to exclude from the output, see [ignore](#ignore). |
| `namespace_override` | *(none)* | Replaces the leading part that the package names of all files have in common, see [namespace_override](#namespace_override). |

## Configuration file

`config_file=<path>` names a JSON file whose keys are option names. This allows a project to keep its options in one
place:

```json
{
  "prefix": "esb",
  "ignore": ["esb::gpio::fldConfig"],
  "title": "ESB protocol",
  "omit_conf": true
}
```

```sh
protoc ... --hikaripb_out=type=sphinxdocs,config_file=hikaripb.json:docs protos/*.proto
```

- Options on the command line take precedence over the file, and the file takes precedence over the defaults. A value
  replaces the value from the lower-priority source; a list is replaced as a whole. `type` may be set in the file,
  `config_file` may not.
- A flag is `true` or `false`, a list is an array of strings (or a string with entries separated by `|`), and all
  other options are strings. Text values are written verbatim (`"title": "C++ protocol"`) and may contain commas.
- The path of the file, and the paths it contains (`pages`), are relative to the directory in which `protoc` runs. A
  path that begins with a drive letter cannot be used for `config_file` because it contains a `:`.
- A file that cannot be read or does not contain valid JSON aborts the run with an error message.

## single_file

By default, each generator writes one output per `.proto` file. `single_file=<name>` merges all of them into one
output; the configuration page of each generator lists the resulting file names. The option is supported by `c`,
`cpp` and `py`; `sphinxdocs` rejects it.

The name is mandatory (a bare `single_file` is rejected) and must be an identifier. The files are merged in dependency
order, and the shared runtime files are generated in the same way as without the option. Every type must have a unique
name in the merged output.

## ignore

`ignore=<name>[|<name>...]` excludes messages and enums from the output. A name can be written in protobuf notation,
`esb.gpio.fldConfig`, or as the generated C symbol, `esb_gpio_fldConfig`. A configuration file also accepts the C++
notation `esb::gpio::fldConfig`. A nested type is specified by its full name (`esb.Outer.Inner`) or by its flat name
(`esb_Inner`).

A type that is still used by another generated message cannot be excluded: `c`, `cpp` and `py` abort with an error,
and `sphinxdocs` shows the type of the field without a link. The configuration page of each generator describes which
parts of the output are excluded.

## namespace_override

`namespace_override=<namespace>` replaces the leading part that the package names of all generated files have in
common; the packages below it keep their names. With `acme`, the packages `esb`, `esb.gpio` and `esb.net.core` become
`acme`, `acme.gpio` and `acme.net.core`. If the packages have nothing in common, the override is prepended. The value
is dotted (`a.b`, or `a::b` in a configuration file); an empty value has no effect. The configuration page of each
generator describes where the namespace appears: in the prefix of the C symbols, in the C++ namespaces, in the
packages of the Python modules, or in the names and labels of the documentation.
