# Architecture Report: AutoGen-DocIntel

**Project:** AutoGen-DocIntel — Multi-Agent Regulatory Compliance Intelligence Platform  
**Author:** Dev Desai  
**Organization:** Amneal Pharmaceuticals — Regulatory Affairs Division  
**Role:** AI Engineering Intern  
**Status:** Production-deployed internal tool, actively used by regulatory affairs analysts

---

## 1. System Overview

AutoGen-DocIntel is a multi-agent GenAI platform for pharmaceutical regulatory compliance that ingests regulatory submission documents, assesses risk across three compliance dimensions (Stability, Impurity, Validation), predicts specific issues per dimension, computes an overall risk score, and generates recommended remediation actions — all grounded in a Knowledge Graph of historical deficiency data and augmented by real-time internet access for current regulatory guidance.

The system serves the Regulatory Affairs team at Amneal Pharmaceuticals, where analysts manually review submission documents against FDA and ICH guidelines to identify potential deficiencies before regulatory filing. This manual process takes an average of 6–8 hours per document and is prone to inconsistency across reviewers, missed cross-references to historical deficiency patterns, and delayed access to the latest regulatory guidance updates. AutoGen-DocIntel reduces this to under 15 minutes per document by orchestrating a team of specialized AI agents — each responsible for a distinct compliance task — through Microsoft AutoGen's multi-agent conversation framework, with a supervisor agent coordinating the workflow and aggregating results into a structured risk report.

The platform stores all historical deficiency data, regulatory precedents, and document assessments in a Neo4j Knowledge Graph, enabling graph-traversal queries that surface deficiency patterns across product families, therapeutic areas, and regulatory jurisdictions that flat-file search cannot detect. The FAISS vector index provides semantic search over unstructured regulatory text (FDA warning letters, complete response letters, guidance documents), while the on-server LLM (Mistral-7B, deployed locally) has tool access to internet search for real-time regulatory intelligence — enabling the system to reference guidance documents published after the Knowledge Graph's last update.

### High-Level Data Flow

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         DOCUMENT INPUT LAYER                              │
│                                                                           │
│  ┌──────────────────┐    ┌──────────────────┐    ┌────────────────────┐  │
│  │  PDF/DOCX Upload  │    │  Structured Data  │    │  Historical        │  │
│  │  (Submission Doc)  │    │  (COA, Batch      │    │  Deficiency DB     │  │
│  │                    │    │   Records, Specs)  │    │  (FDA Letters)     │  │
│  └────────┬──────────┘    └────────┬──────────┘    └────────┬───────────┘  │
└───────────┼─────────────────────────┼───────────────────────┼─────────────┘
            │                         │                       │
            ▼                         ▼                       ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE LAYER (Dual Store)                            │
│                                                                           │
│  ┌─────────────────────────────┐  ┌────────────────────────────────────┐ │
│  │  Neo4j Knowledge Graph       │  │  FAISS Vector Index                │ │
│  │  • Deficiency entities       │  │  • Embedded regulatory text        │ │
│  │  • Product → deficiency      │  │  • FDA guidance chunks             │ │
│  │    relationships             │  │  • Historical CRL passages         │ │
│  │  • Temporal patterns         │  │  • Semantic similarity search      │ │
│  │  • Cross-product links       │  │                                    │ │
│  └──────────────┬──────────────┘  └──────────────────┬─────────────────┘ │
└─────────────────┼────────────────────────────────────┼───────────────────┘
                  │                                    │
                  ▼                                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                    AGENT ORCHESTRATION LAYER (AutoGen)                     │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  SUPERVISOR AGENT (Orchestrator)                                     │ │
│  │  Routes tasks, aggregates results, manages agent conversation flow   │ │
│  └──────┬──────────┬──────────────┬──────────────┬─────────────────────┘ │
│         │          │              │              │                        │
│         ▼          ▼              ▼              ▼                        │
│  ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────────┐       │
│  │ Document   │ │ Risk     │ │ Knowledge│ │ Recommendation       │       │
│  │ Parser     │ │ Assessor │ │ Retrieval│ │ Agent                │       │
│  │ Agent      │ │ Agent    │ │ Agent    │ │ (Internet-augmented) │       │
│  └───────────┘ └──────────┘ └──────────┘ └──────────────────────┘       │
│                                                                           │
│  Backbone LLM: Mistral-7B (on-server, GPTQ 4-bit)                       │
└───────────────────────────────────┬───────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                         OUTPUT LAYER                                      │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  Structured Risk Report (JSON + Rendered PDF)                     │    │
│  │                                                                    │    │
│  │  Per-dimension:   Stability  |  Impurity  |  Validation            │    │
│  │  Risk Level:      High/Med/Low                                     │    │
│  │  Predicted Issue: Missing Data | Limits Unclear | Acceptable       │    │
│  │  Evidence:        Retrieved passages + KG paths                    │    │
│  │                                                                    │    │
│  │  Overall Risk Score: 0–100                                         │    │
│  │  Recommended Actions: Prioritized remediation steps                │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Layer

### 2.1 Historical Deficiency Database

The primary knowledge source is a structured collection of historical regulatory deficiencies compiled from FDA Complete Response Letters (CRLs), Warning Letters, Form 483 observations, and internal audit findings related to Amneal's product portfolio. This corpus represents years of regulatory interaction data, curated by the Regulatory Affairs team.

Each deficiency record is structured with the following fields:

| Field | Type | Description |
|---|---|---|
| `deficiency_id` | String | Unique identifier |
| `product_name` | String | Drug product or API name |
| `therapeutic_area` | Categorical | Therapeutic classification |
| `deficiency_type` | Categorical | Stability / Impurity / Validation / Other |
| `severity` | Categorical | Critical / Major / Minor |
| `issue_category` | Categorical | Missing Data / Limits Unclear / Method Inadequate / Acceptable |
| `regulatory_body` | Categorical | FDA / EMA / Health Canada / etc. |
| `date_received` | Date | When the deficiency was issued |
| `resolution_action` | Text | How the deficiency was resolved |
| `resolution_time_days` | Integer | Days to resolution |
| `related_products` | List[String] | Cross-referenced products with similar issues |
| `document_section` | String | Section of submission where deficiency was found |
| `raw_text` | Text | Original deficiency language from the regulatory body |

The database contains approximately 2,800 deficiency records spanning 340 distinct products across 12 therapeutic areas. The records are ingested from internal compliance databases and manually curated regulatory correspondence.

### 2.2 Knowledge Graph (Neo4j)

The historical deficiency data is modeled as a property graph in Neo4j with the following node and relationship schema:

**Nodes:**

| Node Label | Key Properties | Count |
|---|---|---|
| `Product` | name, ndc_code, dosage_form, therapeutic_area | ~340 |
| `Deficiency` | deficiency_id, type, severity, issue_category, date | ~2,800 |
| `RegulatoryBody` | name, jurisdiction | 6 |
| `GuidanceDocument` | title, document_id, effective_date, url | ~180 |
| `Section` | name (e.g., "3.2.P.5.3 Validation of Analytical Procedures") | ~95 |
| `Resolution` | action_text, resolution_time_days, effectiveness_score | ~2,400 |

**Relationships:**

| Relationship | From → To | Properties |
|---|---|---|
| `HAS_DEFICIENCY` | Product → Deficiency | submission_date, cycle_number |
| `ISSUED_BY` | Deficiency → RegulatoryBody | letter_type, reference_number |
| `IN_SECTION` | Deficiency → Section | page_range |
| `RESOLVED_BY` | Deficiency → Resolution | date_resolved |
| `REFERENCES` | Deficiency → GuidanceDocument | cited_section |
| `SIMILAR_TO` | Deficiency → Deficiency | similarity_score (cosine) |
| `SAME_PRODUCT_FAMILY` | Product → Product | relationship_type |

The Knowledge Graph enables queries that flat-file search cannot: "Show all Stability deficiencies for extended-release dosage forms in the cardiovascular therapeutic area that cited ICH Q1A(R2), ranked by resolution time" — a query that traverses Product → Deficiency → GuidanceDocument → Section with filters on dosage_form, therapeutic_area, and resolution time. These graph-traversal patterns surface cross-product deficiency trends that inform the Risk Assessor Agent's predictions.

The graph is populated via a batch ETL pipeline that ingests records from the compliance database, resolves entity references (product name normalization, guidance document linking), and computes `SIMILAR_TO` edges using cosine similarity between deficiency text embeddings (threshold > 0.82).

### 2.3 FAISS Vector Index

Unstructured regulatory text — FDA guidance documents, historical deficiency letter language, ICH guideline passages, and internal SOP excerpts — is chunked (512-token windows, 64-token overlap), embedded using `all-MiniLM-L6-v2` sentence-transformer, and indexed in FAISS (IVF-Flat, 256 Voronoi cells, trained on the full corpus).

| Metric | Value |
|---|---|
| Total chunks indexed | ~18,400 |
| Embedding dimensions | 384 |
| Index type | IVF-Flat (256 cells) |
| Index size on disk | ~27 MB |
| Query latency (top-10, nprobe=16) | 3.8 ms |
| Recall@10 (vs brute-force baseline) | 96.7% |

FAISS is chosen over ChromaDB for this project because the corpus is significantly larger (~18,400 chunks vs the AAC project's ~2,000), query latency requirements are tighter (analysts expect near-instant retrieval in an interactive UI), and metadata filtering is handled by the Knowledge Graph rather than the vector store — so ChromaDB's native metadata filtering advantage does not apply. FAISS's IVF-Flat index provides sub-4ms retrieval at 96.7% recall, which meets the latency target.

### 2.4 Document Input Processing

Uploaded regulatory submission documents (PDF or DOCX) are processed through a multi-stage extraction pipeline:

1. **Text extraction** — PDF text is extracted via PyMuPDF (fitz); DOCX via python-docx. Scanned PDFs fall back to Tesseract OCR.
2. **Section segmentation** — The Document Parser Agent identifies ICH CTD (Common Technical Document) section boundaries using regex patterns matched against standard section numbering (e.g., "3.2.P.5.3", "3.2.S.7.1") and heading detection.
3. **Table extraction** — Structured data tables (stability data, impurity profiles, specification tables) are extracted using Camelot or Tabula and converted to pandas DataFrames for downstream numerical analysis.
4. **Entity extraction** — Product names, API names, specification limits, test methods, storage conditions, and time points are extracted using a combination of regex patterns and LLM-based named entity recognition via the Document Parser Agent.

The extraction pipeline achieves 94.3% accurate section identification across 20 document templates tested during development, measured as the percentage of correctly identified CTD section boundaries compared to manual annotation by a regulatory affairs analyst.

---

## 3. Agent Architecture (AutoGen)

### 3.1 Supervisor Agent

The Supervisor Agent orchestrates the multi-agent conversation flow using AutoGen's `GroupChat` with `GroupChatManager`. It implements a deterministic task routing protocol:

1. Receive uploaded document from the user.
2. Route to **Document Parser Agent** for extraction and structuring.
3. Route to **Knowledge Retrieval Agent** with extracted entities for historical context.
4. Route to **Risk Assessor Agent** with parsed document data + historical context for per-dimension risk evaluation.
5. Route to **Recommendation Agent** with risk assessment results for action generation.
6. Aggregate all agent outputs into the final structured risk report.
7. Return the report to the user via the UI.

The Supervisor uses AutoGen's `speaker_selection_method="round_robin"` for the deterministic pipeline stages, with a fallback to `"auto"` (LLM-based speaker selection) when agents need to request clarification from each other — for example, when the Risk Assessor identifies an ambiguous specification limit and needs the Document Parser to re-extract the relevant table.

The Supervisor maintains a shared conversation state (`GroupChat.messages`) that accumulates structured intermediate outputs from each agent. Each agent appends its results as a Pydantic-validated JSON block within its message, ensuring downstream agents receive type-safe structured data rather than free-text.

### 3.2 Document Parser Agent

**Role:** Extract structured content from uploaded regulatory submissions.

**Tools:**
- `extract_pdf_text(file_path)` — PyMuPDF text extraction
- `extract_tables(file_path, pages)` — Camelot/Tabula table extraction
- `segment_ctd_sections(text)` — Regex + LLM section boundary detection
- `extract_entities(text, section)` — NER for product names, limits, methods

**Output schema (Pydantic):**

```python
class ParsedDocument(BaseModel):
    product_name: str
    dosage_form: str
    sections: Dict[str, SectionContent]  # CTD section → content
    stability_data: Optional[List[StabilityTable]]
    impurity_profiles: Optional[List[ImpurityTable]]
    validation_summaries: Optional[List[ValidationSummary]]
    specification_limits: Dict[str, SpecLimit]
    extraction_confidence: float  # 0–1
```

The agent processes a typical 80-page regulatory submission in approximately 12 seconds, measured as wall-clock time from file upload to structured output emission on the deployed server hardware.

### 3.3 Knowledge Retrieval Agent

**Role:** Retrieve relevant historical deficiencies and regulatory guidance for the parsed document's product, dosage form, and identified sections.

**Tools:**
- `query_knowledge_graph(cypher_query)` — Execute Cypher queries against Neo4j
- `search_faiss(query_text, top_k, filters)` — Semantic search over regulatory text
- `get_similar_deficiencies(product, deficiency_type, top_k)` — Combined KG + FAISS retrieval

**Retrieval strategy:**

The agent executes a two-phase retrieval:

**Phase 1 — Structured graph query:** The agent constructs a Cypher query based on the parsed document's product name, dosage form, and therapeutic area to retrieve all historical deficiencies for the product and its related products:

```cypher
MATCH (p:Product)-[:HAS_DEFICIENCY]->(d:Deficiency)-[:IN_SECTION]->(s:Section)
WHERE p.name = $product_name OR (p)-[:SAME_PRODUCT_FAMILY]->(:Product {name: $product_name})
RETURN d, s, p
ORDER BY d.date DESC
LIMIT 50
```

**Phase 2 — Semantic vector search:** For each of the three compliance dimensions (Stability, Impurity, Validation), the agent queries FAISS with the extracted section text to find the most semantically similar historical deficiency language and relevant FDA guidance passages:

```python
stability_context = faiss_index.search(
    embed(parsed_doc.sections["3.2.P.8.1"]),  # Stability section text
    top_k=10
)
```

The two phases are fused by the agent, which formats the combined results as a structured context package for the Risk Assessor Agent. The Knowledge Retrieval Agent returns an average of 23.4 relevant passages per document query, measured across 150 test documents during development.

### 3.4 Risk Assessor Agent

**Role:** Evaluate risk across three compliance dimensions and predict specific issues.

**Tools:**
- `assess_stability(stability_data, context)` — Evaluate stability data completeness, trend analysis, specification compliance
- `assess_impurity(impurity_profiles, context)` — Evaluate impurity profiling, qualification thresholds, reporting limits
- `assess_validation(validation_summaries, context)` — Evaluate method validation parameters, system suitability, acceptance criteria
- `compute_overall_risk(dimension_risks)` — Weighted aggregation into 0–100 score

**Assessment logic per dimension:**

For each dimension, the Risk Assessor Agent applies a structured chain-of-thought evaluation:

1. **Completeness check** — Are all required data elements present per ICH guidelines (Q1A/Q1B for Stability, Q3A/Q3B for Impurity, Q2(R1) for Validation)?
2. **Specification compliance** — Do reported values fall within specified limits? Are limits themselves aligned with compendial or ICH thresholds?
3. **Trend analysis** — For stability data, do degradation trends suggest out-of-specification results at shelf-life? For impurity, do levels approach qualification thresholds?
4. **Historical pattern matching** — Does the Knowledge Graph context reveal that similar products or formulations previously received deficiencies on this dimension?
5. **Issue classification** — Based on findings, classify the predicted issue:
   - **Missing Data** — Required test results, time points, or parameters are absent.
   - **Limits Unclear** — Specification limits are not explicitly stated, inconsistent across sections, or misaligned with ICH thresholds.
   - **Acceptable** — Data is complete, within limits, and consistent with historical approvals.

**Output schema:**

```python
class DimensionRisk(BaseModel):
    dimension: Literal["Stability", "Impurity", "Validation"]
    risk_level: Literal["High", "Medium", "Low"]
    predicted_issue: Literal["Missing Data", "Limits Unclear", "Acceptable"]
    confidence: float  # 0–1
    evidence: List[EvidenceItem]  # Retrieved passages + KG paths supporting the assessment
    specific_findings: List[str]  # Human-readable finding statements

class RiskReport(BaseModel):
    dimensions: List[DimensionRisk]
    overall_risk_score: int  # 0–100
    risk_justification: str
```

The overall risk score is computed as a weighted sum: `Stability (0.35) + Impurity (0.35) + Validation (0.30)`, where each dimension is mapped to a numerical value (High=90, Medium=55, Low=15) and weighted by regulatory impact. The weights are calibrated based on historical deficiency frequency analysis: Stability and Impurity deficiencies each account for approximately 35% of total FDA CRL deficiencies in the therapeutic areas Amneal operates in, while Validation accounts for approximately 30%.

The Risk Assessor achieves 87.6% agreement with senior regulatory analyst assessments on a held-out evaluation set of 85 previously reviewed documents, measured as the percentage of (dimension, risk_level) pairs where the agent's assessment matches the analyst's ground-truth label.

### 3.5 Recommendation Agent (Internet-Augmented)

**Role:** Generate prioritized remediation actions based on the risk assessment, grounded in both historical resolutions and current regulatory guidance.

**Tools:**
- `search_web(query)` — Internet search via Tavily/SerpAPI for current FDA guidance, draft guidance documents, and recent enforcement actions
- `query_resolutions(deficiency_type, severity)` — Retrieve successful resolution actions from the Knowledge Graph
- `generate_action_plan(risk_report, context)` — LLM-based action plan generation with structured output

**Internet access rationale:** Regulatory guidance evolves continuously. FDA publishes draft guidance documents, final guidance revisions, and Compliance Policy Guides that can change compliance requirements between Knowledge Graph updates. The Recommendation Agent's internet access ensures it can reference guidance published after the last ETL batch — for example, a revised ICH Q1A stability testing guideline or a newly published FDA industry letter.

The agent generates recommendations in a structured format:

```python
class Recommendation(BaseModel):
    priority: Literal["Immediate", "Before Submission", "Advisory"]
    action: str  # Specific remediation step
    rationale: str  # Why this action addresses the identified risk
    reference: str  # Regulatory citation (ICH guideline, FDA guidance, or historical resolution)
    estimated_effort: str  # E.g., "2–3 weeks, requires additional stability study at accelerated condition"
```

The Recommendation Agent produces an average of 4.7 recommendations per document, with 91.2% of recommendations rated as "actionable" by regulatory analysts in a quality review of 60 generated reports, where "actionable" means the recommendation specifies a concrete step the team can execute without further interpretation.

---

## 4. Model Architecture

### 4.1 Backbone LLM: Mistral-7B (On-Server, GPTQ 4-bit)

All four agents share a single Mistral-7B backbone deployed on-server via GPTQ 4-bit quantization. The model is loaded once into GPU memory and accessed by each agent through AutoGen's `OpenAI`-compatible API wrapper pointing to a local vLLM or text-generation-inference (TGI) server.

| Parameter | Value |
|---|---|
| Model | Mistral-7B-Instruct-v0.3 |
| Quantization | GPTQ 4-bit |
| VRAM footprint | ~4.2 GB |
| Serving framework | vLLM with OpenAI-compatible API |
| Max context length | 8,192 tokens |
| Temperature (risk assessment) | 0.1 (near-deterministic for compliance tasks) |
| Temperature (recommendations) | 0.4 (slightly creative for action suggestions) |
| Structured output enforcement | Pydantic + constrained decoding via Outlines |

Mistral-7B is chosen over cloud LLMs (GPT-4, Claude) because pharmaceutical regulatory data is highly confidential — submission documents contain proprietary formulation details, manufacturing processes, and pre-approval clinical data that cannot be transmitted to external APIs. On-server deployment ensures all data remains within Amneal's network perimeter.

The model is served with temperature 0.1 for the Risk Assessor Agent (where deterministic, reproducible assessments are critical for regulatory consistency) and 0.4 for the Recommendation Agent (where slightly more creative generation produces more diverse and useful remediation suggestions).

### 4.2 Embedding Model

The sentence-transformer `all-MiniLM-L6-v2` (384 dimensions, 22M parameters) generates embeddings for FAISS indexing and query-time embedding. It runs on CPU with 6.4 ms per-embedding latency for single queries, measured on the server hardware. The model is chosen for its balance of embedding quality and inference speed — larger models (e.g., `instructor-xl`, `e5-large-v2`) provide marginally better retrieval quality but at 5–8× latency, which is unacceptable in an interactive application where analysts expect sub-second retrieval.

### 4.3 Knowledge Graph Query Generation

The Knowledge Retrieval Agent generates Cypher queries dynamically based on the parsed document's entities. Rather than hardcoding query templates, the agent uses the LLM to generate Cypher from natural language descriptions of the retrieval need, with a few-shot prompt containing 8 example (description → Cypher) pairs covering the most common query patterns. Generated queries are validated against the Neo4j schema before execution; malformed queries trigger a retry with error feedback injected into the agent's conversation.

The Cypher generation achieves 93.8% syntactically valid queries on the first attempt, measured across 200 test retrieval requests during development. With one retry, validity reaches 98.4%.

---

## 5. Evaluation

### 5.1 Risk Assessment Accuracy

The system is evaluated against ground-truth assessments from senior regulatory analysts on 85 previously reviewed submission documents. Each document has analyst-labeled (dimension, risk_level, predicted_issue) tuples for Stability, Impurity, and Validation.

**Per-dimension risk level agreement:**

| Dimension | Accuracy | Precision (High) | Recall (High) | F1 (High) |
|---|---|---|---|---|
| Stability | 88.2% | 0.86 | 0.91 | 0.88 |
| Impurity | 87.1% | 0.83 | 0.89 | 0.86 |
| Validation | 87.6% | 0.85 | 0.87 | 0.86 |
| **Weighted Average** | **87.6%** | **0.85** | **0.89** | **0.87** |

**Predicted issue classification accuracy:**

| Issue Category | Precision | Recall | F1 |
|---|---|---|---|
| Missing Data | 0.91 | 0.88 | 0.89 |
| Limits Unclear | 0.82 | 0.79 | 0.80 |
| Acceptable | 0.89 | 0.93 | 0.91 |
| **Macro Average** | **0.87** | **0.87** | **0.87** |

"Limits Unclear" is the hardest category — it requires the agent to detect subtle inconsistencies between specification limits stated in different document sections, which depends on both extraction accuracy and cross-section reasoning. This is an active area of improvement.

### 5.2 Retrieval Quality

| Metric | FAISS Only | KG Only | KG + FAISS (Fused) |
|---|---|---|---|
| Precision@10 | 0.72 | 0.68 | 0.84 |
| Recall@10 | 0.81 | 0.76 | 0.91 |
| MRR | 0.69 | 0.73 | 0.82 |

The fused KG + FAISS retrieval outperforms either source alone by 12+ points on Precision@10, confirming that structured graph relationships and unstructured semantic similarity provide complementary signals. The Knowledge Graph excels at surfacing precedent-based context (same product family, same regulatory body), while FAISS excels at finding semantically similar deficiency language across unrelated products.

### 5.3 Recommendation Quality

60 generated risk reports are reviewed by two senior regulatory analysts. Each recommendation is rated on a 3-point scale:

| Rating | Criteria | Percentage |
|---|---|---|
| Actionable | Specific, executable, correctly referenced | 91.2% |
| Partially Actionable | Correct direction but too vague or missing reference | 6.5% |
| Not Actionable | Incorrect, irrelevant, or misleading | 2.3% |

Inter-rater agreement (Cohen's κ) between the two analysts is 0.84, indicating strong consistency.

### 5.4 Time Savings

| Metric | Manual Process | AutoGen-DocIntel | Improvement |
|---|---|---|---|
| Average review time per document | 6.8 hours | 14.2 minutes | 96.5% reduction |
| Average risk assessments per day per analyst | 1.2 documents | 18+ documents | 15× throughput |
| Missed cross-reference rate | 12.3% | 2.1% | 83% reduction |

---

## 6. Serving Layer

### 6.1 API Design (FastAPI)

The system exposes a FastAPI REST API with the following endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/documents/upload` | POST | Upload regulatory submission (PDF/DOCX), returns job_id |
| `/documents/{job_id}/status` | GET | Check processing status (queued/parsing/assessing/complete) |
| `/documents/{job_id}/report` | GET | Retrieve completed risk report (JSON) |
| `/documents/{job_id}/report/pdf` | GET | Retrieve rendered PDF risk report |
| `/knowledge-graph/query` | POST | Execute ad-hoc Cypher query against Neo4j |
| `/search` | POST | Semantic search over FAISS index |
| `/agents/conversation` | WebSocket | Real-time agent conversation stream for UI |
| `/health` | GET | Health check (LLM server, Neo4j, FAISS index) |

The WebSocket endpoint streams the agent conversation in real time, allowing analysts to observe which agent is currently active, what retrieval queries are being executed, and what intermediate findings are emerging — providing full transparency into the AI's reasoning process.

### 6.2 User Interface (Streamlit)

The Streamlit dashboard provides:

- **Document upload panel** with drag-and-drop PDF/DOCX support.
- **Real-time agent activity feed** showing the AutoGen conversation as it executes — analysts see which agent is speaking, what tools it's invoking, and what intermediate results it's producing.
- **Risk dashboard** with color-coded cards (red/yellow/green) for each dimension, the overall risk score as a gauge chart, and predicted issues with evidence links.
- **Recommendation panel** with prioritized actions, each expandable to show the regulatory citation and historical resolution precedent.
- **Knowledge Graph explorer** — an interactive Neo4j Browser-style visualization where analysts can explore the deficiency network around the current product.
- **Document viewer** with highlighted sections corresponding to identified risk areas, linked directly to the Risk Assessor's evidence citations.

### 6.3 Latency Characteristics

| Component | Latency | Conditions |
|---|---|---|
| Document parsing (80-page PDF) | 12.3 sec | PyMuPDF + Camelot + LLM entity extraction |
| FAISS retrieval (3 dimensions × top-10) | 11.4 ms | IVF-Flat, nprobe=16, 384-dim embeddings |
| Neo4j graph query (per dimension) | 45.2 ms | Cypher traversal, warm cache, ~2,800 nodes |
| Risk assessment (per dimension) | 8.4 sec | Mistral-7B, temperature=0.1, structured output |
| Recommendation generation | 11.7 sec | Mistral-7B, temperature=0.4, internet search included |
| **Total end-to-end (full report)** | **~52 sec** | **Single document, all 4 agents, GPU inference** |

The 52-second total includes document parsing (12s), three parallel risk assessments (8.4s × 3 = 25.2s, but serialized due to single GPU = 25.2s), recommendation generation (11.7s), and overhead (3.1s). The risk assessments are serialized because the single Mistral-7B instance processes one agent request at a time. With multi-GPU or batched inference, the three dimension assessments could be parallelized to reduce total time to approximately 35 seconds.

---

## 7. Monitoring and Observability

### 7.1 Structured Logging

Every agent interaction is logged as a structured JSON event:

- **`agent_message`** — Agent name, message content, tools invoked, tool results, timestamp, token count.
- **`retrieval_event`** — FAISS query vector, top-k results with scores, Cypher query string, Neo4j result count.
- **`risk_assessment_event`** — Dimension, input features, predicted risk level, predicted issue, confidence score, evidence passages used.
- **`recommendation_event`** — Generated actions, internet search queries executed, regulatory references cited.
- **`user_feedback`** — Analyst's override of risk level or issue category (when they disagree with the system), used for continuous improvement tracking.

### 7.2 Analyst Feedback Loop

When analysts disagree with the system's assessment, they override the risk level or issue category in the UI. These overrides are logged with the full agent reasoning chain that produced the original assessment, creating a growing dataset of correction pairs. This data is reviewed monthly to identify systematic failure patterns and inform prompt refinement or retrieval strategy adjustments.

Override rate across the first 150 production documents: 8.4% of dimension-level assessments are overridden, with 62% of overrides being escalations (agent rated Low, analyst corrected to Medium or High) and 38% being de-escalations.

---

## 8. Testing and CI/CD

### 8.1 Test Suite

The repository contains 31 test files with 214 total test cases:

- **Unit tests** for document parsing: section segmentation on 8 template variants, table extraction accuracy on 15 sample tables, entity extraction on 40 annotated passages.
- **Unit tests** for retrieval: FAISS index build/query consistency, Neo4j Cypher generation from 20 natural language descriptions, Knowledge Graph schema validation.
- **Integration tests** for the agent pipeline: end-to-end document upload → risk report generation on 5 representative documents, validating output schema compliance and non-empty evidence lists.
- **Regression tests** for known failure cases: 12 documents where earlier versions produced incorrect assessments, with assertions that current pipeline produces correct risk levels.
- **Agent conversation tests** — Verify that the Supervisor correctly routes to each agent in sequence and that agents produce Pydantic-valid JSON outputs.

Test suite achieves 84.7% line coverage on the core pipeline modules (agents, retrieval, parsing, risk assessment).

### 8.2 CI/CD

The CI pipeline runs on GitHub Actions:

1. Linting (ruff) on all Python source.
2. Unit tests via pytest with coverage reporting.
3. Schema validation — all Pydantic models are tested for serialization/deserialization round-trips.
4. A lightweight smoke test that loads Mistral-7B, executes a single risk assessment prompt, and validates the output structure.

Full integration tests (requiring GPU, Neo4j, and FAISS index) run nightly on the deployment server.

---

## 9. Deployment Infrastructure

### 9.1 Server Deployment

The system is deployed on Amneal's internal server infrastructure, not cloud-hosted — regulatory submission data cannot leave the corporate network.

- **Runtime:** Python 3.11
- **LLM serving:** vLLM with OpenAI-compatible API, serving Mistral-7B GPTQ 4-bit
- **API server:** FastAPI + Uvicorn, 4 worker processes behind nginx reverse proxy
- **Knowledge Graph:** Neo4j Community Edition 5.x, running on the same server
- **Vector index:** FAISS loaded in-process by the FastAPI workers (shared memory via mmap)
- **UI:** Streamlit, served on internal port, accessible via corporate VPN
- **GPU:** NVIDIA A100 40GB (shared with other internal AI workloads; Mistral-7B uses ~4.2 GB)
- **RAM:** 64 GB system RAM (Neo4j ~8 GB, FAISS mmap ~27 MB, application overhead ~4 GB)
- **Storage:** 500 GB SSD for document storage, Knowledge Graph persistence, and FAISS index

### 9.2 Security

- All endpoints require corporate SSO authentication via OAuth 2.0.
- Document uploads are stored in an encrypted volume; files are purged after 90 days per data retention policy.
- The LLM server is not exposed to the internet; only the Recommendation Agent's internet search tool has outbound access, routed through a corporate proxy with domain allowlisting restricted to FDA.gov, ICH.org, and approved regulatory databases.
- Agent conversation logs are stored in an audit-compliant logging system accessible only to authorized personnel.

---

## 10. Key Engineering Decisions

### 10.1 AutoGen Multi-Agent over Single-Model Monolith

**Chosen:** Four specialized agents orchestrated by a Supervisor via AutoGen's GroupChat.  
**Over:** A single LLM handling all tasks via a long prompt.  
**Why:** A monolithic prompt would need to simultaneously parse documents, query a Knowledge Graph, assess risk, and generate recommendations — exceeding the 8,192-token context window and producing unreliable results when the model attempts to "hold" all intermediate state in a single generation. The multi-agent architecture decomposes the problem: each agent has a focused system prompt, access to specific tools, and produces structured intermediate output. This is debuggable (each agent's reasoning is logged independently), composable (new agents can be added without modifying existing ones), and robust (a failure in one agent doesn't corrupt the entire pipeline).

### 10.2 Knowledge Graph (Neo4j) over Relational Database

**Chosen:** Neo4j property graph for historical deficiency data.  
**Over:** PostgreSQL with relational tables.  
**Why:** Regulatory deficiency patterns are inherently graph-structured: a product has deficiencies, which reference guidance documents, which cite sections, which are similar to deficiencies on related products. A 3-hop query like "find all deficiencies on products in the same family as Product X that cited ICH Q3B and were resolved by additional testing" requires multiple JOINs in SQL that become complex, slow, and hard to maintain. In Neo4j, this is a single Cypher traversal with clear semantics. The `SIMILAR_TO` relationship between deficiencies — computed via embedding cosine similarity — enables the system to discover non-obvious deficiency patterns across therapeutic areas that would require a full-text-search + manual analysis workflow in a relational system.

### 10.3 FAISS over ChromaDB

**Chosen:** FAISS IVF-Flat for vector search.  
**Over:** ChromaDB.  
**Why:** The regulatory text corpus (~18,400 chunks) is large enough that retrieval latency matters for interactive use. FAISS IVF-Flat achieves 3.8 ms query latency at 96.7% recall@10, compared to ChromaDB's typical 15–25 ms for similar corpus sizes. Metadata filtering — ChromaDB's key advantage — is unnecessary here because structured filtering is handled by Neo4j Cypher queries upstream. FAISS's index-only architecture (no embedded server, no persistence layer overhead) also simplifies deployment: the index is a single file loaded via mmap, consuming minimal RAM.

### 10.4 Deterministic Routing over LLM-Based Speaker Selection

**Chosen:** `round_robin` speaker selection for the main pipeline stages, with `auto` fallback only for inter-agent clarification.  
**Over:** Full `auto` (LLM-based) speaker selection throughout.  
**Why:** In a regulatory compliance system, the processing order must be deterministic and auditable. If the LLM-based speaker selector occasionally routes the Risk Assessor before the Document Parser has finished, the assessment runs on incomplete data — a silent failure that could produce an incorrect risk report with no error signal. Deterministic routing ensures the pipeline executes in the correct order every time, while the `auto` fallback preserves the flexibility for agents to request clarification from each other when needed.

### 10.5 Mistral-7B Local over Cloud LLMs

**Chosen:** Mistral-7B GPTQ 4-bit, served locally via vLLM.  
**Over:** GPT-4 or Claude via API.  
**Why:** Regulatory submission documents contain highly confidential pre-approval data — formulation compositions, manufacturing process parameters, dissolution profiles, bioequivalence study results. Transmitting this data to cloud APIs violates Amneal's information security policy and potentially FDA 21 CFR Part 11 electronic records requirements. Local deployment keeps all data within the corporate network. Mistral-7B at 4-bit quantization fits within the shared A100's available memory and provides sufficient reasoning capability for the structured risk assessment task, as validated by the 87.6% analyst agreement rate.

### 10.6 Pydantic Structured Outputs over Free-Text Agent Communication

**Chosen:** Every agent emits Pydantic-validated JSON in its messages; downstream agents parse structured data, not free text.  
**Over:** Agents communicating in natural language, with downstream agents extracting information via LLM parsing.  
**Why:** Free-text inter-agent communication introduces parsing fragility: if the Risk Assessor's natural-language output uses a slightly different format than the Recommendation Agent expects, the pipeline fails silently or produces incorrect recommendations. Pydantic schemas enforce type safety at every handoff point. If an agent's output doesn't conform to the schema, the system raises an immediate validation error rather than propagating malformed data downstream. This is critical in a regulatory context where an incorrect risk level or missing evidence citation has real compliance consequences.

### 10.7 Dual-Temperature Strategy over Uniform Temperature

**Chosen:** Temperature 0.1 for Risk Assessment, temperature 0.4 for Recommendations.  
**Over:** A single temperature for all agents.  
**Why:** Risk assessment must be deterministic and reproducible — if two analysts upload the same document, they must receive the same risk levels. Temperature 0.1 ensures near-deterministic generation, where the same input produces effectively identical outputs across runs. Recommendation generation benefits from slightly higher diversity — different phrasings and approaches to remediation make the suggestions more useful to analysts who may have already considered the obvious options. The 0.4 temperature provides this diversity without introducing hallucination risk.

### 10.8 Internet Access for Recommendation Agent Only

**Chosen:** Only the Recommendation Agent has outbound internet access; all other agents operate on local data.  
**Over:** Giving all agents internet access.  
**Why:** The attack surface of internet-connected LLM agents includes prompt injection via web content, data exfiltration via crafted search queries, and information poisoning via malicious web pages. Restricting internet access to a single agent through a domain-allowlisted corporate proxy (FDA.gov, ICH.org, and approved regulatory databases only) minimizes this surface. The Risk Assessor, which produces the compliance-critical risk levels, operates exclusively on local Knowledge Graph and FAISS data — its outputs cannot be influenced by external web content.

---

## 11. Known Limitations

**Single-company training data:** The historical deficiency database reflects Amneal's product portfolio and regulatory interaction patterns. The system's risk predictions may not generalize to companies with different product mixes, therapeutic areas, or regulatory strategies.

**OCR fallback quality:** Scanned PDF submissions processed via Tesseract OCR achieve lower extraction accuracy (~82% character-level accuracy) compared to text-based PDFs (~99.6%). This affects downstream risk assessment quality for legacy documents.

**Knowledge Graph freshness:** The Neo4j graph is updated via batch ETL on a weekly cadence. Deficiencies received between ETL runs are not reflected in the graph until the next batch. The Recommendation Agent's internet access partially compensates for this lag regarding public regulatory guidance, but internal deficiency data has up to 7 days of latency.

**"Limits Unclear" detection:** This issue category has the lowest F1 score (0.80) because it requires cross-section reasoning — comparing specification limits stated in the Quality Overall Summary with those in the individual study reports. Improving this requires either longer context windows or a dedicated cross-section verification agent.

**Single-GPU serialization:** The three dimension assessments are serialized on a single Mistral-7B instance, contributing approximately 25 seconds to the 52-second total pipeline time. Multi-GPU or batch inference would reduce this to approximately 8–10 seconds per document.

---

## 12. Repository Structure

```
AutoGen-DocIntel/
├── README.md                          # System overview, setup, quick start
├── requirements.txt
├── pyproject.toml
├── .github/workflows/                 # CI pipeline (lint, test, smoke)
├── src/
│   ├── agents/
│   │   ├── supervisor.py              # AutoGen GroupChat + manager config
│   │   ├── document_parser.py         # Document extraction agent
│   │   ├── knowledge_retrieval.py     # KG + FAISS retrieval agent
│   │   ├── risk_assessor.py           # Risk assessment agent
│   │   └── recommendation.py          # Internet-augmented recommendation agent
│   ├── knowledge/
│   │   ├── graph.py                   # Neo4j connection, Cypher helpers
│   │   ├── faiss_index.py             # FAISS build, query, mmap loading
│   │   ├── embeddings.py              # Sentence-transformer embedding
│   │   └── etl.py                     # Batch ETL pipeline for KG population
│   ├── parsing/
│   │   ├── pdf_extractor.py           # PyMuPDF + Tesseract OCR
│   │   ├── table_extractor.py         # Camelot/Tabula table extraction
│   │   ├── section_segmenter.py       # CTD section boundary detection
│   │   └── entity_extractor.py        # NER for regulatory entities
│   ├── models/
│   │   ├── schemas.py                 # All Pydantic models (ParsedDocument, RiskReport, etc.)
│   │   └── risk_weights.py            # Dimension weights, severity mappings
│   ├── api/
│   │   ├── main.py                    # FastAPI app, endpoints
│   │   ├── websocket.py               # Agent conversation streaming
│   │   └── auth.py                    # OAuth 2.0 SSO integration
│   └── ui/
│       └── app.py                     # Streamlit dashboard
├── tests/
│   ├── test_parsing/                  # 8 template variants, 15 tables, 40 entity tests
│   ├── test_retrieval/                # FAISS, Cypher generation, schema validation
│   ├── test_agents/                   # Agent conversation flow, Pydantic output validation
│   ├── test_integration/              # End-to-end on 5 representative documents
│   └── test_regression/               # 12 known failure cases
├── data/
│   ├── deficiency_records/            # Anonymized historical deficiency exports
│   ├── guidance_chunks/               # Pre-chunked regulatory text for FAISS
│   └── evaluation/                    # 85 analyst-labeled ground-truth documents
├── scripts/
│   ├── build_faiss_index.py           # Index construction script
│   ├── populate_knowledge_graph.py    # Neo4j ETL execution
│   └── evaluate.py                    # Run evaluation suite
└── docker-compose.yml                 # Neo4j + vLLM + FastAPI + Streamlit
```

---

*Published internally at Amneal Pharmaceuticals, Regulatory Affairs Division. The system is deployed on corporate infrastructure and accessed by authorized regulatory affairs analysts via corporate VPN.*
