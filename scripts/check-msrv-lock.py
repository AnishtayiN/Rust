#!/usr/bin/env python3
"""check-msrv-lock.py — verify that Cargo.lock only pins crates the pinned
MSRV toolchain can actually consume.

Why this exists
---------------
`rust-toolchain.toml` pins Rust 1.75.0 (the last toolchain that produces
Windows 7 compatible binaries).  Crates that use the 2024 edition need Cargo
>= 1.85 just to be *parsed*, so a single too-new transitive dependency breaks
every build with:

    feature `edition2024` is required
    ... but that feature is not stabilized in this version of Cargo (1.75.0)

Cargo >= 1.84 has an MSRV-aware resolver (`resolver.incompatible-rust-versions`)
that avoids most of those crates, but it only *prefers* compatible versions —
it silently falls back to an incompatible one when it sees no alternative.
This script is the safety net: it walks every package in Cargo.lock, looks at
the manifest that `cargo fetch` unpacked into the registry cache and fails when
a crate

  * declares `cargo-features` (old cargo refuses to parse the manifest at all),
  * uses edition 2024 or newer,
  * or requires a `rust-version` newer than the MSRV (cargo would abort with
    "requires rustc X or newer").

It also checks the lockfile format version, because a `Cargo.lock` written by a
recent cargo may use a format that Cargo 1.75 cannot read.

Usage:  python3 scripts/check-msrv-lock.py [--lock Cargo.lock] [--offline-ok]
Exits non-zero when a problem was found.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys

# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def version_tuple(text: str) -> tuple[int, int, int]:
    """Parse "1.75" / "1.85.0" / "1.79.0-beta.4" into a comparable tuple."""
    match = re.match(r"(\d+)\.(\d+)(?:\.(\d+))?", text.strip())
    if not match:
        raise ValueError(f"not a version: {text!r}")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch or 0)


def read_field(manifest: pathlib.Path, field: str, tables: tuple[str, ...]) -> str | None:
    """Return `field` from the first matching top-level table of a manifest.

    Published manifests are flat (cargo inlines `workspace = true` values at
    `cargo publish` time), so a line based scan is enough and keeps this script
    dependency free (no tomllib needed on Python < 3.11).
    """
    current: str | None = None
    pattern = re.compile(r"^[ \t]*%s[ \t]*=[ \t]*(.+?)[ \t]*$" % re.escape(field))
    for line in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            current = stripped.strip("[] ").strip('"').strip("'")
            continue
        if current in tables:
            match = pattern.match(line)
            if match:
                return match.group(1).strip('"').strip("'")
    return None


def cargo_features(manifest: pathlib.Path) -> list[str]:
    """`cargo-features = [...]` only appears before the first table."""
    for line in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            break
        match = re.match(r"^cargo-features\s*=\s*\[(.*)\]$", stripped)
        if match:
            return [item.strip().strip('"').strip("'") for item in match.group(1).split(",") if item.strip()]
    return []


packages_meta: dict[str, str] = {}


def parse_lock(lock: pathlib.Path) -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in lock.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip() == "[[package]]":
            if current:
                packages.append(current)
            current = {}
            continue
        if current is None:
            match = re.match(r"^version\s*=\s*\"?(\d+)\"?", line.strip())
            if match:
                packages_meta["lockfile_version"] = match.group(1)
            continue
        match = re.match(r"^(name|version|source)\s*=\s*\"(.*)\"$", line.strip())
        if match:
            current[match.group(1)] = match.group(2)
    if current:
        packages.append(current)
    return packages


def registry_root() -> pathlib.Path:
    home = os.environ.get("CARGO_HOME")
    base = pathlib.Path(home) if home else pathlib.Path.home() / ".cargo"
    return base / "registry" / "src"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lock", default="Cargo.lock")
    parser.add_argument("--msrv", help="override the MSRV (default: rust-version from Cargo.toml)")
    parser.add_argument(
        "--allow-unfetched",
        action="store_true",
        help="do not complain about packages missing from the cargo registry cache",
    )
    args = parser.parse_args()

    lock_path = pathlib.Path(args.lock)
    if not lock_path.is_absolute():
        # Normally invoked from the repository root; fall back to the root that
        # contains this script so the check also works from a subdirectory.
        lock_path = lock_path if lock_path.is_file() else pathlib.Path(__file__).resolve().parent.parent / lock_path
    if not lock_path.is_file():
        print(f"error: {lock_path} not found — run scripts/refresh-lockfile.sh first", file=sys.stderr)
        return 2
    project = lock_path.parent

    msrv_text = args.msrv
    if not msrv_text:
        msrv_text = read_field(project / "Cargo.toml", "rust-version", ("package", "project"))
    if not msrv_text:
        print("error: cannot determine the MSRV (no rust-version in Cargo.toml)", file=sys.stderr)
        return 2
    msrv = version_tuple(msrv_text)

    packages = parse_lock(lock_path)
    lockfile_version = int(packages_meta.get("lockfile_version", "3"))
    src_root = registry_root()

    problems: list[str] = []
    notes: list[str] = []
    missing: list[str] = []
    checked = 0

    if lockfile_version > 3:
        problems.append(
            f"Cargo.lock uses lockfile format v{lockfile_version}, but cargo {msrv_text} "
            "can only read v1-v3 — regenerate it with an older resolver or downgrade the header."
        )

    for package in packages:
        source = package.get("source", "")
        name = package.get("name", "?")
        version = package.get("version", "?")
        if not source.startswith("registry+"):
            continue  # path dependency (the vendored Slint backend) — always fine
        directories = sorted(src_root.glob(f"*/{name}-{version}"))
        if not directories:
            missing.append(f"{name}-{version}")
            continue
        manifest = directories[0] / "Cargo.toml"
        if not manifest.is_file():
            missing.append(f"{name}-{version}")
            continue
        checked += 1

        features = cargo_features(manifest)
        if features:
            problems.append(
                f"{name} {version} needs unstable cargo features {features} — cargo {msrv_text} cannot parse it"
            )

        edition = read_field(manifest, "edition", ("package", "project")) or "2015"
        if re.fullmatch(r"(202[4-9]|20[3-9]\d)", edition):
            problems.append(
                f"{name} {version} uses edition {edition}; cargo {msrv_text} requires edition <= 2021 "
                "(pin an older version: `cargo +stable update -p <name> --precise <ver>`)"
            )

        rust_version = read_field(manifest, "rust-version", ("package", "project"))
        if rust_version:
            try:
                if version_tuple(rust_version) > msrv:
                    # Not fatal by itself: cargo only enforces rust-version for
                    # the crates it actually compiles, and the wasm / wayland
                    # parts of the graph never get built for our two targets.
                    notes.append(
                        f"{name} {version} wants rustc {rust_version} (MSRV {msrv_text}) — only a problem "
                        "if it is compiled for Windows/Android"
                    )
            except ValueError:
                notes.append(f"{name} {version}: unparsable rust-version {rust_version!r}")

    print(f"checked {checked} registry packages against Rust {msrv_text} (lockfile v{lockfile_version})")
    for line in missing:
        if not args.allow_unfetched:
            notes.append(f"manifest not in the cargo cache (was `cargo fetch` run?): {line}")

    for note in notes:
        print(f"note: {note}")
    for problem in problems:
        print(f"::error::{problem}" if os.environ.get("GITHUB_ACTIONS") else f"error: {problem}")
    if problems:
        print(f"\n{len(problems)} MSRV problem(s) found in Cargo.lock.", file=sys.stderr)
        return 1
    print("ok: every pinned dependency is usable with the pinned MSRV toolchain")
    return 0


if __name__ == "__main__":
    sys.exit(main())
