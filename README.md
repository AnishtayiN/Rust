# Rust Academy

A **complete, graphical Rust programming course** that runs as a polished
native application on **Android and Windows**.

<img src="assets/logo.svg" alt="Rust Academy" width="180"/>

Learn Rust the hands-on way: short lessons, interactive quizzes, annotated
code, a step-by-step Code Lab simulator, a searchable cheat sheet,
achievements, streaks and a weekly progress dashboard — all in one dark,
modern UI with an orange "Rust" accent, built with [Slint](https://slint.dev).

---

## Features

| Area | What you get |
| --- | --- |
| **Course** | 3 modules, 10 lessons (Getting Started → Ownership → Power Features), each with explanations, annotated Rust code, tips/warnings and a 4-question quiz |
| **Code Lab** | 4 interactive Rust scenarios (move semantics, borrowing, shadowing, iterators) stepped through line-by-line with live variable state, manual stepping **and an auto-play timer** |
| **Cheat sheet** | 15 searchable entries in 5 categories (Basics, Ownership, Patterns, Tools) with collapsible cards |
| **Progress** | XP, daily streak, weekly bar chart, lessons completed, per-lesson best quiz score, 12 badges/achievements |
| **Settings** | 4 accent themes, one-tap reset (with confirmation), about dialog with live app version |
| **Responsive UI** | Desktop sidebar layout; automatically switches to a mobile layout with bottom navigation on narrow screens (phones, small windows) |

Everything (lessons, stats, quiz results, opened cheat-sheet entries, accent
theme) is **saved automatically** and restored on the next launch.

## Supported systems

| Platform | Version range |
| --- | --- |
| **Android** (APK) | Android 7.0 (API 24) → latest Android |
| **Windows** (EXE) | Windows 7 → Windows 11 |

The executables are 64-bit: `aarch64` **and** `x86_64` Android (all modern
phones/tablets plus emulators) and `x86_64` Windows.

## Staying on Rust 1.75: why `Cargo.lock` is committed

The toolchain is pinned to **Rust 1.75.0** (the last release that still
produces Windows 7 binaries), and that Cargo cannot even *read* the manifest of
a crate published with edition 2024 — edition 2024 was stabilised with 1.85:

```text
error: failed to download replaced source registry `crates-io`
Caused by:
  failed to parse manifest at `.../icu_normalizer-2.3.0/Cargo.toml`
  feature `edition2024` is required
```

So a single too-new transitive dependency breaks **both** platform builds before
a line of code is compiled. The remedy is to freeze the resolved graph in a
committed `Cargo.lock` and to build with `--locked`, never re-resolving on the
old toolchain. Three pieces keep that arrangement healthy:

* **The MSRV-aware resolver.** `rust-version = "1.75"` in `Cargo.toml` lets
  Cargo ≥ 1.84 prefer dependency releases that still support 1.75. The policy is
  passed per command (`resolver.incompatible-rust-versions = "fallback"`)
  instead of living in a config file, so the old Cargo never sees a key it does
  not know. Do **not** add `resolver = "3"` or switch `edition` to `2024`:
  either one makes the pinned toolchain unable to build the project at all.
* **`scripts/refresh-lockfile.sh`** regenerates `Cargo.lock` that way and then
  repairs and audits it:
  * `scripts/msrv-autopin.py` — the resolver only *prefers* MSRV-compatible
    versions; when a crate has none (the wasm-only `wasip2`/`wit-bindgen`
    subtree, `redox_syscall`, …) it pins an older release, and if the crate
    itself cannot move it moves the crates that depend on it, letting cargo
    verify every requirement on the way;
  * `scripts/check-msrv-lock.py` — after `cargo fetch` unpacked the graph, this
    fails if any locked crate uses edition 2024, an unstable `cargo-features`
    key, or a lockfile format that Cargo 1.75 cannot read (a newer declared
    `rust-version` is reported as a note: those crates only matter when they
    are actually compiled for Windows/Android).
* **`scripts/msrv-pins.toml`** covers the crates that need a newer compiler
  than they admit. `rowan` 0.15.18/0.15.19, for instance, use `ptr_addr_eq`
  (stable since Rust 1.76) but declare no `rust-version`, so neither the MSRV-aware
  resolver, nor a manifest scan, nor `cargo +1.75.0 fetch` can see it coming —
  only the build does, with `error[E0658]: use of unstable library feature
  'ptr_addr_eq'`. Those crates are pinned by hand in that file; `msrv-autopin.py`
  re-applies the pins on every refresh and `check-msrv-lock.py` fails when the
  lockfile drifts away from one.
* **`--oracle` (or `MSRV_BUILD_ORACLE=...`)** hands `msrv-autopin.py` a real build
  command as the source of truth, so a compile error becomes a downgrade instead
  of a red release build:

  ```sh
  MSRV_BUILD_ORACLE='cargo +1.75.0 check --locked --workspace --target x86_64-pc-windows-msvc' \
    ./scripts/refresh-lockfile.sh
  ```

  When that fixes something, record the version it landed on in
  `scripts/msrv-pins.toml` so the next refresh keeps it.  To find candidates
  before a build trips over them, `python3 scripts/msrv-autopin.py --list
  --suggest-pins` reports every locked crate published after the date in
  `[package.metadata.msrv] released` that declares no `rust-version`, together
  with the newest release from before that date.

* **`scripts/set-version.py`** writes a version into `Cargo.toml` **and**
  `Cargo.lock` — the root package's version is recorded in the lock too, and an
  out-of-sync lock would make every `--locked` build fail.

```sh
./scripts/refresh-lockfile.sh                      # re-resolve for Rust 1.75
python3 scripts/check-msrv-lock.py                  # audit Cargo.lock
cargo build --release --bin rust-academy --locked   # always --locked
```

Run the refresh whenever a dependency has to move (or when CI warns that
`Cargo.lock` drifted); commit the new lock together with the change that needs
it. The [`CI` workflow](.github/workflows/ci.yml) performs the same audit on
every push/PR before building both artifacts — and with
*"Re-resolve with the MSRV-aware resolver"* ticked it also re-pins the generated
lock against a real `cargo check` for the Windows target, so a dependency
refresh can be verified (and repaired) before it is committed.  Android-only
dependencies are judged by the Android build job itself.

## Getting a release

Releases are produced by the **manual** GitHub Actions workflow
`.github/workflows/release.yml`:

1. Open **Actions → Release → Run workflow**.
2. Type the app version (for example `1.2.0`) — the workflow **asks for it
   before building** and uses it everywhere (Cargo version, APK
   versionName/versionCode, EXE version resources, artifact names, Git tag and
   release).
3. The workflow builds the Android APK and the Windows EXE and publishes a
   GitHub release tagged `v<version>` containing **exactly two artifacts**:

   ```
   rust-academy-1.2.0-android.apk
   rust-academy-1.2.0-windows.exe
   ```

> **Installing the APK:** copy it to the device and allow installation from
> unknown sources. The APK is signed with the repository's release key
> (`keystore/`), so updates keep installing over previous versions.
>
> **Windows SmartScreen** may warn about the unsigned installer — choose
> *"More info → Run anyway"*.

## Building locally

### Windows

```sh
cargo build --release --bin rust-academy --locked
target/release/rust-academy.exe
```

`--locked` reuses the committed `Cargo.lock`; without it cargo would
re-resolve every dependency to its newest release, which no longer works with
the pinned 1.75 toolchain (see *Staying on Rust 1.75*).

Rust 1.75 (pinned in `rust-toolchain.toml`) is used so the binary still runs
on Windows 7. The build embeds the Rust Academy icon and version resources.

### Android

Requirements: Rust 1.75 with the Android targets (in `rust-toolchain.toml`),
Android SDK (platform 35 + build-tools 35), NDK r26.1, JDK 17, and
[cargo-apk](https://github.com/rust-mobile/cargo-apk) 0.9.7.

```sh
export ANDROID_HOME="$HOME/Android/Sdk"
export ANDROID_NDK_ROOT="$ANDROID_HOME/ndk/26.1.10909125"
export JAVA_HOME=...            # JDK 17

cargo install cargo-apk --locked --version 0.9.7

# Vendor + patch Slint's Android backend (needed for API 24 support)
bash scripts/prepare-vendor.sh

# Build (signed with keystore/rust-academy-release.p12)
cargo apk build --release --lib
# -> target/release/apk/rust-academy.apk
# (cargo apk cannot forward --locked, so check the lock first:
#  cargo metadata --locked --format-version 1 > /dev/null)
```

`cargo apk run --release --lib` installs it on a connected device/emulator.

## Why this project vendors part of Slint

Slint 1.8's official Android backend has three pieces that only exist on newer
Android versions, so on **Android 7.0/7.1 it would crash at startup**:

| Upstream code | Requires | Patch in `vendor/` |
| --- | --- | --- |
| `InMemoryDexClassLoader` in `javahelper.rs` | API 26+ | DexClassLoader from a file in app-internal storage (works everywhere) |
| `BlendModeColorFilter` in `SlintAndroidJavaHelper.java` | API 29+ | `PorterDuffColorFilter` (API 1+) |
| `Menu.setGroupDividerEnabled` in `SlintAndroidJavaHelper.java` | API 28+ | guarded with `Build.VERSION.SDK_INT >= 28` |

`vendor/slint-android-backend` is wired in through
`[patch.crates-io]` in `Cargo.toml`, and
[`scripts/prepare-vendor.sh`](scripts/prepare-vendor.sh) reproducibly
re-downloads the exact upstream v1.8.0 tarball and re-applies the patch (use
`scripts/prepare-vendor.sh --check` to verify a checkout).

Similarly, the project pins **Rust 1.75.0** — the last release that can
produce Windows 7 compatible binaries — and keeps Slint at **1.8.x** (the
newer releases have a higher MSRV and dropped API 24 support even earlier).

## Project layout

```
Cargo.toml                 Cargo manifest + Android packaging metadata (cargo apk)
Cargo.lock                 Frozen dependency graph (builds use --locked; see below)
build.rs                   Slint compiler + Windows icon/version resources
rust-toolchain.toml        Rust 1.75.0 + Android/Windows targets
src/
  main.rs                  Windows entry point
  lib.rs                   UI wiring, state, quiz/lab/cheat-sheet logic, persistence
  content.rs               All course content (lessons, code, quizzes, scenarios, ...)
ui/
  theme.slint              Design tokens (dark palette + orange accent)
  components.slint         Reusable components, structs, icon set
  app.slint                MainWindow: 9 views, responsive sidebar/bottom-nav
assets/
  icons/                   42 hand-made SVG icons · logo.svg · Windows & Android icons
res/                      Android launcher icons (mipmaps)
vendor/slint-android-backend  Patched Slint Android backend (API 24 support)
scripts/prepare-vendor.sh  Regenerate/verify the vendored backend
scripts/refresh-lockfile.sh Regenerate Cargo.lock for the pinned MSRV toolchain
scripts/msrv-autopin.py    Pin back dependencies the MSRV resolver falls back on
scripts/check-msrv-lock.py Audit Cargo.lock against Rust 1.75
keystore/                  Android release signing key (+ README)
.github/workflows/ci.yml         MSRV lockfile audit + both platform builds (no publishing)
.github/workflows/release.yml  Manual release workflow (asks for version, 2 artifacts)
```

## Privacy & data

The app is fully offline: no accounts, no telemetry, no network access.
Progress is stored in `%APPDATA%\RustAcademy\rust-academy.json` on Windows and
in the app's internal storage on Android.

## License

The Rust Academy source (Rust, Slint UI, content, icons) is provided under the
**MIT License**. The vendored Slint Android backend keeps its original Slint
license (GPL-3.0-only OR Slint Royalty-free OR Slint Software; see
`vendor/slint-android-backend/LICENSES/`).
