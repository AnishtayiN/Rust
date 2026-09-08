#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# diagnose-lockfile.sh — explain why `cargo --locked` does not accept Cargo.lock.
#
# `error: the lock file Cargo.lock needs to be updated but --locked was passed`
# only says that cargo's own resolution differs from the committed file; it does
# not say *where*.  This script shows both resolutions next to each other:
#
#   1. the verdict for the committed lockfile;
#   2. a fresh MSRV-aware resolution (what cargo would write from scratch);
#   3. the curated pins from scripts/msrv-pins.toml re-applied on top of it,
#      which is the state scripts/refresh-lockfile.sh leaves the lock in;
#   4. the entries of the pinned crates in both files, so the difference between
#      a hand-edited lock and a cargo-written one can be read directly;
#   5. the verdict for the lock cargo just wrote, and the manifest audit.
#
# It leaves the working tree as it found it (pass --keep to keep the regenerated
# lockfile) and writes its report to "${RUNNER_TEMP:-/tmp}/lockdiff.log", which
# scripts/ci-diagnostics.sh turns into a comment on the pull request.
#
# Usage: scripts/diagnose-lockfile.sh [--keep]     # in a checkout of this repo
# ---------------------------------------------------------------------------
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"
RT="${RUNNER_TEMP:-/tmp}"
LOG="${RT}/lockdiff.log"
: >"${LOG}"

MSRV_TOOLCHAIN="${MSRV_TOOLCHAIN:-$(sed -n 's/^channel[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' rust-toolchain.toml | head -1)}"
KEEP=0
[[ "${1:-}" == "--keep" ]] && KEEP=1

say() { printf '%s\n' "$*" | tee -a "${LOG}"; }

cargo_for() { # cargo_for <toolchain> -> echoes the right cargo invocation
    if command -v rustup >/dev/null 2>&1; then echo "cargo +${1}"; else echo "cargo"; fi
}

PY=python3
command -v python3 >/dev/null 2>&1 || PY=python

# The pinned crates as `name version` lines, read by the same parser the pinner
# uses, so this report always talks about the same pins.
PINS="$($PY scripts/msrv-autopin.py --print-pins 2>/dev/null)"

say "== 1. the committed Cargo.lock, with the pinned toolchain (${MSRV_TOOLCHAIN}) =="
# shellcheck disable=SC2086
verdict="$($(cargo_for "${MSRV_TOOLCHAIN}") fetch --locked 2>&1 | tail -6)"
say "${verdict:-ok: cargo is happy with the committed lockfile}"

cp Cargo.lock "${RT}/committed.Cargo.lock"

say ""
say "== 2. a fresh MSRV-aware resolution (stable) =="
if command -v rustup >/dev/null 2>&1; then
    rustup toolchain install stable --profile minimal >/dev/null 2>&1 || true
fi
RESOLVE="$(cargo_for "${RESOLVE_TOOLCHAIN:-stable}")"
# shellcheck disable=SC2086
if ${RESOLVE} generate-lockfile --config 'resolver.incompatible-rust-versions="fallback"' 2>&1 |
    tail -4 >>"${LOG}"; then
    say "regenerated: $(grep -c '^\[\[package\]\]' Cargo.lock) packages"
else
    say "generate-lockfile failed:"
    tail -8 "${LOG}"
fi

say ""
say "== 3. re-applying the curated pins on top of it =="
if [[ -z "${PINS}" ]]; then
    say "(no pins in scripts/msrv-pins.toml)"
fi
while read -r name want; do
    [[ -n "${name:-}" ]] || continue
    # shellcheck disable=SC2086
    out="$(${RESOLVE} update -p "${name}" --precise "${want}" 2>&1)"
    say "${name} -> ${want}: $(printf '%s\n' "${out}" | grep -E 'Downgrading|Adding|Removing|error' | head -3 | tr '\n' ' ')"
done <<<"${PINS}"

say ""
say "== 4. the pinned crates: committed lock vs the lock cargo wrote =="
$PY - "${RT}/committed.Cargo.lock" Cargo.lock <<'PYTHON' >>"${LOG}" 2>&1
import pathlib
import re
import sys

files = [pathlib.Path(text) for text in sys.argv[1:]]
pins = pathlib.Path("scripts/msrv-pins.toml").read_text()
section = pins.split("[pins]", 1)[1] if "[pins]" in pins else ""
crates = sorted(set(re.findall(r"(?m)^([a-z0-9_.-]+)\s*=", section)))


def entry(path, crate):
    for block in re.split(r"\n\[\[package\]\]\n", path.read_text())[1:]:
        if f'name = "{crate}"' in block:
            return block.strip()
    return "(not in this lockfile)"


for crate in crates:
    print(f"### {crate}")
    for path in files:
        print(f"--- {path}")
        print("\n".join(entry(path, crate).splitlines()[:14]))
    print()
PYTHON
say "$(tail -70 "${LOG}")"

say ""
say "== 5. does ${MSRV_TOOLCHAIN} accept the lock cargo just wrote? =="
# shellcheck disable=SC2086
if $(cargo_for "${MSRV_TOOLCHAIN}") fetch --locked 2>&1 | tail -6 | tee -a "${LOG}"; then
    say "-> yes: the difference shown above is the patch the committed lockfile needs"
    say "== 6. manifest audit of that lockfile =="
    $PY scripts/check-msrv-lock.py 2>&1 | grep -vE '^note: manifest not in the cargo cache' |
        tail -12 | tee -a "${LOG}"
else
    say "-> no: even a freshly resolved and pinned lock is rejected; look at Cargo.toml requirements"
fi

if [[ "${KEEP}" == 0 ]]; then
    cp "${RT}/committed.Cargo.lock" Cargo.lock
    say ""
    say "(restored the committed Cargo.lock)"
fi
say "(full report: ${LOG})"
