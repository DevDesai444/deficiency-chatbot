# DefPredict — System Pipeline (file-level data & logic flow)

This is the exact pipeline as implemented, stage by stage, with the source file and
function for every step and the data object that flows out of it.

## Data object evolution (the "json thing" as it mutates down the pipeline)

```
PDF bytes
  └─(parse)→        PDFDocument { pages: [PageContent{ text, tables:[ExtractedTable] }], toc }
  └─(skip+split)→   ParsedSection[]        # cover page + change-history dropped, re-cut by headings
  └─(group)→        ChunkGroup[]           # 5 sections per group  (deterministic, ceil(n/5))
  └─(extraction)→   IntermediateReport { sections:[SectionSummary], findings:[ExtractionFinding], consensus_notes }
  └─(detection)→    FlawReport { findings:[FlawFinding], consensus_summary, agents_participated }
  └─(correction)→   RecommendationSet { recommendations:[Correction], flaws_found, loop counts }
```

## Full flowchart

```mermaid
flowchart TD

%% ============================= API LAYER =============================
subgraph API["🌐 API LAYER — src/api/"]
  UP["PDF upload (≤50MB, ≥100B)"] --> ANALYZE["POST /api/analyze<br/><b>routes/upload.py :: analyze()</b><br/>job_id = uuid4.hex[:12]<br/>save → UPLOAD_DIR/{job_id}_{name}.pdf"]
  ANALYZE -->|"{job_id, status: accepted}"| CLIENT["Client polls / opens WebSocket"]
  ANALYZE --> BG["BackgroundTask<br/><b>routes/upload.py :: pipeline_runner()</b><br/>runs pipeline, then deletes upload"]
  APP["main.py :: FastAPI app<br/>mounts health / upload / results / ws"]
end

BG --> ORCH

%% ============================= ORCHESTRATOR =============================
subgraph ORCHESTRATOR["🎬 ORCHESTRATOR — src/agents/orchestrator.py :: run_pipeline()"]
  ORCH["create_job() → status=extracting"] --> P1
  P1["1) doc = extract_pdf(pdf)"] --> P2
  P2["2) ctd = classify_document(doc)"] --> P3
  P3["3) sections = split_document(doc)"] --> P4
  P4["4) groups = group_sections(sections)"] --> P5
  P5["5) run_extraction(groups) → IntermediateReport"] --> P6
  P6["6) run_flaw_detection(report) → FlawReport"] --> P7
  P7["7) run_correction_loop(flaws) → RecommendationSet"] --> P8
  P8["status=complete, store recommendations"]
end

%% ============================= PARSE =============================
subgraph PARSE["📄 PARSE — src/parse/"]
  direction TB
  E1["<b>pdf.py :: extract_pdf()</b><br/>fitz.open (PyMuPDF), get_toc()"] --> E2{"<b>ocr.py :: is_scanned_page()</b><br/>image &gt;50% of page<br/>OR glyphless font?"}
  E2 -->|yes| E3["<b>ocr.py :: ocr_page()</b><br/>render 200dpi PNG → base64<br/>POST Databricks endpoint<br/>'defpredict-rapidocr' (RapidOCR)<br/>→ text regions + boxes<br/><b>layout.py :: reconstruct_page()</b><br/>boxes → lines (spaces) + tables"]
  E2 -->|no| E4["page.get_text('text')<br/>(embedded text layer)"]
  E3 -->|"creds missing / call fails"| E4
  E1 --> ET["<b>pdf.py :: extract_tables()</b><br/>page.find_tables() → ExtractedTable<br/>(digital pages; scans add OCR tables)"]
  E3 --> EOUT["PDFDocument"]
  E4 --> EOUT
  ET --> EOUT
end
P1 -.calls.-> E1
EOUT -.returns.-> P1

%% ============================= SPLIT =============================
subgraph SPLIT["✂️ SECTION SPLIT — src/parse/section_splitter.py"]
  direction TB
  C1["<b>classify_document()</b><br/>TOC regex → headers → filename<br/>e.g. 3.2.S.4.3 → S_4_3_VALIDATION"]
  S1["<b>split_document()</b>"] --> S2["<b>_skip_cover_and_history()</b><br/>drop page 1 + trailing history"]
  S2 --> S3["<b>_split_by_internal_sections()</b><br/>concat text, regex numbered headings<br/>_is_probable_heading filter<br/>attach tables by title/number"]
  S3 --> S4["ParsedSection[]"]
  G1["<b>group_sections(max=5)</b><br/>ceil(n/5) → ChunkGroup[]<br/>⚠ DETERMINISTIC — no LLM"]
end
P2 -.calls.-> C1
P3 -.calls.-> S1
P4 -.calls.-> G1
S4 --> G1

%% ============================= EXTRACTION LAYER =============================
subgraph EXTRACT["🧩 EXTRACTION LAYER — src/agents/extraction/  (N agents = N groups)"]
  direction TB
  X1["<b>group.py :: run_extraction()</b>"] --> X2["per group: <b>agent.py :: make_extraction_agent()</b><br/>Extractor_group_0 … group_k<br/>+ make_extraction_moderator"]
  X2 --> X3["<b>RoundRobinGroupChat</b> (AutoGen)<br/>task = build_extraction_prompt(group)<br/>section.text[:4000] + tables<br/>stop on 'EXTRACTION_COMPLETE'"]
  X3 --> X4["per group: <b>structured_call(STRUCTURED_EXTRACTOR)</b><br/>→ GroupExtract (temp=0)"]
  X4 --> X5["<b>anchor.py :: filter_anchored()</b><br/>DROP any span not in source text<br/>digit-exact, ratio≥0.92 — no rewrite"]
  X5 --> X6["IntermediateReport"]
end
P5 -.calls.-> X1
X6 --> P5

%% ============================= DETECTION LAYER =============================
subgraph DETECT["🔎 FLAW DETECTION LAYER — src/agents/detection/  (M agents = LLM's pick)"]
  direction TB
  D0["<b>classifier.py :: select_flaw_types()</b><br/>⭐ LLM chooses which categories apply<br/>prompt=FLAW_TYPE_SELECTOR + flaw_catalog<br/>fallback = ALL 15 FLAW_TYPE_DEFINITIONS"]
  D0 --> D1["per type: <b>agent.py :: make_flaw_agent()</b><br/>+ make_flaw_moderator (70B)"]
  D1 --> D2["<b>SelectorGroupChat</b> (AutoGen)<br/>candidate_func: each speaks once → moderator<br/>task = describe_document + IntermediateReport JSON<br/>+ historical RAG context<br/>stop on 'CONSENSUS_REACHED'"]
  D2 --> D3["<b>_extract_structured_findings()</b><br/>chat_completion(FINDING_EXTRACTOR)<br/>→ FlawFinding[]"]
  D3 --> D4["FlawReport"]
end
P6 -.calls.-> D0
D4 --> P6

%% RAG side-feed into detection
subgraph RAG["🗃️ RETRIEVAL / RAG — src/retrieval + src/databricks"]
  R1["knowledge_base.py :: get_deficiencies_by_type()"] --> R2["delta.py :: query_deficiencies()<br/>(Databricks Delta table)"]
  R3["vector.py :: search_similar()<br/>vector_search.py :: embed_query()"]
end
D2 -.historical context.-> R1

%% ============================= CORRECTION LAYER =============================
subgraph CORRECT["🛠️ CORRECTION LAYER — src/agents/correction/loop.py :: run_correction_loop()"]
  direction TB
  K0{"flaws_found?"} -->|no| KEMPTY["RecommendationSet (empty)"]
  K0 -->|yes| K1["<b>suggestor.py :: generate_corrections()</b><br/>structured_call(SUGGESTOR)<br/>model = suggestor_endpoint"]
  K1 --> K2["<b>evaluator.py :: evaluate_corrections()</b><br/>structured_call(EVALUATOR)<br/>model = evaluator_endpoint"]
  K2 --> K3{"Verdict"}
  K3 -->|PASS| KOK["RecommendationSet (approved)"]
  K3 -->|MINOR_REVISION| K1
  K3 -->|DEEPER_REVIEW| KBREAK["break outer loop"]
  KLOOP["loops: max_inner_loops=3 × (max_outer_loops+1)=2"]
end
P7 -.calls.-> K0
KOK --> P7
KEMPTY --> P7

%% ============================= EVENTS / STATUS =============================
subgraph EVENTS["📡 LIVE EVENTS & STATUS (cross-cutting)"]
  EV1["event_bus.py :: emit_sync()<br/>AgentEvent(job_id, layer, type, agent, msg)"] --> EV2["in-memory queues per job_id"]
  EV2 --> EV3["api/ws.py :: WebSocket → frontend live stream"]
  ST1["databricks/delta.py :: update_job_status()<br/>extracting→detecting→correcting→complete"]
  RES["api/routes/results.py :: GET results"]
end
ORCH -.every stage.-> EV1
ORCH -.state.-> ST1
P8 --> RES

%% ============================= LLM PLUMBING =============================
subgraph LLM["🤖 LLM PLUMBING — src/llm/ + config.py"]
  L1["client.py :: chat_completion()"]
  L2["structured.py :: structured_call()<br/>(schema-validated + JSON repair)"]
  L3["prompts.py :: all system prompts"]
  L4["config.py :: get_settings()<br/>resolved_llm_model (8B agents)<br/>moderator_model (70B)<br/>suggestor_endpoint / evaluator_endpoint"]
end
```

## Per-stage reference table

| # | Stage | File :: function | Input | Output | LLM? |
|---|-------|------------------|-------|--------|------|
| 0 | Upload | `api/routes/upload.py :: analyze` | PDF | `job_id`, spawns background task | no |
| 1 | Parse | `parse/pdf.py :: extract_pdf` (+ `ocr.py`) | PDF path | `PDFDocument` | RapidOCR (Databricks) for scanned pages |
| 2 | Classify | `parse/section_splitter.py :: classify_document` | `PDFDocument` | `CTDSection` | no (regex; LLM only as fallback in `classifier.py`) |
| 3 | Split | `parse/section_splitter.py :: split_document` | `PDFDocument` | `ParsedSection[]` | no |
| 4 | Group | `parse/section_splitter.py :: group_sections` | `ParsedSection[]` | `ChunkGroup[]` | **no — deterministic ceil(n/5)** |
| 5 | Extraction | `agents/extraction/group.py :: run_extraction` | `ChunkGroup[]` | `IntermediateReport` | yes (N agents + moderator, RoundRobin) |
| 5b | Anchor guard | `agents/extraction/anchor.py :: filter_anchored` | extract + source | pruned findings | no — deterministic |
| 6a | Select flaw types | `agents/detection/classifier.py :: select_flaw_types` | `IntermediateReport` | `list[str]` | **yes — LLM decides M agents** |
| 6b | Detection | `agents/detection/group.py :: run_flaw_detection` | `IntermediateReport` | `FlawReport` | yes (M agents + 70B moderator, Selector) |
| 6c | Structure findings | `..detection/group.py :: _extract_structured_findings` | consensus text | `FlawFinding[]` | yes |
| 7a | Suggest | `agents/correction/suggestor.py :: generate_corrections` | `FlawReport` | `Correction[]` | yes |
| 7b | Evaluate | `agents/correction/evaluator.py :: evaluate_corrections` | corrections | `Verdict` + feedback | yes |
| 7 | Correction loop | `agents/correction/loop.py :: run_correction_loop` | `FlawReport` | `RecommendationSet` | orchestrates 7a↔7b |

## Two facts your mental model had slightly off

1. **Parsed output is NOT passed bit-for-bit to the extraction LLM.** It is cover/history-stripped, re-cut by headings, table-reattached, grouped, then truncated to `section.text[:4000]` per section by `build_extraction_prompt`.
2. **The "LLM that decides how many agents" only exists for the *detection* layer** (`select_flaw_types`). The *extraction* agent count is deterministic (one per `ChunkGroup`).
