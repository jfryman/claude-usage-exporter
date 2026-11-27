# Practices

- Rules for changing the code (public repo hygiene, metrics as interface, no token output, no runtime
  deps, packaging, checks, CHANGELOG style, signed commits) are in the top-level `AGENTS.md`.
  This file covers how to work in it.
- **Test locally:** `python -m pytest -q` and `ruff check . && ruff format --check .`. Packaging
  changes: `scripts/build-deb.sh` (builds in a Debian container, lintian must print nothing) then
  `scripts/smoke-test.sh` (clean container, fake credentials, `scripts/mock-upstream.py`, curl
  `/metrics`, remove and purge).
- **Versions agree in three places:** `pyproject.toml`, `src/claude_usage_exporter/__init__.py`,
  `debian/changelog`. CI fails if they don't.
- **Release:** follow `docs/releasing.md` exactly. Never move or reuse a tag; a broken release gets
  a new patch version.
- **Upstream changed shape:** capture an anonymized response into `tests/fixtures/`, add a test that
  shows the new shape, then change the parser. Keep the bad-shape tests that assert `up 0`.
- **New metric:** document it in `docs/metrics.md`, add it to the dashboard if users need it, and
  CHANGELOG it under Added.
- **Dependabot:** merge green PRs; the setuptools floor stays at what Debian stable ships.
- **Lode:** update it in the same PR as the change it describes.
