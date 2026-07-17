import json
import os
from pathlib import Path

from openai import OpenAI

from db import db_session
from evaluation.ground_truth import generate

OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "eval" / "ground_truth.json"


if __name__ == "__main__":
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    with db_session() as conn:
        questions = generate(conn, openai_client)

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(questions, indent=2))
    print(f"Wrote {len(questions)} ground-truth questions to {OUTPUT_PATH}")
