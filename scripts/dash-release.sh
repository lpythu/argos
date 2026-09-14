#!/usr/bin/env bash
# buildof: docker build/push Harbor, helm office. Invoked by release.yml.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REGISTRY="${REGISTRY:-harbor.saidc}"
IMAGE="${IMAGE:-platform/argos}"
TAG="${TAG:-${GITHUB_REF_NAME:?set TAG or GITHUB_REF_NAME}}"
HELM_HOST="${HELM_HOST:-office}"
FULL_IMAGE="${REGISTRY}/${IMAGE}:${TAG}"

if [[ ! "$TAG" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "error: TAG must be X.Y.Z (got ${TAG})" >&2
  exit 1
fi

secret=""
for secret in \
  /home/saidc/.harbor/robot-saidc.secret \
  "${HOME}/.harbor/robot-saidc.secret" \
  /root/.harbor/robot-saidc.secret; do
  if [[ -f "$secret" ]]; then
    docker login "$REGISTRY" -u 'robot$saidc' --password-stdin <"$secret" >/dev/null
    break
  fi
  secret=""
done
if [[ -z "$secret" ]]; then
  echo "error: missing Harbor robot secret" >&2
  exit 1
fi

echo "==> build ${FULL_IMAGE}"
docker buildx build \
  --builder "${BUILDX_BUILDER:-default}" \
  --pull \
  --provenance=false \
  --network="${DOCKER_BUILD_NETWORK:-host}" \
  --build-arg "NODE_IMAGE=${REGISTRY}/base/saidc-node:22-pnpm11.12.0" \
  --build-arg "BASE_IMAGE=${REGISTRY}/base/saidc-uv:0.12.0" \
  -t "${FULL_IMAGE}" \
  --load \
  .

echo "==> push ${FULL_IMAGE}"
docker push "${FULL_IMAGE}"

echo "==> helm argos office tag=${TAG}"
remote="$(ssh -o BatchMode=yes "${HELM_HOST}" mktemp -d)"
tar -C "$ROOT" -cf - chart | ssh -o BatchMode=yes "${HELM_HOST}" "tar -C '${remote}' -xf -"
ssh -o BatchMode=yes "${HELM_HOST}" \
  "helm upgrade --install argos '${remote}/chart' \
    -n platform --create-namespace \
    -f '${remote}/chart/values.yaml' \
    -f '${remote}/chart/values-office.yaml' \
    --set 'image.repository=${REGISTRY}/${IMAGE}' \
    --set 'image.tag=${TAG}' \
    --take-ownership --wait --timeout 5m"
echo "OK dash ${FULL_IMAGE}"
