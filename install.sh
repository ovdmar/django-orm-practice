#!/bin/sh
# curl -fsSL https://raw.githubusercontent.com/ovdmar/django-orm-practice/main/install.sh | sh
#
# Downloads the latest release, installs Django into a virtualenv of its own, and puts
# an `orm` command on your PATH. Needs curl, tar and python3 - no git, no sudo.
# Re-run it any time to update; your progress lives elsewhere and is left alone.
set -eu

URL="${ORM_URL:-https://github.com/ovdmar/django-orm-practice/releases/latest/download/django-orm-practice.tar.gz}"
DIR="${ORM_DIR:-$HOME/.local/share/django-orm-practice}"
BIN="${ORM_BIN:-$HOME/.local/bin}"

for tool in curl tar python3; do
    command -v "$tool" >/dev/null 2>&1 || { echo "$tool is required" >&2; exit 1; }
done

echo "downloading into $DIR"
mkdir -p "$DIR"
curl -fsSL "$URL" | tar -xzf - --strip-components=1 -C "$DIR"

sh "$DIR/setup.sh"

mkdir -p "$BIN"
ln -sf "$DIR/orm" "$BIN/orm"

version="$(cat "$DIR/VERSION" 2>/dev/null || echo "")"
echo
case ":${PATH}:" in
    *":$BIN:"*) echo "${version:+$version }ready - run:  orm" ;;
    *) echo "${version:+$version }ready - run:  $BIN/orm"
       echo "(add $BIN to your PATH and it is just 'orm')" ;;
esac
