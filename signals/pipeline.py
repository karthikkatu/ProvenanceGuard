"""
Detection pipeline — combines Signal 1 (LLM) and Signal 2 (Stylometric).

Scoring formula from planning.md:
    Final Score = (Signal 1 × 0.5) + (Signal 2 × 0.5)

Attribution thresholds from planning.md:
    < 0.45          → human
    0.45 – 0.69     → uncertain
    ≥ 0.70          → ai
"""

from signals.llm_classifier import analyze_with_groq
from signals.stylometric import analyze_stylometric


def run_pipeline(text: str) -> dict:
    """
    Run both detection signals and return the combined result.

    Returns:
        {
            "attribution_result": "human" | "uncertain" | "ai",
            "confidence_score":   float in [0.0, 1.0],
            "signal_1":           {"score": float, "reason": str},
            "signal_2":           {"score": float, "reason": str, "metrics": {...}},
            "combined_reason":    str,
        }
    """
    signal_1 = analyze_with_groq(text)
    signal_2 = analyze_stylometric(text)

    confidence_score   = round(0.5 * signal_1["score"] + 0.5 * signal_2["score"], 4)
    attribution_result = _classify(confidence_score)
    combined_reason    = _explain(signal_1["score"], signal_2["score"], confidence_score)

    return {
        "attribution_result": attribution_result,
        "confidence_score":   confidence_score,
        "signal_1":           signal_1,
        "signal_2":           signal_2,
        "combined_reason":    combined_reason,
    }


def _classify(score: float) -> str:
    """Map a confidence score to an attribution label. Thresholds from planning.md."""
    if score < 0.45:
        return "human"
    if score < 0.70:
        return "uncertain"
    return "ai"


def _explain(s1: float, s2: float, combined: float) -> str:
    gap = abs(s1 - s2)
    if gap > 0.30:
        return (
            f"Signals disagree (LLM: {s1:.2f}, stylometric: {s2:.2f}). "
            "Confidence is reduced by signal disagreement."
        )
    label = _classify(combined)
    if label == "ai":
        return f"Both signals lean AI-generated (LLM: {s1:.2f}, stylometric: {s2:.2f})."
    if label == "human":
        return f"Both signals lean human-written (LLM: {s1:.2f}, stylometric: {s2:.2f})."
    return (
        f"Signals provide weak or mixed evidence "
        f"(LLM: {s1:.2f}, stylometric: {s2:.2f})."
    )
