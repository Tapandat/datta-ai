import json
import re
from typing import Annotated, TypedDict
from urllib.parse import urlparse

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from src.llm import get_response_text, llm
from src.tools import search_web
from src.logger import get_logger


logger = get_logger("graph")


# =========================================================
# STATE
# =========================================================

def merge_lists(left, right):
    return left + right


class ResearchState(TypedDict):
    question: str
    sub_questions: list[str]
    search_results: Annotated[list[str], merge_lists]
    sources: Annotated[list[dict], merge_lists]
    verified_evidence: list[dict]
    research_round: int
    max_research_rounds: int
    research_complete: bool
    verification_failed: bool
    answer: str


class SearchState(TypedDict):
    question: str
    result: Annotated[list[str], merge_lists]
    sources: Annotated[list[dict], merge_lists]


# =========================================================
# TEXT / JSON HELPERS
# =========================================================

def normalize_text(value: str) -> str:
    value = str(value or "").lower()
    value = value.replace("–", "-").replace("—", "-").replace("−", "-")
    value = value.replace("“", '"').replace("”", '"')
    value = value.replace("’", "'").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", value).strip()


def extract_json(text: str):
    """Extract the first valid JSON array/object from an LLM response."""
    text = str(text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    starts = [i for i in (text.find("["), text.find("{")) if i >= 0]
    if not starts:
        return None

    start = min(starts)
    for end in range(len(text), start, -1):
        candidate = text[start:end].strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def safe_llm_invoke(prompt: str):
    """One LLM call; retry only a transient server failure once."""
    try:
        return llm.invoke(prompt)
    except Exception as first_error:
        message = str(first_error)
        transient = any(
            marker in message
            for marker in ("429", "503", "500", "UNAVAILABLE", "rate_limit")
        )
        # Do not retry rate-limit/quota errors. A retry only burns time
        # and may consume another request when the provider is limited.
        if "429" in message or "rate_limit" in message.lower():
            logger.warning("Groq rate limit reached; no retry performed.")
            return None
        if transient:
            logger.warning("Temporary Groq service error; retrying once...")
            try:
                return llm.invoke(prompt)
            except Exception:
                pass
        logger.exception("Groq request failed | error_type=%s", type(first_error).__name__)
        return None


# =========================================================
# SOURCE HELPERS
# =========================================================

def normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url.strip())
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}"
    except Exception:
        return url.strip().lower()


def deduplicate_sources(sources: list[dict]) -> list[dict]:
    unique = []
    seen = set()
    for source in sources:
        url = str(source.get("url", "")).strip()
        if not url:
            continue
        key = normalize_url(url)
        if key in seen:
            continue
        seen.add(key)
        unique.append(source)
    return unique


def get_source_credibility(source: dict) -> float:
    try:
        return max(0.0, min(float(source.get("credibility_score", 0.40)), 1.0))
    except (TypeError, ValueError):
        return 0.40


def assign_source_ids(sources: list[dict]) -> list[dict]:
    result = []
    for index, source in enumerate(sources, 1):
        result.append({
            "id": index,
            "title": str(source.get("title", "")).strip(),
            "url": str(source.get("url", "")).strip(),
            "domain": str(source.get("domain", "")).strip(),
            "snippet": str(source.get("snippet", "")).strip(),
            "quality": source.get("quality", "unknown"),
            "source_type": source.get("source_type", "general_web"),
            "source_level": source.get("source_level", "secondary"),
            "domain_reputation": source.get("domain_reputation", 0.40),
            "recency_score": source.get("recency_score"),
            "specificity_score": source.get("specificity_score", 0.50),
            "query_relevance_score": source.get("query_relevance_score", 0.50),
            "credibility_score": source.get("credibility_score", 0.40),
        })
    return result


def select_sources(sources: list[dict], limit: int = 16) -> list[dict]:
    """Select strong evidence while preserving source diversity."""
    sources = deduplicate_sources(sources)
    ranked = sorted(
        sources,
        key=lambda s: (
            get_source_credibility(s),
            float(s.get("query_relevance_score", 0.50) or 0.50),
            float(s.get("specificity_score", 0.50) or 0.50),
        ),
        reverse=True,
    )

    selected = []
    domain_counts = {}

    # Make room for primary evidence when it exists.
    for source in ranked:
        if source.get("source_level") == "primary":
            selected.append(source)
            domain = str(source.get("domain", ""))
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            break

    # Prefer independent domains and avoid a single publisher dominating.
    for source in ranked:
        if len(selected) >= limit:
            break
        if source in selected:
            continue
        domain = str(source.get("domain", ""))
        if domain_counts.get(domain, 0) >= 2:
            continue
        selected.append(source)
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    if len(selected) < limit:
        for source in ranked:
            if len(selected) >= limit:
                break
            if source not in selected:
                selected.append(source)

    return selected[:limit]


# =========================================================
# EVIDENCE GUARDRAILS
# =========================================================

def extract_numbers(text: str) -> list[str]:
    text = normalize_text(text)
    matches = re.findall(
        r"(?<![a-z])\$?\s*\d+(?:[.,]\d+)?"
        r"(?:\s*(?:%|x|million|billion|trillion|m|bn|tn))?",
        text,
        flags=re.I,
    )
    return [re.sub(r"\s+", "", x).replace(",", "") for x in matches]


def numeric_claim_supported(claim: str, evidence: str) -> bool:
    claim_numbers = extract_numbers(claim)
    evidence_numbers = extract_numbers(evidence)
    return all(number in evidence_numbers for number in claim_numbers)


def get_evidence_credibility(quotes: list[dict], source_map: dict) -> float:
    """Score evidence using unique source domains rather than duplicate URLs."""
    unique_sources = {}
    for quote in quotes:
        sid = quote.get("source_id")
        if sid not in source_map:
            continue
        source = source_map[sid]
        domain = source.get("domain") or f"source-{sid}"
        score = get_source_credibility(source)
        unique_sources[domain] = max(unique_sources.get(domain, 0.0), score)

    scores = list(unique_sources.values())
    return round(sum(scores) / len(scores), 2) if scores else 0.0


def rank_verified_evidence(items: list[dict]) -> list[dict]:
    status = {"SUPPORTED": 3, "PARTIAL": 2, "UNSUPPORTED": 1}
    confidence = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    return sorted(
        items,
        key=lambda x: (
            status.get(x.get("status"), 0),
            confidence.get(x.get("confidence"), 0),
            x.get("evidence_credibility", 0),
        ),
        reverse=True,
    )


# =========================================================
# 1. DETERMINISTIC RESEARCH PLAN — ZERO GROQ CALLS
# =========================================================

def plan_research(state: ResearchState):
    question = state["question"].strip()
    state.setdefault("research_round", 0)
    state.setdefault("max_research_rounds", 1)
    state.setdefault("research_complete", False)
    state.setdefault("verification_failed", False)

    sub_questions = [
        f"What objective measurements, experiments, and quantitative studies report the impact of {question}?",
        f"What do major surveys, industry reports, and independent research organizations report about {question}?",
        f"How does the impact of {question} vary by task, user experience, workflow, or context?",
        f"What limitations, quality problems, security risks, disagreements, and counter-evidence are documented about {question}?",
    ]

    logger.info("Research plan created | sub_questions=%d", len(sub_questions))
    for i, item in enumerate(sub_questions, 1):
        logger.info("Research sub-question %d: %s", i, item)
    logger.info("Planning used no LLM request.")

    return {"sub_questions": sub_questions}


# =========================================================
# 2. PARALLEL SEARCH
# =========================================================

def create_search_tasks(state: ResearchState):
    return [
        Send("search", {"question": q, "result": [], "sources": []})
        for q in state["sub_questions"]
    ]


def search(state: SearchState):
    question = state["question"]
    logger.info("Web search started | question=%s", question)

    try:
        raw = search_web.invoke({"query": question})
        parsed = json.loads(raw)
    except Exception as exc:
        logger.exception("Search node failed | error_type=%s", type(exc).__name__)
        parsed = {"sources": []}

    sources = parsed.get("sources", [])
    research_text = f"RESEARCH QUESTION:\n{question}\n\nSEARCH RESULTS:\n"

    for source in sources:
        research_text += (
            f"Title: {source.get('title', '')}\n"
            f"URL: {source.get('url', '')}\n"
            f"Domain: {source.get('domain', '')}\n"
            f"Source type: {source.get('source_type', 'general_web')}\n"
            f"Credibility: {source.get('credibility_score', 0.40)}\n"
            f"Snippet: {source.get('snippet', '')}\n\n"
        )

    return {"result": [research_text], "sources": sources}


# =========================================================
# 3. GROQ EVIDENCE VERIFICATION — ONE CALL
# =========================================================

def verify_evidence(state: ResearchState):
    logger.info("Evidence verification started")

    sources = assign_source_ids(select_sources(state.get("sources", [])))
    source_map = {s["id"]: s for s in sources}

    if not sources:
        logger.warning("No sources available for verification.")
        return {
            "verified_evidence": state.get("verified_evidence", []),
            "verification_failed": True,
            "research_complete": True,
        }

    source_text = "\n\n".join(
        f"SOURCE [{s['id']}]\n"
        f"Title: {s['title']}\n"
        f"URL: {s['url']}\n"
        f"Domain: {s['domain']}\n"
        f"Type: {s['source_type']}\n"
        f"Level: {s['source_level']}\n"
        f"Credibility: {get_source_credibility(s):.2f}\n"
        f"Evidence: {s['snippet'][:1200]}"
        for s in sources
    )

    prompt = f"""
You are a strict evidence verifier for a research system.
Return ONLY valid JSON. No markdown. No explanation outside JSON.

QUESTION:
{state['question']}

SOURCES:
{source_text}

Find only important factual claims directly supported by the source snippets.
Return at most 8 claims.

For each claim use exactly this structure:
{{
  "claim": "specific factual claim",
  "source_ids": [1],
  "evidence_quotes": [{{"source_id": 1, "quote": "EXACT text copied from the snippet"}}],
  "status": "SUPPORTED",
  "confidence": "MEDIUM",
  "reason": "brief reason"
}}

Rules:
- Quote text must be copied exactly from the supplied snippet.
- Never invent source IDs or quotes.
- SUPPORTED means the snippet directly establishes the claim.
- PARTIAL means only part of the claim is established.
- UNSUPPORTED means the supplied snippets do not establish it.
- Quantitative claims require their exact numbers to appear in the quote.
- Do not infer numbers.
- Do not combine unrelated snippets into a stronger claim.
- Use HIGH confidence only when at least two independent domains support the same claim and the evidence quality is strong.
- Prefer primary sources for claims about official facts, measurements, product capabilities, regulations, research findings, or organizational statements.
- Do not treat multiple pages from the same domain as independent corroboration.
- If sources disagree, preserve the disagreement instead of merging them into one stronger claim.
- Match each claim to the source that directly establishes it; do not use a source merely because it discusses the general topic.
- Return [] when there is insufficient evidence.
"""

    response = safe_llm_invoke(prompt)
    if response is None:
        previous = state.get("verified_evidence", [])
        logger.warning("LLM verification failed; preserving previous verified evidence.")
        return {
            "verified_evidence": previous,
            "verification_failed": True,
            "research_complete": True,
        }

    parsed = extract_json(get_response_text(response))
    if not isinstance(parsed, list):
        logger.warning("LLM returned invalid evidence JSON.")
        previous = state.get("verified_evidence", [])
        return {
            "verified_evidence": previous,
            "verification_failed": True,
            "research_complete": True,
        }

    verified = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim", "")).strip()
        if not claim:
            continue

        source_ids = [
            x for x in item.get("source_ids", [])
            if isinstance(x, int) and x in source_map
        ]

        quotes = []
        for raw_quote in item.get("evidence_quotes", []):
            if not isinstance(raw_quote, dict):
                continue
            sid = raw_quote.get("source_id")
            quote = str(raw_quote.get("quote", "")).strip()
            if sid not in source_map or not quote:
                continue
            if normalize_text(quote) in normalize_text(source_map[sid]["snippet"]):
                quotes.append({"source_id": sid, "quote": quote})

        status = str(item.get("status", "UNSUPPORTED")).upper()
        confidence = str(item.get("confidence", "LOW")).upper()
        if status not in {"SUPPORTED", "PARTIAL", "UNSUPPORTED"}:
            status = "UNSUPPORTED"
        if confidence not in {"HIGH", "MEDIUM", "LOW"}:
            confidence = "LOW"

        evidence_text = " ".join(q["quote"] for q in quotes)
        quote_ids = {q["source_id"] for q in quotes}

        if not quotes:
            status, confidence = "UNSUPPORTED", "LOW"
            reason = "No returned quote could be matched to a retrieved source snippet."
        elif not quote_ids.intersection(source_ids):
            status, confidence = "UNSUPPORTED", "LOW"
            reason = "Validated quotes do not match the claimed source IDs."
        elif not numeric_claim_supported(claim, evidence_text):
            status, confidence = "UNSUPPORTED", "LOW"
            reason = "A number in the claim was not present in the validated evidence."
        else:
            reason = str(item.get("reason", "")).strip()

        domains = {
            source_map[q["source_id"]]["domain"]
            for q in quotes
            if source_map[q["source_id"]]["domain"]
        }
        credibility = get_evidence_credibility(quotes, source_map)

        if status == "SUPPORTED":
            primary_domains = {
                source_map[q["source_id"]]["domain"]
                for q in quotes
                if q.get("source_id") in source_map
                and source_map[q["source_id"]].get("source_level") == "primary"
            }
            if len(domains) >= 2 and primary_domains and credibility >= 0.70:
                confidence = "HIGH"
            elif len(domains) >= 1 and credibility >= 0.50:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"
        elif status == "PARTIAL" and confidence == "HIGH":
            confidence = "MEDIUM"

        verified.append({
            "claim": claim,
            "source_ids": source_ids,
            "evidence_quotes": quotes,
            "status": status,
            "confidence": confidence,
            "evidence_credibility": credibility,
            "reason": reason,
        })

    verified = rank_verified_evidence(verified)
    supported = sum(x["status"] == "SUPPORTED" for x in verified)
    partial = sum(x["status"] == "PARTIAL" for x in verified)
    unsupported = sum(x["status"] == "UNSUPPORTED" for x in verified)

    logger.info("Claims verified: %d", len(verified))
    logger.info("Supported claims: %d", supported)
    logger.info("Partial claims: %d", partial)
    logger.info("Unsupported claims: %d", unsupported)

    return {
        "verified_evidence": verified,
        "verification_failed": False,
        "research_complete": False,
    }


# =========================================================
# 4. WEAK CLAIM DETECTION + TARGETED SEARCH
# =========================================================

def get_weak_claims(state: ResearchState) -> list[dict]:
    return [
        item for item in state.get("verified_evidence", [])
        if item.get("status") != "SUPPORTED"
        or item.get("confidence") == "LOW"
    ]


def build_follow_up_queries(state: ResearchState) -> list[str]:
    stop_words = {
        "the", "a", "an", "and", "or", "of", "to", "in", "for", "on",
        "with", "from", "that", "this", "are", "is", "was", "were", "be",
        "by", "as", "how", "what", "which", "does", "do", "can", "may",
    }
    queries = []
    for item in get_weak_claims(state)[:3]:
        words = re.findall(r"[A-Za-z0-9%$.-]+", item.get("claim", ""))
        keywords = [w for w in words if w.lower() not in stop_words][:12]
        if not keywords:
            continue
        base = " ".join(keywords)
        claim_lower = item.get("claim", "").lower()
        if any(x in claim_lower for x in ("security", "vulnerab", "attack")):
            suffix = " security study evidence"
        elif any(x in claim_lower for x in ("productivity", "task", "speed", "output")):
            suffix = " productivity experiment study"
        elif any(x in claim_lower for x in ("percent", "%", "adoption", "survey")):
            suffix = " survey report statistics"
        else:
            suffix = " research study evidence"
        queries.append(base + suffix)

    unique = []
    seen = set()
    for q in queries:
        key = normalize_text(q)
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique[:3]


def deep_research(state: ResearchState):
    current = state.get("research_round", 0)
    maximum = state.get("max_research_rounds", 1)

    if state.get("verification_failed") or current >= maximum:
        return {"research_complete": True}

    queries = build_follow_up_queries(state)
    if not queries:
        return {"research_complete": True}

    logger.info("Deep research round %d/%d", current + 1, maximum)
    results = []
    sources = []

    for query in queries:
        logger.info("Targeted search: %s", query)
        try:
            parsed = json.loads(search_web.invoke({"query": query}))
        except Exception as exc:
            logger.exception("Targeted search failed | error_type=%s", type(exc).__name__)
            parsed = {"sources": []}
        found = parsed.get("sources", [])
        sources.extend(found)
        text = f"FOLLOW-UP RESEARCH QUESTION:\n{query}\n\nSEARCH RESULTS:\n"
        for source in found:
            text += (
                f"Title: {source.get('title', '')}\n"
                f"URL: {source.get('url', '')}\n"
                f"Domain: {source.get('domain', '')}\n"
                f"Snippet: {source.get('snippet', '')}\n\n"
            )
        results.append(text)

    return {
        "search_results": results,
        "sources": sources,
        "research_round": current + 1,
        "research_complete": False,
        "verification_failed": False,
    }


def should_continue_research(state: ResearchState) -> str:
    if state.get("verification_failed"):
        return "generate_answer"
    if state.get("research_round", 0) >= state.get("max_research_rounds", 1):
        return "generate_answer"
    if get_weak_claims(state):
        return "deep_research"
    return "generate_answer"


# =========================================================
# 5. FINAL REPORT
# =========================================================

def build_evidence_quality_section(evidence: list[dict]) -> str:
    lines = ["\n\n# Evidence Quality\n"]
    if not evidence:
        lines.append("No claims passed evidence verification.")
        return "\n".join(lines)
    for item in evidence:
        icon = "✅" if item["status"] == "SUPPORTED" else "⚠️" if item["status"] == "PARTIAL" else "❌"
        ids = " ".join(f"[{x}]" for x in item.get("source_ids", []))
        lines.append(
            f"- {icon} **{item['confidence']}** — {item['claim']} {ids} "
            f"(credibility: {item.get('evidence_credibility', 0):.2f})"
        )
    return "\n".join(lines)


def build_sources_section(answer: str, sources: list[dict]) -> str:
    cited_ids = {int(x) for x in re.findall(r"\[(\d+)\]", answer)}
    cited = [s for s in sources if s["id"] in cited_ids]
    lines = ["\n\n# Sources\n"]
    if not cited:
        lines.append("No sources were cited in the generated report.")
        return "\n".join(lines)
    for s in cited:
        lines.append(f"[{s['id']}] {s['title']} — {s['url']}")
    return "\n".join(lines)


def validate_citations(answer: str, sources: list[dict]) -> str:
    valid_ids = {str(s["id"]) for s in sources}
    return re.sub(
        r"\[(\d+)\]",
        lambda m: m.group(0) if m.group(1) in valid_ids else "",
        answer,
    )


def deterministic_report(state: ResearchState, sources: list[dict]) -> str:
    evidence = rank_verified_evidence(state.get("verified_evidence", []))
    lines = ["# Executive Summary", ""]
    if not evidence:
        lines.append(
            "The available search results could not be converted into deterministically "
            "verified claims. The system therefore does not present the retrieved material "
            "as established findings."
        )
        lines += ["", "# Evidence and Analysis", "", "No claims passed the evidence verification checks."]
        return "\n".join(lines)

    supported = [x for x in evidence if x["status"] == "SUPPORTED"]
    lines.append("The following findings were supported by retrieved source snippets and passed the system's evidence checks.")
    lines += ["", "# Evidence and Analysis", ""]
    for item in supported:
        refs = " ".join(f"[{x}]" for x in item["source_ids"])
        lines.append(f"- {item['claim']} {refs}")
    return "\n".join(lines)


def generate_answer(state: ResearchState):
    sources = assign_source_ids(deduplicate_sources(state.get("sources", [])))
    evidence = rank_verified_evidence(state.get("verified_evidence", []))

    # Never synthesize factual conclusions from raw search text when
    # verification produced no usable evidence.
    if not evidence:
        answer = deterministic_report(state, sources)
        logger.warning("No verified evidence; using safe deterministic report.")
    else:
        evidence_text = json.dumps(evidence, ensure_ascii=False, indent=2)
        prompt = f"""
You are an evidence-grounded research report writer.

QUESTION:
{state['question']}

VERIFIED EVIDENCE ONLY:
{evidence_text}

Write a concise professional report with:
# Executive Summary
# Key Findings
# Benefits / Positive Effects
# Limitations and Risks
# Evidence Gaps
# Conclusion

Rules:
1. Use ONLY the verified evidence above for factual claims.
2. Do not introduce facts from memory or raw search results.
3. Do not invent numbers.
4. Keep the wording proportional to the evidence.
5. Preserve disagreement or uncertainty.
6. Cite claims using only the source IDs already attached to the evidence, e.g. [3].
7. Do not create a Sources or Evidence Quality section.
"""
        response = safe_llm_invoke(prompt)
        if response is None:
            answer = deterministic_report(state, sources)
            logger.warning("Final LLM failed; using deterministic final-report fallback.")
        else:
            answer = get_response_text(response).strip()

    answer = validate_citations(answer, sources)
    answer += build_evidence_quality_section(evidence)
    answer += build_sources_section(answer, sources)

    cited_count = len(set(re.findall(r"\[(\d+)\]", answer)))
    logger.info("Unique sources collected: %d", len(sources))
    logger.info("Sources actually cited: %d", cited_count)

    return {"answer": answer, "sources": sources}


# =========================================================
# LANGGRAPH
# =========================================================

builder = StateGraph(ResearchState)
builder.add_node("plan_research", plan_research)
builder.add_node("search", search)
builder.add_node("verify_evidence", verify_evidence)
builder.add_node("deep_research", deep_research)
builder.add_node("generate_answer", generate_answer)

builder.add_edge(START, "plan_research")
builder.add_conditional_edges("plan_research", create_search_tasks, ["search"])
builder.add_edge("search", "verify_evidence")
builder.add_conditional_edges(
    "verify_evidence",
    should_continue_research,
    {"deep_research": "deep_research", "generate_answer": "generate_answer"},
)
builder.add_edge("deep_research", "verify_evidence")
builder.add_edge("generate_answer", END)

research_graph = builder.compile()
