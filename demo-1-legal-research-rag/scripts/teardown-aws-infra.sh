#!/usr/bin/env bash
#
# teardown-aws-infra.sh — Convenience wrapper for cleanup
#
# Equivalent to: ./setup-aws-infra.sh --cleanup
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/setup-aws-infra.sh" --cleanup "$@"
