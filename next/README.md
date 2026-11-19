# Native migration (in progress)

The Xray core is written in Go. PulseGrid's existing dashboard, API, Xray
supervisor and SQLite storage are still Python. Do not treat this directory as a
replacement for the current service or uninstall Python yet.

- `go/cmd/tlscheck`: the Go certificate/key and IP/DNS identity validator. The
  installer builds it and uses it during installation and certificate deployment.
  This is not a public CA trust check: dashboard and core clients verify trust.
- `rust/health`: a Rust port of the health score and verdict calculation. It is
  not yet wired into the Doctor or production service.

Build and test with Go 1.19+ and stable Rust:

```sh
(cd next/go && go test ./...)
cargo test --manifest-path next/rust/health/Cargo.toml
```

A complete migration still needs a Go API and storage layer, Go Xray process
supervision, a Rust diagnostic worker with network probes, data migration, full
API compatibility, packaging and systemd deployment, and end-to-end tests. The
existing service stays in place until these are ready and validated.
