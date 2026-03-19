# Demo 1: Legal Research RAG Pipeline — Vector Store Solutions

[![AWS Services](https://img.shields.io/badge/AWS-OpenSearch%20Serverless%20%7C%20DynamoDB%20%7C%20Lambda%20%7C%20Bedrock%20%7C%20S3-orange.svg)](https://aws.amazon.com/)
[![AIP-C01](https://img.shields.io/badge/Cert-AWS%20AIP--C01-232F3E?logo=amazon-aws)](https://aws.amazon.com/certification/certified-ai-practitioner/)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

Hands-on demo for **AWS Certified AI Practitioner (AIP-C01)** — Task 1.4: Design and implement
vector store solutions, focusing on **OpenSearch Serverless with Neural Search Pipeline**, **DynamoDB
metadata tracking**, and **Lambda-based document processing** for a RAG pipeline.

---

## Real-World Context

A mid-size law firm processes hundreds of legal documents monthly — case briefs, contract templates, regulatory guidance memos, and internal legal opinions.\
Attorneys spend 10+ hours per week searching for relevant precedents across disconnected document stores.\
Keyword search misses semantically related content (e.g., searching "breach of contract" doesn't surface documents about "contractual non-performance" or "failure to perform obligations").

The firm wants to build a **Legal Research Knowledge Assistant** powered by Amazon Bedrock that can answer natural-language questions like:

- *"What are our standard indemnification clauses for SaaS agreements?"*
- *"Find precedents related to force majeure in supply chain disputes"*
- *"Summarize our firm's position on data privacy compliance under GDPR"*

This demo builds the **foundational infrastructure and document processing pipeline** (Phases 1 and 2) that enables this assistant:

- **Phase 1** provisions OpenSearch Serverless with a neural ingest pipeline (ML connector → Bedrock Titan V2 → auto-embedding), a hybrid search pipeline (70/30 semantic/keyword), a DynamoDB table for document metadata tracking, and an S3 bucket for raw document storage
- **Phase 2** implements a Lambda function that processes uploaded .txt documents — extracting text, performing semantic chunking, indexing into OpenSearch (embeddings generated server-side by the neural pipeline), and tracking metadata in DynamoDB

### Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│  PHASE 1 — Infrastructure Setup                                        │
│                                                                        │
│  ┌──────────────┐  ┌─────────────────────────┐  ┌───────────────────┐  │
│  │  S3 Bucket   │  │  OpenSearch Serverless  │  │  DynamoDB Table   │  │
│  │  legal-docs- │  │  legal-research-vectors │  │  LegalDocMetadata │  │
│  │  {region}    │  │  Neural ingest pipeline │  │  PK: document_id  │  │
│  │              │  │  ┌───────────────────┐  │  │  SK: chunk_id     │  │
│  │  /raw-docs/  │  │  │ ML Connector      │  │  │  GSI: doc_type    │  │
│  │  /processed/ │  │  │ → Bedrock Titan V2│  │  │  GSI: status      │  │
│  │              │  │  │ → 1024d embeddings│  │  │                   │  │
│  │              │  │  └───────────────────┘  │  │                   │  │
│  │              │  │  Hybrid search pipeline │  │                   │  │
│  │              │  │  (70% semantic/30% kw)  │  │                   │  │
│  └──────┬───────┘  └────────────┬────────────┘  └────────┬──────────┘  │
│         │                       │                        │             │
└─────────┼───────────────────────┼────────────────────────┼─────────────┘
          │                       │                        │
          ▼                       ▼                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 2 — Document Processing Pipeline                                 │
│                                                                         │
│  S3 Upload Event                                                        │
│       │                                                                 │
│       ▼                                                                 │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Lambda: legal-doc-processor                                     │   │
│  │                                                                  │   │
│  │  1. Download .txt document from S3                               │   │
│  │  2. Detect document type and extract metadata                    │   │
│  │  3. Semantic chunking (paragraph-aware, 500-token target)        │   │
│  │  4. Index chunks into OpenSearch (no embedding — pipeline does   │   │
│  │     it server-side via Bedrock Titan V2)                         │   │
│  │  5. Store metadata + chunk tracking in DynamoDB                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Outputs:                                                               │
│    • Vectors indexed in OpenSearch (neural pipeline → knn_vector)      │
│    • Metadata rows in DynamoDB (1 parent + N chunk records per doc)     │
│    • Processing status tracked end-to-end                               │
└─────────────────────────────────────────────────────────────────────────┘
```

## AIP-C01 Exam Coverage

| AIP-C01 Section | Requirement | Where It's Demonstrated |
|-----------------|-------------|-------------------------|
| 1.4 | Advanced vector database architectures for FM augmentation | OpenSearch Serverless with neural ingest pipeline (ML connector → Bedrock Titan V2) |
| 1.4 | Comprehensive metadata frameworks for search precision | DynamoDB metadata table with GSIs for type/status filtering |
| 1.4 | High-performance vector database architectures | HNSW/FAISS index with hybrid search pipeline (70/30 semantic/keyword) |
| 1.4 | Integration components connecting AWS services | Lambda → OpenSearch (neural pipeline) + DynamoDB, S3 trigger |
| 1.4 | Data maintenance systems for current/accurate vector stores | Checksum-based change detection, processing status tracking |

## Files

| File | Purpose |
|------|---------|
| `synth_data/generate_legal_docs.py` | Generate 30 synthetic legal documents (case briefs, contracts, memos) as text files |
| `lambda_processing/document_processor.py` | Lambda function: text extraction, semantic chunking, OpenSearch indexing (neural pipeline generates embeddings) |
| `scripts/setup-aws-infra.sh` | Provision all Phase 1 + Phase 2 infrastructure (including neural search setup) and run the pipeline |
| `scripts/package-lambda.sh` | Package Lambda function with dependencies into a deployment zip |
| `scripts/teardown-aws-infra.sh` | Clean up all AWS resources in reverse dependency order |

## Quick Start

```bash
cd aip-c01-1.4-demos/demo-1-legal-research-rag/

# Generate synthetic legal documents
python3 synth_data/generate_legal_docs.py

# Deploy to AWS (provisions OpenSearch Serverless, DynamoDB, Lambda, S3)
./scripts/setup-aws-infra.sh --dry-run     # Preview
./scripts/setup-aws-infra.sh               # Deploy
./scripts/setup-aws-infra.sh --cleanup     # Tear down
```

## Requirements

- Python 3.9+ (standard library only for data generation)
- AWS CLI v2 configured with valid credentials
- AWS account with access to: OpenSearch Serverless, DynamoDB, Lambda, S3, Bedrock (Titan Embeddings V2 — used by neural pipeline, not Lambda)
- `opensearch-py` and `requests-aws4auth` Python packages (for neural search setup and Lambda)
- `zip` command (for Lambda packaging)
- `jq` (optional, for JSON parsing)

## License

MIT
