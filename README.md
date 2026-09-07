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
cargo build --release --bin rust-academy
target/release/rust-academy.exe
```

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
keystore/                  Android release signing key (+ README)
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
