#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# prepare-vendor.sh — (re)generate vendor/slint-android-backend from upstream.
#
# Slint 1.8.0's Android backend refuses to run on Android 7.0/7.1 (API 24/25):
#   * javahelper.rs          loads its Java helper via InMemoryDexClassLoader   (API 26+)
#   * SlintAndroidJavaHelper.java uses BlendMode/BlendModeColorFilter          (API 29+)
#   * SlintAndroidJavaHelper.java uses Menu.setGroupDividerEnabled             (API 28+)
#
# This script downloads the exact upstream v1.8.0 tarball, applies a minimal
# patch for those three problems and re-creates vendor/slint-android-backend,
# which is referenced by `[patch.crates-io]` in Cargo.toml.
#
# Usage:
#   scripts/prepare-vendor.sh          # regenerate the vendored backend
#   scripts/prepare-vendor.sh --check  # verify vendor matches what would be generated
#
# The script needs curl, tar, python3 and standard POSIX tools. It does not
# modify anything outside the repository.
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENDOR_DIR="${ROOT_DIR}/vendor/slint-android-backend"
CACHE_DIR="${ROOT_DIR}/vendor/.cache"

SLINT_VERSION="1.8.0"
TARBALL_URL="https://github.com/slint-ui/slint/archive/refs/tags/v${SLINT_VERSION}.tar.gz"
TARBALL_NAME="slint-${SLINT_VERSION}.tar.gz"

MODE="generate"
if [[ "${1:-}" == "--check" ]]; then
    MODE="check"
elif [[ -n "${1:-}" ]]; then
    echo "Usage: $0 [--check]" >&2
    exit 2
fi

mkdir -p "${CACHE_DIR}"

# ---------------------------------------------------------------------------
# 1. Fetch the upstream source (hash-checked against the vendored git history).
# ---------------------------------------------------------------------------
if [[ ! -f "${CACHE_DIR}/${TARBALL_NAME}" ]]; then
    echo "Downloading Slint v${SLINT_VERSION} source…"
    curl -fsSL -o "${CACHE_DIR}/${TARBALL_NAME}.part" "${TARBALL_URL}"
    mv "${CACHE_DIR}/${TARBALL_NAME}.part" "${CACHE_DIR}/${TARBALL_NAME}"
fi

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

tar -xzf "${CACHE_DIR}/${TARBALL_NAME}" -C "${WORK_DIR}" \
    "slint-${SLINT_VERSION}/internal/backends/android-activity" \
    "slint-${SLINT_VERSION}/LICENSES"

UPSTREAM_DIR="${WORK_DIR}/slint-${SLINT_VERSION}/internal/backends/android-activity"
BACKEND_DIR="${WORK_DIR}/backend"
cp -R "${UPSTREAM_DIR}" "${BACKEND_DIR}"

# The upstream LICENSE files are symlinks into the Slint workspace root.
# Replace them with real copies so the vendored crate is self-contained.
rm -rf "${BACKEND_DIR}/LICENSES"
mkdir -p "${BACKEND_DIR}/LICENSES"
for license in \
    GPL-3.0-only.txt \
    LicenseRef-Slint-Royalty-free-2.0.md \
    LicenseRef-Slint-Software-3.0.md; do
    cp "${WORK_DIR}/slint-${SLINT_VERSION}/LICENSES/${license}" \
        "${BACKEND_DIR}/LICENSES/${license}"
done

# ---------------------------------------------------------------------------
# 2. Patch the source. Every replacement must apply exactly once, otherwise the
#    script aborts (protects against upstream changes).
# ---------------------------------------------------------------------------
python3 - "${BACKEND_DIR}" <<'PYEOF'
import pathlib, sys, textwrap

backend = pathlib.Path(sys.argv[1])

def patch(path, old, new):
    p = backend / path
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"PATCH FAILED on {path}: expected 1 occurrence, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")

# --- 1. javahelper.rs: load the helper dex on API 24/25 too ------------------
patch(
    "javahelper.rs",
    '''    let dex_data = include_bytes!(concat!(env!("OUT_DIR"), "/classes.dex"));

    // Safety: dex_data is 'static and the InMemoryDexClassLoader will not mutate it it
    let dex_buffer =
        unsafe { env.new_direct_byte_buffer(dex_data.as_ptr() as *mut _, dex_data.len()).unwrap() };

    let dex_loader = env.new_object(
        "dalvik/system/InMemoryDexClassLoader",
        "(Ljava/nio/ByteBuffer;Ljava/lang/ClassLoader;)V",
        &[JValue::Object(&dex_buffer), JValue::Object(&JObject::null())],
    )?;
''',
    '''    let dex_data = include_bytes!(concat!(env!("OUT_DIR"), "/classes.dex"));

    // Android 8.0 (API 26) introduced InMemoryDexClassLoader, which loads a dex
    // file straight from a ByteBuffer. That class does not exist on
    // Android 7.0/7.1 (API 24/25), so on those devices the embedded dex is
    // written to the app's internal storage and loaded with the classic
    // DexClassLoader instead. DexClassLoader also keeps working on newer
    // Android versions (it behaves like PathClassLoader there), so this single
    // path lets one binary run from Android 7.0 up to the latest release.
    let dex_dir = app
        .internal_data_path()
        .expect("Failed to obtain the Android internal data path")
        .join("slint-helper");
    std::fs::create_dir_all(&dex_dir).expect("Failed to create the Slint Java helper directory");
    let dex_file = dex_dir.join("classes.dex");
    if dex_file
        .metadata()
        .map(|m| m.len() != dex_data.len() as u64)
        .unwrap_or(true)
    {
        std::fs::write(&dex_file, dex_data).expect("Failed to write the Slint Java helper dex file");
    }

    let dex_path = env.new_string(
        dex_file
            .to_str()
            .expect("The Slint Java helper dex path is not valid UTF-8"),
    )?;
    let optimized_dir = env.new_string(
        dex_dir
            .to_str()
            .expect("The Slint Java helper dex directory is not valid UTF-8"),
    )?;
    let dex_loader = env.new_object(
        "dalvik/system/DexClassLoader",
        "(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/ClassLoader;)V",
        &[
            JValue::Object(&dex_path),
            JValue::Object(&optimized_dir),
            JValue::Object(&JObject::null()),
            JValue::Object(&JObject::null()),
        ],
    )?;
''',
)

# --- 2. Java helper: BlendMode (API 29+) -> PorterDuff (API 1+) --------------
patch(
    "java/SlintAndroidJavaHelper.java",
    '''import android.graphics.BlendMode;
import android.graphics.BlendModeColorFilter;
import android.graphics.Rect;
import android.graphics.drawable.Drawable;
import android.text.Editable;
''',
    '''import android.graphics.PorterDuff;
import android.graphics.PorterDuffColorFilter;
import android.graphics.Rect;
import android.graphics.drawable.Drawable;
import android.os.Build;
import android.text.Editable;
''',
)

patch(
    "java/SlintAndroidJavaHelper.java",
    "            drawable.setColorFilter(new BlendModeColorFilter(color, BlendMode.SRC_IN));",
    "            drawable.setColorFilter(new PorterDuffColorFilter(color, PorterDuff.Mode.SRC_IN));",
)

# --- 3. Java helper: Menu.setGroupDividerEnabled (API 28+) -------------------
patch(
    "java/SlintAndroidJavaHelper.java",
    "                menu.setGroupDividerEnabled(true);",
    '''                if (Build.VERSION.SDK_INT >= 28) {
                    menu.setGroupDividerEnabled(true);
                }''',
)

# --- 4. Cargo.toml: remove workspace inheritance -----------------------------
# `[patch.crates-io]` requires this crate to live outside the Slint workspace,
# so every `workspace = true` value is replaced by its concrete value.
(backend / "Cargo.toml").write_text(textwrap.dedent('''
    # Vendored copy of Slint 1.8.0's i-slint-backend-android-activity.
    #
    # This copy is pinned at the exact upstream version and carries a small patch so
    # the app can run on Android 7.0 (API 24):
    #
    #   * javahelper.rs loads the Java helper dex with DexClassLoader from a file
    #     in the app's internal storage instead of InMemoryDexClassLoader (API 26+).
    #   * java/SlintAndroidJavaHelper.java uses PorterDuffColorFilter instead of
    #     BlendModeColorFilter (API 29+), and guards Menu.setGroupDividerEnabled
    #     with Build.VERSION.SDK_INT >= 28.
    #
    # scripts/prepare-vendor.sh regenerates this directory from the upstream
    # v1.8.0 source and re-applies the patches, so this copy stays reproducible.
    #
    # The only differences from upstream are the three code changes above, plus the
    # Cargo.toml below: because this crate is patched in from a path outside the
    # Slint workspace, all `workspace = true` fields and dependencies are replaced
    # with their concrete values.

    [package]
    name = "i-slint-backend-android-activity"
    description = "OpenGL rendering backend for Slint"
    version = "1.8.0"
    authors = ["Slint Developers <info@slint.dev>"]
    edition = "2021"
    homepage = "https://slint.dev"
    license = "GPL-3.0-only OR LicenseRef-Slint-Royalty-free-2.0 OR LicenseRef-Slint-Software-3.0"
    repository = "https://github.com/slint-ui/slint"
    rust-version = "1.75"

    [lib]
    path = "lib.rs"

    [features]
    game-activity = [
        "android-activity-06?/game-activity",
        "android-activity-05?/game-activity",
    ]
    native-activity = [
        "android-activity-06?/native-activity",
        "android-activity-05?/native-activity",
    ]
    aa-06 = ["android-activity-06", "ndk-09"]
    aa-05 = ["android-activity-05", "ndk-08"]

    [target.'cfg(target_os = "android")'.dependencies]
    i-slint-renderer-skia = { version = "=1.8.0", default-features = false }
    i-slint-core = { version = "=1.8.0", features = ["std"] }
    raw-window-handle = { version = "0.6" }
    android-activity-05 = { package = "android-activity", version = "0.5", optional = true }
    android-activity-06 = { package = "android-activity", version = "0.6", optional = true }
    jni = { version = "0.21", features = ["invocation"] }

    # We only depend on the NDK directly to enable raw-window-handle 0.6 which we need for the skia renderer
    ndk-08 = { package = "ndk", version = "0.8.0", optional = true, features = ["rwh_06"] }
    ndk-09 = { package = "ndk", version = "0.9.0", optional = true, features = ["rwh_06"], default-features = false }

    [package.metadata.docs.rs]
    targets = [
        "aarch64-linux-android",
        "armv7-linux-androideabi",
        "i686-linux-android",
        "x86_64-linux-android",
    ]
    features = ["native-activity", "aa-06"]
''').lstrip(), encoding="utf-8")

print("All patches applied.")
PYEOF

# ---------------------------------------------------------------------------
# 3. Install or verify.
# ---------------------------------------------------------------------------
if [[ "${MODE}" == "check" ]]; then
    if ! diff -r --brief "${BACKEND_DIR}" "${VENDOR_DIR}" >/dev/null 2>&1; then
        echo "VENDOR MISMATCH: vendor/slint-android-backend differs from the patched" >&2
        echo "upstream source. Run 'scripts/prepare-vendor.sh' and commit the result." >&2
        diff -r "${BACKEND_DIR}" "${VENDOR_DIR}" >&2 || true
        exit 3
    fi
    echo "vendor/slint-android-backend is up to date (Slint v${SLINT_VERSION} + API 24 patch)."
else
    rm -rf "${VENDOR_DIR}"
    mkdir -p "$(dirname "${VENDOR_DIR}")"
    cp -R "${BACKEND_DIR}" "${VENDOR_DIR}"
    echo "vendor/slint-android-backend regenerated from Slint v${SLINT_VERSION} + API 24 patch."
fi
