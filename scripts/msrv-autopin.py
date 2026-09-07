#!/usr/bin/env python3
"""msrv-autopin.py — make Cargo.lock usable with the pinned MSRV toolchain.

Cargo >= 1.84 resolves dependencies *preferentially* for the project's
`package.rust-version`, but it still falls back to an MSRV-incompatible crate
when no other version satisfies its parents.  Those leftovers are exactly the
crates that break the build with

    feature `edition2024` is required          (cargo too old to parse it)
    requires rustc 1.85 or newer ...           (rustc too old to build it)

This tool closes that gap: it walks every package in Cargo.lock, asks the
crates.io index which Rust version each locked release needs, and downgrades
the offenders (one `cargo update --precise` at a time, so cargo itself keeps
verifying that the parents' version requirements stay satisfied).  When a crate
has no MSRV-compatible release at all, its parents are downgraded instead, which
usually drops the problematic crate out of the graph entirely.

It is used by scripts/refresh-lockfile.sh and can also be run by hand:

    python3 scripts/msrv-autopin.py [--resolve-toolchain stable] [--rounds 12]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

INDEX_URL = os.environ.get("CARGO_INDEX_URL", "https://index.crates.io")
USER_AGENT = "rust-academy-msrv-autopin"


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def run(argv: list[str], **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run that reports "command missing" instead of raising."""
    try:
        return subprocess.run(argv, text=True, capture_output=True, **kwargs)
    except FileNotFoundError as error:
        completed = subprocess.CompletedProcess(argv, returncode=127, stdout="", stderr=f"{error}")
        return completed



def semver(text: str) -> tuple[int, int, int, int, str] | None:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.\-]+))?(?:\+.*)?$", text.strip())
    if not match:
        return None
    major, minor, patch, pre = match.groups()
    return int(major), int(minor), int(patch), 0 if pre else 1, pre or ""


def version_tuple(text: str) -> tuple[int, int, int]:
    parsed = semver(text)
    if not parsed:
        match = re.match(r"(\d+)\.(\d+)", text)
        if not match:
            return (0, 0, 0)
        return int(match[1]), int(match[2]), 0
    return parsed[0], parsed[1], parsed[2]


def index_path(name: str) -> str:
    lowered = name.lower()
    if len(lowered) == 1:
        return f"1/{lowered}"
    if len(lowered) == 2:
        return f"2/{lowered}"
    if len(lowered) == 3:
        return f"3/{lowered[0]}/{lowered}"
    return f"{lowered[0:2]}/{lowered[2:4]}/{lowered}"


_index_cache: dict[str, list[dict]] = {}


def fetch_index(name: str) -> list[dict]:
    """All published versions of `name` from the sparse crates.io index."""
    if name in _index_cache:
        return _index_cache[name]
    url = f"{INDEX_URL}/{index_path(name)}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=30) as reply:
            body = reply.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        print(f"warning: cannot read the index for {name}: {error}", file=sys.stderr)
        _index_cache[name] = []
        return []
    entries = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    _index_cache[name] = entries
    return entries


def read_lock(lock: pathlib.Path) -> tuple[int, list[dict]]:
    """Return (lockfile version, [{name, version, source, deps:[(name, version|None)]}])."""
    lockfile_version = 3
    packages: list[dict] = []
    current: dict | None = None
    in_deps = False
    for line in lock.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped == "[[package]]":
            if current:
                packages.append(current)
            current = {"deps": []}
            in_deps = False
            continue
        if stripped == "[package]" or stripped.startswith("[[") and not stripped.startswith("[[package]]"):
            current = None
            continue
        if current is None:
            match = re.match(r"^version\s*=\s*(\d+)", stripped)
            if match:
                lockfile_version = int(match.group(1))
            continue
        match = re.match(r"^(name|version|source)\s*=\s*\"(.*)\"$", stripped)
        if match and not in_deps:
            current[match.group(1)] = match.group(2)
            continue
        if stripped == "dependencies = [":
            in_deps = True
            continue
        if in_deps:
            if stripped == "]":
                in_deps = False
                continue
            entry = stripped.strip('",')
            parts = entry.split()
            if len(parts) >= 2 and re.match(r"^\d", parts[1]):
                current["deps"].append((parts[0], parts[1]))
            elif entry:
                current["deps"].append((entry, None))
    if current:
        packages.append(current)
    return lockfile_version, packages


def parents_of(packages: list[dict], name: str) -> list[str]:
    found = []
    for package in packages:
        if package.get("name") == name:
            continue
        for dep_name, _ in package.get("deps", []):
            if dep_name == name:
                found.append(package["name"])
                break
    return sorted(set(found))


# ---------------------------------------------------------------------------
# the actual work
# ---------------------------------------------------------------------------


class Autopin:
    def __init__(self, root: pathlib.Path, msrv: str, cargo_resolve: list[str], cargo_msrv: list[str]) -> None:
        self.root = root
        self.lock = root / "Cargo.lock"
        self.msrv = version_tuple(msrv)
        self.msrv_text = msrv
        self.cargo_resolve = cargo_resolve
        self.cargo_msrv = cargo_msrv
        self.blacklist: set[tuple[str, str]] = set()  # (name, candidate) already tried

    # -- problem detection -------------------------------------------------
    def locked_registry_packages(self) -> list[dict]:
        _, packages = read_lock(self.lock)
        return [
            package
            for package in packages
            if package.get("source", "").startswith("registry+")
        ]

    def problems(self) -> list[dict]:
        registry = self.locked_registry_packages()
        names = sorted({package["name"] for package in registry})
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(fetch_index, names))

        problems: list[dict] = []
        for package in registry:
            name, version = package["name"], package["version"]
            entry = next((item for item in _index_cache.get(name, []) if item.get("vers") == version), None)
            if entry is None:
                continue
            rust_version = entry.get("rust_version")
            if not rust_version:
                continue
            if version_tuple(rust_version) > self.msrv:
                problems.append(
                    {
                        "name": name,
                        "version": version,
                        "reason": f"requires rustc {rust_version} (MSRV is {self.msrv_text})",
                    }
                )
        return problems

    # -- fixes -------------------------------------------------------------
    def candidates(self, name: str, current: str) -> list[str]:
        entries = fetch_index(name)
        if not entries:
            return []
        upper = semver(current)
        versions = []
        for entry in entries:
            if entry.get("yanked"):
                continue
            text = entry.get("vers", "")
            if (name, text) in self.blacklist:
                continue
            parsed = semver(text)
            if parsed is None or (upper and parsed >= upper):
                continue  # only real downgrades
            rust_version = entry.get("rust_version")
            if rust_version and version_tuple(rust_version) > self.msrv:
                continue
            versions.append(text)
        versions.sort(key=lambda text: semver(text) or (0, 0, 0, 0, ""), reverse=True)
        return versions[:25]

    def downgrade(self, name: str, version: str, reason: str) -> bool:
        candidates = self.candidates(name, version)
        if not candidates:
            print(f"  {name} {version}: {reason} -> no MSRV-compatible release to downgrade to")
            return False
        specifier = f"{name}@{version}"
        for candidate in candidates:
            result = run(self.cargo_resolve + ["update", "--manifest-path", str(self.root / "Cargo.toml"), "-p", specifier, "--precise", candidate])
            if result.returncode == 0:
                self.blacklist.add((name, candidate))
                print(f"  {name} {version} -> {candidate}  ({reason})")
                return True
            self.blacklist.add((name, candidate))
        tail = result.stderr.strip().splitlines()
        print(f"  {name} {version}: {reason} -> every downgrade rejected by cargo ({tail[-1] if tail else 'see cargo output'})")
        return False

    def fetch_offender(self) -> tuple[bool, list[dict]]:
        """Ask the pinned cargo to download + parse every locked manifest.

        Returns (succeeded, problems).  This is the authoritative check: cargo
        1.75 refuses to even *read* a crate published with edition 2024.
        """
        result = run(self.cargo_msrv + ["fetch", "--locked", "--manifest-path", str(self.root / "Cargo.toml")], cwd=str(self.root))
        if result.returncode == 0:
            return True, []
        output = result.stdout + result.stderr
        offenders = {}
        for match in re.finditer(r"registry/src/[^/\']*/([A-Za-z0-9_.+-]+)-(\d[^/\']*)/Cargo\.toml", output):
            offenders.setdefault(match.group(1), match.group(2))
        problems = [
            {"name": name, "version": version, "reason": f"cargo {self.msrv_text} cannot parse its manifest (edition 2024?)"}
            for name, version in offenders.items()
        ]
        if not problems:
            sys.stdout.write(output[-3000:])
        return False, problems

    def current_version(self, name: str) -> str | None:
        for package in self.locked_registry_packages():
            if package.get("name") == name:
                return package.get("version")
        return None

    # -- driver ------------------------------------------------------------
    def resolve_problem(self, problem: dict, depth: int = 0) -> bool:
        """Move `problem`'s package to a usable version, its parents if need be."""
        name = problem["name"]
        version = self.current_version(name) or problem["version"]
        if version != problem["version"]:
            return True  # already handled (usually because an ancestor moved)
        if self.downgrade(name, version, problem["reason"]):
            return True
        if depth >= 4:
            return False
        # The crate itself has no usable release: drop it out of the graph by
        # moving one of the crates that depend on it to an older version.
        packages = self.locked_registry_packages()
        for parent_name in parents_of(packages, name):
            parent_version = next((p["version"] for p in packages if p.get("name") == parent_name), None)
            if not parent_version or (parent_name, parent_version) in self.blacklist:
                continue
            if self.resolve_problem(
                {"name": parent_name, "version": parent_version, "reason": f"requires {name} {version}"},
                depth + 1,
            ):
                return True
        print(f"  {name} {version}: giving up (no version works and no ancestor can move)")
        return False

    def fix(self, rounds: int) -> list[dict]:
        unresolved: list[dict] = []
        seen_unresolved: set[tuple[str, str]] = set()
        for round_number in range(1, rounds + 1):
            problems = self.problems()
            if not problems:
                ok, fetch_problems = self.fetch_offender()
                if ok:
                    return []
                problems = fetch_problems
            problems = [problem for problem in problems if (problem["name"], problem["version"]) not in seen_unresolved]
            if not problems:
                break
            print(f"round {round_number}: {len(problems)} dependency version(s) are unusable with Rust {self.msrv_text}")
            progressed = False
            for problem in problems:
                if self.resolve_problem(problem):
                    progressed = True
                else:
                    seen_unresolved.add((problem["name"], problem["version"]))
                    unresolved.append(problem)
            if not progressed:
                print("no further progress is possible; stopping", file=sys.stderr)
                break
        problems = self.problems()
        if not problems:
            ok, fetch_problems = self.fetch_offender()
            if ok:
                return []
            problems = fetch_problems or [{"name": "(cargo fetch)", "version": "", "reason": "see the output above"}]
        return problems + unresolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--msrv", help="MSRV to target (default: rust-version from Cargo.toml)")
    parser.add_argument("--resolve-toolchain", default="stable", help="toolchain used for `cargo update`")
    parser.add_argument("--msrv-toolchain", help="toolchain used for the final `cargo fetch` check")
    parser.add_argument("--rounds", type=int, default=12)
    parser.add_argument(
        "--list",
        action="store_true",
        help="only report the offenders and the version that would be selected for each of them",
    )
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    manifest = root / "Cargo.toml"
    msrv = args.msrv
    if not msrv:
        match = re.search(r"(?m)^rust-version\s*=\s*\"([^\"]+)\"", manifest.read_text(encoding="utf-8"))
        if not match:
            print("error: no rust-version in Cargo.toml", file=sys.stderr)
            return 2
        msrv = match.group(1)

    have_rustup = run(["rustup", "--version"]).returncode == 0

    def cargo_for(toolchain: str) -> list[str]:
        return ["cargo", f"+{toolchain}"] if have_rustup else ["cargo"]

    autopin = Autopin(root, msrv, cargo_for(args.resolve_toolchain), cargo_for(args.msrv_toolchain or msrv))
    if args.list:
        problems = autopin.problems()
        for problem in problems:
            choices = autopin.candidates(problem["name"], problem["version"])
            print(f"{problem['name']} {problem['version']} -> {choices[0] if choices else '(no MSRV-compatible release)'}  [{problem['reason']}]")
        print(f"{len(problems)} package(s) are too new for Rust {msrv}")
        return 0
    remaining = autopin.fix(args.rounds)

    if remaining:
        print(f"\n{len(remaining)} package(s) could not be made Rust {msrv}-compatible:", file=sys.stderr)
        for problem in remaining:
            print(f"  - {problem['name']} {problem['version']}: {problem['reason']}".rstrip(), file=sys.stderr)
        return 1
    print(f"ok: Cargo.lock only contains crates usable with Rust {msrv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
