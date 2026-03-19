# OpenSearch Data Ingestion: Architectures, Chunking, and the Neural Plugin

> **Context**: This document covers the data ingestion landscape for Amazon
> OpenSearch — specifically for vector search and RAG workloads. It answers:
> what are the ingestion options, how do they handle chunking, and when should
> you use each one?

---

## Table of Contents

1. [The Three Ingestion Paths](#the-three-ingestion-paths)
2. [Neural Ingest Pipeline (Built Into OpenSearch)](#neural-ingest-pipeline-built-into-opensearch)
3. [OpenSearch Ingestion (OSI) — Managed Pipeline Service](#opensearch-ingestion-osi--managed-pipeline-service)
4. [Lambda-Based Ingestion](#lambda-based-ingestion)
5. [Chunking Strategies: What Exists and What Doesn't](#chunking-strategies-what-exists-and-what-doesnt)
6. [Multi-Pipeline Architectures](#multi-pipeline-architectures)
7. [Decision Framework: Which Ingestion Path?](#decision-framework-which-ingestion-path)
8. [Our Demo Architecture](#our-demo-architecture)
9. [References](#references)

---

## The Three Ingestion Paths

There are three distinct ways to get data into an OpenSearch vector index.
They operate at different layers and are often confused with each other.

```
                                ┌─────────────────────────────┐
                                │   Amazon OpenSearch Service  │
                                │  ┌───────────────────────┐  │
  ┌──────────┐    Path A        │  │ Neural Ingest Pipeline │  │
  │ Your App ├──── _doc API ───►│  │  (text_embedding proc) │  │
  │ / Lambda │                  │  │  Calls Bedrock/SM for  │  │
  └──────────┘                  │  │  embeddings at index   │  │
                                │  │  time — automatic      │  │
  ┌──────────┐    Path B        │  └───────────────────────┘  │
  │   OSI    ├── bulk API ─────►│                             │
  │ Pipeline │   (managed)      │  ┌───────────────────────┐  │
  └──────────┘                  │  │  Vector Index (kNN)    │  │
                                │  │  text + 1024d vectors  │  │
  ┌──────────┐    Path C        │  └───────────────────────┘  │
  │  Lambda  ├── _doc API ─────►│                             │
  │ + custom │   (your code)    └─────────────────────────────┘
  │ chunking │
  └──────────┘
```

| Path | What It Is | Who Handles Chunking | Who Handles Embeddings |
|------|-----------|---------------------|----------------------|
| **A. Neural Ingest Pipeline** | OpenSearch-internal processor chain | You (before sending) | OpenSearch (automatic via pipeline) |
| **B. OSI Pipeline** | Managed AWS service *outside* OpenSearch | OSI (`text_chunking` processor) or Lambda processor | OSI (`ml_inference` processor) or OpenSearch neural pipeline |
| **C. Lambda + Neural Pipeline** | Custom code + OpenSearch pipeline | Lambda (your code) | OpenSearch (automatic via pipeline) |

**Key insight**: Paths B and C both ultimately push documents into OpenSearch,
where Path A's neural ingest pipeline can *still* auto-generate embeddings.
They are complementary, not mutually exclusive.

---

## Neural Ingest Pipeline (Built Into OpenSearch)

This is the `neural-ingest-pipeline` we configured in our demo. It's an
OpenSearch-internal processor — not a separate AWS service.

### How It Works

When a document is indexed into an index that has a `default_pipeline` set,
OpenSearch intercepts the document and runs it through the pipeline's
processors before storing it. Our pipeline has one processor:

```json
{
  "text_embedding": {
    "model_id": "<registered-model-id>",
    "field_map": { "content": "embedding" }
  }
}
```

This calls Bedrock Titan Embeddings V2 via the ML connector, generates a
1024-dimensional vector from the `content` field, and stores it in the
`embedding` field — **all automatically, server-side**.

### What It Does NOT Do

- ❌ Read from S3 or other sources
- ❌ Chunk documents
- ❌ Extract metadata
- ❌ Route different document types

It only generates embeddings for documents that arrive at the index. Everything
upstream — reading files, chunking text, extracting metadata — must happen
before the document reaches OpenSearch.

### Verification

```bash
# Check the pipeline exists and is attached
GET /legal-documents/_settings
# → "default_pipeline": "neural-ingest-pipeline"

# Index a text-only document (no embedding field)
POST /legal-documents/_doc
{ "content": "Fourth Amendment privacy protections..." }

# Retrieve it — embedding field is auto-generated
GET /legal-documents/_doc/<id>
# → "embedding": [0.004303, 0.008802, 0.051674, ...] (1024 values)
```

---

## OpenSearch Ingestion (OSI) — Managed Pipeline Service

OSI is a **separate AWS service** that sits outside OpenSearch. It's built on
the [Data Prepper](https://opensearch.org/docs/latest/data-prepper/) open-source
project and provides managed, serverless data pipelines.

### What OSI Can Do

```yaml
# Example OSI pipeline configuration
version: "2"
log-pipeline:
  source:
    s3:
      notification_type: "sqs"
      codec:
        newline: {}
      sqs:
        queue_url: "https://sqs.us-west-2.amazonaws.com/123456789/my-queue"
      aws:
        region: "us-west-2"
  processor:
    - text_chunking:                    # Step 1: Chunk text
        algorithm:
          fixed_token_length:
            token_limit: 384
            overlap_rate: 0.2
    - ml_inference:                     # Step 2: Generate embeddings
        model_id: "<model-id>"
        input_map:
          - input_field: "content"
        output_map:
          - output_field: "embedding"
  sink:
    - opensearch:                       # Step 3: Index into OpenSearch
        hosts: ["https://<collection-id>.us-west-2.aoss.amazonaws.com"]
        index: "my-index"
```

### OSI's `text_chunking` Processor — Two Algorithms Only

| Algorithm | How It Splits | Parameters |
|-----------|--------------|------------|
| **`fixed_token_length`** | Counts tokens, splits at limit | `token_limit`, `overlap_rate` (0.0–0.5), `tokenizer` |
| **`delimiter`** | Splits on a character/string | `delimiter` (e.g., `\n\n`, `.`, `---`) |

**That's it.** No semantic chunking. No hierarchical chunking. No
sentence-boundary detection. No document-structure awareness.

### Processor Chaining (Pseudo-Hierarchical)

You *can* chain multiple `text_chunking` processors to approximate
structure-aware splitting:

```yaml
processor:
  - text_chunking:
      algorithm:
        delimiter:
          delimiter: "\n\n"           # First: split by paragraphs
  - text_chunking:
      algorithm:
        fixed_token_length:
          token_limit: 384            # Then: enforce max size
          overlap_rate: 0.2
```

This preserves paragraph boundaries where possible while ensuring no chunk
exceeds the token limit. It's the closest OSI gets to hierarchical chunking
natively.

### Custom Logic: The Lambda Processor

For anything beyond fixed-size or delimiter splitting, OSI offers the
`aws_lambda` processor — a bridge to custom code:

```yaml
processor:
  - aws_lambda:
      function_name: "my-custom-chunker"
      max_retries: 3
      batch_options:
        batch_key: "events"
        threshold:
          event_count: 10
```

The Lambda receives a batch of events, applies any logic you want
(semantic chunking via LangChain, document parsing via Docling, etc.),
and returns the modified events. **Constraints**:

- 5 MB payload limit per batch
- Lambda cold-start latency applies
- Requires `lambda:InvokeFunction` permission on the OSI pipeline role

---

## Lambda-Based Ingestion

This is what our demo uses: a Lambda function that handles the entire
upstream pipeline, then pushes chunks to OpenSearch where the neural
ingest pipeline generates embeddings.

### What Lambda Handles (Our Demo)

```
S3 (raw-docs/*.txt)
  → S3 Event Notification
    → Lambda (legal-doc-processor)
      1. Download .txt from S3
      2. Detect document type (case brief, contract, statute, etc.)
      3. Extract metadata (author, date, topics, case numbers)
      4. Semantic chunking (paragraph-aware, ~500 token target, 2-sentence overlap)
      5. POST each chunk to OpenSearch /legal-documents/_doc
         → Neural ingest pipeline auto-generates embeddings
      6. Write metadata + chunk tracking to DynamoDB
```

The Lambda does sophisticated, domain-specific processing that OSI's
native processors can't replicate — document type classification,
regex-based entity extraction, paragraph-aware semantic chunking with
configurable overlap.

---

## Chunking Strategies: What Exists and What Doesn't

### Native Support Across the Ecosystem

| Strategy | OSI (text_chunking) | OpenSearch Ingest | Bedrock KB | Lambda |
|----------|:------------------:|:-----------------:|:----------:|:------:|
| Fixed token/size | ✅ | ✅ | ✅ | ✅ |
| Delimiter-based | ✅ | ✅ | ❌ | ✅ |
| Sentence-boundary | ❌ | ❌ | ❌ | ✅ (NLP libs) |
| Paragraph-aware | ❌ (use delimiter `\n\n`) | ❌ | ❌ | ✅ |
| Semantic (topic-shift) | ❌ | ❌ | ✅ | ✅ (LangChain) |
| Hierarchical (parent-child) | ❌ | ❌ | ✅ | ✅ |
| Document-structure (headings, tables) | ❌ | ❌ | ❌ | ✅ (Docling, Unstructured) |
| Custom / pluggable | Via Lambda processor | ❌ | ❌ | Full control |

### The Semantic Chunking Gap

Neither OSI nor OpenSearch's built-in ingest pipeline supports semantic
chunking — splitting text based on topic shifts or meaning boundaries.
The options for semantic chunking are:

1. **Bedrock Knowledge Bases** — offers semantic chunking out of the box,
   but you give up control over the vector store configuration
2. **Lambda with NLP libraries** — LangChain's `SemanticChunker`, NLTK
   sentence tokenizers, or spaCy for entity-aware splitting
3. **Pre-processing pipeline** — Docling, Unstructured.io, or PyMuPDF
   for structure-aware parsing *before* any chunking

### Can Users Define Custom Chunking Strategies in OSI?

**Not as native processors, no.** OSI's processor list is fixed (Data Prepper
built-ins). You cannot write a custom OSI processor plugin and deploy it to
the managed service.

The **only extensibility mechanism** is the `aws_lambda` processor, which
lets you call arbitrary code. So the answer is: yes, via Lambda, with the
5 MB payload constraint.

An open RFC ([opensearch-project/neural-search#794](https://github.com/opensearch-project/neural-search/issues/794))
proposes model-based tokenization for the `text_chunking` processor, but
it's not yet implemented.

---

## Multi-Pipeline Architectures

### Can I Create Separate OSI Pipelines for Different S3 Prefixes?

**Yes, absolutely.** Three patterns:

### Pattern 1: Sub-Pipelines with Conditional Routing (Single OSI Pipeline)

```yaml
version: "2"
# Entry pipeline reads from S3
entry-pipeline:
  source:
    s3:
      notification_type: "sqs"
      sqs:
        queue_url: "https://sqs.../my-queue"
  route:
    - contracts: '/s3/key =~ "contracts/.*"'
    - case_law:  '/s3/key =~ "case-law/.*"'
  sink:
    - pipeline:
        name: "contracts-pipeline"
      routes: ["contracts"]
    - pipeline:
        name: "case-law-pipeline"
      routes: ["case_law"]

# Different chunking + different models per document type
contracts-pipeline:
  source:
    pipeline:
      name: "entry-pipeline"
  processor:
    - text_chunking:
        algorithm:
          fixed_token_length:
            token_limit: 256          # Shorter chunks for contracts
    - ml_inference:
        model_id: "<cohere-embed-model>"
  sink:
    - opensearch:
        index: "contracts-index"

case-law-pipeline:
  source:
    pipeline:
      name: "entry-pipeline"
  processor:
    - text_chunking:
        algorithm:
          fixed_token_length:
            token_limit: 512          # Longer chunks for case law
    - ml_inference:
        model_id: "<titan-embed-model>"
  sink:
    - opensearch:
        index: "case-law-index"
```

**Constraint**: Only *one* sub-pipeline can have an external source (S3, DynamoDB, etc.).
All others receive events from sibling sub-pipelines.

### Pattern 2: Separate OSI Pipelines (Full Isolation)

Deploy completely independent pipelines — each with its own S3 source config,
SQS queue, processor chain, and IAM role. Best for:
- Different scaling requirements
- Independent failure domains
- Different teams managing different document types

### Pattern 3: Three-Pipeline Batch Architecture

For cost-efficient bulk processing of large corpuses:

```
Pipeline 1: S3 → text_chunking → S3 staging (chunked docs)
Pipeline 2: S3 staging → batch ml_inference (Bedrock) → S3 results
Pipeline 3: S3 results → transform → OpenSearch index
```

Leverages batch inference pricing instead of real-time per-request costs.

---

## Decision Framework: Which Ingestion Path?

```
                    ┌──────────────────────────────┐
                    │ What type of documents?       │
                    └──────────┬───────────────────┘
                               │
              ┌────────────────┼────────────────────┐
              ▼                ▼                     ▼
    ┌─────────────┐   ┌──────────────┐    ┌──────────────────┐
    │ Simple text  │   │ Mixed types  │    │ Complex (PDF,    │
    │ Fixed format │   │ Some need    │    │ images, tables,  │
    │              │   │ custom logic │    │ scanned docs)    │
    └──────┬──────┘   └──────┬───────┘    └────────┬─────────┘
           │                 │                      │
           ▼                 ▼                      ▼
      ┌─────────┐     ┌──────────────┐      ┌────────────────┐
      │   OSI   │     │ OSI + Lambda │      │    Lambda +    │
      │ Native  │     │  Processor   │      │ Neural Ingest  │
      └─────────┘     └──────────────┘      │   Pipeline     │
                                            └────────────────┘
```

| Factor | OSI Native | OSI + Lambda Processor | Lambda + Neural Pipeline |
|--------|:----------:|:----------------------:|:------------------------:|
| **Chunking** | Fixed-size, delimiter | Custom (any library) | Custom (any library) |
| **Embeddings** | OSI `ml_inference` or neural pipeline | OSI `ml_inference` or neural pipeline | Neural pipeline (auto) |
| **Infrastructure** | Fully managed | Managed + Lambda | Lambda + OpenSearch |
| **Scaling** | Auto (OCU-based) | Auto + Lambda concurrency | Lambda concurrency |
| **Document parsing** | Basic (text only) | Custom via Lambda | Full control |
| **Multi-destination** | OpenSearch only | OpenSearch only | OpenSearch + DynamoDB + anything |
| **Ops burden** | Low | Medium | Higher |
| **Cost model** | OCU-hours | OCU-hours + Lambda | Lambda invocations |
| **Best for** | Logs, catalogs, CMS content | Mixed workloads | Complex docs, multi-store writes |

### Quick Decision Rules

- **"I just want to index text files with embeddings"** → OSI native
- **"I have PDFs, contracts, and need entity extraction"** → Lambda + neural pipeline
- **"Most docs are simple but some need special handling"** → OSI + Lambda processor
- **"I need to write to both OpenSearch AND DynamoDB"** → Lambda + neural pipeline
- **"I want zero infrastructure to manage"** → Bedrock Knowledge Bases
- **"I'm backfilling millions of existing records"** → Three-pipeline batch pattern

---

## Our Demo Architecture

Our Legal Research RAG demo uses **Path C: Lambda + Neural Ingest Pipeline**
because:

1. **Domain-specific document types** — case briefs, contracts, statutes,
   legal memos each have different structure and metadata patterns
2. **Custom metadata extraction** — regex-based entity extraction for case
   numbers, party names, statute references
3. **Paragraph-aware semantic chunking** — ~500 token target with 2-sentence
   overlap, respecting paragraph boundaries
4. **Dual-write requirement** — chunks go to OpenSearch for search, metadata
   goes to DynamoDB for tracking and filtering
5. **Neural pipeline handles embeddings** — Lambda doesn't call Bedrock
   directly; the OpenSearch neural ingest pipeline auto-generates 1024d
   Titan V2 embeddings server-side

```
S3 raw-docs/*.txt
    │
    ├── S3 Event Notification ──► Lambda (legal-doc-processor)
    │                               │
    │                               ├── Detect document type
    │                               ├── Extract metadata (author, date, topics)
    │                               ├── Semantic chunk (~500 tokens, 2-sentence overlap)
    │                               │
    │                               ├──► OpenSearch /legal-documents/_doc
    │                               │       └── Neural Ingest Pipeline (auto)
    │                               │            └── Bedrock Titan V2 → 1024d embedding
    │                               │
    │                               └──► DynamoDB (LegalDocMetadata)
    │                                     └── document_id, chunk_id, status, metadata
    │
    └── Query Path:
         User query ──► Hybrid Search (70% semantic / 30% keyword)
                         ├── neural: Titan V2 encodes query → kNN similarity
                         └── match: BM25 keyword scoring
```

---

## References

1. [Supported plugins and options for Amazon OpenSearch Ingestion — AWS Developer Guide](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/pipeline-config-reference.html)
2. [Text chunking processor — OpenSearch Documentation](https://docs.opensearch.org/latest/ingest-pipelines/processors/text-chunking/)
3. [AWS Lambda processor — OpenSearch Data Prepper](https://opensearch.org/docs/latest/data-prepper/pipelines/configuration/processors/aws-lambda/)
4. [Using an OpenSearch Ingestion pipeline with AWS Lambda — AWS Developer Guide](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/configure-client-lambda.html)
5. [Overview of pipeline features in Amazon OpenSearch Ingestion — AWS Developer Guide](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/osis-features-overview.html)
6. [Batch inference with OSI pipelines — AWS Developer Guide](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/configure-clients-ml-commons-batch.html)
7. [Configure neural search in Amazon OpenSearch Serverless — AWS Developer Guide](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-configure-neural-search.html)
8. [Generate vector embeddings using AWS Lambda as a processor for Amazon OSI — AWS Big Data Blog](https://aws.amazon.com/blogs/big-data/generate-vector-embeddings-for-your-data-using-aws-lambda-as-a-processor-for-amazon-opensearch-ingestion/)
9. [Configure machine learning on OpenSearch Serverless — AWS Developer Guide](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-configure-machine-learning.html)
10. [Building powerful RAG pipelines with Docling and OpenSearch — OpenSearch Blog](https://opensearch.org/blog/building-powerful-rag-pipelines-with-docling-and-opensearch/)
11. [RFC: Model-based Tokenizer — opensearch-project/neural-search#794](https://github.com/opensearch-project/neural-search/issues/794)
12. [Advanced usage of the semantic field in OpenSearch — OpenSearch Blog](https://opensearch.org/blog/advanced-usage-of-the-semantic-field-in-opensearch/)
