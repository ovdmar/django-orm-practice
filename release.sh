#!/bin/sh
# ./release.sh v1.0.1   - build the tarball install.sh downloads, and publish it
#
# The tarball is what users get, so it carries only tracked files plus a VERSION
# stamp. No git is needed to install it, only curl and tar.
set -eu
cd "$(dirname "$0")"

TAG="${1:?usage: ./release.sh vX.Y.Z}"
NAME=django-orm-practice
OUT="$NAME.tar.gz"

test -z "$(git status --porcelain)" || { echo "working tree is dirty"; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
git archive --format=tar --prefix="$NAME/" HEAD > "$tmp/archive.tar"
echo "$TAG" > "$tmp/VERSION"
tar --append --file="$tmp/archive.tar" --transform="s|^VERSION|$NAME/VERSION|" \
    -C "$tmp" VERSION
gzip -c "$tmp/archive.tar" > "$OUT"
echo "built $OUT ($(du -h "$OUT" | cut -f1), $(tar -tzf "$OUT" | wc -l) entries)"

git tag -f "$TAG"
git push -q origin "$TAG"
gh release create "$TAG" "$OUT" --title "$TAG" \
    --notes "Install or update:

\`\`\`sh
curl -fsSL https://raw.githubusercontent.com/ovdmar/$NAME/main/install.sh | sh
\`\`\`

Needs curl, tar and python3. No git, no sudo."
rm -f "$OUT"
echo "published $TAG"
