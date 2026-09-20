import json
import re
from difflib import SequenceMatcher

from langchain_classic.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from shared.schemas import Evidence, ComplianceReport, ComplianceStatus, Finding, QueryIntent
from .config import llm, USE_CHAT_HISTORY

# Convert the requirements or the query into an ordered text list.
def format_requirements(requirements: list[str]) -> str:
    lines = []
    for i, requirement in enumerate(requirements, start=1):
        lines.append(f"{i}. {requirement}")
    return "\n".join(lines)


# Convert the Evidence that returned from the embedded search to text.
def format_evidence(evidence: list[Evidence]) -> str:
    if not evidence:
        return "No evidence was retrieved for this requirement."

    blocks = []

    for i, item in enumerate(evidence, start=1):
        metadata = item.metadata

        block = (
            f"Evidence {i}:\n"
            f"Document: {metadata.filename}\n"
            f"Page: {metadata.page_number}\n"
            f"Section: {metadata.section_title}\n"
            f"Similarity Score: {item.score}\n"
            f"Text: {item.text}"
        )

        blocks.append(block)

    return "\n".join(blocks)


# This allows the LLM to reference prior conversation context during reasoning.
reasoning_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
            You are a legal and compliance analysis assistant.
            Your task is to evaluate the provided compliance requirements
            against the provided evidence.

            Rules:
            1. Use ONLY the requirements and evidence provided.
            2. Do NOT use external knowledge.
            3. Do NOT invent facts.
            4. Do NOT invent document names, page numbers, sections,
            requirements, or evidence.
            5. If the evidence is not enough to evaluate a requirement,
            use INSUFFICIENT_EVIDENCE.
            6. Produce one Finding for every requirement.
            7. Return a complete ComplianceReport.
            8. If the requirement states a specific value (a number of hours, days or years,
            or a list of required items) and the evidence states a different value, the status
            is NON_COMPLIANT, never INSUFFICIENT_EVIDENCE. Compare the numbers explicitly.
            9. If the requirement lists several required elements and the evidence covers only
            some of them, the status is PARTIALLY_COMPLIANT and the analysis must name the
            missing elements.
            10. Use INSUFFICIENT_EVIDENCE only when none of the evidence discusses the subject
            of the requirement. Ignore evidence that is unrelated to the requirement.
            11. If the requirement is marked "Minimum Standard" and is NON_COMPLIANT,
            the severity is HIGH.
            12. For the document and the page, copy exactly what is written in the evidence
            block. A section number is NOT a page number.

            INSTRUCTIONS:
            For each requirement listed above, produce one Finding object. Evaluate the \
            evidence and determine whether the requirement is supported, contradicted, \
            or cannot be assessed.
            
            For each Finding, populate every field as follows:
            - finding_id: A unique identifier in the format "F-001", "F-002", etc.
            - severity: One of HIGH, MEDIUM, or LOW based on the impact of non-compliance.
            - status: One of COMPLIANT, PARTIALLY_COMPLIANT, NON_COMPLIANT, \
            or INSUFFICIENT_EVIDENCE.
            - requirement: The exact requirement text being evaluated.
            - document: The document name from the evidence that relates to this finding. \
            If no specific document applies, use "N/A".
            - page: The page number from the evidence. If not available, use 0.
            - section: The section title from the evidence. If not available, use "N/A".
            - evidence: The specific text from the evidence that supports or contradicts \
            the requirement. Quote it exactly.
            - analysis: A concise explanation of how the evidence relates to the requirement, \
            including why the chosen status was assigned.
            - recommendation: A concrete action to achieve or maintain compliance, \
            or "No action required" if fully compliant.
            
            After evaluating all requirements, produce a top-level ComplianceReport object:
            - status: The overall compliance status (COMPLIANT if all are COMPLIANT, \
            NON_COMPLIANT if any are NON_COMPLIANT, otherwise PARTIALLY_COMPLIANT. \
            Use INSUFFICIENT_EVIDENCE only if every finding is INSUFFICIENT_EVIDENCE).
            - summary: A brief summary (2-4 sentences) of the overall compliance posture.
            - findings: The list of all Finding objects produced above.
            
            Respond ONLY with the JSON objects. Do not include commentary, markdown, \
            or any text outside the JSON structure.
            """
        ),
        ("placeholder", "{chat_history}"),
        (
            "human",
            """
            REQUIREMENTS:

            {requirements}


            EVIDENCE:

            {evidence}
            """
        ),
    ]
)

# gpt-oss on Groq has two known problems with tool calling, and both crash the request although the answer is fine:
#  1. it names the tool "functions.ComplianceReport" instead of "ComplianceReport"
#     -> LangChain raises OutputParserException ("Unknown tool type").
#  2. it writes the JSON as plain text (often inside a ```json fence) instead of calling the tool
#     -> Groq answers 400 "tool_use_failed" and puts the text in error["failed_generation"].
# _structured_output reads the answer itself in both cases. If the model really returned something
# invalid it tries once more and then raises the original error.
def _failed_generation(error):
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        body = body.get("error", body)
        if isinstance(body, dict):
            return body.get("failed_generation")
    return None


def _parse_json_text(text, schema):
    data = json.loads(text[text.index("{"): text.rindex("}") + 1])   # drops the ```json fence
    if isinstance(data, dict) and list(data) == [schema.__name__]:   # {"ComplianceReport": {...}}
        data = data[schema.__name__]
    return schema.model_validate(data)


def _structured_output(schema, attempts: int = 2):
    chain = llm.with_structured_output(schema, include_raw=True)

    def run(prompt_value):
        error = None
        for _ in range(attempts):
            try:
                out = chain.invoke(prompt_value)
            except Exception as e:
                text = _failed_generation(e)
                if text is None:
                    raise                      # a different error (rate limit, network, ...): do not hide it
                try:
                    return _parse_json_text(text, schema)
                except Exception:
                    error = e
                    continue
            if out.get("parsed") is not None:
                return out["parsed"]
            error = out.get("parsing_error")
            for call in getattr(out.get("raw"), "tool_calls", None) or []:
                try:
                    return schema.model_validate(call["args"])
                except Exception as e:
                    error = e
        raise error or ValueError(f"The model did not return a valid {schema.__name__}.")

    return RunnableLambda(run)


# Define the structure that the LLM must return.
structured_llm = _structured_output(ComplianceReport)

# Combine the prompt and the structured output into a reasoning chain.
reasoning_chain = reasoning_prompt | structured_llm


#---------------------------------------------------
# helpers that build the final report in code (not by the LLM)
#---------------------------------------------------
def _norm(text: str) -> str:
    return " ".join(text.split())


# Fill document / page / section from the evidence chunk that REALLY contains the quoted text.
# (The LLM used to write these itself and sometimes copied a section number as the page.)
def _ground_citation(finding: Finding, evidence: list[Evidence]) -> None:
    quote = _norm(finding.evidence).strip(" \"'“”.…")
    best, best_size = None, 0
    for item in evidence:
        text = _norm(item.text)
        size = SequenceMatcher(None, text, quote, autojunk=False).find_longest_match(0, len(text), 0, len(quote)).size
        if size > best_size:
            best, best_size = item, size

    if best is not None and best_size >= min(len(quote), 30) and best_size >= 0.4 * len(quote):
        finding.document = best.metadata.filename
        finding.page = best.metadata.page_number
        finding.section = best.metadata.section_title
    else:
        finding.document, finding.page, finding.section = "N/A", 0, "N/A"
        if finding.status != ComplianceStatus.INSUFFICIENT_EVIDENCE:
            finding.analysis += " (Note: the quoted text could not be matched to the retrieved evidence.)"


# Same rule that the prompt describes: all COMPLIANT -> COMPLIANT, any NON_COMPLIANT -> NON_COMPLIANT,
# every finding INSUFFICIENT_EVIDENCE -> INSUFFICIENT_EVIDENCE, otherwise PARTIALLY_COMPLIANT.
def _overall_status(findings: list[Finding]) -> ComplianceStatus:
    statuses = {f.status for f in findings}
    if statuses == {ComplianceStatus.COMPLIANT}:
        return ComplianceStatus.COMPLIANT
    if ComplianceStatus.NON_COMPLIANT in statuses:
        return ComplianceStatus.NON_COMPLIANT
    if statuses == {ComplianceStatus.INSUFFICIENT_EVIDENCE}:
        return ComplianceStatus.INSUFFICIENT_EVIDENCE
    return ComplianceStatus.PARTIALLY_COMPLIANT


_STATUS_WORDS = {
    ComplianceStatus.COMPLIANT: "compliant",
    ComplianceStatus.PARTIALLY_COMPLIANT: "partially compliant",
    ComplianceStatus.NON_COMPLIANT: "non-compliant",
    ComplianceStatus.INSUFFICIENT_EVIDENCE: "with insufficient evidence",
}


# The summary is built from the real findings, so the counts are always right.
def _summary(findings: list[Finding], labels: list[str]) -> str:
    counts = []
    for status in ComplianceStatus:
        n = sum(1 for f in findings if f.status == status)
        if n:
            counts.append(f"{n} {_STATUS_WORDS[status]}")
    text = f"Evaluated {len(findings)} requirement(s): {', '.join(counts)}."

    problems = [
        f"{f.finding_id} ({label})"
        for f, label in zip(findings, labels)
        if f.status in (ComplianceStatus.NON_COMPLIANT, ComplianceStatus.PARTIALLY_COMPLIANT)
    ]
    if problems:
        text += " Needs attention: " + "; ".join(problems) + "."
    return text
#---------------------------------------------------


#---------------------------------------------------
# make the llm analyse ONE requirement with ITS OWN evidence
#---------------------------------------------------
def _evaluate(requirement: str, evidence: list[Evidence], memory: ConversationBufferMemory) -> Finding:

    formatted_requirements = format_requirements([requirement])
    formatted_evidence = format_evidence(evidence)

    # allows the LLM to reference prior conversation context (off by default, see USE_CHAT_HISTORY).
    chat_history = memory.load_memory_variables({}).get("history", []) if USE_CHAT_HISTORY else []

    report = reasoning_chain.invoke(
        {
            "requirements": formatted_requirements,
            "evidence": formatted_evidence,
            "chat_history": chat_history,
        }
    )

    if report.findings:
        finding = report.findings[0]
    else:
        finding = Finding(
            finding_id="F-000",
            severity="LOW",
            status=ComplianceStatus.INSUFFICIENT_EVIDENCE,
            requirement=requirement,
            document="N/A",
            page=0,
            section="N/A",
            evidence="No evidence provided.",
            analysis="The model did not return a finding for this requirement.",
            recommendation="Run the analysis again or review the document manually.",
        )

    finding.requirement = _norm(requirement)   # the exact requirement text, not a paraphrase
    _ground_citation(finding, evidence)
    return finding
#---------------------------------------------------


#---------------------------------------------------
# make the llm analyse the evidence with the query
# evidence_by_req: requirement text (or the query) -> the evidence found for it
#---------------------------------------------------
def reasoning(evidence_by_req: dict[str, list[Evidence]], memory: ConversationBufferMemory) -> ComplianceReport:

    findings = []
    labels = []
    for i, (requirement, evidence) in enumerate(evidence_by_req.items(), start=1):
        finding = _evaluate(requirement, evidence, memory)
        finding.finding_id = f"F-{i:03d}"
        findings.append(finding)
        labels.append(requirement.split("\n")[0].strip()[:90])

    return ComplianceReport(
        status=_overall_status(findings),
        summary=_summary(findings, labels),
        findings=findings,
    )
#---------------------------------------------------


#---------------------------------------------------
# find which documents the query talks about (by keywords, not by the LLM)
#---------------------------------------------------
_DOC_KEYWORDS = {
    "vendor_nda": r"\bnda\b|non-?disclosure|confidentiality agreement",
    "terms_of_services": r"terms of services?|\btos\b|terms and conditions",
    "privacy_policy": r"privacy",
}


def detect_doc_types(query: str) -> list[str]:
    q = query.lower()
    return [doc_type for doc_type, pattern in _DOC_KEYWORDS.items() if re.search(pattern, q)]
#---------------------------------------------------


#---------------------------------------------------
# make the llm make the rotation of the query
#---------------------------------------------------
router_chain = _structured_output(QueryIntent)
def route_query(query: str) -> QueryIntent:
    prompt = f"""
    Analyze this user query: '{query}'
    
    Task 1: Determine 'is_requirement_check' (Boolean)
    - Set to TRUE if the query mentions words like "comply", "requirements", "standards", "required", or asks to check/verify a condition.
    - Set to FALSE ONLY if the query is a simple factual extraction from a contract without comparing it to any external rules.
    
    Task 2: Determine 'target_doc_types' (List of strings)
    - Identify which document types are the target of this query.
    - Possible values: 'privacy_policy', 'vendor_nda', 'terms_of_services', or 'all'.
    - If a specific contract is mentioned (e.g., NDA, Privacy, Terms), output its corresponding type. If none, output ['all'].

    Task 3: Determine 'topics' (List of strings)
    - Split the query into the distinct compliance subjects it asks about, each as a short phrase of 2 to 6 words
      (for example: 'confidentiality survival period', 'breach notification timeline', 'data retention periods').
    - Do NOT put document names or words like "comply", "requirements", "standards" inside a topic.
    - If the query asks about one subject only, output exactly one topic.
    """    
    result = router_chain.invoke(prompt)

    # The LLM was not stable when a query names two documents (the same question gave different targets),
    # so when the query names a document, the keywords decide.
    detected = detect_doc_types(query)
    if detected:
        result.target_doc_types = detected
    return result
#---------------------------------------------------