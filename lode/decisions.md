# Decisions

- **Standard library only.** The `.deb` then depends on nothing but `python3`, and there's no
  supply chain to audit beyond the interpreter.
- **Debian package, not PyPI or pipx.** The main consumers are hosts managed by configuration
  management with an apt repository, where a pinned package version is the unit of change.
- **debhelper + pybuild over nfpm.** dh-python gives the dist-packages layout, `python3:any`
  dependencies and byte-compile maintainer scripts for free, and lintian understands the result.
- **Units are opt-in.** The exporter reads one user's credentials, so it runs per user; installing
  the package never enables or starts anything for anyone.
- **Read-only credentials.** Refreshing the token would race the CLI and could log the user out.
- **Fail soft on schema drift.** The endpoint is undocumented; a shape change reports `up 0` and an
  alertable signal instead of a crash loop.
- **Signed SHA256SUMS + draft-until-signed releases.** Downstream pullers verify one signature and
  can safely follow `releases/latest`.
