#!/usr/bin/env bash
# Bump argospy semver and create an annotated tag X.Y.Z (no v). Does not publish.
# Usage: ./scripts/release.sh 0.6.1
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <version>" >&2
  echo "Example: $0 0.6.1" >&2
  exit 1
fi

VERSION="$1"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid version: $VERSION (want X.Y.Z)" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean. Commit or stash first." >&2
  exit 1
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "main" ]]; then
  echo "Must be on main (current: $BRANCH)" >&2
  exit 1
fi

if git rev-parse -q --verify "refs/tags/${VERSION}" >/dev/null; then
  echo "Tag ${VERSION} already exists." >&2
  exit 1
fi

python3 - "$VERSION" <<'PY'
import pathlib, re, sys

version = sys.argv[1]
root = pathlib.Path(".")
text = (root / "pyproject.toml").read_text()
new, n = re.subn(r'(?m)^version = "[^"]+"$', f'version = "{version}"', text, count=1)
if n != 1:
    raise SystemExit("Failed to update pyproject.toml")
(root / "pyproject.toml").write_text(new)
print(f"bumped argospy to {version}")
PY

git add pyproject.toml
git commit -m "Release ${VERSION}."
git tag -a "${VERSION}" -m "argos ${VERSION}"
echo "Tagged ${VERSION}. Push with: git push origin main --tags"
