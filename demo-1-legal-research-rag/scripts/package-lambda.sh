#!/usr/bin/env bash
#
# package-lambda.sh — Package the Lambda function with dependencies into a deployment zip
#
# Creates a self-contained zip at /tmp/legal-doc-processor.zip ready for
# `aws lambda create-function --zip-file fileb://...` or update-function-code.
#
# Usage:
#   ./scripts/package-lambda.sh                    # Package with default name
#   ./scripts/package-lambda.sh --output my.zip    # Custom output path
#   ./scripts/package-lambda.sh --clean            # Remove build artifacts only
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LAMBDA_SRC="${DEMO_DIR}/lambda_processing/document_processor.py"

FUNCTION_NAME="legal-doc-processor"
PKG_DIR="/tmp/${FUNCTION_NAME}-pkg"
OUTPUT_ZIP="/tmp/${FUNCTION_NAME}.zip"

# ── Parse args ───────────────────────────────────────────────────────────────
CLEAN_ONLY=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output)  OUTPUT_ZIP="$2"; shift 2 ;;
        --clean)   CLEAN_ONLY=true; shift ;;
        --help|-h)
            echo "Usage: $(basename "$0") [--output path.zip] [--clean]"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Clean ────────────────────────────────────────────────────────────────────
cleanup() {
    rm -rf "${PKG_DIR}"
    echo "✅ Build artifacts cleaned"
}

if ${CLEAN_ONLY}; then
    cleanup
    rm -f "${OUTPUT_ZIP}"
    echo "✅ Removed ${OUTPUT_ZIP}"
    exit 0
fi

# ── Validate ─────────────────────────────────────────────────────────────────
if [[ ! -f "${LAMBDA_SRC}" ]]; then
    echo "❌ Lambda source not found: ${LAMBDA_SRC}" >&2
    exit 1
fi

if ! command -v pip3 &>/dev/null; then
    echo "❌ pip3 not found — required to install Lambda dependencies" >&2
    exit 1
fi

if ! command -v zip &>/dev/null; then
    echo "❌ zip not found — required for Lambda packaging" >&2
    exit 1
fi

# ── Build ────────────────────────────────────────────────────────────────────
echo "📦 Packaging Lambda function..."

# Clean previous build
rm -rf "${PKG_DIR}"
rm -f "${OUTPUT_ZIP}"
mkdir -p "${PKG_DIR}"

# Install dependencies for Lambda (Linux target)
echo "   Installing dependencies: opensearch-py, requests-aws4auth"
pip3 install --quiet --target "${PKG_DIR}" opensearch-py requests-aws4auth 2>/dev/null

# Copy Lambda handler
cp "${LAMBDA_SRC}" "${PKG_DIR}/"

# Remove unnecessary files to reduce zip size
find "${PKG_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${PKG_DIR}" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find "${PKG_DIR}" -name "*.pyc" -delete 2>/dev/null || true

# Create zip
(cd "${PKG_DIR}" && zip -qr "${OUTPUT_ZIP}" .)

# Report
ZIP_SIZE=$(du -h "${OUTPUT_ZIP}" | cut -f1)
echo "✅ Lambda package created: ${OUTPUT_ZIP} (${ZIP_SIZE})"
echo "   Handler: document_processor.lambda_handler"

# Clean build dir
rm -rf "${PKG_DIR}"
