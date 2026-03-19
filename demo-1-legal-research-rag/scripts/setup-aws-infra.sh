#!/usr/bin/env bash
#
# setup-aws-infra.sh — Provision AWS infrastructure for Demo 1: Legal Research RAG Pipeline
#
# Phase 1: OpenSearch Serverless + DynamoDB + S3 + IAM
# Phase 2: Lambda document processor + S3 event trigger + end-to-end pipeline run
#
# Idempotent: safe to run multiple times. Checks existence before creating each resource.
#
# Usage:
#   ./setup-aws-infra.sh              # Create all resources and run pipeline
#   ./setup-aws-infra.sh --dry-run    # Show what would be created
#   ./setup-aws-infra.sh --cleanup    # Tear down all resources
#   ./setup-aws-infra.sh --help       # Show this help
#
set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_FILE="${SCRIPT_DIR}/setup.log"

# AWS
AWS_REGION="${AWS_REGION:-us-west-2}"
AWS_PROFILE="${AWS_PROFILE:-001}"
export AWS_PROFILE
AWS_ACCOUNT_ID=""  # Populated at runtime via STS

# S3
BUCKET_NAME="demo-1-legal-research-rag-pdx"

# OpenSearch Serverless
AOSS_COLLECTION_NAME="legal-research-vectors"
AOSS_INDEX_NAME="legal-documents"

# DynamoDB
DYNAMODB_TABLE_NAME="LegalDocMetadata"

# Lambda
LAMBDA_FUNCTION_NAME="legal-doc-processor"
LAMBDA_ROLE_NAME="LambdaRole-LegalDocProcessor"
LAMBDA_RUNTIME="python3.13"
LAMBDA_HANDLER="document_processor.lambda_handler"
LAMBDA_MEMORY=512
LAMBDA_TIMEOUT=300

# Bedrock (for neural ingest pipeline — ML connector, not Lambda)
EMBEDDING_MODEL_ID="amazon.titan-embed-text-v2:0"
NEURAL_PIPELINE_NAME="neural-ingest-pipeline"
HYBRID_PIPELINE_NAME="hybrid-search-pipeline"

# Tags
TAG_PROJECT="aip-c01-demos"
TAG_DEMO="legal-research-rag"

# Runtime flags
DRY_RUN=false
CLEANUP=false

# Counters
CREATED=0
SKIPPED=0
ERRORS=0
DELETED=0

# ═══════════════════════════════════════════════════════════════════════════════
# COLOR & LOGGING UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()      { local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"; echo "${msg}" >> "${LOG_FILE}"; }
info()     { echo -e "${BLUE}ℹ${NC}  $*"; log "INFO  $*"; }
success()  { echo -e "${GREEN}✅${NC} $*"; log "OK    $*"; }
skip()     { echo -e "${YELLOW}⏭${NC}  $*"; log "SKIP  $*"; }
warn()     { echo -e "${YELLOW}⚠️${NC}  $*"; log "WARN  $*"; }
error()    { echo -e "${RED}❌${NC} $*" >&2; log "ERROR $*"; }
step()     { echo -e "\n${BOLD}${CYAN}── Step $1: $2${NC}"; log "STEP  $1 — $2"; }
header()   { echo -e "\n${BOLD}════════════════════════════════════════════════════════════${NC}"; echo -e "${BOLD}  $*${NC}"; echo -e "${BOLD}════════════════════════════════════════════════════════════${NC}\n"; }
dryrun()   { echo -e "  ${YELLOW}[DRY-RUN]${NC} Would: $*"; log "DRYRUN $*"; }

# Error trap
trap 'error "Script failed at line ${LINENO} (exit code $?)"; exit 1' ERR

# ═══════════════════════════════════════════════════════════════════════════════
# USAGE
# ═══════════════════════════════════════════════════════════════════════════════
usage() {
    cat <<EOF
${BOLD}Usage:${NC} $(basename "$0") [OPTIONS]

Provision AWS infrastructure for Demo 1: Legal Research RAG Pipeline.

${BOLD}Options:${NC}
  --dry-run    Show what would be created without executing any AWS commands
  --cleanup    Tear down all resources in reverse order
  --help       Show this help message

${BOLD}Phase 1 Resources:${NC}
  • S3 bucket:                  ${BUCKET_NAME}
  • OpenSearch Serverless:      ${AOSS_COLLECTION_NAME}
  • DynamoDB table:             ${DYNAMODB_TABLE_NAME}
  • IAM role (Lambda):          ${LAMBDA_ROLE_NAME}

${BOLD}Phase 2 Resources:${NC}
  • Lambda function:            ${LAMBDA_FUNCTION_NAME}
  • S3 event notification:      triggers Lambda on raw-docs/ uploads

${BOLD}Region:${NC} ${AWS_REGION}
${BOLD}Profile:${NC} ${AWS_PROFILE}
${BOLD}Log file:${NC} ${LOG_FILE}
EOF
    exit 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# PARSE ARGUMENTS
# ═══════════════════════════════════════════════════════════════════════════════
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)  DRY_RUN=true; shift ;;
        --cleanup)  CLEANUP=true; shift ;;
        --help|-h)  usage ;;
        *)          error "Unknown option: $1"; usage ;;
    esac
done

# ═══════════════════════════════════════════════════════════════════════════════
# PREREQUISITES CHECK
# ═══════════════════════════════════════════════════════════════════════════════
check_prerequisites() {
    header "Prerequisites Check"

    if ! command -v aws &>/dev/null; then
        error "AWS CLI not found. Install: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"
        exit 1
    fi
    success "AWS CLI installed: $(aws --version 2>&1)"

    if ! command -v python3 &>/dev/null; then
        error "python3 not found."
        exit 1
    fi
    success "Python3 installed: $(python3 --version 2>&1)"

    if ! command -v zip &>/dev/null; then
        error "zip not found. Required for Lambda packaging."
        exit 1
    fi
    success "zip installed"

    if command -v jq &>/dev/null; then
        success "jq installed: $(jq --version 2>&1)"
    else
        warn "jq not found — JSON parsing will use aws --query instead"
    fi

    info "Validating AWS credentials..."
    local sts_output
    if ! sts_output="$(aws sts get-caller-identity --region "${AWS_REGION}" --output json --no-cli-pager 2>&1)"; then
        error "AWS credentials not configured or expired."
        exit 1
    fi
    AWS_ACCOUNT_ID="$(echo "${sts_output}" | python3 -c "import sys,json; print(json.load(sys.stdin)['Account'])")"
    local caller_arn
    caller_arn="$(echo "${sts_output}" | python3 -c "import sys,json; print(json.load(sys.stdin)['Arn'])")"
    success "AWS credentials valid — Account: ${AWS_ACCOUNT_ID}"
    info "Caller: ${caller_arn}"
    info "Region: ${AWS_REGION}"
}


# ═══════════════════════════════════════════════════════════════════════════════
# SYNTHETIC DATA GENERATION
# ═══════════════════════════════════════════════════════════════════════════════
ensure_synth_data() {
    local data_dir="${DEMO_DIR}/synth_data/output"
    local manifest="${data_dir}/manifest.json"

    if [[ -f "${manifest}" ]]; then
        local doc_count
        doc_count="$(python3 -c "import json; print(len(json.load(open('${manifest}'))))")"
        success "Synthetic data already exists (${doc_count} documents)"
        return 0
    fi

    info "Synthetic data not found — generating..."
    if ${DRY_RUN}; then
        dryrun "python3 ${DEMO_DIR}/synth_data/generate_legal_docs.py"
        return 0
    fi

    (cd "${DEMO_DIR}" && python3 synth_data/generate_legal_docs.py)
    success "Synthetic data generated"
}

ensure_lambda_outputs() {
    local output_dir="${DEMO_DIR}/lambda_processing/output"
    local results="${output_dir}/processing_results.json"

    if [[ -f "${results}" ]]; then
        success "Lambda processing outputs already exist"
        return 0
    fi

    info "Lambda processing outputs not found — generating locally..."
    if ${DRY_RUN}; then
        dryrun "python3 ${DEMO_DIR}/lambda_processing/document_processor.py"
        return 0
    fi

    (cd "${DEMO_DIR}" && python3 lambda_processing/document_processor.py)
    success "Lambda processing outputs generated (local mode)"
}

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1, STEP 1: S3 BUCKET
# ═══════════════════════════════════════════════════════════════════════════════
create_s3_bucket() {
    step "1" "S3 Bucket — ${BUCKET_NAME}"

    if ${DRY_RUN}; then
        dryrun "Create S3 bucket s3://${BUCKET_NAME} in ${AWS_REGION}"
        return 0
    fi

    if aws s3api head-bucket --bucket "${BUCKET_NAME}" --region "${AWS_REGION}" 2>/dev/null; then
        skip "Bucket ${BUCKET_NAME} already exists"
        ((SKIPPED++)) || true
    else
        info "Creating bucket ${BUCKET_NAME}..."
        if [[ "${AWS_REGION}" == "us-east-1" ]]; then
            aws s3api create-bucket \
                --bucket "${BUCKET_NAME}" \
                --region "${AWS_REGION}" \
                --no-cli-pager
        else
            aws s3api create-bucket \
                --bucket "${BUCKET_NAME}" \
                --region "${AWS_REGION}" \
                --create-bucket-configuration "LocationConstraint=${AWS_REGION}" \
                --no-cli-pager
        fi

        aws s3api put-public-access-block \
            --bucket "${BUCKET_NAME}" \
            --public-access-block-configuration \
            "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
            --region "${AWS_REGION}" \
            --no-cli-pager

        aws s3api put-bucket-tagging \
            --bucket "${BUCKET_NAME}" \
            --tagging "TagSet=[{Key=Project,Value=${TAG_PROJECT}},{Key=Demo,Value=${TAG_DEMO}}]" \
            --region "${AWS_REGION}" \
            --no-cli-pager

        success "Bucket ${BUCKET_NAME} created"
        ((CREATED++)) || true
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1, STEP 2: UPLOAD DOCUMENTS TO S3
# ═══════════════════════════════════════════════════════════════════════════════
upload_documents() {
    step "2" "Upload legal documents to S3"

    local data_dir="${DEMO_DIR}/synth_data/output"

    if ${DRY_RUN}; then
        dryrun "Upload 30 legal documents to s3://${BUCKET_NAME}/raw-docs/"
        dryrun "Upload manifest.json to s3://${BUCKET_NAME}/metadata/"
        return 0
    fi

    info "Uploading documents to s3://${BUCKET_NAME}/raw-docs/..."
    local count=0
    for f in "${data_dir}"/*.txt; do
        local filename
        filename="$(basename "${f}")"
        aws s3 cp "${f}" "s3://${BUCKET_NAME}/raw-docs/${filename}" \
            --region "${AWS_REGION}" --no-cli-pager --quiet
        ((count++)) || true
    done
    success "Uploaded ${count} documents to raw-docs/"

    info "Uploading manifest..."
    aws s3 cp "${data_dir}/manifest.json" "s3://${BUCKET_NAME}/metadata/manifest.json" \
        --region "${AWS_REGION}" --no-cli-pager --quiet
    success "Uploaded manifest.json to metadata/"

    ((CREATED++)) || true
}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1, STEP 3: OPENSEARCH SERVERLESS COLLECTION
# ═══════════════════════════════════════════════════════════════════════════════
create_opensearch_serverless() {
    step "3" "OpenSearch Serverless Collection — ${AOSS_COLLECTION_NAME}"

    if ${DRY_RUN}; then
        dryrun "Create OpenSearch Serverless encryption policy"
        dryrun "Create OpenSearch Serverless network policy"
        dryrun "Create OpenSearch Serverless data access policy"
        dryrun "Create OpenSearch Serverless collection (type: VECTORSEARCH)"
        return 0
    fi

    # Check if collection already exists
    local existing_id
    existing_id="$(aws opensearchserverless list-collections \
        --region "${AWS_REGION}" \
        --query "collectionSummaries[?name=='${AOSS_COLLECTION_NAME}'].id" \
        --output text \
        --no-cli-pager 2>/dev/null || echo "")"

    if [[ -n "${existing_id}" && "${existing_id}" != "None" ]]; then
        skip "OpenSearch Serverless collection ${AOSS_COLLECTION_NAME} already exists (ID: ${existing_id})"
        ((SKIPPED++)) || true
        return 0
    fi

    # Get caller identity for data access policy
    local caller_arn
    caller_arn="$(aws sts get-caller-identity --region "${AWS_REGION}" --query "Arn" --output text --no-cli-pager)"
    # Normalize assumed-role ARN to role ARN for AOSS policies
    local principal_arn="${caller_arn}"
    if [[ "${caller_arn}" == *":assumed-role/"* ]]; then
        local role_name
        role_name="$(echo "${caller_arn}" | sed 's|.*:assumed-role/\([^/]*\)/.*|\1|')"
        principal_arn="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${role_name}"
    fi

    local lambda_role_arn="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}"

    # ── 3a: Encryption policy ──
    info "Creating encryption policy..."
    local enc_policy_name="legal-research-enc"
    local enc_policy_exists
    enc_policy_exists="$(aws opensearchserverless get-security-policy \
        --name "${enc_policy_name}" --type encryption \
        --region "${AWS_REGION}" \
        --query "securityPolicyDetail.name" \
        --output text \
        --no-cli-pager 2>/dev/null || echo "")"

    if [[ -z "${enc_policy_exists}" || "${enc_policy_exists}" == "None" ]]; then
        aws opensearchserverless create-security-policy \
            --name "${enc_policy_name}" \
            --type encryption \
            --policy "{\"Rules\":[{\"ResourceType\":\"collection\",\"Resource\":[\"collection/${AOSS_COLLECTION_NAME}\"]}],\"AWSOwnedKey\":true}" \
            --region "${AWS_REGION}" \
            --no-cli-pager
        success "Encryption policy created: ${enc_policy_name}"
    else
        skip "Encryption policy ${enc_policy_name} already exists"
    fi

    # ── 3b: Network policy (public access for demo) ──
    info "Creating network policy..."
    local net_policy_name="legal-research-net"
    local net_policy_exists
    net_policy_exists="$(aws opensearchserverless get-security-policy \
        --name "${net_policy_name}" --type network \
        --region "${AWS_REGION}" \
        --query "securityPolicyDetail.name" \
        --output text \
        --no-cli-pager 2>/dev/null || echo "")"

    if [[ -z "${net_policy_exists}" || "${net_policy_exists}" == "None" ]]; then
        aws opensearchserverless create-security-policy \
            --name "${net_policy_name}" \
            --type network \
            --policy "[{\"Rules\":[{\"ResourceType\":\"collection\",\"Resource\":[\"collection/${AOSS_COLLECTION_NAME}\"]},{\"ResourceType\":\"dashboard\",\"Resource\":[\"collection/${AOSS_COLLECTION_NAME}\"]}],\"AllowFromPublic\":true}]" \
            --region "${AWS_REGION}" \
            --no-cli-pager
        success "Network policy created: ${net_policy_name}"
    else
        skip "Network policy ${net_policy_name} already exists"
    fi

    # ── 3c: Data access policy ──
    info "Creating data access policy..."
    local dap_name="legal-research-dap"
    local dap_exists
    dap_exists="$(aws opensearchserverless get-access-policy \
        --name "${dap_name}" --type data \
        --region "${AWS_REGION}" \
        --query "accessPolicyDetail.name" \
        --output text \
        --no-cli-pager 2>/dev/null || echo "")"

    if [[ -z "${dap_exists}" || "${dap_exists}" == "None" ]]; then
        aws opensearchserverless create-access-policy \
            --name "${dap_name}" \
            --type data \
            --policy "[{\"Rules\":[{\"ResourceType\":\"index\",\"Resource\":[\"index/${AOSS_COLLECTION_NAME}/*\"],\"Permission\":[\"aoss:CreateIndex\",\"aoss:UpdateIndex\",\"aoss:DescribeIndex\",\"aoss:ReadDocument\",\"aoss:WriteDocument\"]},{\"ResourceType\":\"collection\",\"Resource\":[\"collection/${AOSS_COLLECTION_NAME}\"],\"Permission\":[\"aoss:CreateCollectionItems\",\"aoss:DescribeCollectionItems\",\"aoss:UpdateCollectionItems\"]}],\"Principal\":[\"${principal_arn}\",\"${lambda_role_arn}\"]}]" \
            --region "${AWS_REGION}" \
            --no-cli-pager
        success "Data access policy created: ${dap_name}"
    else
        skip "Data access policy ${dap_name} already exists"
    fi

    # ── 3d: Create the collection ──
    info "Creating OpenSearch Serverless collection (type: VECTORSEARCH)..."
    aws opensearchserverless create-collection \
        --name "${AOSS_COLLECTION_NAME}" \
        --type VECTORSEARCH \
        --description "Vector store for legal research RAG pipeline — AIP-C01 Demo" \
        --tags "[{\"key\":\"Project\",\"value\":\"${TAG_PROJECT}\"},{\"key\":\"Demo\",\"value\":\"${TAG_DEMO}\"}]" \
        --region "${AWS_REGION}" \
        --no-cli-pager

    success "OpenSearch Serverless collection creation initiated: ${AOSS_COLLECTION_NAME}"
    ((CREATED++)) || true

    # Wait for collection to become ACTIVE
    info "Waiting for collection to become ACTIVE (this may take 2-5 minutes)..."
    local elapsed=0
    local max_wait=600
    local collection_active=false
    while [[ ${elapsed} -lt ${max_wait} ]]; do
        local status
        status="$(aws opensearchserverless list-collections \
            --region "${AWS_REGION}" \
            --query "collectionSummaries[?name=='${AOSS_COLLECTION_NAME}'].status" \
            --output text \
            --no-cli-pager 2>/dev/null || echo "UNKNOWN")"

        if [[ "${status}" == "ACTIVE" ]]; then
            collection_active=true
            break
        fi
        sleep 15
        elapsed=$((elapsed + 15))
        info "  Collection status: ${status} (${elapsed}s elapsed)..."
    done

    if ${collection_active}; then
        local endpoint
        endpoint="$(aws opensearchserverless list-collections \
            --region "${AWS_REGION}" \
            --query "collectionSummaries[?name=='${AOSS_COLLECTION_NAME}'].arn" \
            --output text \
            --no-cli-pager)"
        success "Collection is ACTIVE"
        info "Collection ARN: ${endpoint}"
    else
        warn "Collection did not become ACTIVE within ${max_wait}s — check AWS console"
    fi
}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1, STEP 3b: NEURAL SEARCH SETUP (ML Connector → Model → Pipelines → Index)
# ═══════════════════════════════════════════════════════════════════════════════
setup_neural_search() {
    step "3b" "Neural Search — ML Connector, Model, Pipelines, Index"

    if ${DRY_RUN}; then
        dryrun "Create ML connector to Bedrock Titan Embeddings V2"
        dryrun "Register and deploy ML model"
        dryrun "Create neural ingest pipeline: ${NEURAL_PIPELINE_NAME}"
        dryrun "Create hybrid search pipeline: ${HYBRID_PIPELINE_NAME}"
        dryrun "Create index: ${AOSS_INDEX_NAME} with neural pipeline"
        return 0
    fi

    # Get the AOSS endpoint
    local collection_id
    collection_id="$(aws opensearchserverless list-collections \
        --region "${AWS_REGION}" \
        --query "collectionSummaries[?name=='${AOSS_COLLECTION_NAME}'].id" \
        --output text \
        --no-cli-pager 2>/dev/null || echo "")"

    if [[ -z "${collection_id}" || "${collection_id}" == "None" ]]; then
        error "OpenSearch Serverless collection not found — cannot set up neural search"
        ((ERRORS++)) || true
        return 1
    fi

    local aoss_host="${collection_id}.${AWS_REGION}.aoss.amazonaws.com"

    # Build AWS SigV4 curl helper
    aoss_curl() {
        local method="$1"
        local path="$2"
        local body="${3:-}"

        if [[ -n "${body}" ]]; then
            aws opensearchserverless-query \
                --endpoint-url "https://${aoss_host}" \
                2>/dev/null || true
            # Use Python + requests-aws4auth for AOSS API calls
            python3 -c "
import json, boto3, requests
from requests_aws4auth import AWS4Auth

session = boto3.Session()
creds = session.get_credentials().get_frozen_credentials()
auth = AWS4Auth(creds.access_key, creds.secret_key, '${AWS_REGION}', 'aoss',
                session_token=creds.token)

url = 'https://${aoss_host}${path}'
headers = {'Content-Type': 'application/json'}
resp = requests.request('${method}', url, auth=auth, headers=headers,
                        data=json.dumps(${body}), timeout=30)
print(resp.text)
if resp.status_code >= 400:
    raise SystemExit(f'HTTP {resp.status_code}: {resp.text}')
"
        else
            python3 -c "
import json, boto3, requests
from requests_aws4auth import AWS4Auth

session = boto3.Session()
creds = session.get_credentials().get_frozen_credentials()
auth = AWS4Auth(creds.access_key, creds.secret_key, '${AWS_REGION}', 'aoss',
                session_token=creds.token)

url = 'https://${aoss_host}${path}'
resp = requests.request('${method}', url, auth=auth, timeout=30)
print(resp.text)
if resp.status_code >= 400:
    raise SystemExit(f'HTTP {resp.status_code}: {resp.text}')
"
        fi
    }

    # ── 3b-1: Check if index already exists ──
    info "Checking if index ${AOSS_INDEX_NAME} already exists..."
    local index_exists=false
    if python3 -c "
import boto3, requests
from requests_aws4auth import AWS4Auth
session = boto3.Session()
creds = session.get_credentials().get_frozen_credentials()
auth = AWS4Auth(creds.access_key, creds.secret_key, '${AWS_REGION}', 'aoss', session_token=creds.token)
resp = requests.head('https://${aoss_host}/${AOSS_INDEX_NAME}', auth=auth, timeout=30)
exit(0 if resp.status_code == 200 else 1)
" 2>/dev/null; then
        index_exists=true
        skip "Index ${AOSS_INDEX_NAME} already exists — skipping neural search setup"
        ((SKIPPED++)) || true
        return 0
    fi

    # ── 3b-2: Register ML connector to Bedrock Titan Embeddings V2 ──
    info "Creating ML connector to Bedrock Titan Embeddings V2..."
    local connector_response
    connector_response="$(python3 -c "
import json, boto3, requests
from requests_aws4auth import AWS4Auth

session = boto3.Session()
creds = session.get_credentials().get_frozen_credentials()
auth = AWS4Auth(creds.access_key, creds.secret_key, '${AWS_REGION}', 'aoss', session_token=creds.token)

connector_body = {
    'name': 'Bedrock Titan Embed V2 Connector',
    'description': 'Connector for Amazon Bedrock Titan Embeddings V2 (1024d)',
    'version': '1.0',
    'protocol': 'aws_sigv4',
    'credential': {
        'roleArn': 'arn:aws:iam::${AWS_ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}'
    },
    'parameters': {
        'region': '${AWS_REGION}',
        'service_name': 'bedrock',
        'model': '${EMBEDDING_MODEL_ID}'
    },
    'actions': [{
        'action_type': 'predict',
        'method': 'POST',
        'url': 'https://bedrock-runtime.${AWS_REGION}.amazonaws.com/model/${EMBEDDING_MODEL_ID}/invoke',
        'headers': {'Content-Type': 'application/json'},
        'request_body': '{\"inputText\": \"\${parameters.inputText}\", \"dimensions\": 1024, \"normalize\": true}',
        'pre_process_function': 'connector.pre_process.bedrock.embedding',
        'post_process_function': 'connector.post_process.bedrock.embedding'
    }]
}

resp = requests.post('https://${aoss_host}/_plugins/_ml/connectors/_create',
                     auth=auth, headers={'Content-Type': 'application/json'},
                     data=json.dumps(connector_body), timeout=60)
print(resp.text)
if resp.status_code >= 400:
    raise SystemExit(f'HTTP {resp.status_code}')
" 2>&1)"

    local connector_id
    connector_id="$(echo "${connector_response}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('connector_id',''))" 2>/dev/null || echo "")"

    if [[ -z "${connector_id}" ]]; then
        warn "ML connector creation response: ${connector_response}"
        warn "Skipping neural search setup — connector creation failed"
        warn "You may need to set up neural search manually via the OpenSearch dashboard"
        ((ERRORS++)) || true
        return 0
    fi
    success "ML connector created: ${connector_id}"

    # ── 3b-3: Register and deploy model ──
    info "Registering ML model..."
    local model_response
    model_response="$(python3 -c "
import json, boto3, requests
from requests_aws4auth import AWS4Auth

session = boto3.Session()
creds = session.get_credentials().get_frozen_credentials()
auth = AWS4Auth(creds.access_key, creds.secret_key, '${AWS_REGION}', 'aoss', session_token=creds.token)

model_body = {
    'name': 'Titan Embed V2 1024d',
    'function_name': 'remote',
    'description': 'Bedrock Titan Embeddings V2 via ML connector',
    'connector_id': '${connector_id}'
}

resp = requests.post('https://${aoss_host}/_plugins/_ml/models/_register',
                     auth=auth, headers={'Content-Type': 'application/json'},
                     data=json.dumps(model_body), timeout=60)
result = resp.json()
print(json.dumps(result))
" 2>&1)"

    local model_id
    model_id="$(echo "${model_response}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('model_id',''))" 2>/dev/null || echo "")"

    if [[ -z "${model_id}" ]]; then
        warn "Model registration response: ${model_response}"
        warn "Skipping neural search setup — model registration failed"
        ((ERRORS++)) || true
        return 0
    fi
    success "ML model registered: ${model_id}"

    # Deploy model (AOSS auto-deploys remote models, but call deploy to be safe)
    info "Deploying ML model..."
    python3 -c "
import json, boto3, requests
from requests_aws4auth import AWS4Auth

session = boto3.Session()
creds = session.get_credentials().get_frozen_credentials()
auth = AWS4Auth(creds.access_key, creds.secret_key, '${AWS_REGION}', 'aoss', session_token=creds.token)

resp = requests.post('https://${aoss_host}/_plugins/_ml/models/${model_id}/_deploy',
                     auth=auth, headers={'Content-Type': 'application/json'}, timeout=60)
print(resp.text)
" 2>/dev/null || true
    success "ML model deployed: ${model_id}"

    # Brief pause for model deployment propagation
    sleep 5

    # ── 3b-4: Create neural ingest pipeline ──
    info "Creating neural ingest pipeline: ${NEURAL_PIPELINE_NAME}..."
    python3 -c "
import json, boto3, requests
from requests_aws4auth import AWS4Auth

session = boto3.Session()
creds = session.get_credentials().get_frozen_credentials()
auth = AWS4Auth(creds.access_key, creds.secret_key, '${AWS_REGION}', 'aoss', session_token=creds.token)

pipeline_body = {
    'description': 'Neural ingest pipeline — generates embeddings from content field via Bedrock Titan V2',
    'processors': [{
        'text_embedding': {
            'model_id': '${model_id}',
            'field_map': {
                'content': 'embedding'
            }
        }
    }]
}

resp = requests.put('https://${aoss_host}/_ingest/pipeline/${NEURAL_PIPELINE_NAME}',
                    auth=auth, headers={'Content-Type': 'application/json'},
                    data=json.dumps(pipeline_body), timeout=30)
print(resp.text)
if resp.status_code >= 400:
    raise SystemExit(f'HTTP {resp.status_code}: {resp.text}')
"
    success "Neural ingest pipeline created: ${NEURAL_PIPELINE_NAME}"

    # ── 3b-5: Create hybrid search pipeline ──
    info "Creating hybrid search pipeline: ${HYBRID_PIPELINE_NAME}..."
    python3 -c "
import json, boto3, requests
from requests_aws4auth import AWS4Auth

session = boto3.Session()
creds = session.get_credentials().get_frozen_credentials()
auth = AWS4Auth(creds.access_key, creds.secret_key, '${AWS_REGION}', 'aoss', session_token=creds.token)

pipeline_body = {
    'description': 'Hybrid search pipeline — normalizes and combines semantic + keyword scores (70/30)',
    'phase_results_processors': [{
        'normalization-processor': {
            'normalization': {'technique': 'min_max'},
            'combination': {
                'technique': 'arithmetic_mean',
                'parameters': {'weights': [0.7, 0.3]}
            }
        }
    }]
}

resp = requests.put('https://${aoss_host}/_search/pipeline/${HYBRID_PIPELINE_NAME}',
                    auth=auth, headers={'Content-Type': 'application/json'},
                    data=json.dumps(pipeline_body), timeout=30)
print(resp.text)
if resp.status_code >= 400:
    raise SystemExit(f'HTTP {resp.status_code}: {resp.text}')
"
    success "Hybrid search pipeline created: ${HYBRID_PIPELINE_NAME}"

    # ── 3b-6: Create index with neural pipeline as default ──
    info "Creating index: ${AOSS_INDEX_NAME} with neural ingest pipeline..."
    python3 -c "
import json, boto3, requests
from requests_aws4auth import AWS4Auth

session = boto3.Session()
creds = session.get_credentials().get_frozen_credentials()
auth = AWS4Auth(creds.access_key, creds.secret_key, '${AWS_REGION}', 'aoss', session_token=creds.token)

index_body = {
    'settings': {
        'index': {
            'knn': True,
            'knn.algo_param.ef_search': 512,
            'default_pipeline': '${NEURAL_PIPELINE_NAME}'
        }
    },
    'mappings': {
        'properties': {
            'document_id': {'type': 'keyword'},
            'chunk_id': {'type': 'keyword'},
            'content': {'type': 'text'},
            'embedding': {
                'type': 'knn_vector',
                'dimension': 1024,
                'method': {
                    'name': 'hnsw',
                    'space_type': 'cosinesimil',
                    'engine': 'faiss',
                    'parameters': {
                        'ef_construction': 256,
                        'm': 16
                    }
                }
            },
            'title': {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},
            'document_type': {'type': 'keyword'},
            'author': {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},
            'date': {
                'type': 'date',
                'format': 'yyyy-MM-dd||yyyy-MM-dd\\'T\\'HH:mm:ss||epoch_millis'
            },
            'topics': {'type': 'keyword'}
        }
    }
}

resp = requests.put('https://${aoss_host}/${AOSS_INDEX_NAME}',
                    auth=auth, headers={'Content-Type': 'application/json'},
                    data=json.dumps(index_body), timeout=30)
print(resp.text)
if resp.status_code >= 400:
    raise SystemExit(f'HTTP {resp.status_code}: {resp.text}')
"
    success "Index created: ${AOSS_INDEX_NAME} (neural pipeline: ${NEURAL_PIPELINE_NAME})"
    info "ML Model ID: ${model_id} — save this for hybrid search queries"
    ((CREATED++)) || true

    # Save model ID for later use
    echo "${model_id}" > "/tmp/aoss-model-id.txt"
}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1, STEP 4: DYNAMODB TABLE
# ═══════════════════════════════════════════════════════════════════════════════
create_dynamodb_table() {
    step "4" "DynamoDB Table — ${DYNAMODB_TABLE_NAME}"

    if ${DRY_RUN}; then
        dryrun "Create DynamoDB table ${DYNAMODB_TABLE_NAME} (PK: document_id, SK: chunk_id)"
        dryrun "Create GSI: DocumentTypeIndex (PK: document_type, SK: last_updated)"
        dryrun "Create GSI: ProcessingStatusIndex (PK: processing_status, SK: last_updated)"
        return 0
    fi

    # Check if table exists
    if aws dynamodb describe-table --table-name "${DYNAMODB_TABLE_NAME}" \
        --region "${AWS_REGION}" --no-cli-pager 2>/dev/null; then
        skip "DynamoDB table ${DYNAMODB_TABLE_NAME} already exists"
        ((SKIPPED++)) || true
        return 0
    fi

    info "Creating DynamoDB table ${DYNAMODB_TABLE_NAME}..."
    aws dynamodb create-table \
        --table-name "${DYNAMODB_TABLE_NAME}" \
        --key-schema \
            "AttributeName=document_id,KeyType=HASH" \
            "AttributeName=chunk_id,KeyType=RANGE" \
        --attribute-definitions \
            "AttributeName=document_id,AttributeType=S" \
            "AttributeName=chunk_id,AttributeType=S" \
            "AttributeName=document_type,AttributeType=S" \
            "AttributeName=processing_status,AttributeType=S" \
            "AttributeName=last_updated,AttributeType=S" \
        --global-secondary-indexes \
            "IndexName=DocumentTypeIndex,KeySchema=[{AttributeName=document_type,KeyType=HASH},{AttributeName=last_updated,KeyType=RANGE}],Projection={ProjectionType=ALL}" \
            "IndexName=ProcessingStatusIndex,KeySchema=[{AttributeName=processing_status,KeyType=HASH},{AttributeName=last_updated,KeyType=RANGE}],Projection={ProjectionType=ALL}" \
        --billing-mode PAY_PER_REQUEST \
        --tags "Key=Project,Value=${TAG_PROJECT}" "Key=Demo,Value=${TAG_DEMO}" \
        --region "${AWS_REGION}" \
        --no-cli-pager

    # Wait for table to become ACTIVE
    info "Waiting for table to become ACTIVE..."
    aws dynamodb wait table-exists \
        --table-name "${DYNAMODB_TABLE_NAME}" \
        --region "${AWS_REGION}" \
        --no-cli-pager

    success "DynamoDB table ${DYNAMODB_TABLE_NAME} created (PAY_PER_REQUEST, 2 GSIs)"
    ((CREATED++)) || true
}

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2, STEP 5: IAM ROLE FOR LAMBDA
# ═══════════════════════════════════════════════════════════════════════════════
create_lambda_iam_role() {
    step "5" "IAM Role for Lambda — ${LAMBDA_ROLE_NAME}"

    if ${DRY_RUN}; then
        dryrun "Create IAM role ${LAMBDA_ROLE_NAME} with lambda.amazonaws.com trust"
        dryrun "Attach policies for S3, DynamoDB, Bedrock, OpenSearch Serverless, CloudWatch Logs"
        return 0
    fi

    if aws iam get-role --role-name "${LAMBDA_ROLE_NAME}" --no-cli-pager 2>/dev/null; then
        skip "IAM role ${LAMBDA_ROLE_NAME} already exists"
        # Always update inline policy to ensure permissions are current
        info "Updating inline policy..."
    else
        info "Creating IAM role ${LAMBDA_ROLE_NAME}..."

        local trust_policy
        trust_policy=$(cat <<'TRUST_EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
TRUST_EOF
        )

        aws iam create-role \
            --role-name "${LAMBDA_ROLE_NAME}" \
            --assume-role-policy-document "${trust_policy}" \
            --description "Lambda execution role for legal document processor" \
            --tags "Key=Project,Value=${TAG_PROJECT}" "Key=Demo,Value=${TAG_DEMO}" \
            --no-cli-pager

        # Attach basic Lambda execution policy (CloudWatch Logs)
        aws iam attach-role-policy \
            --role-name "${LAMBDA_ROLE_NAME}" \
            --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" \
            --no-cli-pager

        # Attach X-Ray tracing policy for observability
        aws iam attach-role-policy \
            --role-name "${LAMBDA_ROLE_NAME}" \
            --policy-arn "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess" \
            --no-cli-pager

        ((CREATED++)) || true
        info "Waiting 10s for IAM role propagation..."
        sleep 10
    fi

    # Inline policy for S3, DynamoDB, Bedrock, OpenSearch Serverless
    local inline_policy
    inline_policy=$(cat <<POLICY_EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "S3ReadAccess",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::${BUCKET_NAME}",
                "arn:aws:s3:::${BUCKET_NAME}/*"
            ]
        },
        {
            "Sid": "DynamoDBAccess",
            "Effect": "Allow",
            "Action": [
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:UpdateItem",
                "dynamodb:Query",
                "dynamodb:Scan"
            ],
            "Resource": [
                "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DYNAMODB_TABLE_NAME}",
                "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DYNAMODB_TABLE_NAME}/index/*"
            ]
        },
        {
            "Sid": "BedrockForNeuralPipeline",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel"
            ],
            "Resource": [
                "arn:aws:bedrock:${AWS_REGION}::foundation-model/${EMBEDDING_MODEL_ID}"
            ]
        },
        {
            "Sid": "OpenSearchServerlessAccess",
            "Effect": "Allow",
            "Action": [
                "aoss:APIAccessAll"
            ],
            "Resource": [
                "arn:aws:aoss:${AWS_REGION}:${AWS_ACCOUNT_ID}:collection/*"
            ]
        }
    ]
}
POLICY_EOF
    )

    aws iam put-role-policy \
        --role-name "${LAMBDA_ROLE_NAME}" \
        --policy-name "LegalDocProcessorPolicy" \
        --policy-document "${inline_policy}" \
        --no-cli-pager

    success "IAM role ${LAMBDA_ROLE_NAME} configured with S3, DynamoDB, Bedrock (neural pipeline), AOSS permissions"
}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2, STEP 6: LAMBDA FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════
create_lambda_function() {
    step "6" "Lambda Function — ${LAMBDA_FUNCTION_NAME}"

    local role_arn="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}"

    if ${DRY_RUN}; then
        dryrun "Package Lambda function from lambda_processing/document_processor.py"
        dryrun "Create Lambda function ${LAMBDA_FUNCTION_NAME}"
        return 0
    fi

    # Package Lambda code using the packaging script
    info "Packaging Lambda function..."
    local zip_file="/tmp/${LAMBDA_FUNCTION_NAME}.zip"
    "${SCRIPT_DIR}/package-lambda.sh" --output "${zip_file}"

    if aws lambda get-function --function-name "${LAMBDA_FUNCTION_NAME}" \
        --region "${AWS_REGION}" --no-cli-pager 2>/dev/null; then
        info "Lambda function exists — updating code..."
        aws lambda update-function-code \
            --function-name "${LAMBDA_FUNCTION_NAME}" \
            --zip-file "fileb://${zip_file}" \
            --region "${AWS_REGION}" \
            --no-cli-pager

        # Wait for update to complete
        aws lambda wait function-updated-v2 \
            --function-name "${LAMBDA_FUNCTION_NAME}" \
            --region "${AWS_REGION}" \
            --no-cli-pager 2>/dev/null || sleep 5

        success "Lambda function code updated"
        ((SKIPPED++)) || true
    else
        info "Creating Lambda function ${LAMBDA_FUNCTION_NAME}..."

        # Get OpenSearch endpoint if collection exists
        local aoss_endpoint=""
        local collection_id
        collection_id="$(aws opensearchserverless list-collections \
            --region "${AWS_REGION}" \
            --query "collectionSummaries[?name=='${AOSS_COLLECTION_NAME}'].id" \
            --output text \
            --no-cli-pager 2>/dev/null || echo "")"

        if [[ -n "${collection_id}" && "${collection_id}" != "None" ]]; then
            aoss_endpoint="${collection_id}.${AWS_REGION}.aoss.amazonaws.com"
        fi

        aws lambda create-function \
            --function-name "${LAMBDA_FUNCTION_NAME}" \
            --runtime "${LAMBDA_RUNTIME}" \
            --role "${role_arn}" \
            --handler "${LAMBDA_HANDLER}" \
            --zip-file "fileb://${zip_file}" \
            --memory-size ${LAMBDA_MEMORY} \
            --timeout ${LAMBDA_TIMEOUT} \
            --tracing-config "Mode=Active" \
            --logging-config "LogFormat=JSON,ApplicationLogLevel=INFO,SystemLogLevel=INFO" \
            --environment "Variables={OPENSEARCH_ENDPOINT=${aoss_endpoint},DYNAMODB_TABLE=${DYNAMODB_TABLE_NAME},OPENSEARCH_INDEX=${AOSS_INDEX_NAME},AWS_REGION_NAME=${AWS_REGION}}" \
            --tags "Project=${TAG_PROJECT},Demo=${TAG_DEMO}" \
            --region "${AWS_REGION}" \
            --no-cli-pager

        # Wait for function to become Active
        aws lambda wait function-active-v2 \
            --function-name "${LAMBDA_FUNCTION_NAME}" \
            --region "${AWS_REGION}" \
            --no-cli-pager 2>/dev/null || sleep 5

        success "Lambda function ${LAMBDA_FUNCTION_NAME} created"
        ((CREATED++)) || true
    fi

    rm -f "${zip_file}"
}

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2, STEP 7: S3 EVENT NOTIFICATION → LAMBDA
# ═══════════════════════════════════════════════════════════════════════════════
configure_s3_trigger() {
    step "7" "S3 Event Notification → Lambda Trigger"

    if ${DRY_RUN}; then
        dryrun "Add Lambda permission for S3 invocation"
        dryrun "Configure S3 event notification on ${BUCKET_NAME}/raw-docs/ → ${LAMBDA_FUNCTION_NAME}"
        return 0
    fi

    local lambda_arn
    lambda_arn="$(aws lambda get-function \
        --function-name "${LAMBDA_FUNCTION_NAME}" \
        --region "${AWS_REGION}" \
        --query "Configuration.FunctionArn" \
        --output text \
        --no-cli-pager)"

    # Add permission for S3 to invoke Lambda (idempotent — remove first if exists)
    info "Configuring S3 → Lambda permission..."
    aws lambda remove-permission \
        --function-name "${LAMBDA_FUNCTION_NAME}" \
        --statement-id "S3InvokePermission" \
        --region "${AWS_REGION}" \
        --no-cli-pager 2>/dev/null || true

    aws lambda add-permission \
        --function-name "${LAMBDA_FUNCTION_NAME}" \
        --statement-id "S3InvokePermission" \
        --action "lambda:InvokeFunction" \
        --principal "s3.amazonaws.com" \
        --source-arn "arn:aws:s3:::${BUCKET_NAME}" \
        --source-account "${AWS_ACCOUNT_ID}" \
        --region "${AWS_REGION}" \
        --no-cli-pager

    # Configure S3 event notification
    info "Configuring S3 event notification..."
    local notification_config
    notification_config=$(cat <<NOTIF_EOF
{
    "LambdaFunctionConfigurations": [
        {
            "Id": "LegalDocUploadTrigger",
            "LambdaFunctionArn": "${lambda_arn}",
            "Events": ["s3:ObjectCreated:*"],
            "Filter": {
                "Key": {
                    "FilterRules": [
                        {
                            "Name": "prefix",
                            "Value": "raw-docs/"
                        },
                        {
                            "Name": "suffix",
                            "Value": ".txt"
                        }
                    ]
                }
            }
        }
    ]
}
NOTIF_EOF
    )

    aws s3api put-bucket-notification-configuration \
        --bucket "${BUCKET_NAME}" \
        --notification-configuration "${notification_config}" \
        --region "${AWS_REGION}" \
        --no-cli-pager

    success "S3 event notification configured: raw-docs/*.txt → ${LAMBDA_FUNCTION_NAME}"
    ((CREATED++)) || true
}

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2, STEP 8: TEST PIPELINE (invoke Lambda manually for one document)
# ═══════════════════════════════════════════════════════════════════════════════
test_pipeline() {
    step "8" "Test Pipeline — Invoke Lambda for sample document"

    if ${DRY_RUN}; then
        dryrun "Invoke Lambda ${LAMBDA_FUNCTION_NAME} with sample S3 event"
        return 0
    fi

    info "Invoking Lambda with a sample document event..."

    local test_event
    test_event=$(cat <<EVENT_EOF
{
    "Records": [
        {
            "s3": {
                "bucket": {"name": "${BUCKET_NAME}"},
                "object": {"key": "raw-docs/case_brief_01.txt"}
            }
        }
    ]
}
EVENT_EOF
    )

    local response_file="/tmp/lambda-test-response.json"
    aws lambda invoke \
        --function-name "${LAMBDA_FUNCTION_NAME}" \
        --payload "$(echo "${test_event}" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)))")" \
        --region "${AWS_REGION}" \
        --no-cli-pager \
        "${response_file}" 2>/dev/null || true

    if [[ -f "${response_file}" ]]; then
        local status_code
        status_code="$(python3 -c "import json; r=json.load(open('${response_file}')); print(r.get('statusCode', 'N/A'))" 2>/dev/null || echo "N/A")"

        if [[ "${status_code}" == "200" ]]; then
            success "Lambda test invocation succeeded (statusCode: 200)"
            local body
            body="$(python3 -c "import json; r=json.load(open('${response_file}')); print(json.dumps(json.loads(r['body']), indent=2))" 2>/dev/null || echo "{}")"
            info "Response:"
            echo "${body}" | head -20
        else
            warn "Lambda returned statusCode: ${status_code}"
            info "Check CloudWatch Logs: /aws/lambda/${LAMBDA_FUNCTION_NAME}"
        fi
        rm -f "${response_file}"
    else
        warn "No response file — Lambda may have timed out or errored"
        info "Check CloudWatch Logs: /aws/lambda/${LAMBDA_FUNCTION_NAME}"
    fi
}


# ═══════════════════════════════════════════════════════════════════════════════
# CLEANUP — Tear down all resources in reverse dependency order
# ═══════════════════════════════════════════════════════════════════════════════
cleanup() {
    header "Cleanup — Tearing Down All Resources"

    # Step 1: Remove S3 event notification
    step "C1" "Remove S3 event notification"
    if aws s3api head-bucket --bucket "${BUCKET_NAME}" --region "${AWS_REGION}" 2>/dev/null; then
        aws s3api put-bucket-notification-configuration \
            --bucket "${BUCKET_NAME}" \
            --notification-configuration '{"LambdaFunctionConfigurations":[]}' \
            --region "${AWS_REGION}" \
            --no-cli-pager 2>/dev/null || true
        success "S3 event notification removed"
    fi

    # Step 2: Delete Lambda function
    step "C2" "Delete Lambda function — ${LAMBDA_FUNCTION_NAME}"
    if aws lambda get-function --function-name "${LAMBDA_FUNCTION_NAME}" \
        --region "${AWS_REGION}" --no-cli-pager 2>/dev/null; then
        aws lambda delete-function \
            --function-name "${LAMBDA_FUNCTION_NAME}" \
            --region "${AWS_REGION}" \
            --no-cli-pager
        success "Lambda function deleted: ${LAMBDA_FUNCTION_NAME}"
        ((DELETED++)) || true
    else
        skip "Lambda function ${LAMBDA_FUNCTION_NAME} not found"
    fi

    # Step 3: Delete IAM role
    step "C3" "Delete IAM role — ${LAMBDA_ROLE_NAME}"
    if aws iam get-role --role-name "${LAMBDA_ROLE_NAME}" --no-cli-pager 2>/dev/null; then
        # Detach managed policies
        local policies
        policies="$(aws iam list-attached-role-policies \
            --role-name "${LAMBDA_ROLE_NAME}" \
            --query "AttachedPolicies[].PolicyArn" \
            --output text \
            --no-cli-pager 2>/dev/null || echo "")"
        for policy_arn in ${policies}; do
            aws iam detach-role-policy \
                --role-name "${LAMBDA_ROLE_NAME}" \
                --policy-arn "${policy_arn}" \
                --no-cli-pager 2>/dev/null || true
        done

        # Delete inline policies
        local inline_policies
        inline_policies="$(aws iam list-role-policies \
            --role-name "${LAMBDA_ROLE_NAME}" \
            --query "PolicyNames[]" \
            --output text \
            --no-cli-pager 2>/dev/null || echo "")"
        for policy_name in ${inline_policies}; do
            aws iam delete-role-policy \
                --role-name "${LAMBDA_ROLE_NAME}" \
                --policy-name "${policy_name}" \
                --no-cli-pager 2>/dev/null || true
        done

        aws iam delete-role --role-name "${LAMBDA_ROLE_NAME}" --no-cli-pager
        success "IAM role deleted: ${LAMBDA_ROLE_NAME}"
        ((DELETED++)) || true
    else
        skip "IAM role ${LAMBDA_ROLE_NAME} not found"
    fi

    # Step 4: Delete DynamoDB table
    step "C4" "Delete DynamoDB table — ${DYNAMODB_TABLE_NAME}"
    if aws dynamodb describe-table --table-name "${DYNAMODB_TABLE_NAME}" \
        --region "${AWS_REGION}" --no-cli-pager 2>/dev/null; then
        aws dynamodb delete-table \
            --table-name "${DYNAMODB_TABLE_NAME}" \
            --region "${AWS_REGION}" \
            --no-cli-pager
        info "Waiting for table deletion..."
        aws dynamodb wait table-not-exists \
            --table-name "${DYNAMODB_TABLE_NAME}" \
            --region "${AWS_REGION}" \
            --no-cli-pager 2>/dev/null || sleep 10
        success "DynamoDB table deleted: ${DYNAMODB_TABLE_NAME}"
        ((DELETED++)) || true
    else
        skip "DynamoDB table ${DYNAMODB_TABLE_NAME} not found"
    fi

    # Step 5: Delete OpenSearch Serverless collection and policies
    step "C5" "Delete OpenSearch Serverless — ${AOSS_COLLECTION_NAME}"
    local collection_id
    collection_id="$(aws opensearchserverless list-collections \
        --region "${AWS_REGION}" \
        --query "collectionSummaries[?name=='${AOSS_COLLECTION_NAME}'].id" \
        --output text \
        --no-cli-pager 2>/dev/null || echo "")"

    if [[ -n "${collection_id}" && "${collection_id}" != "None" ]]; then
        aws opensearchserverless delete-collection \
            --id "${collection_id}" \
            --region "${AWS_REGION}" \
            --no-cli-pager
        success "OpenSearch Serverless collection deletion initiated: ${AOSS_COLLECTION_NAME}"
        ((DELETED++)) || true

        # Wait for collection to be deleted before removing policies
        info "Waiting for collection deletion (up to 5 minutes)..."
        local elapsed=0
        while [[ ${elapsed} -lt 300 ]]; do
            local status
            status="$(aws opensearchserverless list-collections \
                --region "${AWS_REGION}" \
                --query "collectionSummaries[?name=='${AOSS_COLLECTION_NAME}'].status" \
                --output text \
                --no-cli-pager 2>/dev/null || echo "")"
            if [[ -z "${status}" || "${status}" == "None" ]]; then
                success "Collection deleted"
                break
            fi
            sleep 15
            elapsed=$((elapsed + 15))
            info "  Status: ${status} (${elapsed}s)..."
        done
    else
        skip "OpenSearch Serverless collection ${AOSS_COLLECTION_NAME} not found"
    fi

    # Delete AOSS policies
    for policy_name in "legal-research-dap"; do
        aws opensearchserverless delete-access-policy \
            --name "${policy_name}" --type data \
            --region "${AWS_REGION}" \
            --no-cli-pager 2>/dev/null || true
    done
    for policy_name in "legal-research-net"; do
        aws opensearchserverless delete-security-policy \
            --name "${policy_name}" --type network \
            --region "${AWS_REGION}" \
            --no-cli-pager 2>/dev/null || true
    done
    for policy_name in "legal-research-enc"; do
        aws opensearchserverless delete-security-policy \
            --name "${policy_name}" --type encryption \
            --region "${AWS_REGION}" \
            --no-cli-pager 2>/dev/null || true
    done
    success "OpenSearch Serverless policies deleted"

    # Step 6: Empty and delete S3 bucket
    step "C6" "Delete S3 bucket — ${BUCKET_NAME}"
    if aws s3api head-bucket --bucket "${BUCKET_NAME}" --region "${AWS_REGION}" 2>/dev/null; then
        info "Emptying bucket..."
        aws s3 rm "s3://${BUCKET_NAME}" --recursive \
            --region "${AWS_REGION}" --no-cli-pager --quiet 2>/dev/null || true
        aws s3api delete-bucket \
            --bucket "${BUCKET_NAME}" \
            --region "${AWS_REGION}" \
            --no-cli-pager
        success "S3 bucket deleted: ${BUCKET_NAME}"
        ((DELETED++)) || true
    else
        skip "S3 bucket ${BUCKET_NAME} not found"
    fi

    header "Cleanup Complete"
    echo -e "  ${GREEN}Deleted:${NC} ${DELETED} resources"
}


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print_summary() {
    header "Deployment Summary"

    echo -e "  ${GREEN}Created:${NC} ${CREATED} resources"
    echo -e "  ${YELLOW}Skipped:${NC} ${SKIPPED} resources (already existed)"
    if [[ ${ERRORS} -gt 0 ]]; then
        echo -e "  ${RED}Errors:${NC}  ${ERRORS}"
    fi

    echo ""
    echo -e "  ${BOLD}Phase 1 — Infrastructure:${NC}"
    echo -e "    S3 Bucket:              s3://${BUCKET_NAME}"
    echo -e "    OpenSearch Serverless:  ${AOSS_COLLECTION_NAME} (VECTORSEARCH)"
    echo -e "    Neural Ingest Pipeline: ${NEURAL_PIPELINE_NAME} (Bedrock Titan V2 → 1024d)"
    echo -e "    Hybrid Search Pipeline: ${HYBRID_PIPELINE_NAME} (70% semantic / 30% keyword)"
    echo -e "    DynamoDB Table:         ${DYNAMODB_TABLE_NAME}"
    echo ""
    echo -e "  ${BOLD}Phase 2 — Processing Pipeline:${NC}"
    echo -e "    Lambda Function:        ${LAMBDA_FUNCTION_NAME}"
    echo -e "    S3 Trigger:             raw-docs/*.txt → Lambda"
    echo -e "    Embedding:              Server-side via neural ingest pipeline (not Lambda)"
    echo ""
    echo -e "  ${BOLD}Console Links:${NC}"
    echo -e "    S3:          https://${AWS_REGION}.console.aws.amazon.com/s3/buckets/${BUCKET_NAME}"
    echo -e "    OpenSearch:  https://${AWS_REGION}.console.aws.amazon.com/aos/home#/serverless/collections"
    echo -e "    DynamoDB:    https://${AWS_REGION}.console.aws.amazon.com/dynamodbv2/home#table?name=${DYNAMODB_TABLE_NAME}"
    echo -e "    Lambda:      https://${AWS_REGION}.console.aws.amazon.com/lambda/home#/functions/${LAMBDA_FUNCTION_NAME}"
    echo ""
    echo -e "  ${BOLD}Log file:${NC} ${LOG_FILE}"
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
main() {
    # Initialize log
    echo "=== Setup started at $(date) ===" > "${LOG_FILE}"

    check_prerequisites

    if ${CLEANUP}; then
        cleanup
        exit 0
    fi

    if ${DRY_RUN}; then
        header "DRY RUN — No resources will be created"
    fi

    # Generate synthetic data and local processing outputs
    header "Pre-flight: Generate Synthetic Data & Local Outputs"
    ensure_synth_data
    ensure_lambda_outputs

    # ── Phase 1: Infrastructure ──
    header "Phase 1: Infrastructure Setup"
    create_s3_bucket
    upload_documents
    create_opensearch_serverless
    setup_neural_search
    create_dynamodb_table

    # ── Phase 2: Processing Pipeline ──
    header "Phase 2: Document Processing Pipeline"
    create_lambda_iam_role
    create_lambda_function
    configure_s3_trigger
    test_pipeline

    # Summary
    print_summary
}

main "$@"
