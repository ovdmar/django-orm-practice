#!/bin/sh
# curl -fsSL https://raw.githubusercontent.com/ovdmar/django-orm-practice/main/install.sh | sh
#
# Clones (or updates) the drill, installs Django into a virtualenv of its own, and
# puts an `orm` command on your PATH. Re-run it any time to update.
set -eu

REPO="${ORM_REPO:-https://github.com/ovdmar/django-orm-practice.git}"
DIR="${ORM_DIR:-$HOME/.local/share/django-orm-practice}"
BIN="${ORM_BIN:-$HOME/.local/bin}"

for tool in git python3 curl; do
    command -v "$tool" >/dev/null 2>&1 || { echo "$tool is required"; exit 1; }
done

if [ -d "$DIR/.git" ]; then
    echo "updating $DIR"
    git -C "$DIR" pull --ff-only --quiet
else
    echo "cloning into $DIR"
    mkdir -p "$(dirname "$DIR")"
    git clone --quiet --depth 1 "$REPO" "$DIR"
fi

sh "$DIR/setup.sh"

mkdir -p "$BIN"
ln -sf "$DIR/orm" "$BIN/orm"

echo
case ":${PATH}:" in
    *":$BIN:"*) echo "ready - run:  orm" ;;
    *) echo "ready - run:  $BIN/orm"
       echo "(add $BIN to your PATH and it is just 'orm')" ;;
esac
