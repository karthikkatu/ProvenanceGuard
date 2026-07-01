# Provenance Guard

A Flask service that detects whether submitted text is human-written or AI-generated. It combines two independent detection signals — a Groq LLM classifier and local stylometric heuristics — into a single confidence score, displays an honest transparency label, records every decision in a tamper-evident audit log, and lets creators appeal classifications they believe are wrong.

> **Transparency, not proof.** Results are probabilistic estimates, not evidence of authorship.

---

## Table of Contents

- [Setup](#setup)
- [Architecture](#architecture)
- [Detection Pipeline](#detection-pipeline)
  - [Signal 1 — LLM Classifier (Groq)](#signal-1--llm-classifier-groq)
  - [Signal 2 — Stylometric Heuristics](#signal-2--stylometric-heuristics)
  - [Combining Signals](#combining-signals)
- [Confidence Scoring](#confidence-scoring)
- [Transparency Labels](#transparency-labels)
- [API Reference](#api-reference)
  - [POST /submit](#post-submit)
  - [POST /appeal](#post-appeal)
  - [GET /log](#get-log)
- [Rate Limiting](#rate-limiting)
- [Audit Log](#audit-log)
- [Appeals Workflow](#appeals-workflow)
- [Frontend UI](#frontend-ui)
- [Known Limitations](#known-limitations)

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # add your GROQ_API_KEY
python app.py
```

The server starts on `http://localhost:5000`. The SQLite database (`audit.db`) is created automatically on first run.

**Dependencies:**

| Package | Purpose |
|---------|---------|
| `flask>=3.0` | Web framework |
| `flask-limiter>=3.5` | Rate limiting |
| `groq>=0.9` | Groq SDK for LLM classification |
| `python-dotenv>=1.0` | Load `GROQ_API_KEY` from `.env` |

---

## Architecture

```text
Client (browser or API)
  │
  │  POST /submit  { text, creator_id }
  ▼
Flask API — validates input, enforces rate limit (10/min · 100/day)
  │
  ├──────────────────────────────┐
  │                              │
  ▼                              ▼
Signal 1                    Signal 2
Groq LLM Classifier         Stylometric Heuristics
(llama-3.3-70b-versatile)   (sentence variance, TTR,
  │                          punctuation density)
  │  score [0–1]              │  score [0–1]
  └──────────┬────────────────┘
             │
             ▼
   Confidence Scoring Engine
   Final Score = (S1 × 0.5) + (S2 × 0.5)
             │
             ▼
   Transparency Label Generator
   "Likely Human-Written" | "Unable to Determine" | "Likely AI-Generated"
             │
             ▼
   Structured Audit Log (SQLite)
             │
             ▼
   JSON Response → Client
```

**Appeal flow:**

```text
Creator  →  POST /appeal  { content_id, creator_reasoning }
                │
                ▼
          Validate content_id exists in audit log
                │
                ▼
          Write appeal row (linked to original submission)
          Update submission status → "under review"
                │
                ▼
          GET /log surfaces both submission + appeal to reviewers
```

---

## Detection Pipeline

Every submission runs two independent signals. Neither signal is given priority over the other — both contribute equally to the final score.

### Signal 1 — LLM Classifier (Groq)

**File:** [signals/llm_classifier.py](signals/llm_classifier.py)

The text is sent to `llama-3.3-70b-versatile` via the Groq API with a structured system prompt that asks the model to estimate AI-generation probability. The model is constrained to JSON output with `response_format: json_object` and a low temperature (0.1) for deterministic responses.

**What it evaluates:** writing style, phrasing predictability, structural consistency, coherence, and other high-level linguistic signals that LLMs recognize as characteristic of AI versus human authorship.

**Output:**

```json
{
  "score": 0.82,
  "reason": "The text exhibits consistent sentence structure and lacks personal tone, characteristic of AI-generated content."
}
```

`score` is clamped to `[0.0, 1.0]`. On a malformed model response, the signal defaults to `0.5` and sets `parse_error: true`.

---

### Signal 2 — Stylometric Heuristics

**File:** [signals/stylometric.py](signals/stylometric.py)

A deterministic local analysis — no API call, no network latency. Three structural metrics are computed and combined into a weighted score.

| Metric | Weight | What it measures | AI-like pattern |
|--------|--------|------------------|-----------------|
| Sentence length variance (CV) | 60% | Coefficient of variation of per-sentence word counts | Low variance — uniform sentence lengths |
| Type-Token Ratio (TTR) | 25% | Unique words ÷ total words | Low TTR — repetitive vocabulary |
| Punctuation density | 15% | Punctuation characters ÷ total characters | High density — structured, formal prose |

**Scoring formulas:**

```python
sv_ai  = max(0, min(1, 1.0 - sentence_variance / 1.2))   # low CV → AI-like
ttr_ai = max(0, min(1, 1.0 - type_token_ratio))           # low TTR → AI-like
pd_ai  = max(0, min(1, punctuation_density / 0.12))        # high PD → AI-like

score = 0.60 * sv_ai + 0.25 * ttr_ai + 0.15 * pd_ai
```

**Output:**

```json
{
  "score": 0.6022,
  "reason": "Structure appears AI-like: sentence lengths are uniform; vocabulary is highly diverse.",
  "metrics": {
    "sentence_variance": 0.1234,
    "type_token_ratio": 0.8456,
    "punctuation_density": 0.0321,
    "avg_sentence_length": 9.2
  }
}
```

If the text has fewer than 2 sentences or fewer than 10 words, the signal returns `score: 0.5` with a short-text warning.

---

### Combining Signals

**File:** [signals/pipeline.py](signals/pipeline.py)

Both signals are averaged with equal weight:

```
Final Score = (Signal 1 × 0.5) + (Signal 2 × 0.5)
```

A `combined_reason` string is also generated. If the two signals disagree by more than 0.30, it surfaces that disagreement explicitly:

```
"Signals disagree (LLM: 0.80, stylometric: 0.43). Confidence is reduced by signal disagreement."
```

---

## Confidence Scoring

The final score ranges from `0.0` to `1.0`:

| Score range | Interpretation |
|-------------|----------------|
| 0.00 – 0.30 | Strong evidence of human writing |
| 0.31 – 0.44 | Mostly human with some uncertainty |
| 0.45 – 0.55 | Genuinely uncertain |
| 0.56 – 0.69 | Leans AI, but not strongly |
| 0.70 – 1.00 | Strong evidence of AI writing |

**Classification thresholds:**

| Final score | Attribution | Label |
|-------------|-------------|-------|
| < 0.45 | `human` | Likely Human-Written |
| 0.45 – 0.69 | `uncertain` | Unable to Determine |
| ≥ 0.70 | `ai` | Likely AI-Generated |

The uncertain band is intentionally wide. A false positive — labeling genuine human writing as AI-generated — harms a creator's reputation, so borderline cases always fall into `uncertain` rather than forcing a verdict.

---

## Transparency Labels

**File:** [signals/labels.py](signals/labels.py)

Each response includes a `label` object with a human-readable title and explanatory body text:

| Attribution | Title | Body |
|-------------|-------|------|
| `human` | **Likely Human-Written** | Our analysis indicates with high confidence that this content was written by a person. This result is based on multiple detection signals and is not proof of authorship. |
| `uncertain` | **Unable to Determine** | Our analysis found mixed evidence. We cannot confidently determine whether this content was written by a person or generated by AI. |
| `ai` | **Likely AI-Generated** | Our analysis indicates with high confidence that this content was generated using AI. This result is based on multiple detection signals and is not proof of authorship. |

---

## API Reference

### POST /submit

Classify a piece of text. Runs both detection signals, stores the result in the audit log, and returns the full classification.

**Rate limit:** 10 requests per minute, 100 requests per day per IP. Exceeding either returns `HTTP 429`.

**Request:**

```bash
curl -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Machine learning is a subset of artificial intelligence. It enables systems to learn from data.",
    "creator_id": "carol"
  }'
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | yes | The text to analyze. Must be non-empty. |
| `creator_id` | string | yes | Identifier for the content creator (not authenticated, self-reported). |

**Response `200 OK`:**

```json
{
  "content_id": "cont_ad384c33-9247-435f-a5e7-1772c014a28a",
  "creator_id": "carol",
  "text": "Machine learning is a subset of artificial intelligence...",
  "signal_1": {
    "score": 0.8,
    "reason": "The text exhibits a formal and structured tone, lacks personal opinion or emotional language."
  },
  "signal_2": {
    "score": 0.6022,
    "reason": "Structure appears AI-like: sentence lengths are uniform; vocabulary is highly diverse.",
    "metrics": {
      "sentence_variance": 0.0,
      "type_token_ratio": 0.8235,
      "punctuation_density": 0.0161,
      "avg_sentence_length": 8.0
    }
  },
  "attribution_result": "ai",
  "confidence_score": 0.7011,
  "combined_reason": "Both signals lean AI-generated (LLM: 0.80, stylometric: 0.60).",
  "label": {
    "title": "Likely AI-Generated",
    "body": "Our analysis indicates with high confidence that this content was generated using AI. This result is based on multiple detection signals and is not proof of authorship."
  },
  "status": "classified"
}
```

**Error responses:**

| Status | Condition |
|--------|-----------|
| `400` | Missing or invalid `text` or `creator_id` |
| `429` | Rate limit exceeded |
| `500` | `GROQ_API_KEY` not set |
| `502` | Groq API or network error |

---

### POST /appeal

File an appeal on a classification. The original decision is preserved; the submission's status changes to `"under review"` and the appeal is logged.

**No rate limit** on this endpoint.

**Request:**

```bash
curl -X POST http://localhost:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{
    "content_id": "cont_ad384c33-9247-435f-a5e7-1772c014a28a",
    "creator_id": "carol",
    "creator_reasoning": "I wrote every sentence myself. Short sentences were intentional — writing for a non-technical audience.",
    "context": "This was a blog post summary drafted for a general audience, not an academic paper."
  }'
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content_id` | string | yes | ID returned by `/submit`. |
| `creator_reasoning` | string | yes | Why the classification is wrong. |
| `creator_id` | string | no | Creator's identifier (for reviewer context). |
| `context` | string | no | Any additional detail for the human reviewer. |

**Response `200 OK`:**

```json
{
  "appeal_id": "appeal_b038c2e9-8c26-40ec-b1f0-924ea559330b",
  "content_id": "cont_ad384c33-9247-435f-a5e7-1772c014a28a",
  "status": "under review",
  "message": "Appeal received. The submission has been flagged for human review.",
  "timestamp": "2026-06-30T02:32:55.693Z"
}
```

**Error responses:**

| Status | Condition |
|--------|-----------|
| `400` | Missing or invalid `content_id` or `creator_reasoning` |
| `404` | `content_id` not found in the audit log |

---

### GET /log

Retrieve the full audit log: all submissions and all appeals, newest first.

```bash
curl http://localhost:5000/log
```

**Response `200 OK`:**

```json
{
  "entries": [
    {
      "id": 3,
      "content_id": "cont_ad384c33-9247-435f-a5e7-1772c014a28a",
      "creator_id": "carol",
      "text": "Machine learning is a subset of artificial intelligence...",
      "llm_score": 0.8,
      "llm_reason": "The text exhibits a formal and structured tone...",
      "stylometric_score": 0.6022,
      "stylometric_reason": "Structure appears AI-like: sentence lengths are uniform...",
      "attribution": "ai",
      "confidence": 0.7011,
      "label_text": "Likely AI-Generated",
      "status": "under review",
      "timestamp": "2026-06-30T02:32:03.086Z",
      "appeal_status": true
    }
  ],
  "appeals": [
    {
      "appeal_id": "appeal_b038c2e9-8c26-40ec-b1f0-924ea559330b",
      "content_id": "cont_ad384c33-9247-435f-a5e7-1772c014a28a",
      "creator_id": "carol",
      "appeal_reasoning": "I wrote every sentence myself...",
      "context": "",
      "status": "under review",
      "timestamp": "2026-06-30T02:32:55.693Z",
      "attribution": "ai",
      "confidence": 0.7011,
      "llm_score": 0.8,
      "stylometric_score": 0.6022,
      "label_text": "Likely AI-Generated"
    }
  ]
}
```

`appeal_status` in each entry is `true` if any appeal has been filed for that `content_id`, `false` otherwise. The `appeals` array joins each appeal with the original submission's scores and label for reviewer convenience.

---

## Rate Limiting

**File:** [extensions.py](extensions.py), applied in [routes/submit.py](routes/submit.py)

`POST /submit` is rate-limited to **10 requests per minute** and **100 requests per day** per IP address, enforced by `flask-limiter` using in-memory storage. Exceeding either limit returns `HTTP 429 Too Many Requests`.

**Why these numbers:**
- 10 per minute allows a writer to submit, revise, and resubmit several times in a session with no friction.
- 100 per day covers heavy legitimate use — a professional reviewing 100 pieces of content per day is an edge case.
- Both together block automated flooding while being invisible to real users.

**Example — hitting the limit:**

```bash
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:5000/submit \
    -H "Content-Type: application/json" \
    -d '{"text": "Test submission.", "creator_id": "ratelimit-test"}'
done
```

```
200
200
200
200
200
200
200
200
200
200
429
429
```

Requests 1–10 succeed. Requests 11–12 are rejected before the pipeline runs.

---

## Audit Log

**File:** [audit/log.py](audit/log.py)

Every classification and appeal is persisted to a local SQLite database (`audit.db`). The schema is created automatically on startup; if the schema is outdated (missing required columns), the table is recreated.

**Submissions table columns:**

| Column | Type | Description |
|--------|------|-------------|
| `content_id` | TEXT | Unique identifier (`cont_<uuid>`) |
| `creator_id` | TEXT | Self-reported creator identifier |
| `text` | TEXT | Full submitted text |
| `llm_score` | REAL | Signal 1 score (0–1) |
| `llm_reason` | TEXT | LLM's explanation |
| `stylometric_score` | REAL | Signal 2 score (0–1) |
| `stylometric_reason` | TEXT | Heuristic explanation |
| `attribution` | TEXT | `human`, `uncertain`, or `ai` |
| `confidence` | REAL | Combined score (0–1) |
| `label_text` | TEXT | Transparency label title |
| `status` | TEXT | `classified` or `under review` |
| `timestamp` | TEXT | ISO-8601 UTC |

**Appeals table columns:**

| Column | Type | Description |
|--------|------|-------------|
| `appeal_id` | TEXT | Unique identifier (`appeal_<uuid>`) |
| `content_id` | TEXT | Foreign key to submissions |
| `creator_id` | TEXT | Creator who filed the appeal |
| `appeal_reasoning` | TEXT | Creator's explanation |
| `context` | TEXT | Optional supporting context |
| `status` | TEXT | `under review` |
| `timestamp` | TEXT | ISO-8601 UTC |

You can inspect the database directly:

```bash
sqlite3 audit.db "SELECT content_id, attribution, confidence, status FROM submissions;"
```

Or use the included helper:

```bash
python inspect_log.py
```

---

## Appeals Workflow

When a creator disagrees with a classification:

1. They call `POST /appeal` with the `content_id` and their reasoning.
2. The system validates that the `content_id` exists in the database.
3. The original classification is **not changed** — the decision record is immutable.
4. The submission's `status` is updated from `classified` to `under review`.
5. An appeal row is written, linked to the original submission via `content_id`.
6. A human reviewer can then pull `GET /log` to see the full record: original scores, transparency label, creator's appeal reasoning, and any supporting context.

This design ensures the audit trail is complete — both the original automated decision and the human challenge are preserved side-by-side for the reviewer.

---

## Frontend UI

**Files:** [static/index.html](static/index.html), [static/app.js](static/app.js), [static/styles.css](static/styles.css)

The server serves a single-page application at `http://localhost:5000` with three views:

**Analyze tab** — paste text and a creator ID, hit Analyze, and see the full result: attribution badge, confidence score, signal breakdown with metrics, and the transparency label. Three sample buttons load representative human, borderline, and AI texts for testing.

**Audit Log tab** — filterable table of all past submissions (All / Human / Uncertain / AI / Appealed). Shows live stats (total submissions, breakdown by attribution). Each row has an "Appeal" button that opens a modal to file an appeal without leaving the UI.

**About tab** — explains how the two signals work, shows the confidence threshold table, and states the uncertainty disclaimer.

---

## Known Limitations

**Poetry and highly stylized writing** — Short lines, repeated phrases, and unusual formatting can produce a stylometric score that looks AI-like even for genuine poetry.

**Professional or edited prose** — Polished, consistent writing (journalism, technical documentation) can trigger higher AI scores because it resembles structured AI output.

**Very short text** — Fewer than 2 sentences or 10 words is insufficient for Signal 2; it returns `0.5` (uncertain) and the overall confidence will reflect that.

**Human-edited AI content** — If a creator substantially edits AI-generated text, Signal 1 may read it as more human-like while Signal 2 still sees structural AI patterns. The signals will disagree, `combined_reason` will say so explicitly, and the result will likely be `uncertain`.

**`creator_id` is not authenticated** — It is self-reported and used only for audit log context, not as a credential or identity claim.
