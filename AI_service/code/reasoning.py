from langchain_classic.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate
from schemas import Evidence, ComplianceReport, QueryIntent
from config import llm

# Convert the requirements or the query into an ordered text list.
def format_requirements(requirements: list[str]) -> str:
    lines = []
    for i, requirement in enumerate(requirements, start=1):
        lines.append(f"{i}. {requirement}")
    return "\n".join(lines)


# Convert the Evidence that returned from the embedded search to text.
def format_evidence(evidence: list[Evidence]) -> str:
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

# Define the structure that the LLM must return.
structured_llm = llm.with_structured_output(ComplianceReport)

# Combine the prompt and the structured output into a reasoning chain.
reasoning_chain = reasoning_prompt | structured_llm


#---------------------------------------------------
# make the llm analyse the evidence with the query
#---------------------------------------------------
def reasoning(requirements: list[str], evidence: list[Evidence], memory: ConversationBufferMemory) -> ComplianceReport:

    formatted_requirements = format_requirements(requirements)
    formatted_evidence = format_evidence(evidence)

    # allows the LLM to reference prior conversation context.
    chat_history = memory.load_memory_variables({}).get("history", [])

    report = reasoning_chain.invoke(
        {
            "requirements": formatted_requirements,
            "evidence": formatted_evidence,
            "chat_history": chat_history,
        }
    )

    return report
#---------------------------------------------------


#---------------------------------------------------
# make the llm make the rotation of the query
#---------------------------------------------------
router_chain = llm.with_structured_output(QueryIntent)
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
    """    
    result = router_chain.invoke(prompt)
    return result
#---------------------------------------------------
