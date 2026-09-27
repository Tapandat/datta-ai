"""
Research workflow for datta.ai.

The graph is designed to:
- classify the user's research question
- create focused research sub-questions
- search multiple sources in parallel
- rank and deduplicate evidence
- verify a compact evidence set with the LLM
- generate an evidence-backed report
- gracefully fall back when the LLM is temporarily unavailable
"""

from __future__ import annotations

import json
import re
import time
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from src.errors import ResearchError
from src.llm import get_response_text, llm
from src.logger import get_logger
from src.search import web_search


logger = get_logger("graph")


# ============================================================
# Constants
# ============================================================

MAX_PLAN_QUESTIONS = 4
MAX_SEARCH_RESULTS_PER_QUERY = 6
MAX_TOTAL_SOURCES = 12

MAX_VERIFICATION_SOURCES = 6
MAX_VERIFIED_CLAIMS = 6

MAX_SNIPPET_CHARS = 360
MAX_SOURCE_TITLE_CHARS = 150

MIN_LLM_INTERVAL_SECONDS = 1.5

_LAST_LLM_CALL = 0.0


# ============================================================
# State
# ============================================================

class ResearchState(TypedDict, total=False):
    question: str

    question_type: str
    topic: str
    context: str

    sub_questions: list[str]
    max_research_rounds: int

    search_results: Annotated[
        list[dict],
        lambda left, right: left + right,
    ]

    sources: list[dict]
    verification_sources: list[dict]

    evidence: list[dict]

    verification_status: str

    answer: str


class SearchState(TypedDict, total=False):
    """
    State passed to an individual parallel search worker.

    The query is input-only for the worker and is deliberately
    not returned into the shared graph state. This prevents
    concurrent 'query' updates from colliding in LangGraph.
    """

    query: str
    results: list[dict]


# ============================================================
# Text Helpers
# ============================================================

def clean_text(value: object) -> str:
    """Normalize arbitrary values into compact plain text."""

    if value is None:
        return ""

    text = str(value)

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def normalize_topic(value: str) -> str:
    """Clean a topic extracted from a natural-language question."""

    topic = clean_text(value)

    topic = re.sub(
        r"^(what|why|how|when|where|which|who)\s+",
        "",
        topic,
        flags=re.IGNORECASE,
    )

    topic = re.sub(
        r"^(is|are|was|were|does|do|did|can|could|would|should)\s+",
        "",
        topic,
        flags=re.IGNORECASE,
    )

    topic = re.sub(
        r"^to\s+implement\s+",
        "",
        topic,
        flags=re.IGNORECASE,
    )

    topic = re.sub(
        r"^i\s+implement\s+",
        "",
        topic,
        flags=re.IGNORECASE,
    )

    topic = re.sub(
        r"^implement\s+",
        "",
        topic,
        flags=re.IGNORECASE,
    )

    topic = re.sub(
        r"\s+work\b.*$",
        "",
        topic,
        flags=re.IGNORECASE,
    )

    topic = re.sub(
        r"\s+is\s+used\b.*$",
        "",
        topic,
        flags=re.IGNORECASE,
    )

    topic = re.sub(
        r"^the\s+difference\s+between\s+",
        "",
        topic,
        flags=re.IGNORECASE,
    )

    topic = re.sub(
        r"\s+and\s+how\b.*$",
        "",
        topic,
        flags=re.IGNORECASE,
    )

    topic = re.sub(
        r"\s+and\s+what\b.*$",
        "",
        topic,
        flags=re.IGNORECASE,
    )

    topic = re.sub(
        r"\s+in\s+real[- ]world.*$",
        "",
        topic,
        flags=re.IGNORECASE,
    )

    topic = re.sub(
        r"\s+for\s+real[- ]world.*$",
        "",
        topic,
        flags=re.IGNORECASE,
    )

    topic = topic.strip(
        " ?.,:;"
    )

    return topic or "the requested topic"


def shorten(
    value: str,
    limit: int,
) -> str:
    """Limit text length while keeping complete-looking content."""

    text = clean_text(
        value
    )

    if len(text) <= limit:
        return text

    return (
        text[:limit]
        .rstrip()
        + "..."
    )


# ============================================================
# Question Classification
# ============================================================

def classify_question(
    question: str,
) -> str:
    """Classify a research question."""

    text = clean_text(
        question
    ).lower()

    comparison_terms = (
        "difference between",
        "compare",
        "comparison",
        "versus",
        "vs.",
        " vs ",
    )

    forecasting_terms = (
        "forecast",
        "forecasting",
        "predict future",
        "future values",
        "time series prediction",
    )

    implementation_terms = (
        "how to implement",
        "implementation",
        "implement",
        "build",
        "develop",
        "create",
        "deploy",
        "deployment",
        "code for",
        "program for",
    )

    if any(
        term in text
        for term in comparison_terms
    ):
        return "comparison"

    if any(
        term in text
        for term in forecasting_terms
    ):
        return "forecasting"

    if any(
        term in text
        for term in implementation_terms
    ):
        return "implementation"

    return "concept"


# ============================================================
# Topic / Context Extraction
# ============================================================

def extract_topic_and_context(
    question: str,
) -> tuple[str, str]:
    """
    Extract the main topic and optional context.

    Examples:

    What is machine learning and how is it used in
    real-world applications?
        -> machine learning
        -> used in real-world applications

    How do I implement a machine learning model?
        -> machine learning

    How does ARIMA work for time series forecasting?
        -> ARIMA

    What is the difference between supervised and
    unsupervised learning?
        -> supervised and unsupervised learning
    """

    text = clean_text(
        question
    ).rstrip("?").strip()

    # --------------------------------------------------------
    # Comparison
    # --------------------------------------------------------

    difference_match = re.search(
        r"difference\s+between\s+(.+)$",
        text,
        flags=re.IGNORECASE,
    )

    if difference_match:
        topic = difference_match.group(1)

        return (
            normalize_topic(topic),
            "",
        )

    # --------------------------------------------------------
    # Implementation
    # --------------------------------------------------------

    implementation_match = re.search(
        r"implement\s+(?:a|an|the)?\s*(.+?)(?:\s+model)?$",
        text,
        flags=re.IGNORECASE,
    )

    if (
        implementation_match
        and classify_question(text)
        == "implementation"
    ):
        topic = implementation_match.group(1)

        return (
            normalize_topic(topic),
            "",
        )

    # --------------------------------------------------------
    # "How does X work..."
    # --------------------------------------------------------

    how_does_match = re.search(
        r"^how\s+does\s+(.+?)\s+work\b",
        text,
        flags=re.IGNORECASE,
    )

    if how_does_match:
        topic = how_does_match.group(1)

        return (
            normalize_topic(topic),
            "",
        )

    # --------------------------------------------------------
    # "What is X and how..."
    # --------------------------------------------------------

    and_how_match = re.search(
        r"^what\s+is\s+(.+?)\s+and\s+how\s+(.+)$",
        text,
        flags=re.IGNORECASE,
    )

    if and_how_match:
        topic = and_how_match.group(1)
        context = and_how_match.group(2)

        context = re.sub(
            r"^is\s+",
            "",
            context,
            flags=re.IGNORECASE,
        )

        context = re.sub(
            r"^are\s+",
            "",
            context,
            flags=re.IGNORECASE,
        )

        context = re.sub(
            r"^it\s+",
            "",
            context,
            flags=re.IGNORECASE,
        )

        # Normalize the full "is it used in ..." construction.
        context = re.sub(
            r"^it\s+is\s+used\s+in\s+",
            "",
            context,
            flags=re.IGNORECASE,
        )

        context = re.sub(
            r"^it\s+used\s+in\s+",
            "",
            context,
            flags=re.IGNORECASE,
        )

        context = re.sub(
            r"^is\s+used\s+in\s+",
            "",
            context,
            flags=re.IGNORECASE,
        )

        context = re.sub(
            r"^used\s+in\s+",
            "",
            context,
            flags=re.IGNORECASE,
        )

        context = re.sub(
            r"^it\s+",
            "",
            context,
            flags=re.IGNORECASE,
        )

        context = context.strip(
            " ?.,:;"
        )

        return (
            normalize_topic(topic),
            context,
        )

    # --------------------------------------------------------
    # "What is X?"
    # --------------------------------------------------------

    what_is_match = re.search(
        r"^what\s+is\s+(.+)$",
        text,
        flags=re.IGNORECASE,
    )

    if what_is_match:
        topic = what_is_match.group(1)

        return (
            normalize_topic(topic),
            "",
        )

    # --------------------------------------------------------
    # "How do I..."
    # --------------------------------------------------------

    how_do_match = re.search(
        r"^how\s+do\s+i\s+(.+)$",
        text,
        flags=re.IGNORECASE,
    )

    if how_do_match:
        topic = how_do_match.group(1)

        topic = re.sub(
            r"^implement\s+",
            "",
            topic,
            flags=re.IGNORECASE,
        )

        topic = re.sub(
            r"^build\s+",
            "",
            topic,
            flags=re.IGNORECASE,
        )

        topic = re.sub(
            r"^develop\s+",
            "",
            topic,
            flags=re.IGNORECASE,
        )

        return (
            normalize_topic(topic),
            "",
        )

    # --------------------------------------------------------
    # Generic fallback
    # --------------------------------------------------------

    return (
        normalize_topic(text),
        "",
    )


# ============================================================
# JSON Helpers
# ============================================================

def extract_json_object(
    text: str,
) -> dict | None:
    """Extract a JSON object from an LLM response."""

    cleaned = clean_text(
        text
    )

    if not cleaned:
        return None

    try:
        parsed = json.loads(
            cleaned
        )

        if isinstance(
            parsed,
            dict,
        ):
            return parsed

    except json.JSONDecodeError:
        pass

    match = re.search(
        r"\{.*\}",
        text,
        flags=re.DOTALL,
    )

    if not match:
        return None

    try:
        parsed = json.loads(
            match.group(0)
        )

        if isinstance(
            parsed,
            dict,
        ):
            return parsed

    except json.JSONDecodeError:
        return None

    return None


# ============================================================
# LLM Helpers
# ============================================================

def _wait_for_llm_slot() -> None:
    """Serialize LLM calls to reduce rate-limit bursts."""

    global _LAST_LLM_CALL

    now = time.monotonic()

    elapsed = (
        now - _LAST_LLM_CALL
    )

    if elapsed < MIN_LLM_INTERVAL_SECONDS:
        time.sleep(
            MIN_LLM_INTERVAL_SECONDS
            - elapsed
        )


def safe_llm_call(
    prompt: str,
    *,
    operation: str,
) -> str | None:
    """Call the configured LLM safely."""

    global _LAST_LLM_CALL

    _wait_for_llm_slot()

    try:
        response = llm.invoke(
            prompt
        )

        _LAST_LLM_CALL = time.monotonic()

        text = get_response_text(
            response
        ).strip()

        if not text:
            logger.warning(
                "LLM returned empty response | operation=%s",
                operation,
            )

            return None

        return text

    except Exception as exc:
        _LAST_LLM_CALL = time.monotonic()

        error_text = str(
            exc
        ).lower()

        if (
            "429" in error_text
            or "rate limit" in error_text
            or "too many requests" in error_text
            or "resource_exhausted" in error_text
        ):
            logger.warning(
                "Groq rate limit reached | operation=%s",
                operation,
            )

            return None

        logger.exception(
            "LLM call failed | operation=%s | error_type=%s",
            operation,
            type(exc).__name__,
        )

        return None


# ============================================================
# Source Helpers
# ============================================================

def source_key(
    source: dict,
) -> str:
    """Create a stable source identifier."""

    url = clean_text(
        source.get("url")
        or source.get("link")
        or ""
    )

    if url:
        return url.lower().rstrip(
            "/"
        )

    title = clean_text(
        source.get("title")
        or ""
    )

    domain = clean_text(
        source.get("domain")
        or ""
    )

    return (
        f"{domain}|{title}"
    ).lower()


def prepare_source(
    source: dict,
) -> dict:
    """Normalize a search result."""

    return {
        "title": shorten(
            clean_text(
                source.get(
                    "title"
                )
            ),
            MAX_SOURCE_TITLE_CHARS,
        ),
        "url": clean_text(
            source.get("url")
            or source.get("link")
        ),
        "domain": clean_text(
            source.get(
                "domain"
            )
        ),
        "snippet": shorten(
            clean_text(
                source.get(
                    "snippet"
                )
            ),
            MAX_SNIPPET_CHARS,
        ),
        "source_type": clean_text(
            source.get(
                "source_type"
            )
        ),
        "credibility_score": float(
            source.get(
                "credibility_score",
                0.0,
            )
            or 0.0
        ),
        "quality": clean_text(
            source.get(
                "quality"
            )
        ),
        "query_relevance_score": float(
            source.get(
                "query_relevance_score",
                0.0,
            )
            or 0.0
        ),
    }


def deduplicate_sources(
    sources: list[dict],
) -> list[dict]:
    """Remove duplicate sources."""

    seen = set()
    unique = []

    for source in sources:
        key = source_key(
            source
        )

        if not key or key in seen:
            continue

        seen.add(
            key
        )

        unique.append(
            source
        )

    return unique


def select_sources(
    sources: list[dict],
    *,
    limit: int,
) -> list[dict]:
    """Select diverse, high-quality sources."""

    prepared = [
        prepare_source(
            source
        )
        for source in sources
        if isinstance(
            source,
            dict,
        )
    ]

    prepared = deduplicate_sources(
        prepared
    )

    prepared.sort(
        key=lambda item: (
            item.get(
                "credibility_score",
                0.0,
            ),
            item.get(
                "query_relevance_score",
                0.0,
            ),
        ),
        reverse=True,
    )

    selected = []
    domain_counts: dict[str, int] = {}

    for source in prepared:
        domain = (
            source.get(
                "domain"
            )
            or "unknown"
        ).lower()

        if domain_counts.get(
            domain,
            0,
        ) >= 2:
            continue

        selected.append(
            source
        )

        domain_counts[domain] = (
            domain_counts.get(
                domain,
                0,
            )
            + 1
        )

        if len(selected) >= limit:
            break

    return selected


# ============================================================
# Evidence Helpers
# ============================================================

def build_evidence_payload(
    sources: list[dict],
) -> list[dict]:
    """Build compact source data for verification."""

    payload = []

    for index, source in enumerate(
        sources,
        start=1,
    ):
        payload.append(
            {
                "id": index,
                "title": shorten(
                    source.get(
                        "title",
                        "",
                    ),
                    140,
                ),
                "domain": source.get(
                    "domain",
                    "",
                ),
                "snippet": shorten(
                    source.get(
                        "snippet",
                        "",
                    ),
                    420,
                ),
                "url": source.get(
                    "url",
                    "",
                ),
            }
        )

    return payload


def extract_claims(
    verification: dict,
) -> list[dict]:
    """Normalize verified claims."""

    raw_claims = verification.get(
        "claims",
        [],
    )

    if not isinstance(
        raw_claims,
        list,
    ):
        return []

    claims = []

    for claim in raw_claims:
        if not isinstance(
            claim,
            dict,
        ):
            continue

        text = clean_text(
            claim.get(
                "claim"
            )
        )

        if not text:
            continue

        status = clean_text(
            claim.get(
                "status",
                "supported",
            )
        ).lower()

        if status not in {
            "supported",
            "partial",
            "unsupported",
        }:
            status = "supported"

        source_ids = claim.get(
            "source_ids",
            [],
        )

        if not isinstance(
            source_ids,
            list,
        ):
            source_ids = []

        cleaned_source_ids = []

        for source_id in source_ids:
            try:
                value = int(
                    source_id
                )

                if value > 0:
                    cleaned_source_ids.append(
                        value
                    )

            except (
                TypeError,
                ValueError,
            ):
                continue

        confidence = clean_text(
            claim.get(
                "confidence",
                "medium",
            )
        ).lower()

        if confidence not in {
            "high",
            "medium",
            "low",
        }:
            confidence = "medium"

        claims.append(
            {
                "claim": text,
                "status": status,
                "source_ids": cleaned_source_ids,
                "confidence": confidence,
            }
        )

    return claims[
        :MAX_VERIFIED_CLAIMS
    ]


def supported_claims(
    evidence: list[dict],
) -> list[dict]:
    """Return supported or partially supported evidence."""

    return [
        item
        for item in evidence
        if item.get(
            "status"
        )
        in {
            "supported",
            "partial",
        }
        and item.get(
            "source_ids"
        )
    ]


# ============================================================
# Research Planning
# ============================================================

def build_deterministic_plan(
    question: str,
) -> dict:
    """Create a focused research plan."""

    question_type = classify_question(
        question
    )

    topic, context = (
        extract_topic_and_context(
            question
        )
    )

    context_phrase = ""

    if context:
        context_phrase = (
            f" with emphasis on {context}"
        )

    if question_type == "comparison":
        sub_questions = [
            (
                f"What are the core definitions and "
                f"characteristics of {topic}?"
            ),
            (
                f"What are the main similarities and "
                f"differences involving {topic}?"
            ),
            (
                f"What practical use cases and "
                f"trade-offs are documented for {topic}?"
            ),
            (
                f"What limitations, risks, and evidence "
                f"gaps are documented for {topic}?"
            ),
        ]

    elif question_type == "forecasting":
        sub_questions = [
            (
                f"What are the fundamental concepts "
                f"behind {topic}{context_phrase}?"
            ),
            (
                f"How does {topic} work and what methods "
                f"are commonly used{context_phrase}?"
            ),
            (
                f"What evidence exists about forecasting "
                f"performance and practical applications "
                f"of {topic}?"
            ),
            (
                f"What limitations, assumptions, risks, "
                f"and evidence gaps affect {topic}?"
            ),
        ]

    elif question_type == "implementation":
        sub_questions = [
            (
                f"What are the fundamental concepts "
                f"behind {topic}{context_phrase}?"
            ),
            (
                f"What methods, tools, architectures, "
                f"or frameworks are commonly used for {topic}?"
            ),
            (
                f"What implementation steps, requirements, "
                f"and best practices are documented for {topic}?"
            ),
            (
                f"What limitations, risks, and common "
                f"implementation problems are documented?"
            ),
        ]

    else:
        if context:
            practical_question = (
                f"How is {topic} used in {context}?"
            )
        else:
            practical_question = (
                f"What practical applications, benefits, "
                f"and real-world uses of {topic} are documented?"
            )

        sub_questions = [
            (
                f"What is {topic} and what are its "
                f"fundamental concepts?"
            ),
            (
                f"How does {topic} work, and what methods "
                f"or mechanisms are commonly used?"
            ),
            practical_question,
            (
                f"What limitations, risks, challenges, "
                f"and evidence gaps are documented about {topic}?"
            ),
        ]

    return {
        "question_type": question_type,
        "topic": topic,
        "context": context,
        "sub_questions": sub_questions[
            :MAX_PLAN_QUESTIONS
        ],
        "max_research_rounds": 1,
    }


def plan_research(
    state: ResearchState,
) -> ResearchState:
    """Create the research plan."""

    question = clean_text(
        state.get(
            "question"
        )
    )

    if not question:
        raise ResearchError(
            "Research question is empty.",
            user_message=(
                "Please enter a research question."
            ),
        )

    plan = build_deterministic_plan(
        question
    )

    print()
    print(
        "🔎 RESEARCH PLAN"
    )
    print(
        f"Question type: "
        f"{plan['question_type']}"
    )
    print(
        f"Topic: "
        f"{plan['topic']}"
    )

    if plan["context"]:
        print(
            f"Context: "
            f"{plan['context']}"
        )

    for index, sub_question in enumerate(
        plan["sub_questions"],
        start=1,
    ):
        print(
            f"{index}. {sub_question}"
        )

    print(
        "ℹ️ Planning used no LLM request."
    )

    logger.info(
        "Research plan created | type=%s | topic=%s | sub_questions=%d",
        plan["question_type"],
        plan["topic"],
        len(
            plan["sub_questions"]
        ),
    )

    return {
        **state,
        **plan,
    }


# ============================================================
# Parallel Search
# ============================================================

def dispatch_searches(
    state: ResearchState,
):
    """Dispatch one search per research sub-question."""

    sub_questions = state.get(
        "sub_questions",
        [],
    )

    return [
        Send(
            "search",
            {
                "query": question,
            },
        )
        for question in sub_questions
    ]


def search_node(
    state: SearchState,
) -> dict:
    """
    Execute one web search.

    Important:
    The worker receives 'query' and returns its results through
    the parent state's reducer-backed 'search_results' key.
    Returning a plain 'results' key would cause concurrent state
    updates to collide because multiple Send branches execute together.
    """

    query = clean_text(
        state.get(
            "query"
        )
    )

    if not query:
        return {
            "search_results": [],
        }

    print()
    print(
        f"🌐 Searching: {query}"
    )

    try:
        results = web_search(
            query,
            max_results=MAX_SEARCH_RESULTS_PER_QUERY,
        )

        return {
            "search_results": results or [],
        }

    except Exception as exc:
        logger.exception(
            "Search node failed | error_type=%s",
            type(exc).__name__,
        )

        return {
            "search_results": [],
        }


def collect_search_results(
    state: ResearchState,
) -> ResearchState:
    """Collect and rank all search results."""

    raw_sources = state.get(
        "search_results",
        [],
    )

    selected = select_sources(
        raw_sources,
        limit=MAX_TOTAL_SOURCES,
    )

    print()
    print(
        f"📚 Unique sources collected: "
        f"{len(selected)}"
    )

    logger.info(
        "Search collection completed | sources=%d",
        len(selected),
    )

    return {
        **state,
        "sources": selected,
    }


# ============================================================
# Evidence Verification
# ============================================================

def build_verification_prompt(
    question: str,
    sources: list[dict],
) -> str:
    """Build a compact verification prompt."""

    payload = build_evidence_payload(
        sources
    )

    return f"""
You are the evidence verifier for datta.ai.

Research question:
{question}

Use ONLY the supplied sources.

Identify important factual claims that directly answer the research question.
Prioritize definitions, mechanisms, applications, findings, limitations, and other substantive facts.
Do NOT prioritize tangential market-size, promotional, navigation, section-summary, or article-description text unless the question explicitly asks for it.

Do not use outside knowledge.
Do not invent facts.
Do not make predictions.
Do not combine unrelated sources.

Return ONLY valid JSON:

{{
  "claims": [
    {{
      "claim": "short factual claim",
      "status": "supported",
      "source_ids": [1],
      "confidence": "high"
    }}
  ]
}}

Rules:
- status must be supported, partial, or unsupported.
- Include only claims with source_ids.
- Prefer supported claims.
- Maximum 6 claims.
- Each claim must be under 35 words.
- confidence must be high, medium, or low.
- If evidence is insufficient, omit the claim.

Sources:
{json.dumps(
    payload,
    ensure_ascii=False,
)}
""".strip()


def verify_evidence(
    state: ResearchState,
) -> ResearchState:
    """Verify a compact set of evidence."""

    sources = select_sources(
        state.get(
            "sources",
            [],
        ),
        limit=MAX_VERIFICATION_SOURCES,
    )

    if not sources:
        print()
        print(
            "🔍 VERIFYING EVIDENCE..."
        )
        print(
            "⚠️ No usable sources available for verification."
        )

        return {
            **state,
            "evidence": [],
            "verification_sources": [],
            "verification_status": "no_sources",
        }

    print()
    print(
        "🔍 VERIFYING EVIDENCE..."
    )

    prompt = build_verification_prompt(
        state["question"],
        sources,
    )

    response_text = safe_llm_call(
        prompt,
        operation="evidence_verification",
    )

    if not response_text:
        print(
            "   ⚠️ Evidence verification was unavailable."
        )
        print(
            "   ↪ Falling back to deterministic source-backed evidence."
        )

        fallback_evidence = (
            build_fallback_evidence(
                sources,
                state.get("question", ""),
            )
        )

        return {
            **state,
            "verification_sources": sources,
            "evidence": fallback_evidence,
            "verification_status": "fallback",
        }

    verification = extract_json_object(
        response_text
    )

    if not verification:
        logger.warning(
            "Verifier returned invalid JSON."
        )

        print(
            "   ⚠️ Evidence verifier returned invalid structured output."
        )
        print(
            "   ↪ Falling back to deterministic source-backed evidence."
        )

        fallback_evidence = (
            build_fallback_evidence(
                sources,
                state.get("question", ""),
            )
        )

        return {
            **state,
            "verification_sources": sources,
            "evidence": fallback_evidence,
            "verification_status": "fallback",
        }

    evidence = extract_claims(
        verification
    )

    evidence = [
        item
        for item in evidence
        if item.get(
            "source_ids"
        )
    ]

    if not evidence:
        print(
            "   ⚠️ No supported claims were returned by verification."
        )
        print(
            "   ↪ Falling back to deterministic source-backed evidence."
        )

        fallback_evidence = (
            build_fallback_evidence(
                sources,
                state.get("question", ""),
            )
        )

        return {
            **state,
            "sources": sources,
            "evidence": fallback_evidence,
            "verification_status": "fallback",
        }

    print(
        f"   ✓ Claims verified: "
        f"{len(evidence)}"
    )

    logger.info(
        "Evidence verification completed | claims=%d",
        len(evidence),
    )

    return {
        **state,
        "verification_sources": sources,
        "evidence": evidence,
        "verification_status": "verified",
    }


def _fallback_candidate_sentences(text: str) -> list[str]:
    """Extract substantive sentences from a search snippet."""

    text = clean_text(text)
    if not text:
        return []

    # Remove common search-result metadata and promotional prefixes.
    text = re.sub(
        r"^(?:\w{3}\s+\d{1,2},\s+\d{4}\s*[·•-]\s*)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*[·•-]\s*",
        "",
        text,
    )

    parts = re.split(r"(?<=[.!?])\s+|\s*[•|]\s*", text)
    candidates = []

    reject_patterns = (
        r"^section\s+\d",
        r"^chapter\s+\d",
        r"^explore\s+how\b",
        r"^dive\s+into\b",
        r"^discover\s+why\b",
        r"^here\s+are\b",
        r"^learn\s+more\b",
        r"^you\s+will\s+learn\b",
        r"^this\s+article\s+(?:explains|discusses|covers)\b",
        r"^this\s+(?:page|guide|post)\s+(?:explains|discusses|covers)\b",
        r"^read\s+more\b",
        r"^table\s+of\s+contents\b",
    )

    for part in parts:
        candidate = clean_text(part).strip(" -–—")
        if len(candidate) < 45:
            continue
        if len(candidate) > 360:
            candidate = shorten(candidate, 360)

        lower = candidate.lower()
        if any(re.search(pattern, lower) for pattern in reject_patterns):
            continue
        if lower.startswith(("updated ", "published ", "last updated ")):
            continue
        if re.match(r"^(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", lower):
            continue

        candidates.append(candidate)

    return candidates


def _fallback_is_relevant(candidate: str, question: str) -> bool:
    """Reject obvious tangential fallback claims."""

    q = clean_text(question).lower()
    c = candidate.lower()

    # Market-size claims are useful only for market-related questions.
    if "market" in c and not any(
        term in q for term in ("market", "industry size", "market size", "revenue")
    ):
        return False

    # Reject generic article/navigation language that survived sentence splitting.
    if any(
        phrase in c
        for phrase in (
            "section 2",
            "section 3",
            "section 4",
            "explore how",
            "dive into",
            "click here",
            "read more",
        )
    ):
        return False

    return True


def build_fallback_evidence(
    sources: list[dict],
    question: str = "",
) -> list[dict]:
    """Create conservative, relevant, source-backed evidence."""

    candidates: list[tuple[int, dict, str]] = []

    for index, source in enumerate(sources, start=1):
        snippet = clean_text(source.get("snippet"))
        if not snippet:
            continue

        sentences = _fallback_candidate_sentences(snippet)
        for sentence in sentences:
            if not _fallback_is_relevant(sentence, question):
                continue
            candidates.append((index, source, sentence))

    # Prefer stronger sources first, then substantive longer statements.
    candidates.sort(
        key=lambda item: (
            float(item[1].get("credibility_score", 0.0) or 0.0),
            float(item[1].get("query_relevance_score", 0.0) or 0.0),
            len(item[2]),
        ),
        reverse=True,
    )

    evidence = []
    seen_claims = set()
    seen_domains = set()

    for source_id, source, claim in candidates:
        normalized = re.sub(r"\W+", " ", claim.lower()).strip()
        if normalized in seen_claims:
            continue

        # Avoid allowing one domain to dominate the fallback evidence.
        domain = clean_text(source.get("domain")).lower()
        if domain and domain in seen_domains and len(seen_domains) < 4:
            continue

        seen_claims.add(normalized)
        if domain:
            seen_domains.add(domain)

        evidence.append(
            {
                "claim": clean_claim_for_report(claim),
                "status": "partial",
                "source_ids": [source_id],
                "confidence": (
                    "medium"
                    if float(source.get("credibility_score", 0.0) or 0.0) >= 0.60
                    else "low"
                ),
            }
        )

        if len(evidence) >= MAX_VERIFIED_CLAIMS:
            break

    return evidence


# ============================================================
# Deep Research
# ============================================================

def deep_research(
    state: ResearchState,
) -> ResearchState:
    """Perform one conservative follow-up research round."""

    existing_sources = state.get(
        "sources",
        [],
    )

    if not existing_sources:
        return state

    supported = supported_claims(
        state.get(
            "evidence",
            [],
        )
    )

    if supported:
        return state

    logger.info(
        "Deep research skipped | existing evidence=%d",
        len(supported),
    )

    return state


# ============================================================
# Report Helpers
# ============================================================

def clean_claim_for_report(
    claim: str,
) -> str:
    """Normalize claim text."""

    text = clean_text(
        claim
    )

    text = re.sub(
        r"\s+([,.!?;:])",
        r"\1",
        text,
    )

    text = re.sub(
        r"([.!?])\1+",
        r"\1",
        text,
    )

    text = re.sub(
        r"(\d)\s+%",
        r"\1%",
        text,
    )

    text = re.sub(
        r"(\d)\s+(percent|percentage)\b",
        r"\1 percent",
        text,
        flags=re.IGNORECASE,
    )

    return text


def _summary_fragment(claim: str) -> str:
    """Convert a claim into a clean sentence fragment."""

    text = clean_claim_for_report(claim).strip()
    text = re.sub(r"[.!?]+$", "", text).strip()

    if (
        len(text) >= 2
        and text[0].isupper()
        and text[1].islower()
    ):
        text = text[0].lower() + text[1:]

    return text


def build_executive_summary(
    findings: list[dict],
) -> str:
    """Build a concise evidence-backed summary."""

    usable_claims = [
        _summary_fragment(
            item["claim"]
        )
        for item in findings
        if item.get(
            "claim"
        )
    ]

    usable_claims = usable_claims[:3]

    if not usable_claims:
        return (
            "The available source material did not provide "
            "enough evidence for a verified summary."
        )

    if len(usable_claims) == 1:
        return (
            f"The research indicates that "
            f"{usable_claims[0]}."
        )

    if len(usable_claims) == 2:
        return (
            f"The research indicates that "
            f"{usable_claims[0]}. "
            f"It also shows that "
            f"{usable_claims[1]}."
        )

    return (
        f"The research indicates that "
        f"{usable_claims[0]}. "
        f"It also shows that "
        f"{usable_claims[1]}. "
        f"Additionally, "
        f"{usable_claims[2]}."
    )


def format_evidence_claim(
    evidence_item: dict,
) -> str:
    """Format one evidence item."""

    claim = clean_claim_for_report(
        evidence_item.get(
            "claim",
            "",
        )
    )

    source_ids = evidence_item.get(
        "source_ids",
        [],
    )

    citations = " ".join(
        f"[{source_id}]"
        for source_id in source_ids
    )

    return (
        f"{claim} "
        f"{citations}"
    ).strip()


def build_key_findings(
    evidence: list[dict],
) -> str:
    """Build key findings."""

    findings = supported_claims(
        evidence
    )

    if not findings:
        return (
            "No claims passed the evidence verification checks."
        )

    lines = []

    for item in findings[:6]:
        lines.append(
            f"- {format_evidence_claim(item)}"
        )

    return "\n".join(
        lines
    )


def build_benefits_section(
    evidence: list[dict],
) -> str:
    """Build benefits from verified evidence."""

    keywords = (
        "benefit",
        "improve",
        "efficien",
        "advantage",
        "value",
        "use",
        "application",
        "performance",
        "help",
        "enable",
    )

    candidates = []

    for item in supported_claims(
        evidence
    ):
        claim = clean_text(
            item.get(
                "claim"
            )
        )

        if any(
            keyword in claim.lower()
            for keyword in keywords
        ):
            candidates.append(
                item
            )

    if not candidates:
        return (
            "The available verified evidence did not support "
            "a separate benefits assessment."
        )

    return "\n".join(
        f"- {format_evidence_claim(item)}"
        for item in candidates[:4]
    )


def build_limitations_section(
    evidence: list[dict],
) -> str:
    """Build limitations and risks."""

    keywords = (
        "limit",
        "risk",
        "challenge",
        "drawback",
        "bias",
        "uncertain",
        "difficulty",
        "problem",
        "constraint",
    )

    candidates = []

    for item in supported_claims(
        evidence
    ):
        claim = clean_text(
            item.get(
                "claim"
            )
        )

        if any(
            keyword in claim.lower()
            for keyword in keywords
        ):
            candidates.append(
                item
            )

    if not candidates:
        return (
            "The retrieved verified evidence did not establish "
            "a separate limitations or risks assessment."
        )

    return "\n".join(
        f"- {format_evidence_claim(item)}"
        for item in candidates[:4]
    )


def build_evidence_gaps_section(
    evidence: list[dict],
) -> str:
    """Build an evidence-gap section."""

    partial = [
        item
        for item in evidence
        if item.get(
            "status"
        ) == "partial"
    ]

    if partial:
        return (
            "Some retrieved material was only partially supported "
            "or lacked sufficient corroboration for a stronger conclusion."
        )

    if not evidence:
        return (
            "The available source material was insufficient "
            "to establish reliable evidence."
        )

    return (
        "The report is limited to claims supported by the "
        "retrieved sources; topics not represented by those "
        "sources remain outside the evidence base."
    )


def build_evidence_quality_section(
    evidence: list[dict],
) -> str:
    """Build evidence quality ratings."""

    if not evidence:
        return (
            "# Evidence Quality\n\n"
            "No claims passed evidence verification."
        )

    lines = [
        "# Evidence Quality",
        "",
    ]

    for item in evidence[
        :MAX_VERIFIED_CLAIMS
    ]:
        confidence = item.get(
            "confidence",
            "medium",
        ).upper()

        status = item.get(
            "status",
            "supported",
        ).lower()

        if confidence == "HIGH":
            symbol = "✓"
        elif confidence == "LOW":
            symbol = "⚠️"
        else:
            symbol = "•"

        claim = clean_claim_for_report(
            item.get(
                "claim",
                "",
            )
        )

        citations = " ".join(
            f"[{source_id}]"
            for source_id in item.get(
                "source_ids",
                [],
            )
        )

        lines.append(
            f"- {symbol} **{confidence}** — "
            f"{claim} {citations} "
            f"({status})"
        )

    return "\n".join(
        lines
    )


def extract_citation_ids(
    answer: str,
) -> list[int]:
    """Extract source IDs referenced in the report."""

    values = re.findall(
        r"\[(\d+)\]",
        answer,
    )

    ids = []

    for value in values:
        try:
            number = int(
                value
            )

            if number not in ids:
                ids.append(
                    number
                )

        except ValueError:
            continue

    return ids


def build_sources_section(
    answer: str,
    sources: list[dict],
) -> str:
    """Build a source list containing cited sources."""

    citation_ids = extract_citation_ids(
        answer
    )

    if not citation_ids:
        return (
            "# Sources\n\n"
            "No sources were cited in the generated report."
        )

    lines = [
        "# Sources",
        "",
    ]

    for source_id in sorted(citation_ids):
        index = source_id - 1

        if (
            index < 0
            or index >= len(sources)
        ):
            continue

        source = sources[
            index
        ]

        title = clean_text(
            source.get(
                "title"
            )
        )

        url = clean_text(
            source.get(
                "url"
            )
        )

        if not title:
            title = "Untitled source"

        if url:
            lines.append(
                f"[{source_id}] "
                f"{title} — {url}"
            )
        else:
            lines.append(
                f"[{source_id}] "
                f"{title}"
            )

    if len(lines) == 2:
        lines.append(
            "No source metadata was available."
        )

    return "\n".join(
        lines
    )


# ============================================================
# Deterministic Report
# ============================================================

def deterministic_report(
    state: ResearchState,
) -> str:
    """Generate a safe evidence-backed report."""

    evidence = state.get(
        "evidence",
        [],
    )

    sources = state.get(
        "verification_sources",
        [],
    ) or state.get(
        "sources",
        [],
    )

    findings = supported_claims(
        evidence
    )

    if not findings:
        report = (
            "# Executive Summary\n\n"
            "The research workflow retrieved source material, "
            "but the available evidence could not be reliably "
            "verified. The report therefore avoids presenting "
            "unverified material as established findings.\n\n"
            "# Key Findings\n\n"
            "No claims passed the evidence verification checks.\n\n"
            "# Benefits / Positive Effects\n\n"
            "The available verified evidence did not support "
            "a separate benefits assessment.\n\n"
            "# Limitations and Risks\n\n"
            "The retrieved evidence did not provide enough "
            "verified material for a separate limitations and "
            "risks assessment.\n\n"
            "# Evidence Gaps\n\n"
            "The available source material was insufficient "
            "to establish reliable evidence.\n\n"
            "# Conclusion\n\n"
            "The available material was insufficient to produce "
            "verified findings."
        )

    else:
        summary = build_executive_summary(
            findings
        )

        key_findings = build_key_findings(
            findings
        )

        benefits = build_benefits_section(
            findings
        )

        limitations = build_limitations_section(
            findings
        )

        gaps = build_evidence_gaps_section(
            evidence
        )

        report = (
            "# Executive Summary\n\n"
            f"{summary}\n\n"
            "# Key Findings\n\n"
            f"{key_findings}\n\n"
            "# Benefits / Positive Effects\n\n"
            f"{benefits}\n\n"
            "# Limitations and Risks\n\n"
            f"{limitations}\n\n"
            "# Evidence Gaps\n\n"
            f"{gaps}\n\n"
            "# Conclusion\n\n"
            "The report is limited to claims that passed "
            "the application's source and evidence checks."
        )

    report += (
        "\n\n"
        + build_evidence_quality_section(
            evidence
        )
    )

    report += (
        "\n\n"
        + build_sources_section(
            report,
            sources,
        )
    )

    return report


# ============================================================
# Final Report
# ============================================================

def generate_final_report(
    state: ResearchState,
) -> ResearchState:
    """Generate the final research report."""

    evidence = state.get(
        "evidence",
        [],
    )

    sources = state.get(
        "sources",
        [],
    )

    verification_sources = state.get(
        "verification_sources",
        [],
    ) or sources[:MAX_VERIFICATION_SOURCES]

    verified = [
        item
        for item in evidence
        if item.get(
            "status"
        ) == "supported"
        and item.get(
            "source_ids"
        )
    ]

    partial = [
        item
        for item in evidence
        if item.get(
            "status"
        ) == "partial"
        and item.get(
            "source_ids"
        )
    ]

    cited_source_ids = set()

    for item in evidence:
        for source_id in item.get(
            "source_ids",
            [],
        ):
            cited_source_ids.add(
                source_id
            )

    print()
    print(
        f"🔎 Claims verified: "
        f"{len(verified) + len(partial)}"
    )

    print(
        f"🔗 Sources actually cited: "
        f"{len(cited_source_ids)}"
    )

    print(
        f"📑 Evidence items: "
        f"{len(evidence)}"
    )

    answer = deterministic_report(
        state
    )

    print(
        f"📚 Unique sources selected: "
        f"{len(sources)}"
    )

    print(
        f"🔍 Verification sources: "
        f"{len(verification_sources)}"
    )

    logger.info(
        "Research completed | unique_sources=%d | verification_sources=%d | cited_sources=%d | evidence_items=%d",
        len(sources),
        len(verification_sources),
        len(cited_source_ids),
        len(evidence),
    )

    return {
        **state,
        "answer": answer,
    }


# ============================================================
# Graph Construction
# ============================================================

builder = StateGraph(
    ResearchState
)

builder.add_node(
    "plan",
    plan_research,
)

builder.add_node(
    "search",
    search_node,
)

builder.add_node(
    "collect",
    collect_search_results,
)

builder.add_node(
    "verify",
    verify_evidence,
)

builder.add_node(
    "deep_research",
    deep_research,
)

builder.add_node(
    "report",
    generate_final_report,
)


builder.add_edge(
    START,
    "plan",
)

builder.add_conditional_edges(
    "plan",
    dispatch_searches,
    ["search"],
)

builder.add_edge(
    "search",
    "collect",
)

builder.add_edge(
    "collect",
    "verify",
)

builder.add_edge(
    "verify",
    "deep_research",
)

builder.add_edge(
    "deep_research",
    "report",
)

builder.add_edge(
    "report",
    END,
)


research_graph = builder.compile()