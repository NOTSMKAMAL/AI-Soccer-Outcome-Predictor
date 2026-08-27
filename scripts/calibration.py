#!/usr/bin/env python3
"""
Shared calibration / scoring utilities for the prediction backtests (P3).

Used by the offline backtest (scripts/backtest.py) and by the runtime
prediction tracking (engine/tracking.py) so both score predictions identically.

A "record" is a dict:
    {
        "probs":     {"home_win": float, "draw": float, "away_win": float},
        "predicted": "home_win" | "draw" | "away_win",
        "actual":    "home_win" | "draw" | "away_win",
        "correct":   bool,
    }

Reliability (calibration) is reported two ways:
  * Top-label reliability — bin by the model's winning probability (its stated
    confidence) and compare to how often that pick was actually right. This is
    the headline reliability diagram.
  * Multiclass (one-vs-rest) reliability — pool all three class probabilities
    against their binary outcomes. Catches mis-calibration the top-label view
    can hide (e.g. systematically over-stated draw probabilities).
"""
from __future__ import annotations

import math

OUTCOMES = ("home_win", "draw", "away_win")


def _clip(p: float, lo: float = 0.001, hi: float = 0.999) -> float:
    return max(lo, min(hi, p))


def brier_and_logloss(records: list[dict]) -> tuple[float, float]:
    """Multiclass Brier score and log loss over all records."""
    if not records:
        return float("nan"), float("nan")
    brier_sum = log_loss_sum = 0.0
    for r in records:
        p = r["probs"]
        actual = r["actual"]
        for outcome in OUTCOMES:
            o = 1.0 if actual == outcome else 0.0
            pc = _clip(p[outcome])
            brier_sum += (pc - o) ** 2
            if o:
                log_loss_sum += math.log(pc)
    n = len(records)
    return brier_sum / n, -log_loss_sum / n


def top_label_reliability(records: list[dict], n_bins: int = 10) -> tuple[list[dict], float]:
    """
    Bin records by the model's winning probability (confidence). For each bin
    return count, mean confidence, and observed accuracy. Also return the
    Expected Calibration Error (ECE) = sum_b (n_b/N) * |acc_b - conf_b|.
    """
    bins: list[dict] = [
        {"lo": i / n_bins, "hi": (i + 1) / n_bins, "confs": [], "correct": []}
        for i in range(n_bins)
    ]
    for r in records:
        conf = max(r["probs"][o] for o in OUTCOMES)
        idx = min(n_bins - 1, int(conf * n_bins))
        bins[idx]["confs"].append(conf)
        bins[idx]["correct"].append(1.0 if r["correct"] else 0.0)

    n_total = len(records)
    ece = 0.0
    out: list[dict] = []
    for b in bins:
        cnt = len(b["confs"])
        if cnt:
            mean_conf = sum(b["confs"]) / cnt
            acc = sum(b["correct"]) / cnt
            ece += (cnt / n_total) * abs(acc - mean_conf)
        else:
            mean_conf = acc = None
        out.append({
            "lo": b["lo"], "hi": b["hi"], "count": cnt,
            "mean_conf": mean_conf, "accuracy": acc,
        })
    return out, ece


def multiclass_ece(records: list[dict], n_bins: int = 10) -> float:
    """One-vs-rest pooled ECE across all three class probabilities."""
    if not records:
        return float("nan")
    bins = [{"p": [], "o": []} for _ in range(n_bins)]
    for r in records:
        for outcome in OUTCOMES:
            p = r["probs"][outcome]
            o = 1.0 if r["actual"] == outcome else 0.0
            idx = min(n_bins - 1, int(p * n_bins))
            bins[idx]["p"].append(p)
            bins[idx]["o"].append(o)
    n_total = len(records) * len(OUTCOMES)
    ece = 0.0
    for b in bins:
        cnt = len(b["p"])
        if cnt:
            ece += (cnt / n_total) * abs(sum(b["o"]) / cnt - sum(b["p"]) / cnt)
    return ece


def print_reliability(bins: list[dict], ece: float, title: str = "Reliability") -> None:
    """Print a text reliability table (works without any plotting library)."""
    print(f"{title} (top-label) — ECE = {ece:.4f}")
    print(f"  {'bin':>12} | {'n':>5} | {'mean conf':>9} | {'accuracy':>8} | gap")
    print(f"  {'-'*12}-+-{'-'*5}-+-{'-'*9}-+-{'-'*8}-+-----")
    for b in bins:
        if not b["count"]:
            continue
        gap = b["accuracy"] - b["mean_conf"]
        flag = "  <-- overconfident" if gap < -0.10 else ("  <-- underconfident" if gap > 0.10 else "")
        print(f"  {b['lo']:.2f}-{b['hi']:.2f}   | {b['count']:>5} | "
              f"{b['mean_conf']:>9.3f} | {b['accuracy']:>8.3f} | {gap:+.3f}{flag}")


def write_reliability_html(bins: list[dict], path: str, title: str, ece: float) -> bool:
    """
    Write an interactive reliability diagram to `path` (HTML, no extra deps
    beyond plotly which is already a project dependency). Returns True on
    success, False if plotly is unavailable.
    """
    try:
        import plotly.graph_objects as go
    except Exception:
        return False

    xs = [(b["lo"] + b["hi"]) / 2 for b in bins if b["count"]]
    accs = [b["accuracy"] for b in bins if b["count"]]
    confs = [b["mean_conf"] for b in bins if b["count"]]
    counts = [b["count"] for b in bins if b["count"]]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1], mode="lines",
        line=dict(dash="dash", color="gray"), name="perfect calibration",
    ))
    fig.add_trace(go.Scatter(
        x=confs, y=accs, mode="lines+markers",
        marker=dict(size=[max(6, min(28, c ** 0.5 * 2)) for c in counts]),
        text=[f"n={c}" for c in counts], name="model",
        line=dict(color="#13BBAF"),
    ))
    fig.update_layout(
        title=f"{title} — ECE={ece:.4f}",
        xaxis=dict(title="Predicted confidence", range=[0, 1]),
        yaxis=dict(title="Observed accuracy", range=[0, 1]),
        width=640, height=600, template="plotly_dark",
    )
    fig.write_html(path)
    return True
