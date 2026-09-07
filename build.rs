fn main() {
    // Compile the Slint UI (ui/app.slint) into Rust code.
    slint_build::compile("ui/app.slint").expect("failed to compile ui/app.slint");

    // Embed an icon into the Windows executable. If rc.exe / the resource
    // compiler is unavailable we simply continue without an icon so that the
    // build never fails because of a cosmetic resource.
    #[cfg(windows)]
    {
        if std::path::Path::new("assets/icon/app.ico").exists() {
            let mut res = winres::WindowsResource::new();
            res.set_icon("assets/icon/app.ico");
            res.set("FileDescription", "Rust Academy - learn and practice Rust");
            res.set("ProductName", "Rust Academy");
            if let Ok(version) = std::env::var("RUST_ACADEMY_VERSION") {
                res.set("FileVersion", &version);
                res.set("ProductVersion", &version);
            }
            if let Err(err) = res.compile() {
                println!("cargo:warning=Could not embed application icon: {err}");
            }
        }
    }
    println!("cargo:rerun-if-env-changed=RUST_ACADEMY_VERSION");
    println!("cargo:rerun-if-changed=ui/app.slint");
    println!("cargo:rerun-if-changed=ui/components.slint");
    println!("cargo:rerun-if-changed=assets/icon/app.ico");
}
