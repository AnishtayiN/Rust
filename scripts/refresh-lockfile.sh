#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# refresh-lockfile.sh — regenerate Cargo.lock so that it only contains
# dependencies that still build with the pinned MSRV toolchain (Rust 1.75).
#
# Background
# ----------
# The project is pinned to Rust 1.75.0 (rust-toolchain.toml) because that is
# the last release that produces Windows 7 compatible binaries.  Cargo 1.75
# cannot even *parse* the manifest of a crate published with edition 2024
# (those need Cargo >= 1.85), and without a Cargo.lock cargo re-resolves every
# dependency to its newest compatible version — which is how a perfectly
# innocent `cargo build` starts to fail with
#
#   error: failed to download replaced source registry `crates-io`
#   Caused by: feature `edition2024` is required
#
# Cargo >= 1.84 ships an MSRV-aware resolver that prefers dependency versions
# whose `rust-version` is <= the project's `package.rust-version`.  We use it
# (with the permissive "fallback" policy) to write a Cargo.lock, commit that
# lock, and then always build with `--locked`, so the resolved graph never
# drifts underneath the old toolchain again.
#
# Usage
#   scripts/refresh-lockfile.sh              # refresh the existing lock
#   scripts/refresh-lockfile.sh --full       # resolve everything from scratch
#
# Environment overrides
#   RESOLVE_TOOLCHAIN  toolchain used for the resolution step (default: stable)
#   MSRV_TOOLCHAIN     toolchain used to validate the result   (default: from rust-toolchain.toml)
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

FULL=0
if [[ "${1:-}" == "--full" ]]; then
    FULL=1
elif [[ -n "${1:-}" ]]; then
    echo "Usage: $0 [--full]" >&2
    exit 2
fi

# The MSRV is declared in Cargo.toml; the toolchain pin in rust-toolchain.toml
# may carry a patch release (e.g. 1.75.0), which is what we validate against.
MSRV_TOOLCHAIN="${MSRV_TOOLCHAIN:-$(sed -n 's/^channel[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' rust-toolchain.toml | head -1)}"
RESOLVE_TOOLCHAIN="${RESOLVE_TOOLCHAIN:-stable}"
: "${MSRV_TOOLCHAIN:?could not read the toolchain channel from rust-toolchain.toml}"

# Opt the *resolution* into the MSRV-aware resolver without putting a `[resolver]`
# table into the repo (older cargo would not understand it): pass it per command.
MSRV_POLICY='resolver.incompatible-rust-versions="fallback"'

have_rustup=0
command -v rustup >/dev/null 2>&1 && have_rustup=1

cargo_for() { # cargo_for <toolchain> -> echoes the right cargo invocation
    if [[ "${have_rustup}" == 1 ]]; then
        echo "cargo +${1}"
    else
        echo "cargo"
    fi
}

if [[ "${have_rustup}" == 1 ]]; then
    echo "==> making sure the '${RESOLVE_TOOLCHAIN}' and '${MSRV_TOOLCHAIN}' toolchains are installed"
    rustup toolchain install "${RESOLVE_TOOLCHAIN}" --profile minimal >/dev/null
    rustup toolchain install "${MSRV_TOOLCHAIN}" --profile minimal >/dev/null ||
        echo "warning: could not install ${MSRV_TOOLCHAIN} locally; the validation step may be skipped"
fi

RESOLVE_CARGO="$(cargo_for "${RESOLVE_TOOLCHAIN}")"
MSRV_CARGO="$(cargo_for "${MSRV_TOOLCHAIN}")"

if [[ "${FULL}" == 1 || ! -f Cargo.lock ]]; then
    echo "==> resolving the full dependency graph with cargo (${RESOLVE_TOOLCHAIN}), MSRV-aware"
    rm -f Cargo.lock
    # shellcheck disable=SC2086
    ${RESOLVE_CARGO} generate-lockfile --config "${MSRV_POLICY}"
else
    echo "==> updating the existing lockfile with cargo (${RESOLVE_TOOLCHAIN}), MSRV-aware"
    # shellcheck disable=SC2086
    ${RESOLVE_CARGO} update --config "${MSRV_POLICY}"
fi

echo "==> checking the result against cargo ${MSRV_TOOLCHAIN}"
if [[ "${have_rustup}" == 1 ]]; then
    # `fetch` downloads + unpacks every locked crate, which is exactly what
    # makes an edition-2024 manifest explode, and --locked proves the lockfile
    # is in sync with Cargo.toml.
    # shellcheck disable=SC2086
    ${MSRV_CARGO} fetch --locked
fi

if command -v python3 >/dev/null 2>&1; then
    python3 scripts/check-msrv-lock.py
elif command -v python >/dev/null 2>&1; then
    python scripts/check-msrv-lock.py
else
    echo "warning: python not found, skipping the MSRV manifest check" >&2
fi

echo
echo "Cargo.lock refreshed: $(grep -c '^\[\[package\]\]' Cargo.lock) packages."
echo "Commit Cargo.lock and build with --locked."
