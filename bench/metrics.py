"""Metric computation for EleriBench (PRD §3.7 / §2 success criteria): verdict
accuracy + macro-F1, category accuracy, per-anomaly multi-label P/R/F1, and
10-bin expected calibration error (ECE). Pure Python — no sklearn dependency.
"""

from __future__ import annotations

from dataclasses import dataclass


def _prf1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def classification_metrics(preds: list[str | None], golds: list[str]) -> dict:
    """Accuracy + macro-F1 for a single-label field (verdict or category)."""
    n = len(golds)
    correct = sum(1 for p, g in zip(preds, golds) if p == g)
    labels = sorted(set(golds) | {p for p in preds if p is not None})

    per_class: dict[str, dict] = {}
    f1s = []
    for label in labels:
        tp = sum(1 for p, g in zip(preds, golds) if p == label and g == label)
        fp = sum(1 for p, g in zip(preds, golds) if p == label and g != label)
        fn = sum(1 for p, g in zip(preds, golds) if p != label and g == label)
        precision, recall, f1 = _prf1(tp, fp, fn)
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
        f1s.append(f1)

    return {
        "accuracy": correct / n if n else 0.0,
        "macro_f1": sum(f1s) / len(f1s) if f1s else 0.0,
        "per_class": per_class,
        "n": n,
        "parse_failures": sum(1 for p in preds if p is None),
    }


def anomaly_metrics(preds: list[list[str]], golds: list[list[str]], all_labels: list[str]) -> dict:
    """Per-anomaly + micro/macro multi-label P/R/F1."""
    per_anomaly: dict[str, dict] = {}
    macro_f1s = []
    micro_tp = micro_fp = micro_fn = 0

    for label in all_labels:
        tp = sum(1 for p, g in zip(preds, golds) if label in p and label in g)
        fp = sum(1 for p, g in zip(preds, golds) if label in p and label not in g)
        fn = sum(1 for p, g in zip(preds, golds) if label not in p and label in g)
        precision, recall, f1 = _prf1(tp, fp, fn)
        support = tp + fn
        per_anomaly[label] = {"precision": precision, "recall": recall, "f1": f1, "support": support}
        if support > 0:
            macro_f1s.append(f1)
        micro_tp += tp
        micro_fp += fp
        micro_fn += fn

    micro_p, micro_r, micro_f1 = _prf1(micro_tp, micro_fp, micro_fn)
    return {
        "per_anomaly": per_anomaly,
        "macro_f1": sum(macro_f1s) / len(macro_f1s) if macro_f1s else 0.0,
        "micro_precision": micro_p,
        "micro_recall": micro_r,
        "micro_f1": micro_f1,
    }


def expected_calibration_error(confidences: list[float], correct: list[bool], n_bins: int = 10) -> float:
    """Standard 10-bin ECE: weighted average |accuracy - confidence| per bin."""
    n = len(confidences)
    if n == 0:
        return 0.0
    bins = [[] for _ in range(n_bins)]
    for conf, is_correct in zip(confidences, correct):
        idx = min(int(conf * n_bins), n_bins - 1)
        bins[idx].append((conf, is_correct))

    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        bucket_n = len(bucket)
        avg_conf = sum(c for c, _ in bucket) / bucket_n
        avg_acc = sum(1 for _, ok in bucket if ok) / bucket_n
        ece += (bucket_n / n) * abs(avg_acc - avg_conf)
    return ece


def confidence_threshold_coverage(confidences: list[float], correct: list[bool], target_accuracy: float = 0.99) -> dict:
    """PRD §3.7: fit tau such that predictions with confidence >= tau hit target_accuracy;
    report coverage (fraction of predictions auto-resolved at that tau)."""
    n = len(confidences)
    if n == 0:
        return {"tau": 1.0, "coverage": 0.0, "accuracy_at_tau": 0.0}

    thresholds = sorted(set(confidences), reverse=True)
    best = {"tau": 1.01, "coverage": 0.0, "accuracy_at_tau": 1.0}
    for tau in thresholds:
        subset = [ok for c, ok in zip(confidences, correct) if c >= tau]
        if not subset:
            continue
        acc = sum(subset) / len(subset)
        coverage = len(subset) / n
        if acc >= target_accuracy and coverage > best["coverage"]:
            best = {"tau": tau, "coverage": coverage, "accuracy_at_tau": acc}
    return best
