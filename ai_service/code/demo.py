import json
import os

from shared.schemas import Payload
from .pipeline import analyse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAYLOAD_PATH = os.path.join(BASE_DIR, "payload.json")

with open(PAYLOAD_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

payload = Payload(**data)

test_queries = [
    "Does the Privacy Policy comply with our encryption requirements at rest and in transit? Highlight any discrepancies and mention exact pages.",
    "What is the required security breach notification timeframe in the Vendor NDA?",
    "Check the Terms of Service for log retention duration and state if it meets standards.",
    "Does the Vendor NDA's confidentiality survival period and breach notification timeline comply with our compliance requirements?",  # 2 findings, both NON_COMPLIANT: 2 years (needs >= 3) and 5 business days (needs 24 hours)
    "Is the Vendor NDA's definition of Confidential Information broad enough to meet our internal standard?",  # PARTIALLY_COMPLIANT: pricing/commercial terms and non-public financial information are missing
    "Does the Privacy Policy meet our requirements for data retention and international data transfers?",  # 2 findings, both COMPLIANT (transfers are on page 2)
    "Does the Terms of Service properly reference and align with the Privacy Policy regarding data handling?",  # COMPLIANT (ToS section 4, page 1) - must give the SAME answer every time
]

for idx, q in enumerate(test_queries, 1):
    print(f"\n======== Running Test {idx} ========")
    print(f"Query: {q}\n")
    report = analyse(query=q, files=payload)
    if report:
        print(json.dumps(report.model_dump(), indent=2, ensure_ascii=False))
