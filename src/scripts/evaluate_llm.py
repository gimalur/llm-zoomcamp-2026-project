import json
import os
from pathlib import Path

from openai import OpenAI

from app.rag_graph import SYSTEM_PROMPT
from db import db_session
from evaluation.llm_judge import aggregate, evaluate_variant

GROUND_TRUTH_PATH = Path(__file__).resolve().parent.parent.parent / "eval" / "ground_truth.json"
RESULTS_PATH = Path(__file__).resolve().parent.parent.parent / "eval" / "llm_results.md"

CONCISE_PROMPT = """
    You are a knowledge assistant for travel questions. Look up
    destination, culture, food, or transport info when the user's
    question needs it. Do not look anything up for greetings, small
    talk, or questions unrelated to travel.

    Only answer using information you retrieved or already present
    in this conversation - if you don't have the answer there, say you
    don't have such information, don't make things up. Keep answers
    concise and mention which source(s) the info comes from.
""".strip()

VARIANTS = {
    "concise": CONCISE_PROMPT,
    "thorough": SYSTEM_PROMPT,  # current app default, winner of the first run of this eval
}


if __name__ == "__main__":
    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text())
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    scores = {}
    with db_session() as conn:
        for name, prompt in VARIANTS.items():
            print(f"Running variant {name!r} ({len(ground_truth)} questions)...")
            results = evaluate_variant(conn, client, ground_truth, prompt, name)
            scores[name] = aggregate(results)

    winner = max(scores, key=lambda name: scores[name]["relevance_pct"]["RELEVANT"])

    lines = [
        f"# LLM-judge evaluation ({len(ground_truth)} ground-truth questions, judge=gpt-4o-mini)",
        "",
        "| Variant | RELEVANT | PARTLY_RELEVANT | NON_RELEVANT | Tool called | Avg tool rounds | Total cost |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, s in scores.items():
        marker = " (winner)" if name == winner else ""
        r = s["relevance_pct"]
        lines.append(
            f"| {name}{marker} | {r['RELEVANT']:.1%} | {r['PARTLY_RELEVANT']:.1%} | {r['NON_RELEVANT']:.1%} "
            f"| {s['tool_called_pct']:.1%} | {s['avg_tool_rounds']:.2f} | ${s['total_cost']:.4f} |"
        )

    report = "\n".join(lines)
    print(report)
    RESULTS_PATH.write_text(report + "\n")
    print(f"\nWinner: {winner}. Results written to {RESULTS_PATH}")
