#!/bin/sh
if [ ! -d "docs" ]; then
    mkdir docs
fi

if [ -f "CHANGELOG.md" ]; then
    cp CHANGELOG.md docs/
fi

if [ -f "CONTRIBUTING.md" ]; then
    cp CONTRIBUTING.md docs/
fi

if [ -f "LICENSE" ]; then
    cp LICENSE docs/LICENSE.md
fi
