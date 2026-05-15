#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEMPLATE="${ROOT_DIR}/config/profile.template.json"

cd "${ROOT_DIR}"
python3 - "${TEMPLATE}" <<'PY'
import json
import sys

from agent.profile_schema import validate_profile

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as handle:
    profile = json.load(handle)

validate_profile(profile)
print("profile template validation: pass")
PY
