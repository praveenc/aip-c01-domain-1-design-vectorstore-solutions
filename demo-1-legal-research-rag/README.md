# Demo 1: Legal Research RAG Pipeline — Vector Store Solutions

[![AWS Services](https://img.shields.io/badge/AWS-OpenSearch%20Serverless%20%7C%20DynamoDB%20%7C%20Lambda%20%7C%20Bedrock%20%7C%20S3-orange.svg)](https://aws.amazon.com/)
[![AIP-C01](https://img.shields.io/badge/Cert-AWS%20AIP--C01-232F3E?logo=amazon-aws)](https://aws.amazon.com/certification/certified-ai-practitioner/)
[![Python 3.13+](https://img.shields.io/badge/Python-3.13%2B-blue.svg)](https://www.python.org/downloads/)

Hands-on demo for **AWS Certified AI Practitioner (AIP-C01)** — Task 1.4: Design and implement
vector store solutions, featuring **OpenSearch Serverless with Neural Search**, **hybrid search**
(configurable semantic/keyword weighting), **Lambda-based semantic chunking**, and a **full RAG
pipeline** with Amazon Bedrock Claude.

---

## Real-World Context

A mid-size law firm processes hundreds of legal documents monthly — case briefs, contract templates,
regulatory guidance memos, and internal legal opinions. Attorneys spend 10+ hours per week searching
for relevant precedents across disconnected document stores. Keyword search misses semantically
related content (e.g., searching "breach of contract" doesn't surface documents about "contractual
non-performance").

This demo builds a **Legal Research Knowledge Assistant** that can answer natural-language questions:

- *"What are the legal implications of SLA violations in cloud service contracts?"*
- *"Find precedents related to force majeure in supply chain disputes"*
- *"How do courts handle intellectual property disputes in software licensing?"*

---

## Architecture

```
Phase 1: Infrastructure                    Phase 2: Pipeline
┌─────────────────────────┐                ┌──────────────────────────┐
│  S3 Bucket              │                │  Lambda: legal-doc-      │
│  raw-docs/*.txt         │──S3 Event──────│  processor               │
│  metadata/manifest.json │  Notification  │                          │
└─────────────────────────┘                │  1. Download from S3     │
                                           │  2. Detect document type │
┌──────────────────────────┐               │  3. Extract metadata     │
│  OpenSearch Serverless   │◄──chunks──────│  4. Semantic chunk       │
│  legal-research-vectors  │               │     (~500 tokens, 2-sent │
│                          │               │      overlap)            │
│  Neural Ingest Pipeline  │               │  5. POST to OpenSearch   │
│  ┌────────────────────┐  │               │     (neural pipeline     │
│  │ ML Connector       │  │               │      auto-embeds)        │
│  │ → Bedrock Titan V2 │  │               │  6. Write DynamoDB       │
│  │ → 1024d embeddings │  │               └──────────┬───────────────┘
│  └────────────────────┘  │                          │
│                          │               ┌──────────▼──────────────┐
│  Hybrid Search Pipeline  │               │  DynamoDB               │
│  (configurable weights)  │               │  LegalDocMtadata        │
│  Default: 70% semantic   │               │  PK: documnt_id         │
│           30% keyword    │               │  SK: chunkid            │
└──────────────────────────┘               │  GSI: type status       │
                                           └─────────────────────────┘
Phase 3: Query
┌─────────────────────────────────────────────────────────────────┐
│  search_and_rag.py                                              │
│                                                                 │
│  Mode 1: Hybrid Search   — semantic + keyword (configurable)    │
│  Mode 2: Retrieve        — vector similarity + metadata filter  │
│  Mode 3: RAG             — retrieve → Claude generates answer   │
└─────────────────────────────────────────────────────────────────┘
```

---

## AIP-C01 Exam Coverage

| AIP-C01 Section | Requirement | Where It's Demonstrated |
|-----------------|-------------|-------------------------|
| 1.4 | Advanced vector database architectures for FM augmentation | OpenSearch Serverless with neural ingest pipeline (ML connector → Bedrock Titan V2 → 1024d HNSW/FAISS index) |
| 1.4 | Comprehensive metadata frameworks for search precision | DynamoDB metadata table with GSIs; document_type filtering in retrieve queries |
| 1.4 | High-performance vector database architectures | Hybrid search pipeline with configurable semantic/keyword weights; kNN with ef_search=512 |
| 1.4 | Integration components connecting AWS services | S3 → Lambda → OpenSearch (neural pipeline auto-embeds) + DynamoDB; Bedrock for RAG generation |
| 1.4 | Data maintenance systems for current/accurate vector stores | Checksum-based change detection, processing status tracking, idempotent setup/teardown |

---

## Files

| File | Purpose |
|------|---------|
| `synth_data/generate_legal_docs.py` | Generate 30 synthetic legal documents (case briefs, contracts, statutes, memos, opinions) |
| `lambda_processing/document_processor.py` | Lambda: text extraction, semantic chunking (~500 tokens), OpenSearch indexing, DynamoDB metadata |
| `scripts/setup-aws-infra.sh` | Provision all infrastructure, deploy Lambda, configure trigger, ingest documents |
| `scripts/teardown-aws-infra.sh` | Clean up all AWS resources (interactive S3 prompt — bucket names are globally unique) |
| `scripts/package-lambda.sh` | Package Lambda function with `opensearch-py` + `requests-aws4auth` into deployment zip |
| `scripts/search_and_rag.py` | Interactive search & RAG demo — hybrid search, retrieve, and retrieve-and-generate |
| `scripts/requirements.txt` | Python dependencies for AOSS SigV4 calls (`boto3`, `requests`, `requests-aws4auth`) |
| `docs/OPENSEARCH_DATA_INGESTION.md` | Reference: data ingestion architectures for OpenSearch (OSI vs Lambda vs neural pipeline) |

---

## Quick Start

### Prerequisites

- AWS CLI v2 with valid credentials
- [uv](https://docs.astral.sh/uv/) (Python package manager — used for venv + script execution)
- Python 3.13+
- `zip` command (for Lambda packaging)
- AWS account with access to: OpenSearch Serverless, DynamoDB, Lambda, S3, Bedrock (Titan Embeddings V2 + Claude Sonnet)

### Deploy

```bash
cd aip-c01-1.4-demos/demo-1-legal-research-rag/

# Generate synthetic legal documents (if not already present)
python3 synth_data/generate_legal_docs.py

# Preview what will be created
./scripts/setup-aws-infra.sh --dry-run

# Deploy everything (takes ~5-7 min, mostly AOSS collection creation)
./scripts/setup-aws-infra.sh
```

The setup script runs in **three phases**:

1. **Infrastructure** — S3 bucket, IAM role, AOSS collection + neural search (ML connector, model,
   pipelines, index), DynamoDB table
2. **Processing Pipeline** — Lambda function + S3 event trigger
3. **Document Ingestion** — Uploads 30 docs to S3; each upload triggers Lambda → chunk → OpenSearch
   (auto-embed) + DynamoDB. Shows real-time progress.

### Search & RAG Demo

```bash
# Interactive mode — pick from sample queries or type your own
uv run scripts/search_and_rag.py

# Single query — all three search modes
uv run scripts/search_and_rag.py --query "SLA breach remedies in cloud contracts"

# RAG only — retrieve context, generate answer with Claude
uv run scripts/search_and_rag.py -q "What constitutes material breach?" -m rag

# Retrieve with metadata filter (use --list-filters to see valid values)
uv run scripts/search_and_rag.py -q "data privacy breach obligations" -m retrieve --filter regulatory_memo

# List available document types and topics for filtering
uv run scripts/search_and_rag.py --list-filters

# Custom hybrid weights (50/50 instead of default 70/30)
uv run scripts/search_and_rag.py -q "indemnification clauses" --semantic-weight 0.5
```

### Teardown

```bash
./scripts/teardown-aws-infra.sh
# Prompts before deleting S3 bucket (globally unique names)
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Neural ingest pipeline** (not Lambda-side embeddings) | Embeddings generated server-side by OpenSearch — Lambda only chunks and indexes text. Simpler Lambda code, consistent embedding model across all ingestion paths. |
| **Hybrid search** (semantic + keyword) | Pure semantic search misses exact-match queries; pure keyword misses semantic similarity. Combined approach with configurable weights gives best-of-both. |
| **Lambda + neural pipeline** (not OSI) | Legal documents need domain-specific parsing (document type detection, entity extraction, paragraph-aware chunking). OSI's `text_chunking` only supports fixed-size and delimiter. See `docs/OPENSEARCH_DATA_INGESTION.md`. |
| **`uv` for Python venv** (not global pip) | Setup script creates a project-local `.venv` with `uv` for AOSS SigV4 dependencies. No global package pollution. |
| **Dynamic S3 bucket names** | `demo-1-legal-research-rag-<account-id>-<region>` — globally unique, overridable via `BUCKET_NAME` env var. |
| **IAM role with dual trust** | Role trusts both `lambda.amazonaws.com` and `ml.opensearchservice.amazonaws.com` — Lambda uses it for execution, OpenSearch ML connector uses it for Bedrock calls. |

---

## OpenSearch Neural Search Details

The neural search setup creates five resources on the AOSS collection:

| Resource | Purpose |
|----------|---------|
| **ML Connector** | SigV4 connector to Bedrock Titan Embeddings V2 (1024 dimensions) |
| **ML Model** | Registered + deployed remote model linked to the connector |
| **Neural Ingest Pipeline** | `text_embedding` processor — auto-generates embeddings from `content` field |
| **Hybrid Search Pipeline** | `normalization-processor` with configurable `arithmetic_mean` weights |
| **Vector Index** | kNN index with HNSW/FAISS engine, `ef_construction=256`, `m=16`, `ef_search=512` |

The hybrid search pipeline weights (`[0.7, 0.3]` = 70% semantic / 30% keyword) are fully
configurable. You can create additional pipelines with different weights and select them at
query time via `?search_pipeline=<name>`.

---

## License

MIT
