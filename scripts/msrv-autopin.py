#!/usr/bin/env python3
"""msrv-autopin.py — make Cargo.lock usable with the pinned MSRV toolchain.

Cargo >= 1.84 resolves dependencies *preferentially* for the project's
`package.rust-version`, but the policy is a preference, not a rule: for crates
that have no MSRV-compatible release in the requested range cargo happily picks
a too-new one.  Those leftovers are the ones that break every build of this
repository with

    feature `edition2024` is required     (cargo 1.75 cannot parse the manifest)
    requires rustc 1.85 or newer          (rustc 1.75 cannot build it)

This tool fixes the lockfile afterwards:

  * Hard rule (must hold): `cargo +<MSRV> fetch --locked` has to succeed, i.e.
    the old cargo must be able to read *every* manifest in the graph — even the
    ones for targets we never build (wasm/linux), because cargo downloads and
    parses the whole lockfile.
  * Best effort: every locked release whose index `rust-version` is above the
    MSRV is moved to the newest older release that still satisfies its parents,
    which also keeps the actual compilable set of crates buildable.

When a crate itself has no usable release, its ancestors are moved instead (the
offending requirement usually disappears with them); the ancestor to move is
taken from cargo's own "required by package ..." trace, falling back to the
dependency lists in Cargo.lock.

Two extensions cover what neither cargo nor the index can see:

  * `scripts/msrv-pins.toml` keeps hand-picked crates pinned across every
    refresh (for dependencies that need a newer compiler than they declare).
  * `--oracle "<build command>"` runs a real build and reads *its* errors, so
    `error[E0658]: use of unstable library feature ...` also becomes a
    downgrade instead of a red CI run.

Used by scripts/refresh-lockfile.sh; can also be run by hand:

    python3 scripts/msrv-autopin.py [--resolve-toolchain stable] [--rounds 12]
    python3 scripts/msrv-autopin.py --list        # report only
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.request

INDEX_URL = os.environ.get("CARGO_INDEX_URL", "https://index.crates.io")
USER_AGENT = "rust-academy-msrv-autopin"
# A crate that needs this rustc (or newer) is virtually always published with
# the 2024 edition, which is what cargo 1.75 chokes on.
EDITION_2024 = (1, 85)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def run(argv: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, text=True, capture_output=True, cwd=cwd)
    except OSError as error:  # e.g. no rustup/cargo on PATH, or not executable
        return subprocess.CompletedProcess(argv, 127, "", f"cannot run {' '.join(argv)}: {error}")


def semver(text: str) -> tuple[int, int, int, int, str] | None:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.\-]+))?(?:\+.*)?$", text.strip())
    if not match:
        return None
    major, minor, patch, pre = match.groups()
    # A release sorts above its own pre-releases.
    return int(major), int(minor), int(patch), 0 if pre else 1, pre or ""


def version_tuple(text: str) -> tuple[int, int, int]:
    parsed = semver(text)
    if parsed:
        return parsed[0], parsed[1], parsed[2]
    match = re.match(r"(\d+)\.(\d+)", text or "")
    if not match:
        return (0, 0, 0)
    return int(match[1]), int(match[2]), 0


def series_of(text: str) -> tuple[int, int]:
    parsed = version_tuple(text)
    return parsed[0], parsed[1]


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
    """Every published version of `name`, from the sparse crates.io index."""
    if name in _index_cache:
        return _index_cache[name]
    url = f"{INDEX_URL}/{index_path(name)}"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as reply:
            body = reply.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as error:
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
    """(lockfile version, [{name, version, source, deps: [(name, version|None)]}])"""
    lockfile_version = 3
    packages: list[dict] = []
    current: dict | None = None
    in_deps = False
    for line in lock.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped == "[[package]]":
            if current:
                packages.append(current)
            current = {"name": "", "version": "", "source": "", "deps": []}
            in_deps = False
            continue
        if stripped.startswith("["):
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
        if package["name"] == name:
            continue
        if any(dep_name == name for dep_name, _ in package["deps"]):
            found.append(package["name"])
    return sorted(set(found))


TRACE_PACKAGE = re.compile(r"(?:required by package|of package)\s+`?([A-Za-z0-9_.+-]+)\s+v([0-9][^`\s]*)`?")


def ancestors_from_cargo_error(text: str) -> list[str]:
    """The crates cargo blames for keeping the too-new version in the graph."""
    names = []
    for match in TRACE_PACKAGE.finditer(text or ""):
        if match.group(1) not in names:
            names.append(match.group(1))
    return names


# ---------------------------------------------------------------------------
# the actual work
# ---------------------------------------------------------------------------


class Autopin:
    # Compiler/cargo errors that only appear once a crate is built and that a
    # version downgrade can fix.  Anything else the oracle reports is noise for
    # us (a missing C toolchain, a broken source file, ...).
    ORACLE_ERRORS = (
        re.compile(r"error: could not compile `(?P<name>[A-Za-z0-9_.+-]+)`"),
        re.compile(r"error\[E0658\].*?feature '(?P<feature>[^']+)'"),
        re.compile(r"package `(?P<name>[A-Za-z0-9_.+-]+) v(?P<version>[^ `\s]+)` cannot be built because it "
                   r"requires rustc (?P<msrv>\d+\.\d+(?:\.\d+)?)"),
    )

    def __init__(self, root: pathlib.Path, msrv: str, cargo_resolve: list[str], cargo_msrv: list[str],
                 oracle: str = "", pins_file: pathlib.Path | None = None) -> None:
        self.root = root
        self.lock = root / "Cargo.lock"
        self.manifest = root / "Cargo.toml"
        self.msrv = version_tuple(msrv)
        self.msrv_text = msrv
        self.cargo_resolve = cargo_resolve
        self.cargo_msrv = cargo_msrv
        self.tried: set[tuple[str, str]] = set()  # (name, candidate) already attempted
        self.stuck: set[str] = set()  # crates neither they nor their ancestors can move
        # Keep the MSRV-aware policy active while pinning, so that the
        # re-resolution a `cargo update --precise` triggers cannot pull in a
        # brand new crate that the old toolchain cannot read.
        self.policy = ["--config", 'resolver.incompatible-rust-versions="fallback"']
        self.packages: list[dict] = []
        self.oracle = shlex.split(oracle) if oracle else []
        self.pins_file = pins_file or root / "scripts" / "msrv-pins.toml"
        self.pins = self.load_pins()
        self.pin_failures: list[str] = []
        self.oracle_noise = ""
        # Downgrades the *build* forced (name, from, to): those crates lie about
        # their MSRV, so they belong in the pin file as well.
        self.oracle_moves: list[tuple[str, str, str]] = []

    # -- state -------------------------------------------------------------
    def refresh(self) -> None:
        _, packages = read_lock(self.lock)
        self.packages = [package for package in packages if package["source"].startswith("registry+")]

    def versions_of(self, name: str) -> list[str]:
        """Locked versions of `name` — a name can appear more than once."""
        return [package["version"] for package in self.packages if package["name"] == name]

    def current_version(self, name: str) -> str | None:
        versions = self.versions_of(name)
        return versions[0] if versions else None

    # -- problem detection -------------------------------------------------
    def index_problems(self) -> list[dict]:
        """Locked releases whose own index `rust-version` is above the MSRV."""
        self.refresh()
        names = sorted({package["name"] for package in self.packages})
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(fetch_index, names))
        problems = []
        for package in self.packages:
            entry = next((item for item in _index_cache.get(package["name"], []) if item["vers"] == package["version"]), None)
            if not entry or not entry.get("rust_version"):
                continue
            required = version_tuple(entry["rust_version"])
            if required > self.msrv:
                problems.append(
                    {
                        "name": package["name"],
                        "version": package["version"],
                        "rust_version": required,
                        "rust_version_text": entry["rust_version"],
                        "hard": required >= EDITION_2024,
                        "reason": f"requires rustc {entry['rust_version']} (MSRV is {self.msrv_text})",
                    }
                )
        return problems

    def fetch_offender(self) -> tuple[bool, list[dict], str]:
        """Let the pinned cargo download + parse every locked manifest.

        This is the authoritative check: cargo 1.75 refuses to read a manifest
        that uses edition 2024 or an unstable cargo feature.
        """
        result = run(self.cargo_msrv + ["fetch", "--locked"], cwd=str(self.root))
        output = (result.stdout or "") + (result.stderr or "")
        if result.returncode == 0:
            return True, [], output
        offenders: dict[str, str] = {}
        for match in re.finditer(r"registry/src/[^/'\s]+/([A-Za-z0-9_.+-]+)-(\d[^/'\s]*)/Cargo\.toml", output):
            offenders.setdefault(match.group(1), match.group(2))
        problems = [
            {
                "name": name,
                "version": version,
                "rust_version": (999, 0, 0),
                "rust_version_text": "unparsable",
                "hard": True,
                "reason": f"cargo {self.msrv_text} cannot parse its manifest (edition 2024?)",
                "parse_only": True,
            }
            for name, version in offenders.items()
        ]
        return False, problems, output

    # -- curated pins ------------------------------------------------------
    def load_pins(self) -> dict[str, str]:
        """Read `scripts/msrv-pins.toml` (crate -> version that must be locked).

        Some crates need a newer compiler than the project MSRV while declaring
        no `rust-version` at all, which makes them invisible to the MSRV-aware
        resolver, to `cargo +msrv fetch` (their manifest parses fine) and to the
        index scan.  They are pinned here once, and every run puts the pin back
        so that a refresh cannot undo it.
        """
        pins: dict[str, str] = {}
        section = ""
        try:
            text = self.pins_file.read_text(encoding="utf-8")
        except OSError:
            return pins
        for line in text.splitlines():
            stripped = line.split("#", 1)[0].strip()
            if not stripped:
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                section = stripped[1:-1].strip()
                continue
            if section == "pins" and "=" in stripped:
                name, _, version = (part.strip() for part in stripped.partition("="))
                if name and version:
                    pins[name] = version.strip('"').strip("'")
        return pins

    def apply_pins(self) -> list[str]:
        """Force the curated versions into the lockfile; return what failed."""
        failures: list[str] = []
        for name, want in sorted(self.pins.items()):
            self.refresh()
            if want in self.versions_of(name):
                continue
            print(f"pin {name}: {'/'.join(self.versions_of(name)) or 'missing'} -> {want}"
                  f"  ({self.pins_file.name})")
            have = self.versions_of(name)
            spec = f"{name}@{have[0]}" if len(have) == 1 else name
            result = run(self.cargo_resolve + ["update", "--manifest-path", str(self.manifest),
                                               *self.policy, "-p", spec, "--precise", want])
            if result.returncode != 0:
                output = (result.stdout or "") + (result.stderr or "")
                details = [line.strip() for line in output.splitlines() if "error:" in line][:2]
                failures.append(f"{name}@{want} could not be applied: "
                                + ("; ".join(details) or "the requirements of its dependants reject it"))
        self.pin_failures = failures
        return failures

    # -- the build oracle --------------------------------------------------
    def oracle_problems(self) -> list[dict]:
        """Offenders reported by the `--oracle` build command, if it is set."""
        if not self.oracle:
            return []
        result = run(self.oracle, cwd=str(self.root))
        output = (result.stdout or "") + (result.stderr or "")
        if result.returncode == 0:
            self.oracle_noise = ""
            return []
        names = sorted({package["name"] for package in self.packages}, key=len, reverse=True)
        problems: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for line in output.splitlines():
            match = next((m for m in (pattern.search(line) for pattern in self.ORACLE_ERRORS) if m), None)
            if not match:
                continue
            found = match.groupdict()
            name = found.get("name") or ""
            if name not in names:
                name = next((known for known in names if known in line), "")
            if not name or (name, found.get("version", "")) in seen:
                continue
            seen.add((name, found.get("version", "")))
            locked = self.versions_of(name)
            version = found.get("version") or (
                max(locked, key=lambda text: semver(text) or (0, 0, 0, 0, "")) if locked else "")
            if found.get("feature"):
                reason = f"uses the unstable feature `{found['feature']}` (Rust {self.msrv_text} does not have it)"
            elif found.get("msrv"):
                reason = f"requires rustc {found['msrv']} (MSRV is {self.msrv_text})"
            else:
                reason = f"does not build with Rust {self.msrv_text}"
            problems.append({"name": name, "version": version, "reason": reason,
                             "rust_version": (999, 0, 0), "rust_version_text": "undeclared", "hard": True})
        if not problems:
            lines = [line.strip() for line in output.splitlines() if "error" in line.lower()]
            self.oracle_noise = "\n".join(lines or output.splitlines()[-8:])[:1500]
            print(f"warning: the oracle command ({' '.join(self.oracle)}) failed without a "
                  f"version-related error; not touching the lockfile")
        else:
            self.oracle_noise = ""
        return problems

    # -- fixes -------------------------------------------------------------
    def candidates(self, name: str, current: str, limit: tuple[int, int, int] | None = None) -> list[str]:
        """Older releases of `name` that the pinned cargo can still deal with.

        `limit` is the newest rust-version that is still acceptable: the MSRV
        for a normal downgrade, or 1.85 when the goal is merely to get a
        manifest that cargo can *parse* (which is all that matters for crates
        we never compile, e.g. the wasm subtree).  Newest first; the newest
        release of every series is always included so that crossing a
        major/minor boundary stays reachable.
        """
        ceiling = limit or self.msrv
        upper = semver(current)
        top: list[str] = []
        per_series: dict[tuple[int, int], str] = {}
        for entry in fetch_index(name):
            version = entry.get("vers", "")
            if entry.get("yanked") or (name, version) in self.tried:
                continue
            parsed = semver(version)
            if parsed is None or (upper and parsed >= upper):
                continue  # only genuine downgrades
            rust_version = entry.get("rust_version")
            if rust_version and version_tuple(rust_version) > ceiling:
                continue
            top.append(version)
            key = series_of(version)
            if key not in per_series or semver(version) > semver(per_series[key]):
                per_series[key] = version
        chosen = set(top[:20]) | set(per_series.values())
        return sorted(chosen, key=lambda text: semver(text) or (0, 0, 0, 0, ""), reverse=True)[:40]

    def downgrade(self, name: str, version: str, reason: str, ceiling: tuple[int, int, int] | None = None) -> tuple[bool, str]:
        """Try to move `name` to an older release; returns (changed, cargo output)."""
        ordered = self.candidates(name, version, ceiling)
        if not ordered:
            print(f"  {name} {version}: {reason} -> no older usable release left to try")
            return False, ""
        last_output = ""
        for candidate in ordered:
            self.tried.add((name, candidate))
            result = run(
                self.cargo_resolve
                + ["update", "--manifest-path", str(self.manifest), *self.policy, "-p", f"{name}@{version}", "--precise", candidate]
            )
            last_output += (result.stdout or "") + (result.stderr or "")
            if result.returncode == 0:
                print(f"  {name} {version} -> {candidate}  ({reason})")
                return True, last_output
        reasons = [line.strip() for line in last_output.splitlines() if "error:" in line or "required by" in line or "which satisfies" in line]
        for line in list(dict.fromkeys(reasons))[:4]:
            print(f"      {line}")
        return False, last_output

    # -- date gate (report only) -------------------------------------------------

    def msrv_released(self) -> str:
        """The date the MSRV toolchain was released, from the root manifest."""
        try:
            text = (self.root / "Cargo.toml").read_text(encoding="utf-8")
        except OSError:
            return ""
        table = re.search(r"(?ms)^\[package\.metadata\.msrv\]\s*$(.*?)(?=^\[|\Z)", text)
        match = re.search(r'^released\s*=\s*"(\d{4}-\d{2}-\d{2})"', table.group(1), re.M) if table else None
        return match.group(1) if match else ""

    def unpinnable_suspects(self) -> list[dict]:
        """Locked crates that are newer than the MSRV toolchain and silent about it.

        A crate published after the pinned toolchain existed, whose index entry
        carries no `rust_version`, may use anything up to whatever was current
        when it was published — that is how rowan (`ptr_addr_eq`) and fontdue
        (`cast_signed`) broke both release builds while every check was green.
        Only a build can prove such a crate works, so this is deliberately
        report-only: it names the suspects and the newest release that predates
        the MSRV toolchain, which is the version to put in msrv-pins.toml.
        """
        released = self.msrv_released()
        if not released:
            print("note: no [package.metadata.msrv] released date in Cargo.toml; "
                  "cannot date-gate the locked crates")
            return []
        self.refresh()
        names = sorted({package["name"] for package in self.packages})
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(fetch_index, names))
        suspects = []
        for package in self.packages:
            entries = _index_cache.get(package["name"], [])
            entry = next((item for item in entries if item["vers"] == package["version"]), None)
            if not entry or entry.get("rust_version"):
                continue  # declares an MSRV we already checked
            published = (entry.get("pubtime") or "")[:10]
            if not published or published <= released:
                continue
            if self.pins.get(package["name"]) == package["version"]:
                continue  # already pinned on purpose
            older = [item for item in entries
                     if not item.get("yanked") and (item.get("pubtime") or "")[:10] <= released
                     and semver(item["vers"]) and semver(item["vers"]) < semver(package["version"])
                     and (semver(item["vers"]) or ())[:2] == (semver(package["version"]) or ())[:2]]
            suspect = {
                "name": package["name"],
                "version": package["version"],
                "published": published,
                "candidate": older[0]["vers"] if older else "",
                "candidate_published": (older[0].get("pubtime") or "")[:10] if older else "",
            }
            suspects.append(suspect)
        return sorted(suspects, key=lambda item: (item["name"], item["version"]))

    # -- driver ------------------------------------------------------------
    def move_offender(self, problem: dict, depth: int = 0) -> bool:
        """Move the offending crate, or one of its ancestors, to a usable version."""
        name, version = problem["name"], problem["version"]
        if version not in self.versions_of(name):
            return True  # already resolved, usually because an ancestor moved
        ceiling = None if not problem.get("parse_only") else (EDITION_2024[0], EDITION_2024[1] - 1, 99)
        changed, output = self.downgrade(name, version, problem["reason"], ceiling)
        if changed:
            self.refresh()
            return True
        if depth >= 5:
            return False
        ancestors = ancestors_from_cargo_error(output) or parents_of(self.packages, name)
        for ancestor in ancestors:
            # Move the newest locked instance of the ancestor; older duplicates
            # are usually pulled in by something else entirely.
            candidates_versions = self.versions_of(ancestor)
            if not candidates_versions or all((ancestor, item) in self.stuck for item in candidates_versions):
                continue  # every locked instance of the ancestor is a dead end
            ancestor_version = max(candidates_versions, key=lambda text: semver(text) or (0, 0, 0, 0, ""))
            if self.move_offender(
                {
                    "name": ancestor,
                    "version": ancestor_version,
                    "reason": f"keeps {name} {version} in the graph",
                    "parse_only": True,
                },
                depth + 1,
            ):
                self.refresh()
                return True
        self.stuck.add((name, version))
        print(f"  {name} {version}: giving up (neither it nor its ancestors can move)")
        return False

    def fix(self, rounds: int) -> tuple[list[dict], list[dict]]:
        """Returns (hard problems left, soft problems left)."""
        polished = False
        for round_number in range(1, rounds + 1):
            self.refresh()
            self.apply_pins()
            ok, fetch_problems, _ = self.fetch_offender()
            if ok:
                offenders = self.oracle_problems()
                if offenders:
                    print(f"round {round_number}: the build oracle cannot compile "
                          f"{len(offenders)} crate(s) with Rust {self.msrv_text}")
                    for problem in offenders:
                        print(f"  {problem['name']} {problem['version']}: {problem['reason']}")
                    before = {problem["name"]: self.current_version(problem["name"])
                              for problem in offenders}
                    if any(self.move_offender(problem) for problem in offenders):
                        for name, frm in before.items():
                            to = self.current_version(name)
                            if frm and to and to != frm:
                                self.oracle_moves.append((name, frm, to))
                        continue
                    break
                if polished:
                    return [], self.index_problems()
                # Everything parses and (if configured) builds; still try to
                # move the remaining middle-band crates out of the graph
                # (best effort).
                polished = True
                leftovers = sorted(self.index_problems(), key=lambda problem: (not problem["hard"], problem["name"]))
                moved = False
                for problem in leftovers:
                    if self.downgrade(problem["name"], problem["version"], f"best effort: {problem['reason']}"):
                        moved = True
                if not moved:
                    return [], self.index_problems()
                continue
            print(f"round {round_number}: cargo {self.msrv_text} rejects {len(fetch_problems) or '?'} package manifest(s)")
            if not fetch_problems:
                # Something else went wrong (no index/network problem we can pin
                # around); fall back to the index view of the graph.
                fetch_problems = [problem for problem in self.index_problems() if problem["hard"]]
            progressed = False
            for problem in fetch_problems:
                if self.move_offender(problem):
                    progressed = True
            if not progressed:
                break
            self.refresh()
        ok, fetch_problems, output = self.fetch_offender()
        if ok:
            fetch_problems = self.oracle_problems()  # final verdict from the real build
        index_problems = self.index_problems()
        if not ok and not fetch_problems:
            sys.stdout.write(output[-2500:])
            fetch_problems = [{"name": "(cargo fetch failed)", "version": "", "reason": "see the output above", "hard": True}]
        if self.oracle_moves:
            print("\npins the build oracle had to discover — a fresh resolution picks the too-new "
                  "release again, so record them in scripts/msrv-pins.toml:")
            for name, frm, to in sorted(set(self.oracle_moves)):
                print(f'  {name} = "{to}"   # {frm} does not compile with Rust {self.msrv_text}')
        if self.oracle_noise:
            print("note: the oracle also reported errors unrelated to Rust versions, so a clean "
                  "build is not implied by this run")
        # Only "cargo 1.75 cannot read this manifest" is fatal: a crate that
        # merely *declares* a newer rust-version is harmless as long as it is
        # never compiled (the wasm / wayland subtrees in our graph) and the
        # real Windows/Android builds are the judge for the rest.
        return fetch_problems, index_problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--msrv", help="MSRV to target (default: rust-version from Cargo.toml)")
    parser.add_argument("--resolve-toolchain", default="stable", help="toolchain used for `cargo update`")
    parser.add_argument("--msrv-toolchain", help="toolchain used to verify (default: the MSRV)")
    parser.add_argument("--rounds", type=int, default=25)
    parser.add_argument(
        "--oracle",
        default="",
        help='build command to use as the source of truth about what compiles, e.g. '
             '"cargo +1.75.0 check --locked --target x86_64-pc-windows-msvc -p rust-academy"',
    )
    parser.add_argument("--pins-file", default="", help="curated pins (default: scripts/msrv-pins.toml)")
    parser.add_argument(
        "--suggest-pins",
        action="store_true",
        help="with --list: also report locked crates published after the MSRV toolchain that "
             "declare no rust-version (the ones only a build can catch), with a candidate version",
    )
    parser.add_argument(
        "--print-pins",
        action="store_true",
        help="print the curated pins as `name version` lines and exit (used by scripts/diagnose-lockfile.sh)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="only report which locked releases are too new and what they would move to",
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

    autopin = Autopin(root, msrv, cargo_for(args.resolve_toolchain), cargo_for(args.msrv_toolchain or msrv),
                      oracle=args.oracle,
                      pins_file=pathlib.Path(args.pins_file) if args.pins_file else None)

    if args.print_pins:
        for name, want in sorted(autopin.pins.items()):
            print(f"{name} {want}")
        return 0

    if args.list:
        autopin.refresh()
        for name, want in sorted(autopin.pins.items()):
            state = "ok" if want in autopin.versions_of(name) else "NOT LOCKED (locked: %s)" % ("/".join(autopin.versions_of(name)) or "absent")
            print(f"pin {name} = {want}: {state}")
        problems = autopin.index_problems()
        for problem in problems:
            choices = autopin.candidates(problem["name"], problem["version"])
            flag = "hard " if problem["hard"] else "soft "
            print(f"{flag}{problem['name']} {problem['version']} -> {choices[0] if choices else '(none)'}  [{problem['reason']}]")
        if args.suggest_pins:
            suspects = autopin.unpinnable_suspects()
            released = autopin.msrv_released()
            print(f"\n{len(suspects)} locked crate(s) were published after Rust {msrv} "
                  f"({released}) and declare no rust-version — only a build proves they work:")
            for suspect in suspects[:40]:
                hint = (f"newest release from before {released}: {suspect['candidate']} "
                        f"({suspect['candidate_published']})") if suspect["candidate"] else "no older release in the same series"
                print(f"  {suspect['name']} {suspect['version']} (published {suspect['published']}) -> {hint}")
            if len(suspects) > 40:
                print(f"  ... and {len(suspects) - 40} more")
            if suspects:
                print(f"To keep one from coming back, pin it: add `<crate> = \"<version>\"` to "
                      f"{autopin.pins_file.name}")
        print(f"{len(problems)} package(s) are newer than Rust {msrv}")
        if not problems and not autopin.pins:
            print(f"nothing to pin (no {autopin.pins_file.name})")
        return 0

    hard, soft = autopin.fix(args.rounds)
    for failure in autopin.pin_failures:
        print(f"warning: curated pin: {failure}", file=sys.stderr)
    for problem in soft:
        print(
            f"note: {problem['name']} {problem['version']} declares rustc {problem.get('rust_version_text')} "
            "as its minimum but no older release fits its parents' requirements (harmless as long as it is "
            "never compiled for Windows/Android)",
            file=sys.stderr,
        )
    if hard:
        print(f"\n{len(hard)} package(s) could not be made usable with Rust {msrv}:", file=sys.stderr)
        for problem in hard:
            print(f"  - {problem['name']} {problem['version']}: {problem['reason']}".rstrip(), file=sys.stderr)
        print("Pin them by hand: `cargo +stable update -p <crate> --precise <version>`", file=sys.stderr)
        return 1
    print(f"ok: Cargo.lock only contains crates usable with Rust {msrv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
