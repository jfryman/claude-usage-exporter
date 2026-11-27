# Releasing

1. A pull request that bumps the version in all three places (CI checks they agree):
   `pyproject.toml`, `src/claude_usage_exporter/__init__.py`, and `debian/changelog`
   (`dch -v X.Y.Z` or by hand: native package, so no `-1` revision). Move `## [Unreleased]` in
   `CHANGELOG.md` to `## [X.Y.Z] - YYYY-MM-DD`. Squash-merge it.
2. Signed, annotated tag on that commit: `git tag -s vX.Y.Z -m "claude-usage-exporter X.Y.Z"`,
   then `git push origin vX.Y.Z`.
3. The `release` workflow builds the `.deb` in Debian trixie, runs lintian (pedantic, must be
   clean), installs it in clean Debian 12, Ubuntu 24.04 and Ubuntu 26.04 containers and scrapes it
   against a mock endpoint, attests build provenance, and opens a **draft** release with the
   CHANGELOG section as notes and these assets: the `.deb`, `claude-usage-dashboard.json`,
   `claude-usage-exporter-docs-X.Y.Z.tar.gz`, `SHA256SUMS`. The `image` workflow pushes
   `ghcr.io/<owner>/claude-usage-exporter:vX.Y.Z`, `X.Y` and `latest`.
4. Sign the checksums with the release key and publish:
   ```sh
   gh release download vX.Y.Z -p SHA256SUMS -p '*.deb' -D /tmp/rel && cd /tmp/rel
   sha256sum --ignore-missing -c SHA256SUMS
   gh attestation verify claude-usage-exporter_X.Y.Z_all.deb --repo <owner>/claude-usage-exporter
   gpg --armor --detach-sign --local-user 79C5A31806F1AAE42107BD44187A16A92C5675DF SHA256SUMS
   gh release upload vX.Y.Z SHA256SUMS.asc && gh release edit vX.Y.Z --draft=false --latest
   ```

Never move or re-use a tag. A broken release gets a new patch version.
