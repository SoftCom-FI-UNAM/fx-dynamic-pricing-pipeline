#!/usr/bin/env bash
# Empaqueta cada Lambda de src/<nombre>/ en dist/<nombre>.zip (handler.py en la raíz del zip).
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf dist && mkdir dist
for d in src/*/; do
  n=$(basename "$d")
  python3 -I - "$d" "dist/$n.zip" <<'PY'
import sys, zipfile, pathlib
src, out = pathlib.Path(sys.argv[1]), sys.argv[2]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(src.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
            z.write(p, p.relative_to(src))
PY
  echo "dist/$n.zip"
done
