#!/usr/bin/env python3
"""
search_and_rag.py — Demonstrate Retrieve and Retrieve-and-Generate against
                     the Legal Research RAG vector store.

Showcases three search patterns:
  1. Hybrid search   — direct OpenSearch query (semantic + keyword, configurable weights)
  2. Retrieve        — Bedrock-style retrieval from OpenSearch (vector similarity + metadata)
  3. Retrieve & Generate — full RAG: retrieve context, then generate answer with Claude

Usage:
  uv run scripts/search_and_rag.py                         # interactive mode
  uv run scripts/search_and_rag.py --query "..."            # single query, all 3 modes
  uv run scripts/search_and_rag.py --query "..." --mode rag # single query, RAG only
  uv run scripts/search_and_rag.py --help
"""
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "boto3>=1.35.0",
#   "requests>=2.32.0",
#   "requests-aws4auth>=1.3.1",
# ]
# ///

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap

import boto3
import requests
from requests_aws4auth import AWS4Auth

# ─── Configuration ───────────────────────────────────────────────────────────

AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
AOSS_INDEX = os.environ.get("OPENSEARCH_INDEX", "legal-documents")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")

# Neural search pipeline (weights: [semantic, keyword])
HYBRID_PIPELINE = "hybrid-search-pipeline"

# ─── Helpers ─────────────────────────────────────────────────────────────────


def get_aoss_auth() -> tuple[str, AWS4Auth]:
    """Return (host, auth) for OpenSearch Serverless SigV4 requests."""
    session = boto3.Session(region_name=AWS_REGION)
    creds = session.get_credentials().get_frozen_credentials()
    auth = AWS4Auth(
        creds.access_key,
        creds.secret_key,
        AWS_REGION,
        "aoss",
        session_token=creds.token,
    )

    # Resolve collection endpoint
    client = session.client("opensearchserverless", region_name=AWS_REGION)
    collections = client.list_collections()["collectionSummaries"]
    legal = [c for c in collections if c["name"] == "legal-research-vectors"]
    if not legal:
        print("❌ Collection 'legal-research-vectors' not found.", file=sys.stderr)
        sys.exit(1)
    host = f"{legal[0]['id']}.{AWS_REGION}.aoss.amazonaws.com"
    return host, auth


def get_ml_model_id(host: str, auth: AWS4Auth) -> str:
    """Discover the deployed ML model ID from the neural ingest pipeline."""
    resp = requests.get(
        f"https://{host}/_ingest/pipeline/neural-ingest-pipeline",
        auth=auth,
        timeout=15,
    )
    pipeline = resp.json().get("neural-ingest-pipeline", {})
    processors = pipeline.get("processors", [])
    for p in processors:
        if "text_embedding" in p:
            return p["text_embedding"]["model_id"]
    print("❌ Could not find ML model ID in neural-ingest-pipeline.", file=sys.stderr)
    sys.exit(1)


def print_divider(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}\n")


# ─── Mode 1: Hybrid Search (Direct OpenSearch) ──────────────────────────────


def hybrid_search(
    query: str,
    host: str,
    auth: AWS4Auth,
    model_id: str,
    *,
    k: int = 5,
    semantic_weight: float = 0.7,
) -> list[dict]:
    """
    Hybrid search combining semantic (neural) and keyword (BM25) scoring.

    The weights are configurable — the hybrid-search-pipeline uses the default
    70/30 split, but you can create additional pipelines with different weights
    or pass weights at query time.
    """
    print_divider(
        f"Mode 1: Hybrid Search ({semantic_weight:.0%} semantic / {1 - semantic_weight:.0%} keyword)"
    )
    print(f"  Query: {query}\n")

    body = {
        "size": k,
        "_source": ["document_id", "title", "content", "document_type", "author", "date", "topics"],
        "query": {
            "hybrid": {
                "queries": [
                    # Query 1: keyword (BM25)
                    {"match": {"content": {"query": query}}},
                    # Query 2: semantic (neural)
                    {
                        "neural": {
                            "embedding": {
                                "query_text": query,
                                "model_id": model_id,
                                "k": k,
                            }
                        }
                    },
                ]
            }
        },
    }

    resp = requests.post(
        f"https://{host}/{AOSS_INDEX}/_search?search_pipeline={HYBRID_PIPELINE}",
        auth=auth,
        headers={"Content-Type": "application/json"},
        data=json.dumps(body),
        timeout=30,
    )
    result = resp.json()
    hits = result.get("hits", {}).get("hits", [])

    if not hits:
        print("  No results found.\n")
        return []

    for i, hit in enumerate(hits, 1):
        src = hit["_source"]
        score = hit["_score"]
        content_preview = src.get("content", "")[:150].replace("\n", " ")
        print(f"  [{i}] Score: {score:.4f} | Type: {src.get('document_type', 'N/A')}")
        print(f"      Title: {src.get('title', 'N/A')}")
        print(f"      Author: {src.get('author', 'N/A')} | Date: {src.get('date', 'N/A')}")
        print(f"      Topics: {', '.join(src.get('topics', []))}")
        print(f"      Content: {content_preview}...")
        print()

    print(f"  Total: {len(hits)} results")
    return hits


# ─── Mode 2: Retrieve (Vector Similarity + Metadata Filter) ─────────────────


def retrieve(
    query: str,
    host: str,
    auth: AWS4Auth,
    model_id: str,
    *,
    k: int = 5,
    doc_type_filter: str | None = None,
) -> list[dict]:
    """
    Pure semantic retrieval with optional metadata filtering.

    This simulates the Bedrock KB Retrieve API pattern — vector similarity
    search with pre-filtering on metadata fields. Since we're querying
    OpenSearch directly (not via Bedrock KB), we use the neural query type
    with a bool filter wrapper.
    """
    print_divider("Mode 2: Retrieve (Semantic + Metadata Filter)")
    print(f"  Query: {query}")
    if doc_type_filter:
        print(f"  Filter: document_type = '{doc_type_filter}'")
    print()

    # Build query with optional metadata filter
    neural_query: dict = {
        "neural": {
            "embedding": {
                "query_text": query,
                "model_id": model_id,
                "k": k,
            }
        }
    }

    if doc_type_filter:
        body = {
            "size": k,
            "_source": ["document_id", "title", "content", "document_type", "author", "date", "topics"],
            "query": {
                "bool": {
                    "must": [neural_query],
                    "filter": [{"term": {"document_type": doc_type_filter}}],
                }
            },
        }
    else:
        body = {
            "size": k,
            "_source": ["document_id", "title", "content", "document_type", "author", "date", "topics"],
            "query": neural_query,
        }

    resp = requests.post(
        f"https://{host}/{AOSS_INDEX}/_search",
        auth=auth,
        headers={"Content-Type": "application/json"},
        data=json.dumps(body),
        timeout=30,
    )
    result = resp.json()
    hits = result.get("hits", {}).get("hits", [])

    if not hits:
        print("  No results found.\n")
        return []

    for i, hit in enumerate(hits, 1):
        src = hit["_source"]
        score = hit["_score"]
        content_preview = src.get("content", "")[:150].replace("\n", " ")
        print(f"  [{i}] Score: {score:.4f} | Type: {src.get('document_type', 'N/A')}")
        print(f"      Title: {src.get('title', 'N/A')}")
        print(f"      Content: {content_preview}...")
        print()

    print(f"  Total: {len(hits)} results")
    return hits


# ─── Mode 3: Retrieve & Generate (Full RAG) ─────────────────────────────────


def retrieve_and_generate(
    query: str,
    host: str,
    auth: AWS4Auth,
    model_id: str,
    *,
    k: int = 5,
) -> str:
    """
    Full RAG pipeline: retrieve relevant chunks from the vector store,
    then generate an answer using Amazon Bedrock (Claude).

    This implements the Bedrock RetrieveAndGenerate pattern manually:
    1. Retrieve top-k chunks via semantic search
    2. Build a grounded prompt with the retrieved context
    3. Call Bedrock InvokeModel to generate the answer
    """
    print_divider("Mode 3: Retrieve & Generate (RAG with Claude)")
    print(f"  Query: {query}")
    print(f"  Model: {BEDROCK_MODEL_ID}")
    print(f"  Retrieving top-{k} chunks...\n")

    # Step 1: Retrieve context chunks (semantic search)
    neural_query = {
        "size": k,
        "_source": ["document_id", "title", "content", "document_type", "author", "date"],
        "query": {
            "neural": {
                "embedding": {
                    "query_text": query,
                    "model_id": model_id,
                    "k": k,
                }
            }
        },
    }

    resp = requests.post(
        f"https://{host}/{AOSS_INDEX}/_search",
        auth=auth,
        headers={"Content-Type": "application/json"},
        data=json.dumps(neural_query),
        timeout=30,
    )
    result = resp.json()
    hits = result.get("hits", {}).get("hits", [])

    if not hits:
        print("  No context retrieved — cannot generate answer.\n")
        return ""

    # Show retrieved sources
    print("  Retrieved sources:")
    for i, hit in enumerate(hits, 1):
        src = hit["_source"]
        print(f"    [{i}] {src.get('title', 'N/A')} ({src.get('document_type', '?')}, score: {hit['_score']:.4f})")
    print()

    # Step 2: Build grounded prompt with retrieved context
    context_blocks = []
    for i, hit in enumerate(hits, 1):
        src = hit["_source"]
        context_blocks.append(
            f"[Source {i}: {src.get('title', 'Unknown')} | "
            f"Type: {src.get('document_type', 'unknown')} | "
            f"Author: {src.get('author', 'unknown')} | "
            f"Date: {src.get('date', 'unknown')}]\n"
            f"{src.get('content', '')}"
        )

    context = "\n\n---\n\n".join(context_blocks)

    system_prompt = (
        "You are a legal research assistant. Answer questions using ONLY the "
        "provided source documents. Cite sources using [Source N] notation. "
        "If the sources don't contain enough information, say so explicitly. "
        "Prioritize more recent documents when sources conflict."
    )

    user_prompt = f"""Based on the following legal documents, answer this question:

**Question:** {query}

**Retrieved Documents:**

{context}

**Instructions:**
- Use ONLY information from the sources above
- Cite sources as [Source 1], [Source 2], etc.
- Note any limitations or gaps in the available information
- If documents provide conflicting information, note the conflict and prefer the more recent source"""

    # Step 3: Call Bedrock
    print("  Generating answer with Claude...\n")
    bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

    bedrock_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "temperature": 0.1,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    bedrock_resp = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(bedrock_body),
    )

    response_body = json.loads(bedrock_resp["body"].read())
    answer = response_body["content"][0]["text"]
    usage = response_body.get("usage", {})

    # Display answer
    print("  ┌─ Generated Answer ─────────────────────────────────────")
    for line in answer.split("\n"):
        print(f"  │ {line}")
    print("  └────────────────────────────────────────────────────────")
    print(f"\n  Tokens: {usage.get('input_tokens', '?')} in / {usage.get('output_tokens', '?')} out")

    return answer


# ─── Interactive Mode ────────────────────────────────────────────────────────


SAMPLE_QUERIES = [
    "What are the legal implications of SLA violations in cloud service contracts?",
    "How do courts handle intellectual property disputes in software licensing?",
    "What constitutes material breach in technology service agreements?",
    "What are the privacy obligations under data protection regulations?",
    "How are non-compete clauses enforced in employment contracts?",
]


def interactive_mode(host: str, auth: AWS4Auth, model_id: str) -> None:
    """Run interactive query loop with sample queries."""
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Legal Research RAG — Interactive Search & Generation       ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"║  Vector Store: OpenSearch Serverless (legal-research-vectors)║")
    print(f"║  Index: {AOSS_INDEX:<42}       ║")
    print(f"║  LLM: {BEDROCK_MODEL_ID:<44}       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print("\nSample queries:")
    for i, q in enumerate(SAMPLE_QUERIES, 1):
        print(f"  [{i}] {q}")
    print(f"\nType a number (1-{len(SAMPLE_QUERIES)}), a custom query, or 'q' to quit.\n")

    while True:
        try:
            user_input = input("Query> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input or user_input.lower() == "q":
            print("Goodbye!")
            break

        # Resolve query
        if user_input.isdigit() and 1 <= int(user_input) <= len(SAMPLE_QUERIES):
            query = SAMPLE_QUERIES[int(user_input) - 1]
        else:
            query = user_input

        # Run all three modes
        hybrid_search(query, host, auth, model_id)
        retrieve(query, host, auth, model_id)
        retrieve_and_generate(query, host, auth, model_id)

        print(f"\n{'═' * 60}\n")


# ─── CLI ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search and RAG against the Legal Research vector store.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Modes:
              hybrid    Direct OpenSearch hybrid search (semantic + keyword)
              retrieve  Semantic retrieval with optional metadata filtering
              rag       Full RAG: retrieve context → generate answer with Claude
              all       Run all three modes (default)

            Examples:
              uv run scripts/search_and_rag.py
              uv run scripts/search_and_rag.py --query "SLA breach remedies" --mode rag
              uv run scripts/search_and_rag.py --query "privacy law" --mode retrieve --filter case_law
        """),
    )
    parser.add_argument("--query", "-q", help="Search query (omit for interactive mode)")
    parser.add_argument("--mode", "-m", choices=["hybrid", "retrieve", "rag", "all"], default="all")
    parser.add_argument("--filter", "-f", help="Filter by document_type (for retrieve mode)")
    parser.add_argument("--top-k", "-k", type=int, default=5, help="Number of results (default: 5)")
    parser.add_argument(
        "--semantic-weight", "-w", type=float, default=0.7,
        help="Semantic weight for hybrid search (default: 0.7, keyword = 1 - weight)",
    )
    args = parser.parse_args()

    # Connect to OpenSearch
    print("Connecting to OpenSearch Serverless...")
    host, auth = get_aoss_auth()
    model_id = get_ml_model_id(host, auth)
    print(f"  Host: {host}")
    print(f"  Model: {model_id}")

    # Check index has documents
    resp = requests.post(
        f"https://{host}/{AOSS_INDEX}/_count",
        auth=auth,
        timeout=15,
    )
    doc_count = resp.json().get("count", 0)
    print(f"  Documents in index: {doc_count}")
    if doc_count == 0:
        print("\n⚠️  No documents in index. Run setup-aws-infra.sh first to ingest documents.")
        sys.exit(1)

    if not args.query:
        interactive_mode(host, auth, model_id)
        return

    # Single query mode
    query = args.query
    if args.mode in ("hybrid", "all"):
        hybrid_search(query, host, auth, model_id, k=args.top_k, semantic_weight=args.semantic_weight)
    if args.mode in ("retrieve", "all"):
        retrieve(query, host, auth, model_id, k=args.top_k, doc_type_filter=args.filter)
    if args.mode in ("rag", "all"):
        retrieve_and_generate(query, host, auth, model_id, k=args.top_k)


if __name__ == "__main__":
    main()
