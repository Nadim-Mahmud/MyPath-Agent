# MyPath Evaluation Results
**Chapter 6 — LLM Evaluation for Wheelchair-Accessible Campus Navigation**
Thesis: *MyPath: An AI-Powered Wheelchair Accessibility Navigation Assistant*
Author: Nadim Mahmud · Miami University Oxford, OH · 2026

---

## 1. System Overview

MyPath is a FastAPI-based agentic assistant that helps wheelchair users navigate Miami University's Oxford campus. The LLM (cloud or local) orchestrates three MCP tools in a multi-round loop:

| Tool | Purpose |
|------|---------|
| `geocode_place` | Resolve building name → GPS coordinates (Nominatim/OSM) |
| `get_route` | Compute wheelchair-accessible path (GraphHopper routing server) |
| `get_place_accessibility` | Retrieve OSM wheelchair accessibility metadata |

A successful response requires the LLM to: (1) geocode both endpoints, (2) call `get_route` with valid coordinates, (3) return a structured `route_action` with origin/destination. Failure at any step produces a non-routable response.

---

## 2. Evaluation Dataset

**File:** `evaluation/mypath_od_pairs_1.json`

| Property | Value |
|----------|-------|
| Total OD pairs | 50 |
| Campus | Miami University, Oxford OH (39.508°N, 84.734°W) |
| Buildings | 20 campus buildings |
| Categories | 4 (described below) |

### 2.1 Dataset Categories

| Category | Pairs | Description |
|----------|-------|-------------|
| `common` | 20 | Well-known campus buildings, unambiguous names |
| `cross_campus` | 10 | Less-visited buildings, longer routes |
| `problematic` | 10 | Buildings with known OSM data issues or geocoding conflicts |
| `ambiguous` | 10 | Informal names ("the library", "the gym", "Benton Hall") |

### 2.2 Ground Truth

Each pair includes `dest_coords {lat, lon}` ground-truth coordinates. A route is flagged as **wrong location (mode B)** if the returned destination coordinate is >500 m from ground truth (Haversine distance).

---

## 3. Methodology

### 3.1 Harness Design

**File:** `evaluation/mypath_eval_harness.py`

- Each OD pair is sent as a natural-language query to `POST /chat`
- Each pair uses a unique `session_id` (format: `eval_{pair_id}_r{run}_XXXXXXXX`) to prevent cross-pair history contamination
- 3 independent runs per pair per model
- Results classified per run, aggregated per pair

### 3.2 Failure Mode Taxonomy

| Mode | Label | Trigger Condition |
|------|-------|------------------|
| A | Geocoding scope failure | No `route_action` returned; message references location not found or wrong institution |
| B | Wrong location resolved | `route_action` returned but destination >500 m from ground truth |
| C | Routing engine no path | No `route_action`; message references routing/path failure |
| D | Apologetic despite route | `route_action` present but message contains apologetic phrases |
| E | Timeout / HTTP error | Network or server error during request |

### 3.3 Success Metrics

| Metric | Definition |
|--------|-----------|
| **Route success** | ≥1 of 3 runs returned a valid `route_action` with correct destination |
| **Geocoding success** | ≥1 of 3 runs returned any `route_action` (regardless of accuracy) |
| **WC valid** | Equals route success (routing engine is wheelchair-only by design) |
| **Consistent (3/3)** | All 3 runs agreed: either all succeeded or all failed |
| **Mean latency** | Average response time in ms across all 150 records |

### 3.4 Model Switching

- **Gemini models**: Backend restarted via `docker compose up --no-deps ai-core` with `GEMINI_MODEL` env var override
- **Ollama models**: Same mechanism with `LLM_PROVIDER=ollama` + `OLLAMA_MODEL` env vars
- Ollama runs at `http://host.docker.internal:11434` (Mac host, Docker bridge)
- Inter-request delay: 8 s for Gemini (free-tier RPM limit), 1 s for Ollama (local, no rate limits)

### 3.5 Backend Code Changes for Evaluation

| File | Change | Reason |
|------|--------|--------|
| `ai-core/app/constants.py` | `LLM_RETRY_BASE_DELAY_S`: 1.5 s → 10.0 s | Space out 429 retries within Gemini RPM window |
| `ai-core/app/llm/gemini.py` | Added 429 to retryable status codes | Rate-limit errors now retry instead of failing immediately |
| `ai-core/app/llm/ollama.py` | New file — OllamaProvider | Enables local model evaluation |
| `ai-core/app/config.py` | Added `LLM_PROVIDER`, `OLLAMA_MODEL`, `OLLAMA_BASE_URL` | Environment-driven provider selection |
| `ai-core/app/dependencies.py` | Provider selection based on `LLM_PROVIDER` | Routes to Gemini or Ollama at startup |
| `docker-compose.yml` | Added Ollama env vars to `environment:` block | Passes env vars into container |

---

## 4. Experiment 1 — Baseline Model (gemini-1.5-flash)

**CSV:** `results_gemini-1-5-flash_20260626_002153.csv`
**Rows:** 150 (50 pairs × 3 runs) · **Date:** 2026-06-26

> **Model note:** `gemini-1.5-flash` is deprecated on this API key; automatically aliased to `gemini-3.1-flash-lite-preview` by the harness.

### 4.1 Overall Results

| Metric | Value |
|--------|-------|
| Route generation success (≥1/3 runs) | **32/50 (64.0%)** |
| Geocoding success (≥1/3 runs) | 42/50 (84.0%) |
| Wheelchair route validity | 32/50 (64.0%) |
| Strongly consistent (3/3 agree success) | 23/50 (46.0%) |
| Inconsistent (1–2/3 runs succeed) | 9/50 (18.0%) |
| Consistently failed (0/3 runs) | 18/50 (36.0%) |
| Overall consistency rate | 41/50 (82.0%) |
| Mean latency — corrected (runs 1+2) | **11,004 ms** |
| Median latency — corrected (runs 1+2) | 9,236 ms |

> **Latency note:** Run 3 was severely rate-limited (Gemini free-tier daily quota near exhaustion). Individual pair latencies in run 3 ranged from 338 s to 1,075 s due to 429 retry back-off. All latency figures exclude run 3 to reflect true inference time.

### 4.2 Results by Category

| Category | Pairs | Geocode Success | Route Success |
|----------|-------|-----------------|---------------|
| common | 20 | 19/20 (95%) | 19/20 (95%) |
| cross_campus | 10 | 7/10 (70%) | 4/10 (40%) |
| problematic | 10 | 9/10 (90%) | 4/10 (40%) |
| ambiguous | 10 | 7/10 (70%) | 5/10 (50%) |

### 4.3 Failure Mode Distribution (150 run records)

| Mode | Count | % of failures |
|------|-------|--------------|
| A — Geocoding scope failure | 44 | 66.7% |
| B — Wrong location resolved | 22 | 33.3% |
| C — Routing engine no path | 0 | — |
| D — Apologetic despite route | 0 | — |
| E — Timeout / HTTP error | 0 | — |

### 4.4 Consistently Failed Pairs (0/3 runs)

| Pair | Category | Route | Root Cause |
|------|----------|-------|-----------|
| C1_09 | common | Hughes Hall → King Library | Hughes Hall geocodes to Cambridge UK |
| C2_01 | cross_campus | Pearson Hall → Boyd Hall | Pearson Hall resolves to different campus |
| C2_02 | cross_campus | Hughes Hall → Peabody Hall | Hughes Hall → Cambridge UK |
| C2_05 | cross_campus | Benton Hall → Peabody Hall | Benton Hall → Berkeley CA |
| C2_07 | cross_campus | King Library → Boyd Hall | Boyd Hall coords 609 m off in OSM |
| C2_08 | cross_campus | Hughes Hall → Bachelor Hall | Hughes Hall → Cambridge UK |
| C2_09 | cross_campus | Garland Hall → Peabody Hall | Garland Hall → Johns Hopkins |
| C3_01 | problematic | Benton Hall → Elliot Hall | Benton Hall → Berkeley CA |
| C3_02 | problematic | King Library → Hiestand Hall | Hiestand Hall coords 662 m off in OSM |
| C3_04 | problematic | Upham Hall → Hiestand Hall | Hiestand Hall coords 662 m off in OSM |
| C3_07 | problematic | Benton Hall → Peabody Hall | Benton Hall → Berkeley CA |
| C3_09 | problematic | MacMillan Hall → Boyd Hall | Boyd Hall resolved to Kentucky (164 km off) |
| C3_10 | problematic | Roudebush Hall → Hiestand Hall | Hiestand Hall coords 662 m off in OSM |
| C4_01 | ambiguous | Benton Hall → "the library" | Benton Hall → Berkeley, library → Chicago |
| C4_03 | ambiguous | Benton Hall → "student center" | Benton Hall → Berkeley CA |
| C4_04 | ambiguous | "engineering building" → King Library | Engineering building → London UK |
| C4_08 | ambiguous | Garland → Armstrong | Single-word names resolve off-campus |
| C4_10 | ambiguous | Hughes Hall → "the gym" | Hughes Hall → Cambridge, gym → Los Angeles |

### 4.5 Root Cause Analysis

1. **Geocoding scope (Mode A — 44 occurrences):** Nominatim has no campus-scope constraint. Buildings with common names (Hughes Hall, Benton Hall, Garland Hall) resolve to identically-named buildings at Cambridge UK, UC Berkeley, and Johns Hopkins respectively. The LLM correctly detects the cross-city conflict and refuses to route.

2. **OSM coordinate errors (Mode B — 22 occurrences):** Three buildings have incorrect GPS coordinates in OpenStreetMap relative to Miami University's actual layout:
   - **Hiestand Hall**: resolves to 39.5057, −84.7326 (662 m south of actual position)
   - **Boyd Hall**: resolves to 39.5036, −84.7253 (609 m southeast of actual position)
   - **Peabody Hall**: resolves to 39.5016, −84.7258 (680 m south of actual)
   - **Anomaly — MacMillan→Boyd (C3_09)**: Boyd Hall resolved to Lexington KY (164 km off); likely an OSM node collision

3. **Inconsistent pairs (9 pairs):** These pairs succeed in 1–2 of 3 runs, suggesting sensitivity to minor prompt variation or geocoding result ordering. Nominatim result ranking is non-deterministic for tied candidates.

---

## 5. Experiment 2 — Multi-Model Comparison

**Date:** 2026-06-26

### 5.1 Models Evaluated

| Model | Provider | Size | Tool Calling | CSV File |
|-------|----------|------|-------------|----------|
| gemini-1.5-flash | Google Gemini (cloud) | — | Native function calling | `results_gemini-1-5-flash_20260626_002153.csv` |
| qwen2.5:3b | Ollama (local) | 1.9 GB | Yes — calls tools but accepts wrong-city results | `results_qwen2-5:3b_20260626_155257.csv` |
| llama3.2:3b | Ollama (local) | 2.0 GB | Partial — calls tools but leaks system context | `results_llama3-2:3b_20260626_174917.csv` |
| phi4-mini | Ollama (local) | 2.5 GB | Supported by API but model ignores tool calls | `results_phi4-mini_20260626_184200.csv` |
| gemma3:4b | Ollama (local) | 3.3 GB | **Not supported** — Ollama HTTP 400 | Not evaluated |

### 5.2 Overall Comparison Table

| Model | Route Success | Geocode Success | WC Valid | Consistent | Mean Lat (ms) |
|-------|--------------|-----------------|----------|------------|---------------|
| gemini-1.5-flash | **32/50 (64%)** | 42/50 (84%) | 32/50 (64%) | 41/50 (82%) | 11,004 † |
| qwen2.5:3b | 5/50 (10%) | 43/50 (86%) | 5/50 (10%) | 45/50 (90%) | 45,477 |
| llama3.2:3b | 0/50 (0%) | 28/50 (56%) | 0/50 (0%) | 50/50 (100%) | 12,030 |
| phi4-mini | 0/50 (0%) | 0/50 (0%) | 0/50 (0%) | 50/50 (100%) | 11,738 |

† Gemini latency corrected: excludes rate-limit-inflated run 3 (raw mean = 114,442 ms).
‡ llama3.2:3b and phi4-mini consistency=100% reflects consistent total failure (0/3 for all 50 pairs).

### 5.3 Route Success by Category

| Model | common (20) | cross_campus (10) | problematic (10) | ambiguous (10) |
|-------|------------|-------------------|------------------|----------------|
| gemini-1.5-flash | 19/20 (95%) | 4/10 (40%) | 4/10 (40%) | 5/10 (50%) |
| qwen2.5:3b | 2/20 (10%) | 1/10 (10%) | 1/10 (10%) | 1/10 (10%) |
| llama3.2:3b | 0/20 (0%) | 0/10 (0%) | 0/10 (0%) | 0/10 (0%) |
| phi4-mini | 0/20 (0%) | 0/10 (0%) | 0/10 (0%) | 0/10 (0%) |

### 5.4 Failure Mode Breakdown (150 records per model)

| Model | A (Geocode) | B (Wrong loc) | C (No route) | D (Apologetic) | E (Error) |
|-------|-------------|---------------|--------------|----------------|-----------|
| gemini-1.5-flash | 44 | 22 | 0 | 0 | 0 |
| qwen2.5:3b | 64 | 72 | 9 | 0 | 0 |
| llama3.2:3b | 56 | 56 | 38 | 0 | 0 |
| phi4-mini | 133 | 0 | 17 | 0 | 0 |

### 5.5 Per-Model Analysis

#### gemini-1.5-flash (cloud baseline)
- **Strength:** Reliable tool orchestration (geocode → route in correct sequence). 95% success on unambiguous common pairs.
- **Weakness:** No geocoding scope constraint → fails on buildings with same name at other universities. OSM coordinate errors for 3 buildings (Hiestand, Boyd, Peabody) cause mode B failures.
- **Failure pattern:** A + B dominated (66% + 33%). No routing or timeout failures.

#### qwen2.5:3b (best local model)
- **Strength:** Successfully calls geocoding and routing tools. Geocoding success comparable to Gemini (86% per-pair ≥1 run).
- **Weakness:** Accepts geocoding results without sanity-checking coordinates. Routes from Oxford OH to buildings in Illinois, Indiana, California, Australia.
- **Failure pattern:** Heavy mode B (wrong city/country coordinates accepted as valid). Mean latency 45 s indicates multi-round tool loops before giving up.
- **Route success:** 5/50 (10%) — 6.4× worse than Gemini.

#### llama3.2:3b
- **Behavior:** Makes tool calls but leaks raw system context into user-facing responses (JSON snippets, GPS coordinates, routing engine errors visible in output). Tools partially called but routing consistently failed.
- **Anomaly:** geocode_success=56/150 records (mode B) yet route_success=0 — routes were generated to wrong locations but all >500 m threshold.
- **Safety concern:** System prompt context leak is a privacy/UX issue beyond just accuracy.
- **Failure pattern:** A=56, B=56, C=38. All 50 pairs consistently failed across all 3 runs.

#### phi4-mini (Microsoft Phi-4 Mini, 3.8B)
- **Behavior:** Tool calling API supported by Ollama but model consistently ignores tools. Generates plausible-sounding but entirely fabricated route descriptions (fake street names, invented distances). In later runs, began refusing requests ("I'm MyPath Assistant, I can't help with that").
- **Geocoding success:** 0/50 — no tool calls means no route_action ever returned.
- **Hallucination risk:** High — model produces confident, detailed, completely fictional routes.
- **Failure pattern:** A=133 (no tool calls → no route_action → classified as geocoding failure), C=17 (routing keywords in refusal messages).

#### gemma3:4b (not evaluated)
- Ollama API returned HTTP 400: `"gemma3:4b does not support tools"`. Cannot be used with function-calling evaluation harness. Not included in comparison.

---

## 6. Key Findings

### Finding 1: Cloud vs. Local Performance Gap
Gemini (cloud) outperforms the best local model (qwen2.5:3b) by **6.4×** on route success rate (64% vs. 10%). No local model achieved >10% route success. This gap is not explained by model size alone — the dominant factor is reliable tool-call orchestration.

### Finding 2: Tool Orchestration is the Binding Constraint
All local models had geocoding infrastructure available (same Nominatim endpoint) but failed to exploit it:
- phi4-mini: ignored tools entirely, hallucinated routes
- llama3.2:3b: called tools but couldn't complete the geocode→route sequence
- qwen2.5:3b: called tools correctly but didn't validate geocoding results

Gemini's superior instruction-following at function-calling is the primary differentiator.

### Finding 3: Geocoding Scope is the Binding Constraint for Gemini
Among Gemini's 66 failures (150 − 84 successes), 44 (67%) are mode A: buildings resolved to identically-named locations at other universities. Adding a campus-scope bounding box to Nominatim queries would likely raise route success from 64% to ~75–80%.

### Finding 4: OSM Data Quality Affects All Models Equally
Three buildings (Hiestand Hall, Boyd Hall, Peabody Hall) have incorrect GPS coordinates in OpenStreetMap. These failures appear regardless of model — they are infrastructure failures, not LLM failures. OSM data correction would eliminate ~15% of remaining failures.

### Finding 5: Consistency Reveals Model Reliability
- **Gemini:** 82% consistency — 9 pairs are genuinely borderline (1–2/3 runs succeed)
- **Local models:** 90–100% consistency — consistent total failure, no borderline cases
- qwen2.5:3b's 90% consistency hides 5 pairs where 1 run accidentally succeeded (likely a different geocoding result order)

### Finding 6: Local Model Safety Concerns
Beyond accuracy, local models introduce qualitative safety issues:
- **llama3.2:3b:** Leaks system context (raw JSON, GPS coordinates) into user responses
- **phi4-mini:** Confidently fabricates routes that do not exist — higher risk for safety-critical accessibility navigation than a refusal

---

## 7. Files Inventory

```
eval_results/
├── EVALUATION_README.md                          ← This file
├── experiment1_summary.txt                       ← Exp 1 detailed summary (gemini-1.5-flash)
├── experiment2_summary.txt                       ← Exp 2 comparison table (all 4 models)
├── results_gemini-1-5-flash_20260626_002153.csv  ← 150 rows, Exp 1 baseline
├── results_qwen2-5:3b_20260626_155257.csv        ← 150 rows, Ollama local
├── results_llama3-2:3b_20260626_174917.csv       ← 150 rows, Ollama local
├── results_phi4-mini_20260626_184200.csv          ← 150 rows, Ollama local
└── [earlier prototype CSVs — not used in analysis]
    ├── results_gemini-3-1-flash-lite-preview_20260625_234342.csv
    ├── results_gemini-3-1-flash-lite-preview_20260625_234722.csv
    └── results_gemini-3-1-flash-lite-preview_20260625_234803.csv

evaluation/
├── mypath_eval_harness.py    ← Full evaluation harness
└── mypath_od_pairs_1.json    ← 50 OD pair dataset
```

### CSV Schema

| Column | Type | Description |
|--------|------|-------------|
| model | str | Requested model name (e.g. `gemini-1.5-flash`) |
| run | int | Run index (1–3) |
| pair_id | str | OD pair ID (e.g. `C1_01`) |
| category | str | `common` / `cross_campus` / `problematic` / `ambiguous` |
| origin | str | Origin building name |
| destination | str | Destination building name |
| query | str | Natural language query sent to the system |
| geocode_success | bool | True if `route_action` was returned |
| route_success | bool | True if route valid and destination within 500 m of ground truth |
| wc_valid | bool | Same as route_success (routing engine is wheelchair-only) |
| failure_mode | str | A / B / C / D / E or empty on success |
| failure_detail | str | Truncated response or distance error message |
| latency_ms | int | End-to-end response time in milliseconds |
| session_id | str | Unique session ID for this run |

---

## 8. Reproduction Instructions

### Prerequisites
```
Docker Desktop (running)
Ollama (running on host, port 11434)
Python 3.11+  with: requests, httpx
```

### Run Gemini Experiment (Experiment 1)
```bash
# From project root
docker compose up -d
cd evaluation
python3 mypath_eval_harness.py \
  --url http://localhost:8000 \
  --model gemini-1.5-flash \
  --runs 3 \
  --output ../eval_results
```

### Run Ollama Experiment (Experiment 2 — local models)
```bash
# Pull models first
ollama pull qwen2.5:3b
ollama pull llama3.2:3b
ollama pull phi4-mini

cd evaluation
python3 mypath_eval_harness.py \
  --url http://localhost:8000 \
  --model qwen2.5:3b llama3.2:3b phi4-mini \
  --runs 3 \
  --output ../eval_results
```

### Rate Limit Notes
- Gemini free tier: ~10 RPM. Harness uses 8 s inter-request delay.
- Run 3 will experience 429 errors if daily quota is near exhaustion; results remain valid but latency inflates.
- Ollama: no rate limits. Use 1 s delay (default when Ollama model detected).
- Models >4 GB (qwen2.5:7b, llama3.1:8b) cause Ollama OOM on 16 GB Mac — use 3B models only.

---

## 9. Configuration Reference

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `LLM_PROVIDER` | `gemini` | `gemini` or `ollama` |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite-preview` | Gemini model ID |
| `GEMINI_FALLBACK_MODEL` | `gemini-2.5-flash` | Fallback on 429/503 |
| `GEMINI_API_KEY` | — | Google AI Studio API key |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Ollama model name |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama endpoint from Docker |

---

*Generated: 2026-06-26 | Evaluation harness: `evaluation/mypath_eval_harness.py` | Dataset: `evaluation/mypath_od_pairs_1.json`*
