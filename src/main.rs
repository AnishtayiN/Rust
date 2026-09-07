// Rust Academy — Windows entry point.
//
// The run_ui function lives in the library crate, which also provides the
// Android entry point. Keeping a separate executable makes it possible to run
// `cargo build --bin rust-academy` for Windows while `cargo apk build --lib`
// builds the Android cdylib.

fn main() {
    rust_academy::run_ui();
}
