#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MACVPN_DIR="${ROOT_DIR}/scripts/macvpn"

bash -n "${MACVPN_DIR}/install-macvpn-kit.sh"
bash -n "${MACVPN_DIR}/install-macvpn-rootctl.sh"
bash -n "${MACVPN_DIR}/macvpnctl.sh"
bash -n "${MACVPN_DIR}/verify-mac-self-use-package-sandbox.sh"
bash -n "${MACVPN_DIR}/run-mac-self-use-package-direct.sh"
python3 -m json.tool "${MACVPN_DIR}/sing-box.tun.template.json" >/dev/null

python3 - "${MACVPN_DIR}" <<'PY'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
sensitive_key_re = re.compile(r'"(password|auth|token|uuid|server|server_port|username)"\s*:\s*("[^"]+"|[^,\]}]+)')
placeholder_re = re.compile(r'^"__(?:[A-Z0-9_]+)__"$|^"<redacted>"$|^"\$\{?[A-Z0-9_]+\}?"$')
allow_context_re = re.compile(r"redact|scrub|allow|placeholder|template", re.IGNORECASE)
failures = []

for path in sorted(root.glob("*")):
    if not path.is_file():
        continue
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for match in sensitive_key_re.finditer(line):
            value = match.group(2).strip()
            if placeholder_re.match(value) or allow_context_re.search(line):
                continue
            failures.append(f"{path.relative_to(root.parent.parent)}:{number}: secret-looking literal for {match.group(1)}")

if failures:
    print("macvpn kit verification: fail", file=sys.stderr)
    for failure in failures:
        print(failure, file=sys.stderr)
    sys.exit(1)
PY

printf 'macvpn kit verification: pass\n'
