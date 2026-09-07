# Release signing key

`rust-academy-release.p12` is a self-signed PKCS#12 signing key that is
committed to this repository **on purpose**: the release workflow signs every
APK with it, and Android only allows an app to be updated in place when the
new APK is signed with the same key. Keeping one stable key in the repository
means every `v*` release of Rust Academy is an upgrade of the previous one.

Details:

* Alias: `rust-academy`
* Password: `rust-academy-release`
* Validity: 100 years (generated 2026-09-07)
* Subject: `CN=Rust Academy`

This is a **demonstration key**. It is NOT suitable for publishing on Google
Play or any public store — you should generate your own key and keep it in
a secret place before distributing the app commercially:

```sh
keytool -genkeypair -v -keystore release.p12 -storetype PKCS12 \
  -alias rust-academy -keyalg RSA -keysize 2048 -validity 36500 \
  -storepass rust-academy-release -dname "CN=Rust Academy"
```

Then update the path/password in `[package.metadata.android.signing.release]`
in `Cargo.toml`.
