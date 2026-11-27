# AGENTS.md

Notes for anyone (human or agent) changing this repository.

- **Project memory is in [lode/](lode/lode-map.md).** Read `lode/summary.md` first, and update the
  lode in the same PR as the change it describes.

- **Public repository.** No hostnames, IP addresses, internal service names, or anything about a
  particular deployment in code, tests, fixtures, commits or PRs. Fixtures are anonymized.
- **Metric names and labels are the interface.** Renaming or removing one is a breaking change:
  say so in the CHANGELOG and bump the minor version (0.x) or major (1.x+).
- **Never log or export a token value.** Tests assert this; keep them.
- **No runtime dependencies.** The exporter is standard library only, so the `.deb` depends on
  nothing but `python3`.
- **Packaging:** `debian/` builds a native package with debhelper + pybuild. Units live in
  `systemd/` and are opt-in: never enable them for every user on install. lintian must stay clean
  at `--pedantic` with info tags (`scripts/build-deb.sh` enforces it).
- **Checks before a PR:** `python -m pytest -q`, `ruff check . && ruff format --check .`, and the
  container build + smoke test from the README when packaging changes.
- **CHANGELOG:** add entries under `## [Unreleased]`, grouped Added/Changed/Fixed/Removed, each with a
  bold lead saying the effect for a user and the PR number. No CI-only entries.
- **Commits are signed.** `main` takes squash merges. Releases: [docs/releasing.md](docs/releasing.md).
  Never move or re-use a tag.
