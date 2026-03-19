# AIP-C01 Domain 1 (Task 1.4): Design Vector Store Solutions

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/Python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![AWS Services](https://img.shields.io/badge/AWS-OpenSearch%20Serverless%20%7C%20DynamoDB%20%7C%20Lambda%20%7C%20Bedrock%20%7C%20S3-orange.svg)](https://aws.amazon.com/)
[![AIP-C01](https://img.shields.io/badge/Cert-AWS%20AIP--C01-232F3E?logo=amazon-aws)](https://aws.amazon.com/certification/certified-ai-practitioner/)
[![Offline Ready](https://img.shields.io/badge/Runs-Offline%20%E2%9C%93-brightgreen)](demo-1-legal-research-rag/)

Hands-on demos for **AWS Certified AI Practitioner (AIP-C01)** — Domain 1: Fundamentals of AI and ML, focusing on **vector store architectures, semantic search, and document processing pipelines** for foundation model augmentation (RAG).

---

## What This Project Does

A mid-size law firm processes hundreds of legal documents monthly — case briefs, contract templates, regulatory guidance memos, and internal legal opinions. Attorneys spend 10+ hours per week searching for relevant precedents across disconnected document stores. Keyword search misses semantically related content (e.g., searching "breach of contract" doesn't surface documents about "contractual non-performance").

This project builds the **vector store infrastructure and document processing pipeline** that powers a Legal Research Knowledge Assistant on Amazon Bedrock — enabling natural-language queries like:

- *"What are our standard indemnification clauses for SaaS agreements?"*
- *"Find precedents related to force majeure in supply chain disputes"*
- *"Summarize our firm's position on data privacy compliance under GDPR"*

### Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 1 — Infrastructure                                                │
│                                                                          │
│  ┌──────────────┐  ┌──────────────────────────┐  ┌────────────────────┐  │
│  │  S3 Bucket   │  │  OpenSearch Serverless   │  │  DynamoDB Table    │  │
│  │  legal-docs  │  │  VECTORSEARCH collection │  │  LegalDocMetadata  │  │
│  │  /raw-docs/  │  │  Neural Search + kNN     │  │  PK: document_id   │  │
│  └──────┬───────┘  └────────────┬─────────────┘  └────────┬───────────┘  │
└─────────┼───────────────────────┼─────────────────────────┼──────────────┘
          │                       │                         │
          ▼                       ▼                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 2 — Document Processing Pipeline                                  │
│                                                                          │
│  S3 Upload → Lambda: legal-doc-processor                                 │
│    1. Extract text  →  2. Detect document type  →  3. Semantic chunking  │
│    4. Bedrock Titan V2 embeddings  →  5. Index to OpenSearch             │
│    6. Store metadata in DynamoDB   →  7. Track processing status         │
└──────────────────────────────────────────────────────────────────────────┘
```

### Pipeline at a Glance

| Step | AWS Service | What It Does |
|------|-------------|--------------|
| **1. Data Generation** | — (local) | Generate 30 synthetic legal documents (case briefs, contracts, regulatory memos) |
| **2. Infrastructure** | OpenSearch Serverless, DynamoDB, S3 | Provision VECTORSEARCH collection with neural search, metadata table, document bucket |
| **3. Document Processing** | Lambda + Bedrock | Semantic chunking, Titan V2 embedding generation (1024-dim), vector indexing |
| **4. Vector Storage** | OpenSearch Serverless | HNSW index with cosine similarity, knn_vector fields for semantic search |
| **5. Metadata Tracking** | DynamoDB | Parent + chunk records with GSIs for type/status filtering, checksum-based dedup |

---

## AIP-C01 Exam Coverage

| AIP-C01 Section | Requirement | Where It's Demonstrated |
|-----------------|-------------|-------------------------|
| 1.4 | Advanced vector database architectures for FM augmentation | OpenSearch Serverless collection with neural search + knn_vector index |
| 1.4 | Comprehensive metadata frameworks for search precision | DynamoDB metadata table with GSIs for type/status filtering |
| 1.4 | High-performance vector database architectures | OpenSearch index mappings with HNSW algorithm, cosine similarity, Faiss engine |
| 1.4 | Integration components connecting AWS services | Lambda triggered by S3, writing to OpenSearch + DynamoDB via Bedrock embeddings |
| 1.4 | Data maintenance systems for current/accurate vector stores | Checksum-based change detection, processing status tracking |

---

## Demo

| Demo | Description | Status |
|------|-------------|--------|
| [**Demo 1: Legal Research RAG**](demo-1-legal-research-rag/) | End-to-end pipeline: synthetic legal docs → OpenSearch Serverless vector store → Lambda document processing → Bedrock Titan V2 embeddings → DynamoDB metadata tracking | ✅ Complete |

---

## Project Structure

```
.
├── README.md                                    # This file
├── .gitignore
└── demo-1-legal-research-rag/
    ├── README.md                                # Detailed walkthrough & architecture
    ├── pyproject.toml                           # Python 3.13+ / ruff configuration
    ├── synth_data/
    │   └── generate_legal_docs.py               # Generate 30 synthetic legal documents
    ├── lambda_processing/
    │   └── document_processor.py                # Lambda: chunking, embeddings, indexing
    └── scripts/
        ├── setup-aws-infra.sh                   # Provision all Phase 1 + Phase 2 infra
        └── teardown-aws-infra.sh                # Clean up all AWS resources
```

---

## Quick Start

```bash
git clone https://github.com/praveenc/aip-c01-domain-1-design-vectorstore-solutions.git
cd aip-c01-domain-1-design-vectorstore-solutions/demo-1-legal-research-rag/
```

### Option A: Deploy to AWS (recommended)

```bash
./scripts/setup-aws-infra.sh --dry-run     # Preview what will be created
./scripts/setup-aws-infra.sh               # Deploy everything
./scripts/teardown-aws-infra.sh            # Tear down when done
```

> Requires: AWS CLI v2 configured, Python 3.13+, `zip`, `jq` (optional).

### Option B: Run locally (offline, no AWS needed)

```bash
python3 synth_data/generate_legal_docs.py        # Generate 30 synthetic legal documents
python3 lambda_processing/document_processor.py  # Process docs: chunking + sample outputs
```

> All AWS API calls are represented as generated JSON configuration files in each step's `output/` directory.

---

## Requirements

- **Python 3.13+** (standard library only — no `pip install` needed for local execution)
- No AWS account required for local execution
- For AWS deployment: account with access to OpenSearch Serverless, DynamoDB, Lambda, S3, Bedrock (Titan Embeddings V2)

## License

This project is licensed under the [MIT License](LICENSE).
