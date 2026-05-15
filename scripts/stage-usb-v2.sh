#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-/tmp/proxy-gateway-v2-usb-stage}"
USB_ROOT="${TARGET}/PROXY_GATEWAY"
APP_DIR="${USB_ROOT}/app/proxy-gateway-console"
PROFILE_DIR="${USB_ROOT}/profile"

case "${TARGET}" in
  /|/home|"${HOME}"|"${ROOT_DIR}")
    echo "refusing unsafe target: ${TARGET}" >&2
    exit 2
    ;;
esac

mkdir -p "${PROFILE_DIR}" "${USB_ROOT}/runtime" "${USB_ROOT}/state" "${USB_ROOT}/logs" "${USB_ROOT}/recovery"
mkdir -p "${USB_ROOT}/app"
rm -rf "${APP_DIR}"
mkdir -p "${APP_DIR}"

python3 "${ROOT_DIR}/agent/gateway_agent.py" usb-manifest-template > "${USB_ROOT}/manifest.json"
python3 -c 'import json,sys,uuid; path=sys.argv[1]; data=json.load(open(path, encoding="utf-8")); data["marker"]=uuid.uuid4().hex; open(path, "w", encoding="utf-8").write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")' "${USB_ROOT}/manifest.json"
python3 "${ROOT_DIR}/agent/gateway_agent.py" profile-template > "${PROFILE_DIR}/profile.template.json"

cat > "${PROFILE_DIR}/README.md" <<'EOF'
# Recovery Profile

`profile.template.json` is a non-secret template.

Do not put real proxy passwords, auth strings, private endpoints, SSH keys, cloud keys, or API keys in this directory as plaintext.

USB is an optional recovery/import/export medium for v2. The normal v2 direction is Linux LAN Gateway + Mobile Controller with a locally provisioned encrypted profile.

The recovery unlock path expects `profile/profile.json.enc`, created by an explicit encryption step.

Template encryption command:

```bash
~/.local/bin/gateway-agent profile-encrypt --usb-root /path/to/PROXY_GATEWAY --passphrase-file /path/to/passphrase.txt
```

Validation command:

```bash
~/.local/bin/gateway-agent profile-decrypt-check --usb-root /path/to/PROXY_GATEWAY --passphrase-file /path/to/passphrase.txt
```
EOF

tar \
  --exclude='./node_modules' \
  --exclude='./dist' \
  --exclude='./.git' \
  --exclude='./.env' \
  --exclude='./.env.*' \
  --exclude='./coverage' \
  --exclude='./*.tsbuildinfo' \
  --exclude='./agent/tests' \
  --exclude='./server/*.test.mjs' \
  --exclude='./agent/__pycache__' \
  --exclude='./agent/tests/__pycache__' \
  --exclude='./*.log' \
  --exclude='./*.tmp' \
  -C "${ROOT_DIR}" \
  -cf - . | tar -C "${APP_DIR}" -xf -

test -f "${APP_DIR}/LICENSE"
test -f "${APP_DIR}/docs/THIRD_PARTY_NOTICES.md"

find "${USB_ROOT}" -maxdepth 3 -printf '%y %s %p\n'
