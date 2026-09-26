#!/bin/sh
# Create .venv and install Django. Works even on systems with no pip/ensurepip
# (Ubuntu without python3-venv) by bootstrapping pip from the official zipapp.
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv 2>/dev/null || python3 -m venv --without-pip .venv
fi
if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
    [ -f .venv/pip.pyz ] || curl -sSL -o .venv/pip.pyz https://bootstrap.pypa.io/pip/pip.pyz
    .venv/bin/python .venv/pip.pyz install -q -r requirements.txt
else
    .venv/bin/python -m pip install -q -r requirements.txt
fi
.venv/bin/python -c "import django; print('django', django.get_version(), 'ready')"
echo "run ./orm"
