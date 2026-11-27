#!/bin/sh
# Build the .deb and run lintian. Run inside a Debian container from the repo root:
#   podman run --rm -v "$PWD":/src:ro -v "$PWD/dist":/out debian:trixie /src/scripts/build-deb.sh
# Output in /out (or $OUT): the .deb, .buildinfo, .changes and lintian.txt.
set -eu
SRC=${SRC:-/src}
OUT=${OUT:-/out}
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  build-essential debhelper dh-python pybuild-plugin-pyproject \
  python3-all python3-setuptools python3-pytest lintian >/dev/null

work=$(mktemp -d)
cp -a "$SRC" "$work/claude-usage-exporter"
cd "$work/claude-usage-exporter"
rm -rf .git dist

# The three version strings must agree.
py=$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')
mod=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' src/claude_usage_exporter/__init__.py)
deb=$(dpkg-parsechangelog -S Version)
[ "$py" = "$mod" ] && [ "$py" = "$deb" ] || { echo "version mismatch: pyproject $py, module $mod, debian $deb" >&2; exit 1; }
if [ -n "${EXPECT_VERSION:-}" ] && [ "$EXPECT_VERSION" != "$py" ]; then
  echo "tag says $EXPECT_VERSION, source says $py" >&2; exit 1
fi

dpkg-buildpackage -us -uc -b
mkdir -p "$OUT"
cp ../*.deb ../*.buildinfo ../*.changes "$OUT"/
# Clean = no error, warning, info, pedantic or experimental tag. (--fail-on info also trips on the
# python/egg/metadata screen that lintian applies to every Python package, so check the output.)
rc=0
lintian --pedantic --display-info --display-experimental --fail-on error,warning,pedantic \
  ../*.changes >"$OUT/lintian.txt" 2>&1 || rc=$?
cat "$OUT/lintian.txt"
if [ "$rc" -ne 0 ] || grep -q '^[EWIPX]: ' "$OUT/lintian.txt"; then
  echo "lintian: not clean (exit $rc)" >&2; exit 1
fi
echo "lintian: clean (pedantic, info, experimental)"
