import json
import os
from schemas import Payload
from pipeline import analyse, refrech

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAYLOAD_PATH = os.path.join(BASE_DIR, "payload.json")

with open(PAYLOAD_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

payload = Payload(**data)

test_queries = [
    "Does the Privacy Policy comply with our encryption requirements at rest and in transit? Highlight any discrepancies and mention exact pages.",
    "What is the required security breach notification timeframe in the Vendor NDA?",
    "Check the Terms of Service for log retention duration and state if it meets standards."
]

for idx, q in enumerate(test_queries, 1):
    print(f"\n======== Running Test {idx} ========")
    print(f"Query: {q}\n")
    report = analyse(query=q, files=payload)
    if report:
        print(json.dumps(report.model_dump(), indent=2, ensure_ascii=False))