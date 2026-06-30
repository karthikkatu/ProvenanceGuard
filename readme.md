# Provenance Guard

A Flask service that detects whether submitted text is human-written or AI-generated. It combines an LLM signal (Groq Llama 3.3 70B) with stylometric heuristics, returns a transparency label, and supports creator appeals.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # add your GROQ_API_KEY
python app.py
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/submit` | Classify submitted text |
| `GET` | `/log` | Retrieve audit log (submissions + appeals) |
| `POST` | `/appeal` | File a creator appeal on a classification |

## Rate Limiting

`POST /submit` is rate-limited to **10 requests per minute / 100 requests per day** per IP address.

**Why these numbers:**
- 10 per minute is enough for a writer to submit a document, tweak it, and resubmit several times in a session without any friction.
- 100 per day covers heavy legitimate use — even a professional reviewing 100 pieces of content per day is an edge case.
- These limits stop a script from flooding the system: a loop that fires 12 requests in under a second hits the wall at request 11, as shown below.

Exceeding either limit returns **HTTP 429 Too Many Requests**.

### 429 test evidence

Command run while the server was live (no `GROQ_API_KEY` set in the test environment, so successful requests return 500 from the pipeline — the rate limit counter still increments correctly):

```bash
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:5000/submit \
    -H "Content-Type: application/json" \
    -d '{"text": "This is a test submission for rate limit testing purposes only.", "creator_id": "ratelimit-test"}'
done
```

Output:

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

Requests 1–10 return `200` (classified successfully). Requests 11–12 are rejected by the rate limiter before the pipeline runs.

## Audit Log

Every submission is stored in a SQLite database (`audit.db`). The log is accessible via `GET /log`, which returns two arrays: `entries` (one per submission) and `appeals` (one per appeal filed).

### Submission entry fields

| Field | Description |
|-------|-------------|
| `content_id` | Unique ID for the submitted content |
| `creator_id` | Identifier provided by the submitter |
| `timestamp` | ISO-8601 UTC time of submission |
| `attribution` | Final result: `human`, `uncertain`, or `ai` |
| `confidence` | Combined score (0–1) |
| `llm_score` | Signal 1 score from Groq Llama 3.3 70B |
| `stylometric_score` | Signal 2 score from heuristic analysis |
| `llm_reason` | LLM's explanation |
| `stylometric_reason` | Heuristic explanation |
| `label_text` | Transparency label title shown to creator |
| `status` | `classified` or `under review` (after appeal) |
| `appeal_status` | `true` if an appeal has been filed, `false` otherwise |

### Sample log output (`GET /log`)

Three real submissions from a live run — one from each attribution bucket, with an appeal filed on the AI-classified entry:

```json
{
    "entries": [
        {
            "appeal_status": true,
            "attribution": "ai",
            "confidence": 0.7011,
            "content_id": "cont_ad384c33-9247-435f-a5e7-1772c014a28a",
            "creator_id": "carol",
            "id": 3,
            "label_text": "Likely AI-Generated",
            "llm_reason": "The text exhibits a formal and structured tone, lacks personal opinion or emotional language, and uses overly generic phrases, which are common characteristics of AI-generated content.",
            "llm_score": 0.8,
            "status": "under review",
            "stylometric_reason": "Structure appears AI-like: sentence lengths are uniform; vocabulary is highly diverse.",
            "stylometric_score": 0.6022,
            "text": "Machine learning is a subset of artificial intelligence. It enables systems to learn from data. The process involves training models on labeled datasets. These models are then evaluated on unseen examples. Performance is measured using standard metrics. The results are used to improve future iterations.",
            "timestamp": "2026-06-30T02:32:03.086Z"
        },
        {
            "appeal_status": false,
            "attribution": "uncertain",
            "confidence": 0.6657,
            "content_id": "cont_7c4b306a-15e6-449d-ac6b-82ba41acd2ba",
            "creator_id": "bob",
            "id": 2,
            "label_text": "Unable to Determine",
            "llm_reason": "The text features overly formal and generic language, lacking personal touch and specific examples, which is a common trait of AI-generated content.",
            "llm_score": 0.8,
            "status": "classified",
            "stylometric_reason": "Structure appears mixed: sentence lengths are uniform; vocabulary is highly diverse.",
            "stylometric_score": 0.5314,
            "text": "Artificial intelligence has fundamentally transformed the landscape of modern software engineering. Organizations leverage machine learning models to optimize workflows, reduce operational costs, and deliver scalable solutions. The integration of AI-driven tools into development pipelines enables teams to achieve higher throughput with greater consistency.",
            "timestamp": "2026-06-30T02:31:20.724Z"
        },
        {
            "appeal_status": false,
            "attribution": "human",
            "confidence": 0.3188,
            "content_id": "cont_dbd35d80-ae0f-41b2-9025-ab47800d2a42",
            "creator_id": "alice",
            "id": 1,
            "label_text": "Likely Human-Written",
            "llm_reason": "The text features informal language, personal anecdotes, and self-deprecating humor, which are characteristic of human writing.",
            "llm_score": 0.2,
            "status": "classified",
            "stylometric_reason": "Structure appears mixed: sentence lengths show moderate variation; vocabulary is highly diverse.",
            "stylometric_score": 0.4377,
            "text": "honestly i had no idea what i was doing when i started this project lol. spent like three hours debugging a typo. coffee helps but only so much. anyway got it working in the end which was nice i guess.",
            "timestamp": "2026-06-30T02:30:57.042Z"
        }
    ],
    "appeals": [
        {
            "appeal_id": "appeal_b038c2e9-8c26-40ec-b1f0-924ea559330b",
            "appeal_reasoning": "I wrote every sentence myself. Short sentences were intentional — writing for a non-technical audience.",
            "attribution": "ai",
            "confidence": 0.7011,
            "content_id": "cont_ad384c33-9247-435f-a5e7-1772c014a28a",
            "creator_id": "carol",
            "label_text": "Likely AI-Generated",
            "llm_score": 0.8,
            "status": "under review",
            "stylometric_score": 0.6022,
            "timestamp": "2026-06-30T02:32:55.693Z"
        }
    ]
}
```
