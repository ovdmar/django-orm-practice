#!/bin/sh
# Creates .venv and installs Django into it. Nothing outside this directory is touched.
# Works on systems with no pip and no ensurepip (Ubuntu without python3-venv) by
# bootstrapping pip from the official zipapp.
set -eu
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv >/dev/null 2>&1 \
        || python3 -m venv --without-pip .venv >/dev/null 2>&1 \
        || true
fi
if [ ! -x .venv/bin/python ]; then
    echo "could not create a virtualenv - is python3 installed?" >&2
    exit 1
fi

if .venv/bin/python -m pip --version >/dev/null 2>&1; then
    .venv/bin/python -m pip install -q -r requirements.txt
else
    [ -f .venv/pip.pyz ] || curl -fsSL -o .venv/pip.pyz https://bootstrap.pypa.io/pip/pip.pyz
    .venv/bin/python .venv/pip.pyz install -q -r requirements.txt
fi

.venv/bin/python -c "import django; print('django', django.get_version() + ' ready')"
