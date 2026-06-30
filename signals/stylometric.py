"""
Signal 2 – Stylometric Heuristics

Measures structural writing patterns and returns a normalized score [0.0, 1.0]:
  0.0 → strongly human-like structure
  1.0 → strongly AI-like structure

Three metrics feed the score:
  sentence_variance  – coefficient of variation of sentence word counts (60% weight)
  type_token_ratio   – unique_words / total_words                       (25% weight)
  punctuation_density – punctuation_chars / total_chars                 (15% weight)
"""

import re
import statistics
from typing import List, Optional


def analyze_stylometric(text: str) -> dict:
    """
    Analyze structural/stylistic properties of the text.

    Returns:
        {
            "score": float in [0.0, 1.0],
            "reason": str,
            "metrics": {
                "sentence_variance":  float | None,
                "type_token_ratio":   float | None,
                "punctuation_density": float | None,
                "avg_sentence_length": float | None,
            }
        }
    """
    sentences = _split_sentences(text)
    words = _tokenize_words(text)

    if len(sentences) < 2 or len(words) < 10:
        return {
            "score": 0.5,
            "reason": "Text is too short for reliable stylometric analysis.",
            "metrics": {
                "sentence_variance": None,
                "type_token_ratio": None,
                "punctuation_density": None,
                "avg_sentence_length": None,
            },
        }

    # ── raw metrics ──────────────────────────────────────────────────────────
    sentence_variance   = _coefficient_of_variation(sentences)
    type_token_ratio    = len(set(w.lower() for w in words)) / len(words)
    punctuation_density = _punctuation_density(text)
    avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)

    # ── per-metric AI-likelihood scores (0.0 = human-like, 1.0 = AI-like) ───
    #
    # Low sentence variance → uniform lengths → AI-like structure
    sv_ai = max(0.0, min(1.0, 1.0 - sentence_variance / 1.2))
    #
    # Lower vocabulary diversity → somewhat more AI-like
    # (weaker for short texts; AI formal prose can also have high TTR)
    ttr_ai = max(0.0, min(1.0, 1.0 - type_token_ratio))
    #
    # Higher punctuation density → slightly more AI-like (structured writing)
    pd_ai = max(0.0, min(1.0, punctuation_density / 0.12))

    # ── weighted combination ─────────────────────────────────────────────────
    score = round(0.60 * sv_ai + 0.25 * ttr_ai + 0.15 * pd_ai, 4)

    return {
        "score": score,
        "reason": _build_reason(sentence_variance, type_token_ratio, score),
        "metrics": {
            "sentence_variance":   round(sentence_variance, 4),
            "type_token_ratio":    round(type_token_ratio, 4),
            "punctuation_density": round(punctuation_density, 4),
            "avg_sentence_length": round(avg_sentence_length, 1),
        },
    }


# ── helpers ───────────────────────────────────────────────────────────────────

def _split_sentences(text: str) -> List[str]:
    """Split on terminal punctuation followed by whitespace."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p for p in parts if p.strip()]


def _tokenize_words(text: str) -> List[str]:
    """Return alphabetic tokens (handles apostrophe contractions)."""
    return re.findall(r"[a-zA-Z']+", text)


def _coefficient_of_variation(sentences: List[str]) -> float:
    """Standard deviation / mean of per-sentence word counts."""
    lengths = [len(s.split()) for s in sentences if s.strip()]
    if len(lengths) < 2:
        return 0.5
    mean = statistics.mean(lengths)
    return (statistics.stdev(lengths) / mean) if mean > 0 else 0.0


def _punctuation_density(text: str) -> float:
    """Fraction of characters that are punctuation marks."""
    n = len(text)
    if n == 0:
        return 0.0
    return sum(1 for c in text if c in '.,;:!?()-"\'') / n


def _build_reason(sentence_variance: float, ttr: float, score: float) -> str:
    observations = []

    if sentence_variance < 0.35:
        observations.append("sentence lengths are uniform")
    elif sentence_variance > 0.75:
        observations.append("sentence lengths are highly variable")
    else:
        observations.append("sentence lengths show moderate variation")

    if ttr < 0.55:
        observations.append("vocabulary is somewhat repetitive")
    elif ttr > 0.85:
        observations.append("vocabulary is highly diverse")

    if score >= 0.60:
        label = "AI-like"
    elif score < 0.40:
        label = "human-like"
    else:
        label = "mixed"

    return f"Structure appears {label}: {'; '.join(observations)}."
