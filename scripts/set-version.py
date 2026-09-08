#!/usr/bin/env python3
"""set-version.py — write a new app version into Cargo.toml *and* Cargo.lock.

`cargo apk` derives the APK versionName/versionCode from `[package] version`,
and the Windows resources are filled from the same version, so the release
workflow has to rewrite it before building.  Cargo.lock also records the
version of the root package: if it is left untouched, every build that uses
`--locked` fails with "the lock file needs to be updated but --locked was
passed".  This script keeps both files in sync.

Usage:  python3 scripts/set-version.py 1.4.2
"""

from __future__ import annotations

import re
import sys

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


def patch_package_version(text: str, name: str, version: str) -> str:
    """Replace the `version` line that belongs to the `[package]` table."""
    lines = text.splitlines(keepends=True)
    in_package = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("["):
            in_package = stripped in ("[package]", "[project]")
            continue
        if in_package and re.match(r"^version\s*=", stripped):
            lines[index] = re.sub(r"^(version\s*=\s*)\"[^\"]*\"", rf'\1"{version}"', line)
            return "".join(lines)
    raise SystemExit("error: no `version = \"...\"` inside [package] found")


def main() -> int:
    if len(sys.argv) != 2 or not SEMVER.match(sys.argv[1]):
        print(__doc__)
        return 2
    version = sys.argv[1]

    with open("Cargo.toml", encoding="utf-8") as handle:
        manifest = handle.read()
    with open("Cargo.lock", encoding="utf-8") as handle:
        lock = handle.read()

    name = re.search(r"(?m)^name\s*=\s*\"([^\"]+)\"", manifest)
    if not name:
        raise SystemExit("error: cannot read the package name from Cargo.toml")
    name = name.group(1)

    with open("Cargo.toml", "w", encoding="utf-8", newline="") as handle:
        handle.write(patch_package_version(manifest, name, version))

    # In Cargo.lock the root package block looks like:
    #   [[package]]
    #   name = "rust-academy"
    #   version = "0.1.0"
    lock, count = re.subn(
        r'(\[\[package\]\]\nname = "' + re.escape(name) + r'"\nversion = ")[^"]*(")',
        rf"\g<1>{version}\g<2>",
        lock,
        count=1,
    )
    if count:
        with open("Cargo.lock", "w", encoding="utf-8", newline="") as handle:
            handle.write(lock)
        print(f"set {name} = {version} in Cargo.toml and Cargo.lock")
    else:
        raise SystemExit("error: the root package is missing from Cargo.lock")
    return 0


if __name__ == "__main__":
    sys.exit(main())
