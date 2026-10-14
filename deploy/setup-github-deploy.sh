#!/usr/bin/env bash
# Thiết lập một lần: cho GitHub Actions (repo hungdt31/ai-meme-agent, nhánh main) deploy backend lên Cloud Run.
# Dùng Workload Identity Federation: GitHub chứng minh danh tính bằng token OIDC, không cần file key JSON.
# Chạy lại được: bước nào đã có thì bỏ qua.
set -euo pipefail

PROJECT_ID=ai-agent-511607
PROJECT_NUMBER=752511020254
GITHUB_REPO=hungdt31/ai-meme-agent
POOL=github
PROVIDER=ai-meme-agent
DEPLOYER=github-deployer
DEPLOYER_SA="${DEPLOYER}@${PROJECT_ID}.iam.gserviceaccount.com"
# Service account mà Cloud Run và Cloud Build đang dùng (mặc định của Compute Engine)
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud config set project "$PROJECT_ID" >/dev/null

echo "1/5 Bật các API cần cho đăng nhập bằng OIDC"
gcloud services enable iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com

echo "2/5 Tạo service account dùng để deploy: $DEPLOYER_SA"
gcloud iam service-accounts describe "$DEPLOYER_SA" >/dev/null 2>&1 ||
  gcloud iam service-accounts create "$DEPLOYER" --display-name="GitHub Actions deploy Cloud Run"

echo "3/5 Cấp quyền tối thiểu để deploy từ source"
# Upload source, chạy Cloud Build, tạo revision Cloud Run mới
gcloud projects add-iam-policy-binding "$PROJECT_ID" --condition=None --quiet \
  --member="serviceAccount:$DEPLOYER_SA" --role=roles/run.sourceDeveloper >/dev/null
# Được gọi API trong project
gcloud projects add-iam-policy-binding "$PROJECT_ID" --condition=None --quiet \
  --member="serviceAccount:$DEPLOYER_SA" --role=roles/serviceusage.serviceUsageConsumer >/dev/null
# Được giao việc cho service account runtime (chỉ trên đúng account đó, không phải toàn project)
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" --quiet \
  --member="serviceAccount:$DEPLOYER_SA" --role=roles/iam.serviceAccountUser >/dev/null

echo "4/5 Tạo Workload Identity Pool và provider cho GitHub"
gcloud iam workload-identity-pools describe "$POOL" --location=global >/dev/null 2>&1 ||
  gcloud iam workload-identity-pools create "$POOL" --location=global --display-name="GitHub Actions"
gcloud iam workload-identity-pools providers describe "$PROVIDER" --location=global \
  --workload-identity-pool="$POOL" >/dev/null 2>&1 ||
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" \
    --location=global --workload-identity-pool="$POOL" --display-name="ai-meme-agent (main)" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository == '${GITHUB_REPO}' && assertion.ref == 'refs/heads/main'"

echo "5/5 Cho phép đúng repo này mượn service account deploy"
gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" --quiet \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${GITHUB_REPO}" \
  >/dev/null

echo
echo "Xong. Giá trị dùng trong .github/workflows/ci.yml:"
echo "  workload_identity_provider: projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
echo "  service_account:            ${DEPLOYER_SA}"
