"""
Lambda function for legal document processing and semantic chunking.

Processes .txt legal documents uploaded to S3, chunks them semantically,
and indexes into OpenSearch Serverless via a neural ingest pipeline that
handles embedding generation server-side through Bedrock Titan Embeddings V2.

Pipeline:
  1. Download .txt document from S3
  2. Detect document type and extract metadata
  3. Semantic chunking (paragraph-aware, ~500 token target with overlap)
  4. Index chunks into OpenSearch Serverless (neural pipeline generates embeddings)
  5. Store metadata + chunk tracking in DynamoDB

Environment variables (set by the setup script):
  OPENSEARCH_ENDPOINT  — OpenSearch Serverless collection endpoint
  DYNAMODB_TABLE       — DynamoDB metadata table name
  OPENSEARCH_INDEX     — OpenSearch index name
"""

import hashlib
import json
import logging
import os
import re
import uuid
from datetime import UTC, datetime

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ─── Clients (initialized at module level for Lambda container reuse) ────────
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

# ─── Configuration ───────────────────────────────────────────────────────────
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "LegalDocMetadata")
INDEX_NAME = os.environ.get("OPENSEARCH_INDEX", "legal-documents")

# Chunking parameters
MAX_CHUNK_TOKENS = 500  # ~500 tokens ≈ ~375 words ≈ ~2000 chars
CHUNK_OVERLAP_SENTENCES = 2  # Overlap last N sentences from previous chunk
MIN_CHUNK_LENGTH = 100  # Skip chunks shorter than this (chars)


# ─── Document Type Detection ────────────────────────────────────────────────

DOCUMENT_TYPE_PATTERNS = {
    "case_brief": [
        r"CASE BRIEF",
        r"HOLDING:",
        r"REASONING:",
        r"Caption:",
        r"Docket:",
        r"SIGNIFICANCE:",
    ],
    "contract_template": [
        r"AGREEMENT",
        r"LICENSE GRANT",
        r"INDEMNIFICATION",
        r"LIMITATION OF LIABILITY",
        r"WARRANTY",
        r"QUESTIONNAIRE",
        r"CLAUSE LIBRARY",
        r"ACCEPTABLE USE POLICY",
        r"SERVICE LEVEL AGREEMENT",
    ],
    "regulatory_memo": [
        r"INTERNAL MEMORANDUM",
        r"FROM:.*Compliance",
        r"FROM:.*Privacy",
        r"FROM:.*Risk Management",
        r"FROM:.*General Counsel",
        r"FROM:.*Incident Response",
    ],
}


def detect_document_type(text):
    """Detect document type based on content patterns."""
    scores = {}
    for doc_type, patterns in DOCUMENT_TYPE_PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))
        scores[doc_type] = score
    best_type = max(scores, key=scores.get)
    return best_type if scores[best_type] > 0 else "unknown"


def extract_metadata(text, s3_key):
    """Extract document-level metadata from text content."""
    key_stem = s3_key.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    metadata = {
        "title": key_stem.replace("_", " ").title(),
        "author": "Unknown",
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "document_type": detect_document_type(text),
    }

    # Extract title from first non-empty line
    for raw_line in text.split("\n"):
        stripped = raw_line.strip()
        if stripped and not stripped.startswith("INTERNAL") and not stripped.startswith("---"):
            metadata["title"] = stripped
            break

    # Extract author
    author_match = re.search(r"FROM:\s*(.+)", text)
    if author_match:
        metadata["author"] = author_match.group(1).strip()

    # Extract date
    date_match = re.search(
        r"(?:DATE|Date):\s*(\w+ \d{1,2},\s*\d{4}|\d{4}-\d{2}-\d{2})",
        text,
    )
    if date_match:
        metadata["date"] = date_match.group(1).strip()

    # Extract court (for case briefs)
    court_match = re.search(r"Court:\s*(.+)", text)
    if court_match:
        metadata["court"] = court_match.group(1).strip()

    # Extract docket
    docket_match = re.search(r"Docket:\s*(.+)", text)
    if docket_match:
        metadata["docket"] = docket_match.group(1).strip()

    # Extract topic keywords
    topic_keywords = extract_topic_keywords(text)
    metadata["topics"] = topic_keywords

    return metadata


def extract_topic_keywords(text):
    """Extract topic keywords from document text using pattern matching."""
    keywords = set()
    keyword_patterns = {
        "breach_of_contract": r"breach\s+of\s+contract|contractual\s+non-performance",
        "data_privacy": r"GDPR|CCPA|CPRA|data\s+privacy|personal\s+data|data\s+protection",
        "intellectual_property": (
            r"intellectual\s+property|IP\s+ownership|patent|copyright|trade\s+secret"
        ),
        "force_majeure": r"force\s+majeure|impossibility|impracticability",
        "cybersecurity": r"cybersecurity|data\s+breach|incident\s+response|security\s+incident",
        "ai_governance": (
            r"artificial\s+intelligence|AI\s+governance|algorithmic\s+bias|machine\s+learning"
        ),
        "employment_law": r"employment\s+discrimination|Title\s+VII|EEOC|hiring|disparate\s+impact",
        "compliance": r"SOX|HIPAA|AML|KYC|sanctions|OFAC|export\s+control",
        "saas_agreement": r"SaaS|subscription\s+agreement|service\s+level|uptime",
        "indemnification": r"indemnif|hold\s+harmless|defend.*against",
        "limitation_of_liability": (
            r"limitation\s+of\s+liability|liability\s+cap|consequential\s+damages"
        ),
    }
    for topic, pattern in keyword_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            keywords.add(topic)
    return sorted(keywords)


# ─── Semantic Chunking ──────────────────────────────────────────────────────


def semantic_chunk(text, max_chars=2000, overlap_sentences=2):
    """
    Split text into semantic chunks based on paragraph and section boundaries.

    Strategy:
      1. Split on section headers (lines in ALL CAPS or numbered sections)
      2. Within sections, split on paragraph boundaries (double newline)
      3. If a paragraph exceeds max_chars, split on sentence boundaries
      4. Include overlap_sentences from the end of the previous chunk
    """
    # Normalize whitespace
    text = re.sub(r"\r\n", "\n", text)

    # Split into sections based on headers
    section_pattern = r"\n(?=[A-Z][A-Z\s]{3,}(?:\n|:)|\d+\.\s+[A-Z])"
    sections = re.split(section_pattern, text)

    chunks = []
    previous_tail_sentences = []

    for raw_section in sections:
        section = raw_section.strip()
        if not section:
            continue

        # Split section into paragraphs
        paragraphs = re.split(r"\n\n+", section)

        current_chunk = ""
        if previous_tail_sentences:
            current_chunk = " ".join(previous_tail_sentences) + "\n\n"

        for raw_para in paragraphs:
            para = raw_para.strip()
            if not para:
                continue

            # If adding this paragraph would exceed limit, finalize current chunk
            if current_chunk and len(current_chunk) + len(para) > max_chars:
                if len(current_chunk.strip()) >= MIN_CHUNK_LENGTH:
                    chunks.append(current_chunk.strip())
                sentences = _split_sentences(current_chunk)
                tail_count = min(overlap_sentences, len(sentences))
                previous_tail_sentences = sentences[-tail_count:]
                current_chunk = " ".join(previous_tail_sentences) + "\n\n" + para + "\n\n"
            else:
                current_chunk += para + "\n\n"

        # Handle remaining content in section
        if current_chunk.strip() and len(current_chunk.strip()) >= MIN_CHUNK_LENGTH:
            chunks.append(current_chunk.strip())
            sentences = _split_sentences(current_chunk)
            tail_count = min(overlap_sentences, len(sentences))
            previous_tail_sentences = sentences[-tail_count:]
        elif current_chunk.strip():
            # Too short — merge with previous chunk if possible
            if chunks:
                chunks[-1] += "\n\n" + current_chunk.strip()
            else:
                chunks.append(current_chunk.strip())

    # Final pass: merge any remaining tiny chunks
    merged = []
    for chunk in chunks:
        if merged and len(merged[-1]) + len(chunk) < max_chars // 2:
            merged[-1] += "\n\n" + chunk
        else:
            merged.append(chunk)

    return merged or [text]


def _split_sentences(text):
    """Split text into sentences."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


# ─── OpenSearch Serverless Indexing ──────────────────────────────────────────


def _normalize_date(raw_date):
    """Normalize date strings like 'March 22, 2025' to 'yyyy-MM-dd' for OpenSearch."""
    if not raw_date:
        return ""
    # Already in yyyy-MM-dd format
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw_date):
        return raw_date
    # Try parsing common formats
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Fallback: return empty string to avoid mapping errors
    return ""


def index_to_opensearch(doc_id, chunk_id, chunk_text, metadata):
    """Index a document chunk into OpenSearch Serverless.

    Embeddings are generated server-side by the neural ingest pipeline
    configured on the index (text_embedding processor → Bedrock Titan V2).
    """
    from opensearchpy import OpenSearch, RequestsHttpConnection
    from requests_aws4auth import AWS4Auth

    credentials = boto3.Session().get_credentials()
    region = os.environ.get("AWS_REGION", "us-west-2")
    service = "aoss"  # OpenSearch Serverless uses 'aoss' service name

    awsauth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        region,
        service,
        session_token=credentials.token,
    )

    client = OpenSearch(
        hosts=[{"host": OPENSEARCH_ENDPOINT, "port": 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )

    # Normalize date to yyyy-MM-dd for OpenSearch date field mapping
    raw_date = metadata.get("date", "")
    normalized_date = _normalize_date(raw_date)

    # No embedding field — the neural ingest pipeline generates it from 'content'
    document = {
        "document_id": doc_id,
        "chunk_id": chunk_id,
        "content": chunk_text,
        "title": metadata.get("title", ""),
        "document_type": metadata.get("document_type", ""),
        "author": metadata.get("author", ""),
        "date": normalized_date,
        "topics": metadata.get("topics", []),
    }

    # AOSS does not support explicit document IDs in index operations
    return client.index(index=INDEX_NAME, body=document)


# ─── DynamoDB Metadata Storage ───────────────────────────────────────────────


def store_metadata(doc_id, chunk_id, metadata, chunk_info):
    """Store document/chunk metadata in DynamoDB."""
    table = dynamodb.Table(DYNAMODB_TABLE)

    item = {
        "document_id": doc_id,
        "chunk_id": chunk_id,
        "title": metadata.get("title", ""),
        "author": metadata.get("author", ""),
        "document_type": metadata.get("document_type", ""),
        "date": metadata.get("date", ""),
        "topics": metadata.get("topics", []),
        "source_bucket": chunk_info.get("source_bucket", ""),
        "source_key": chunk_info.get("source_key", ""),
        "checksum": chunk_info.get("checksum", ""),
        "chunk_index": chunk_info.get("chunk_index", 0),
        "chunk_length": chunk_info.get("chunk_length", 0),
        "total_chunks": chunk_info.get("total_chunks", 0),
        "embedding_status": chunk_info.get("indexing_status", "pending"),
        "processing_status": chunk_info.get("processing_status", "completed"),
        "last_updated": datetime.now(UTC).isoformat(),
    }

    table.put_item(Item=item)
    return item


# ─── Lambda Handler ──────────────────────────────────────────────────────────


def lambda_handler(event, context):
    """
    Process a .txt document uploaded to S3.

    Chunks the document semantically and indexes into OpenSearch Serverless.
    Embeddings are generated server-side by the neural ingest pipeline.

    Expected event format (S3 trigger):
    {
        "Records": [{
            "s3": {
                "bucket": {"name": "bucket-name"},
                "object": {"key": "raw-docs/document.txt"}
            }
        }]
    }
    """
    logger.info("Processing event: %s", json.dumps(event))

    # Extract S3 info from event
    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = record["s3"]["object"]["key"]

    logger.info("Processing document: s3://%s/%s", bucket, key)

    # Download document
    response = s3.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read()

    # For this demo, all documents are .txt
    text = content.decode("utf-8")

    # Generate document ID and checksum
    doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
    checksum = hashlib.md5(content, usedforsecurity=False).hexdigest()

    # Extract metadata
    metadata = extract_metadata(text, key)
    logger.info("Document type: %s, title: %s", metadata["document_type"], metadata["title"])

    # Semantic chunking
    chunks = semantic_chunk(text)
    logger.info("Generated %d chunks from document", len(chunks))

    # Process each chunk — embeddings are generated server-side by the neural pipeline
    results = []
    for i, chunk_text in enumerate(chunks):
        chunk_id = f"{doc_id}-chunk-{i:03d}"

        # Index to OpenSearch (neural pipeline generates embeddings from 'content')
        indexing_status = "completed"
        if OPENSEARCH_ENDPOINT:
            try:
                index_to_opensearch(doc_id, chunk_id, chunk_text, metadata)
                logger.info("Indexed chunk %s to OpenSearch", chunk_id)
            except Exception:
                logger.exception("OpenSearch indexing failed for %s", chunk_id)
                indexing_status = "failed"

        # Store metadata in DynamoDB
        chunk_info = {
            "source_bucket": bucket,
            "source_key": key,
            "checksum": checksum,
            "chunk_index": i,
            "chunk_length": len(chunk_text),
            "total_chunks": len(chunks),
            "indexing_status": indexing_status,
            "processing_status": "completed",
        }

        try:
            store_metadata(doc_id, chunk_id, metadata, chunk_info)
        except Exception:
            logger.exception("DynamoDB write failed for %s", chunk_id)

        results.append(
            {
                "chunk_id": chunk_id,
                "chunk_length": len(chunk_text),
                "indexing_status": indexing_status,
            }
        )

    # Store parent document record (chunk_id = "DOCUMENT" for the parent)
    parent_info = {
        "source_bucket": bucket,
        "source_key": key,
        "checksum": checksum,
        "chunk_index": -1,
        "chunk_length": len(text),
        "total_chunks": len(chunks),
        "indexing_status": "n/a",
        "processing_status": "completed",
    }
    store_metadata(doc_id, "DOCUMENT", metadata, parent_info)

    response_body = {
        "document_id": doc_id,
        "title": metadata["title"],
        "document_type": metadata["document_type"],
        "chunks_processed": len(chunks),
        "status": "completed",
        "chunks": results,
    }

    logger.info("Document processing complete: %s, %d chunks", doc_id, len(chunks))

    return {"statusCode": 200, "body": json.dumps(response_body)}


# ─── Local Testing ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    """Run locally for testing — reads from synth_data/output/ and prints results."""
    import sys
    from pathlib import Path

    SAMPLE_CONTENT_PREVIEW_LEN = 500

    script_dir = Path(__file__).resolve().parent
    demo_dir = script_dir.parent
    synth_dir = demo_dir / "synth_data" / "output"
    output_dir = script_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not synth_dir.exists():
        print(f"ERROR: Synthetic data not found at {synth_dir}")
        print("Run: python3 synth_data/generate_legal_docs.py first")
        sys.exit(1)

    # Load manifest
    manifest_path = synth_dir / "manifest.json"
    with manifest_path.open() as f:
        manifest = json.load(f)

    print(f"\n{'=' * 60}")
    print("  Document Processing — Local Test Mode")
    print(f"{'=' * 60}")
    print(f"  Documents to process: {len(manifest)}")
    print("  (OpenSearch indexing skipped in local mode — neural pipeline generates embeddings)\n")

    all_results = []
    total_chunks = 0

    for doc_info in manifest:
        filepath = synth_dir / doc_info["filename"]
        with filepath.open() as f:
            text = f.read()

        # Extract metadata
        metadata = extract_metadata(text, doc_info["filename"])

        # Semantic chunking
        chunks = semantic_chunk(text)
        total_chunks += len(chunks)

        result = {
            "document_id": doc_info["document_id"],
            "filename": doc_info["filename"],
            "title": metadata["title"],
            "document_type": metadata["document_type"],
            "author": metadata["author"],
            "topics": metadata["topics"],
            "total_chunks": len(chunks),
            "chunk_lengths": [len(c) for c in chunks],
            "avg_chunk_length": sum(len(c) for c in chunks) // max(len(chunks), 1),
        }
        all_results.append(result)

        print(
            f"  {doc_info['document_id']} | {metadata['document_type']:20s} | "
            f"{len(chunks):2d} chunks | {doc_info['filename']}"
        )

    # Write processing results
    results_path = output_dir / "processing_results.json"
    with results_path.open("w") as f:
        json.dump(all_results, f, indent=2)

    # Write sample DynamoDB items
    sample_items = []
    doc = manifest[0]
    filepath = synth_dir / doc["filename"]
    with filepath.open() as f:
        text = f.read()
    metadata = extract_metadata(text, doc["filename"])
    chunks = semantic_chunk(text)
    checksum = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()

    # Parent record
    sample_items.append(
        {
            "document_id": {"S": doc["document_id"]},
            "chunk_id": {"S": "DOCUMENT"},
            "title": {"S": metadata["title"]},
            "author": {"S": metadata["author"]},
            "document_type": {"S": metadata["document_type"]},
            "date": {"S": metadata.get("date", "")},
            "topics": {"SS": metadata.get("topics", ["general"])},
            "source_key": {"S": f"raw-docs/{doc['filename']}"},
            "checksum": {"S": checksum},
            "total_chunks": {"N": str(len(chunks))},
            "processing_status": {"S": "completed"},
            "last_updated": {"S": datetime.now(UTC).isoformat()},
        }
    )

    # First chunk record
    sample_items.append(
        {
            "document_id": {"S": doc["document_id"]},
            "chunk_id": {"S": f"{doc['document_id']}-chunk-000"},
            "title": {"S": metadata["title"]},
            "document_type": {"S": metadata["document_type"]},
            "chunk_index": {"N": "0"},
            "chunk_length": {"N": str(len(chunks[0]))},
            "total_chunks": {"N": str(len(chunks))},
            "embedding_status": {"S": "n/a — neural pipeline generates embeddings"},
            "processing_status": {"S": "completed"},
            "last_updated": {"S": datetime.now(UTC).isoformat()},
        }
    )

    ddb_path = output_dir / "sample_dynamodb_items.json"
    with ddb_path.open("w") as f:
        json.dump(sample_items, f, indent=2)

    # Write sample OpenSearch document (no embedding — neural pipeline adds it)
    chunk_preview = chunks[0][:SAMPLE_CONTENT_PREVIEW_LEN]
    is_truncated = len(chunks[0]) > SAMPLE_CONTENT_PREVIEW_LEN
    sample_os_doc = {
        "document_id": doc["document_id"],
        "chunk_id": f"{doc['document_id']}-chunk-000",
        "content": chunk_preview + "..." if is_truncated else chunks[0],
        "embedding": "[generated server-side by neural ingest pipeline → Bedrock Titan V2 1024d]",
        "title": metadata["title"],
        "document_type": metadata["document_type"],
        "author": metadata["author"],
        "date": metadata.get("date", ""),
        "topics": metadata.get("topics", []),
    }
    os_path = output_dir / "sample_opensearch_document.json"
    with os_path.open("w") as f:
        json.dump(sample_os_doc, f, indent=2)

    # Write OpenSearch index mapping (neural pipeline generates embeddings from 'content')
    index_mapping = {
        "settings": {
            "index": {
                "knn": True,
                "knn.algo_param.ef_search": 512,
                "default_pipeline": "neural-ingest-pipeline",
            },
        },
        "mappings": {
            "properties": {
                "document_id": {"type": "keyword"},
                "chunk_id": {"type": "keyword"},
                "content": {"type": "text"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "faiss",
                        "parameters": {
                            "ef_construction": 256,
                            "m": 16,
                        },
                    },
                },
                "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "document_type": {"type": "keyword"},
                "author": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "date": {
                    "type": "date",
                    "format": "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ss||epoch_millis",
                },
                "topics": {"type": "keyword"},
            },
        },
    }
    mapping_path = output_dir / "opensearch_index_mapping.json"
    with mapping_path.open("w") as f:
        json.dump(index_mapping, f, indent=2)

    # Write neural pipeline info (replaces direct Bedrock embedding calls)
    neural_pipeline_info = {
        "architecture": "Neural ingest pipeline (server-side embedding generation)",
        "pipeline_name": "neural-ingest-pipeline",
        "model_id": "amazon.titan-embed-text-v2:0",
        "how_it_works": {
            "1_ingest": "Lambda indexes document WITHOUT embedding field",
            "2_pipeline": "Neural ingest pipeline intercepts the index request",
            "3_embed": "Pipeline calls Bedrock Titan V2 via ML connector to generate embedding",
            "4_store": "Embedding is added to the document and stored in the knn_vector field",
        },
        "hybrid_search_pipeline": "hybrid-search-pipeline",
        "hybrid_search_weights": {"semantic": 0.7, "keyword": 0.3},
        "notes": [
            "Titan Embeddings V2 supports dimensions: 256, 512, 1024",
            "Max input: 8192 tokens",
            "Neural pipeline handles truncation and normalization",
            "Lambda no longer needs bedrock:InvokeModel permission",
        ],
    }
    pipeline_path = output_dir / "neural_pipeline_info.json"
    with pipeline_path.open("w") as f:
        json.dump(neural_pipeline_info, f, indent=2)

    print(f"\n  Total chunks across all documents: {total_chunks}")
    print(f"  Average chunks per document: {total_chunks / len(manifest):.1f}")
    print("\n  Output files:")
    print(f"    {results_path}")
    print(f"    {ddb_path}")
    print(f"    {os_path}")
    print(f"    {mapping_path}")
    print(f"    {pipeline_path}")
    print(f"{'=' * 60}\n")
