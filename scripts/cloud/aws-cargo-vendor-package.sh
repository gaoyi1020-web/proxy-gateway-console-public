#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODE="${1:---dry-run}"
REGION="${AWS_REGION:-$(aws configure get region 2>/dev/null || true)}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.micro}"
NAME_PREFIX="${NAME_PREFIX:-proxy-gateway-cargo-vendor}"
PACKAGE_PATH="${PACKAGE_PATH:-/tmp/proxy-gateway-cargo-vendor-source.tar.gz}"
OUT="${OUT:-/tmp/proxy-gateway-desktop-cargo-vendor.tar.gz}"
KEEP_INSTANCE="${KEEP_INSTANCE:-0}"
REMOTE_USER="${REMOTE_USER:-ubuntu}"
REMOTE_PROJECT_DIR="/home/${REMOTE_USER}/proxy-gateway-console"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
KEY_NAME="${NAME_PREFIX}-${TIMESTAMP}"
KEY_PATH="/tmp/${KEY_NAME}.pem"
SECURITY_GROUP_ID=""
INSTANCE_ID=""

usage() {
  cat <<EOF
usage: $0 [--dry-run|--apply]

Environment overrides:
  AWS_REGION       Default: aws configure get region
  INSTANCE_TYPE    Default: t3.micro
  OUT              Default: /tmp/proxy-gateway-desktop-cargo-vendor.tar.gz
  KEEP_INSTANCE    Default: 0. Set 1 to skip automatic termination.
EOF
}

log() {
  printf '\n==> %s\n' "$*"
}

aws_text() {
  aws "$@" --output text
}

ssh_target() {
  printf '%s@%s' "${REMOTE_USER}" "$1"
}

ssh_common_args() {
  printf '%s\n' \
    -i "${KEY_PATH}" \
    -o StrictHostKeyChecking=accept-new \
    -o ConnectTimeout=10 \
    -o ServerAliveInterval=15
}

wait_for_ssh() {
  local public_dns="$1"
  local attempt
  for attempt in $(seq 1 30); do
    if ssh $(ssh_common_args) "$(ssh_target "${public_dns}")" "true" >/dev/null 2>&1; then
      return 0
    fi
    log "Waiting for SSH on ${public_dns} (${attempt}/30)"
    sleep 10
  done
  echo "SSH did not become reachable on ${public_dns}" >&2
  return 1
}

cleanup() {
  local exit_code=$?
  if [[ "${MODE}" == "--apply" && "${KEEP_INSTANCE}" != "1" ]]; then
    if [[ -n "${INSTANCE_ID}" ]]; then
      log "Terminating instance ${INSTANCE_ID}"
      aws ec2 terminate-instances --region "${REGION}" --instance-ids "${INSTANCE_ID}" >/dev/null || true
      aws ec2 wait instance-terminated --region "${REGION}" --instance-ids "${INSTANCE_ID}" || true
    fi
    if [[ -n "${SECURITY_GROUP_ID}" ]]; then
      log "Deleting security group ${SECURITY_GROUP_ID}"
      aws ec2 delete-security-group --region "${REGION}" --group-id "${SECURITY_GROUP_ID}" >/dev/null || true
    fi
    aws ec2 delete-key-pair --region "${REGION}" --key-name "${KEY_NAME}" >/dev/null 2>&1 || true
    rm -f "${KEY_PATH}"
  else
    log "Cleanup skipped or dry-run"
  fi
  exit "${exit_code}"
}

require_apply_or_report() {
  if [[ "${MODE}" == "--dry-run" ]]; then
    log "Dry-run only"
    printf 'Region: %s\n' "${REGION:-unset}"
    printf 'Instance type: %s\n' "${INSTANCE_TYPE}"
    printf 'Output path: %s\n' "${OUT}"
    printf 'Would create one SSH-only EC2 instance, package Cargo vendor deps, download the tarball, and terminate it.\n'
    exit 0
  fi
  if [[ "${MODE}" != "--apply" ]]; then
    usage >&2
    exit 2
  fi
}

remote_vendor_command() {
  cat <<'EOF'
set -euo pipefail
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl build-essential tar
export RUSTUP_DIST_SERVER="${RUSTUP_DIST_SERVER:-https://static.rust-lang.org}"
export RUSTUP_UPDATE_ROOT="${RUSTUP_UPDATE_ROOT:-https://static.rust-lang.org/rustup}"
curl --fail --location --show-error --retry 5 --retry-all-errors --connect-timeout 20 --max-time 600 "${RUSTUP_UPDATE_ROOT}/dist/x86_64-unknown-linux-gnu/rustup-init" -o /tmp/rustup-init
chmod +x /tmp/rustup-init
/tmp/rustup-init -y --profile minimal --default-toolchain stable
. "${HOME}/.cargo/env"
cd "${HOME}/proxy-gateway-console"
scripts/desktop/package-cargo-vendor.sh /tmp/proxy-gateway-desktop-cargo-vendor.tar.gz
tar -tzf /tmp/proxy-gateway-desktop-cargo-vendor.tar.gz >/dev/null
EOF
}

main() {
  require_apply_or_report
  if [[ -z "${REGION}" ]]; then
    echo "AWS region is required; set AWS_REGION or aws configure region" >&2
    exit 2
  fi
  trap cleanup EXIT

  log "Packaging project source"
  "${ROOT_DIR}/scripts/cloud/package-v2-for-aws.sh" "${PACKAGE_PATH}" >/dev/null

  log "Resolving AWS network"
  local public_ip vpc_id subnet_id ami_id
  public_ip="$(curl --noproxy '*' -fsSL https://checkip.amazonaws.com | tr -d '[:space:]')"
  vpc_id="$(aws_text ec2 describe-vpcs --region "${REGION}" --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId')"
  subnet_id="$(aws_text ec2 describe-subnets --region "${REGION}" --filters "Name=vpc-id,Values=${vpc_id}" "Name=default-for-az,Values=true" --query 'Subnets[0].SubnetId')"
  ami_id="$(aws_text ssm get-parameter --region "${REGION}" --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id --query 'Parameter.Value')"

  log "Creating temporary key pair and security group"
  aws ec2 create-key-pair --region "${REGION}" --key-name "${KEY_NAME}" --query KeyMaterial --output text > "${KEY_PATH}"
  chmod 0600 "${KEY_PATH}"
  SECURITY_GROUP_ID="$(aws_text ec2 create-security-group --region "${REGION}" --group-name "${KEY_NAME}" --description "Temporary Cargo vendor packaging" --vpc-id "${vpc_id}" --query GroupId)"
  aws ec2 authorize-security-group-ingress \
    --region "${REGION}" \
    --group-id "${SECURITY_GROUP_ID}" \
    --ip-permissions "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=${public_ip}/32,Description=temporary-ssh-only}]" >/dev/null

  log "Launching temporary instance"
  INSTANCE_ID="$(aws_text ec2 run-instances \
    --region "${REGION}" \
    --image-id "${ami_id}" \
    --instance-type "${INSTANCE_TYPE}" \
    --key-name "${KEY_NAME}" \
    --subnet-id "${subnet_id}" \
    --security-group-ids "${SECURITY_GROUP_ID}" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${KEY_NAME}},{Key=Project,Value=proxy-gateway-v2},{Key=Purpose,Value=cargo-vendor-package}]" \
    --query 'Instances[0].InstanceId')"
  aws ec2 wait instance-status-ok --region "${REGION}" --instance-ids "${INSTANCE_ID}"

  local public_dns
  public_dns="$(aws_text ec2 describe-instances --region "${REGION}" --instance-ids "${INSTANCE_ID}" --query 'Reservations[0].Instances[0].PublicDnsName')"

  log "Uploading source to ${public_dns}"
  wait_for_ssh "${public_dns}"
  ssh $(ssh_common_args) "$(ssh_target "${public_dns}")" "mkdir -p '${REMOTE_PROJECT_DIR}'"
  scp -i "${KEY_PATH}" -o StrictHostKeyChecking=accept-new "${PACKAGE_PATH}" "$(ssh_target "${public_dns}"):/tmp/proxy-gateway-vendor-source.tar.gz"
  ssh $(ssh_common_args) "$(ssh_target "${public_dns}")" "tar -xzf /tmp/proxy-gateway-vendor-source.tar.gz -C '${REMOTE_PROJECT_DIR}'"

  log "Packaging Cargo vendor dependencies"
  ssh $(ssh_common_args) "$(ssh_target "${public_dns}")" "$(remote_vendor_command)"

  log "Downloading vendor package to ${OUT}"
  mkdir -p "$(dirname "${OUT}")"
  scp -i "${KEY_PATH}" -o StrictHostKeyChecking=accept-new "$(ssh_target "${public_dns}"):/tmp/proxy-gateway-desktop-cargo-vendor.tar.gz" "${OUT}"
  tar -tzf "${OUT}" >/dev/null
  du -h "${OUT}"
}

main "$@"
