"""Validate named classifier labels instead of interpreting unknown output as real."""
import math

AI_LABELS = {"ai", "ai-generated", "artificial", "fake", "gan", "generated"}
REAL_LABELS = {"real", "human", "authentic", "natural"}


def parse_ai_score(results):
    if not isinstance(results, list) or not results:
        raise ValueError("Expected a nonempty classifier result list")
    positive = negative = None
    for entry in results:
        label = str(entry["label"]).strip().lower()
        score = float(entry["score"])
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("Classifier returned an invalid score")
        if label in AI_LABELS:
            if positive is not None:
                raise ValueError("Duplicate AI labels")
            positive = score
        elif label in REAL_LABELS:
            if negative is not None:
                raise ValueError("Duplicate real labels")
            negative = score
        else:
            raise ValueError("Unknown model label; configure an explicit label mapping")
    if positive is not None and negative is not None and abs(positive + negative - 1) > .02:
        raise ValueError("Inconsistent binary classifier scores")
    return positive if positive is not None else 1 - negative
