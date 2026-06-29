"""
Standalone test for Signal 1 (Groq LLM classifier).

Run directly:
    python test_signal.py

Requires GROQ_API_KEY in a .env file or the environment.
"""

from dotenv import load_dotenv

load_dotenv()

from signals.llm_classifier import analyze_with_groq

SAMPLES = [
    {
        "label": "Clearly human — personal, fragmented, emotional",
        "text": (
            "i wrote this on my phone while waiting for the bus lol. "
            "my hands were cold and i kept making typos. anyway the point is "
            "that yesterday was honestly one of the weirdest days ive had in a while "
            "and i still dont really know how to feel about it."
        ),
    },
    {
        "label": "Clearly AI — structured, formal, generic",
        "text": (
            "Artificial intelligence has significantly transformed various industries "
            "by enabling automation, improving efficiency, and facilitating data-driven "
            "decision-making. Organizations that adopt AI technologies early are better "
            "positioned to gain competitive advantages in their respective markets. "
            "Furthermore, AI-driven insights allow businesses to identify patterns and "
            "opportunities that would otherwise remain hidden."
        ),
    },
    {
        "label": "Ambiguous — polished literary prose",
        "text": (
            "The afternoon light filtered through the kitchen window in long amber bars. "
            "She had been sitting at the table for almost an hour, not reading, just holding "
            "the book. Outside, the neighbor's dog barked twice and then went quiet."
        ),
    },
]


def run():
    passed = 0
    for sample in SAMPLES:
        print(f"\n{'─' * 60}")
        print(f"Label : {sample['label']}")
        print(f"Text  : {sample['text'][:90]}...")

        result = analyze_with_groq(sample["text"])

        print(f"Score : {result['score']:.2f}")
        print(f"Reason: {result['reason']}")

        if result.get("parse_error"):
            print("WARNING: parse_error flag set — model response was malformed.")

        assert 0.0 <= result["score"] <= 1.0, f"Score out of range: {result['score']}"
        assert "reason" in result, "Missing 'reason' field"
        passed += 1

    print(f"\n{'─' * 60}")
    print(f"All {passed}/{len(SAMPLES)} samples passed shape and range checks.")


if __name__ == "__main__":
    run()
