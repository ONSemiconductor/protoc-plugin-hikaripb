# Copyright (c) 2025 Semiconductor Components Industries, LLC ("onsemi")
# SPDX-License-Identifier: GPL-3.0-or-later

"""The names of packages, messages and enums, as every backend treats them: the namespace override and the ignore list."""

from typing import Iterable


def _parts(namespace: str) -> list[str]:
    """The names of a dotted namespace; `a::b` is `a.b` as well."""
    return [part.strip() for part in namespace.replace("::", ".").split(".") if part.strip()]


class Namespaces:
    """The namespace of every package once the option `namespace_override` is applied.

    The override replaces the leading part that all packages have in common, the packages below it keep their
    names: the packages `esb`, `esb.gpio` and `esb.net.core` become `abc`, `abc.gpio` and `abc.net.core` with the
    override `abc`. Packages that have nothing in common get the override in front.
    """

    def __init__(self, packages: Iterable[str] = (), override: str = ""):
        self.override = _parts(override)
        shared = None
        for package in packages:
            parts = _parts(package)
            if shared is None:
                shared = parts
                continue
            size = 0
            while size < min(len(shared), len(parts)) and shared[size] == parts[size]:
                size += 1
            shared = shared[:size]
        self.shared = shared or []

    def parts(self, package: str) -> list[str]:
        """The names of the namespace of `package`."""
        parts = _parts(package)
        return self.override + parts[len(self.shared):] if self.override else parts

    def package(self, package: str) -> str:
        """The dotted namespace of `package`."""
        return ".".join(self.parts(package))


def _flat(name: str) -> str:
    """A name without its separators: `a.b.C`, `a::b::C` and `a_b_C` are the same name."""
    return name.strip().removeprefix(".").replace("::", "_").replace(".", "_")


def type_names(package: str, namespace: str, chain: str) -> list[str]:
    """The names with which the option `ignore` can name a message or enum.

    `chain` is its name below the package (`Outer.Inner`), `namespace` the namespace of the package after the
    override. Both the package and the namespace name it in full and flat, as C and C++ name nested types.
    """
    flat = chain.rpartition(".")[2]
    return [".".join(part for part in (scope, name) if part) for scope in (package, namespace) for name in (chain, flat)]


class Ignored:
    """The messages and enums that the option `ignore` leaves out."""

    def __init__(self, entries: Iterable[str] = ()):
        self.entries = {_flat(entry) for entry in entries}

    def matches(self, names: Iterable[str]) -> bool:
        """True if one of the names of a message or enum is an entry."""
        return any(_flat(name) in self.entries for name in names)
