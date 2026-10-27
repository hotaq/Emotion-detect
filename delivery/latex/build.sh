#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p ../pdf
for document in report user-manual system-manual; do
  tectonic --keep-logs --outdir ../pdf "$document.tex"
done
