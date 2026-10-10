#!/bin/sh
cd "$(dirname "$0")" || exit 1
nohup python3 pet.py >/dev/null 2>&1 &
