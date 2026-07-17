import json
import os
from pathlib import Path

from openai import OpenAI

from config import Config
from db import db_session
from evaluation.retrieval import evaluate

GROUND_TRUTH_PATH = Path(__file__).resolve().parent.parent.parent / "eval" / "ground_truth.json"
RESULTS_PATH = Path(__file__).resolve().parent.parent.parent / "eval" / "retrieval_results.md"


if __name__ == "__main__":
    gt = json.loads(GROUND_TRUTH_PATH.read_text())
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    with db_session() as conn:
        scores = evaluate(conn, gt, client)

    winner = max(scores, key=lambda k: scores[k][1])  # best MRR@5

    lines = [
        f"# Retrieval evaluation ({len(gt)} ground-truth questions, top_k={Config.Retrieval.TOP_K})",
        "",
        "| Approach | Hit Rate@5 | MRR@5 |",
        "|---|---|---|",
    ]
    for name, (hit_rate, mrr) in scores.items():
        marker = " (winner)" if name == winner else ""
        lines.append(f"| {name}{marker} | {hit_rate:.3f} | {mrr:.3f} |")

    report = "\n".join(lines)
    print(report)
    RESULTS_PATH.write_text(report + "\n")
    print(f"\nWinner: {winner}. Results written to {RESULTS_PATH}")
