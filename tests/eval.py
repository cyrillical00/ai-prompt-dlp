import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from classifier.patterns import PatternRegistry
from classifier.engine import classify

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(filename: str) -> list[dict]:
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path) as f:
        return json.load(f)


def run():
    registry = PatternRegistry()
    positives = load_fixture("should_flag.json")
    negatives = load_fixture("should_not_flag.json")

    tp = 0
    fn = 0
    fp = 0
    tn = 0
    tier_confusion: dict[str, dict[str, int]] = {}

    print("\n=== Positive fixtures (should_flag) ===")
    for case in positives:
        result = classify(case["input"], registry)
        got_tier = result.final_tier
        exp_tier = case["expected_tier"]

        correct = got_tier == exp_tier
        if correct:
            tp += 1
        else:
            fn += 1

        tier_confusion.setdefault(exp_tier, {})
        tier_confusion[exp_tier][got_tier] = tier_confusion[exp_tier].get(got_tier, 0) + 1

        status = "PASS" if correct else "FAIL"
        print(f"  [{status}] #{case['id']} {case['label']}: expected={exp_tier} got={got_tier}")

    print("\n=== Negative fixtures (should_not_flag) ===")
    for case in negatives:
        result = classify(case["input"], registry)
        got_tier = result.final_tier
        exp_tier = case["expected_tier"]

        correct = got_tier == exp_tier
        if correct:
            tn += 1
        else:
            fp += 1

        tier_confusion.setdefault(exp_tier, {})
        tier_confusion[exp_tier][got_tier] = tier_confusion[exp_tier].get(got_tier, 0) + 1

        status = "PASS" if correct else "FAIL"
        categories = [m.category for m in result.matches]
        print(f"  [{status}] #{case['id']} {case['label']}: expected={exp_tier} got={got_tier} cats={categories}")

    total = tp + fn + fp + tn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    print("\n=== Summary ===")
    print(f"  True Positives:  {tp}")
    print(f"  False Negatives: {fn}")
    print(f"  False Positives: {fp}")
    print(f"  True Negatives:  {tn}")
    print(f"  Total fixtures:  {total}")
    print(f"  Precision:       {precision:.2f}")
    print(f"  Recall:          {recall:.2f}")
    print(f"  F1:              {f1:.2f}")

    print("\n=== Tier Confusion Matrix ===")
    all_tiers = sorted({t for row in tier_confusion.values() for t in row} | set(tier_confusion.keys()))
    header = "Expected \\ Got".ljust(12) + " ".join(t.ljust(8) for t in all_tiers)
    print(f"  {header}")
    for exp in sorted(tier_confusion.keys()):
        row = tier_confusion[exp]
        counts = " ".join(str(row.get(got, 0)).ljust(8) for got in all_tiers)
        print(f"  {exp.ljust(12)} {counts}")


if __name__ == "__main__":
    run()
