import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from ddgs import DDGS

from src.logger import get_logger


logger = get_logger("search")


# ============================================================
# SEARCH CONFIGURATION
# ============================================================

DEFAULT_MAX_RESULTS = 8

# Minimum relevance accepted when a query contains enough
# meaningful terms to make relevance measurable.
MIN_RELEVANCE_SCORE = 0.50

# Prevent one domain from dominating a search result set.
MAX_RESULTS_PER_DOMAIN = 2


# ============================================================
# DOMAIN HELPERS
# ============================================================

def get_domain(url: str) -> str:
    """Return a normalized domain from a URL."""

    try:
        domain = urlparse(
            str(url or "")
        ).netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:
        return ""


def get_source_type(domain: str) -> str:
    """Classify a source using its domain."""

    domain = (
        domain or ""
    ).lower()


    # Government
    if (
        domain.endswith(".gov")
        or ".gov." in domain
    ):
        return "government"


    # Academic institutions
    if (
        domain.endswith(".edu")
        or ".edu." in domain
    ):
        return "academic"


    academic_domains = (
        "arxiv.org",
        "nature.com",
        "science.org",
        "sciencedirect.com",
        "springer.com",
        "acm.org",
        "ieee.org",
        "cell.com",
        "pnas.org",
        "bmj.com",
        "plos.org",
    )

    if any(
        domain == item
        or domain.endswith(
            "." + item
        )
        for item in academic_domains
    ):
        return "academic"


    research_domains = (
        "nasa.gov",
        "who.int",
        "worldbank.org",
        "oecd.org",
        "imf.org",
        "nist.gov",
        "nih.gov",
        "cdc.gov",
        "usgs.gov",
        "noaa.gov",
    )

    if any(
        domain == item
        or domain.endswith(
            "." + item
        )
        for item in research_domains
    ):
        return "research_organization"


    company_domains = (
        "openai.com",
        "anthropic.com",
        "google.com",
        "deepmind.google",
        "microsoft.com",
        "meta.com",
        "nvidia.com",
        "aws.amazon.com",
        "ibm.com",
    )

    if any(
        domain == item
        or domain.endswith(
            "." + item
        )
        for item in company_domains
    ):
        return "official_company"


    technical_domains = (
        "github.com",
        "gitlab.com",
    )

    if any(
        domain == item
        or domain.endswith(
            "." + item
        )
        for item in technical_domains
    ):
        return "technical_repository"


    news_domains = (
        "reuters.com",
        "bbc.com",
        "bbc.co.uk",
        "nytimes.com",
        "apnews.com",
        "techcrunch.com",
        "theguardian.com",
    )

    if any(
        domain == item
        or domain.endswith(
            "." + item
        )
        for item in news_domains
    ):
        return "news"


    industry_domains = (
        "gartner.com",
        "mckinsey.com",
        "deloitte.com",
        "accenture.com",
    )

    if any(
        domain == item
        or domain.endswith(
            "." + item
        )
        for item in industry_domains
    ):
        return "industry_research"


    return "general_web"


# ============================================================
# DOMAIN REPUTATION
# ============================================================

def get_domain_reputation(
    domain: str,
) -> float:
    """
    Return a heuristic domain reputation score in [0, 1].

    Reputation is only a ranking signal. It does not prove
    that a source is factually correct.
    """

    domain = (
        domain or ""
    ).lower()


    high_reputation = {
        "arxiv.org",
        "nature.com",
        "science.org",
        "sciencedirect.com",
        "springer.com",
        "acm.org",
        "ieee.org",
        "cell.com",
        "pnas.org",
        "bmj.com",
        "plos.org",
        "nasa.gov",
        "who.int",
        "worldbank.org",
        "oecd.org",
        "imf.org",
        "nist.gov",
        "nih.gov",
        "cdc.gov",
        "usgs.gov",
        "noaa.gov",
    }


    if (
        domain.endswith(".gov")
        or ".gov." in domain
        or domain.endswith(".edu")
        or ".edu." in domain
        or domain in high_reputation
    ):
        return 0.95


    official_companies = {
        "openai.com",
        "anthropic.com",
        "google.com",
        "deepmind.google",
        "microsoft.com",
        "meta.com",
        "nvidia.com",
        "aws.amazon.com",
        "ibm.com",
    }


    if any(
        domain == item
        or domain.endswith(
            "." + item
        )
        for item in official_companies
    ):
        return 0.85


    reputable_news = {
        "reuters.com",
        "bbc.com",
        "bbc.co.uk",
        "nytimes.com",
        "apnews.com",
        "techcrunch.com",
        "theguardian.com",
    }


    if any(
        domain == item
        or domain.endswith(
            "." + item
        )
        for item in reputable_news
    ):
        return 0.85


    if (
        domain in {
            "github.com",
            "gitlab.com",
        }
        or domain.endswith(
            ".github.com"
        )
    ):
        return 0.75


    industry = {
        "gartner.com",
        "mckinsey.com",
        "deloitte.com",
        "accenture.com",
    }


    if any(
        domain == item
        or domain.endswith(
            "." + item
        )
        for item in industry
    ):
        return 0.70


    return 0.40


# ============================================================
# SOURCE LEVEL
# ============================================================

def get_source_level(
    source_type: str,
) -> str:
    """Classify a source as primary or secondary."""

    primary_types = {
        "government",
        "academic",
        "official_company",
        "research_organization",
        "technical_repository",
    }


    return (
        "primary"
        if source_type
        in primary_types
        else "secondary"
    )


# ============================================================
# RECENCY
# ============================================================

def estimate_recency_score(
    result: dict,
):
    """
    Estimate recency from an available date field.

    DDGS does not always provide reliable machine-readable
    publication dates, so None is returned when unavailable.
    """

    date_value = (
        result.get("date")
        or result.get("published")
        or result.get("published_date")
    )


    if not date_value:
        return None


    try:

        date_text = str(
            date_value
        ).strip()


        if date_text.endswith(
            "Z"
        ):
            date_text = (
                date_text[:-1]
                + "+00:00"
            )


        published = (
            datetime.fromisoformat(
                date_text
            )
        )


        if published.tzinfo is None:
            published = published.replace(
                tzinfo=timezone.utc
            )


        now = datetime.now(
            timezone.utc
        )


        age_days = max(
            0,
            (
                now
                - published.astimezone(
                    timezone.utc
                )
            ).days,
        )


        if age_days <= 30:
            return 1.00

        if age_days <= 90:
            return 0.90

        if age_days <= 365:
            return 0.75

        if age_days <= 730:
            return 0.60

        return 0.40


    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None


# ============================================================
# TEXT / QUERY HELPERS
# ============================================================

def _clean_text(
    value,
) -> str:
    """Normalize text from a search result."""

    if value is None:
        return ""


    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def _tokenize(
    text: str,
) -> list[str]:
    """Tokenize searchable text."""

    return re.findall(
        r"[a-z0-9]+",
        str(
            text or ""
        ).lower(),
    )


def _meaningful_query_terms(
    query: str,
) -> set[str]:
    """
    Extract meaningful query terms.

    Generic research words are removed so they do not
    artificially inflate relevance.
    """

    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "for",
        "on",
        "with",
        "from",
        "that",
        "this",
        "are",
        "is",
        "was",
        "were",
        "be",
        "by",
        "as",
        "how",
        "what",
        "which",
        "does",
        "do",
        "can",
        "may",
        "about",
        "report",
        "reports",
        "study",
        "studies",
        "research",
        "researches",
        "objective",
        "objectives",
        "major",
        "independent",
        "documented",
        "documentation",
        "impact",
        "effects",
        "effect",
        "using",
        "use",
        "used",
        "data",
        "information",
        "analysis",
        "analyses",
    }


    return {
        token
        for token in _tokenize(
            query
        )
        if (
            len(token) >= 3
            and token not in stop_words
        )
    }


# ============================================================
# QUERY RELEVANCE
# ============================================================

def estimate_query_relevance(
    query: str,
    result: dict,
) -> float:
    """
    Estimate how closely a result matches the query.

    Title matches receive more weight than snippet-only matches.
    This helps prevent high-reputation but weakly related pages
    from dominating the evidence pool.
    """

    query_terms = (
        _meaningful_query_terms(
            query
        )
    )


    if not query_terms:
        return 0.50


    title = str(
        result.get(
            "title",
            "",
        )
        or ""
    ).lower()


    snippet = str(
        result.get(
            "snippet",
            "",
        )
        or ""
    ).lower()


    title_terms = set(
        _tokenize(
            title
        )
    )


    snippet_terms = set(
        _tokenize(
            snippet
        )
    )


    title_overlap = (
        len(
            query_terms
            & title_terms
        )
        / len(
            query_terms
        )
    )


    snippet_overlap = (
        len(
            query_terms
            & snippet_terms
        )
        / len(
            query_terms
        )
    )


    # Title relevance is more informative than a single
    # accidental word in a long snippet.
    score = (
        title_overlap * 0.65
        + snippet_overlap * 0.35
    )


    # Preserve a useful baseline for very short queries.
    if len(
        query_terms
    ) == 1:
        if (
            title_overlap >= 1.0
            or snippet_overlap >= 1.0
        ):
            return 1.00

        return 0.40


    if score >= 0.75:
        return 1.00

    if score >= 0.55:
        return 0.85

    if score >= 0.40:
        return 0.70

    if score >= 0.25:
        return 0.55

    return 0.40


# ============================================================
# SPECIFICITY
# ============================================================

def estimate_specificity(
    result: dict,
) -> float:
    """Estimate how specifically a result describes its topic."""

    text = " ".join(
        str(
            result.get(
                key,
                "",
            )
            or ""
        )
        for key in (
            "title",
            "snippet",
        )
    ).strip()


    length = len(
        text
    )


    if length >= 500:
        return 0.90

    if length >= 250:
        return 0.80

    if length >= 100:
        return 0.65

    return 0.50


# ============================================================
# CREDIBILITY
# ============================================================

def calculate_credibility_score(
    domain_reputation: float,
    recency_score,
    specificity_score: float,
    source_level: str,
    query_relevance_score: float = 0.50,
) -> float:
    """
    Calculate a combined source-quality score.

    IMPORTANT:
    Relevance is deliberately included as a major component.
    A highly reputable source that does not actually address
    the question should not automatically outrank a relevant
    research source.
    """

    primary_bonus = (
        0.08
        if source_level == "primary"
        else 0.0
    )


    # When publication date is unavailable, reputation,
    # relevance and specificity carry the score.
    if recency_score is None:

        score = (
            domain_reputation * 0.45
            + query_relevance_score * 0.35
            + specificity_score * 0.12
            + primary_bonus
        )


    else:

        score = (
            domain_reputation * 0.38
            + query_relevance_score * 0.30
            + recency_score * 0.15
            + specificity_score * 0.09
            + primary_bonus
        )


    return round(
        min(
            max(
                score,
                0.0,
            ),
            1.0,
        ),
        2,
    )


# ============================================================
# QUALITY LABEL
# ============================================================

def get_quality_label(
    score: float,
) -> str:
    """Convert a score into a readable quality label."""

    if score >= 0.85:
        return "high"

    if score >= 0.65:
        return "good"

    if score >= 0.50:
        return "moderate"

    return "low"


def estimate_source_quality(
    url: str,
) -> str:
    """Return a quality label for a source URL."""

    domain = get_domain(
        url
    )

    score = get_domain_reputation(
        domain
    )

    return get_quality_label(
        score
    )


# ============================================================
# DDGS SEARCH
# ============================================================

def _run_ddgs_search(
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
):
    """
    Execute DDGS safely.

    Provider failures are converted to an empty result list
    so one failed search cannot crash the research graph.
    """

    try:

        return list(
            DDGS().text(
                query,
                max_results=max_results,
            )
        )

    except Exception as exc:

        logger.warning(
            "Web search returned no usable results | "
            "error_type=%s | message=%s",
            type(
                exc
            ).__name__,
            str(
                exc
            ),
        )

        return []


# ============================================================
# RESULT NORMALIZATION
# ============================================================

def _normalize_result(
    query: str,
    result: dict,
):
    """Convert a raw DDGS result into normalized metadata."""

    title = _clean_text(
        result.get(
            "title",
            "",
        )
    )


    url = _clean_text(
        result.get(
            "href"
        )
        or result.get(
            "url"
        )
        or ""
    )


    snippet = _clean_text(
        result.get(
            "body"
        )
        or result.get(
            "snippet"
        )
        or ""
    )


    if not url:
        return None


    domain = get_domain(
        url
    )


    if not domain:
        return None


    source_type = get_source_type(
        domain
    )


    source_level = get_source_level(
        source_type
    )


    domain_reputation = (
        get_domain_reputation(
            domain
        )
    )


    recency_score = (
        estimate_recency_score(
            result
        )
    )


    query_relevance_score = (
        estimate_query_relevance(
            query,
            {
                "title": title,
                "snippet": snippet,
            },
        )
    )


    specificity_score = (
        estimate_specificity(
            {
                "title": title,
                "snippet": snippet,
            }
        )
    )


    credibility_score = (
        calculate_credibility_score(
            domain_reputation=domain_reputation,
            recency_score=recency_score,
            specificity_score=specificity_score,
            source_level=source_level,
            query_relevance_score=query_relevance_score,
        )
    )


    return {
        "title": title,
        "url": url,
        "snippet": snippet,
        "domain": domain,
        "quality": get_quality_label(
            credibility_score
        ),
        "source_type": source_type,
        "source_level": source_level,
        "domain_reputation": domain_reputation,
        "recency_score": recency_score,
        "specificity_score": specificity_score,
        "query_relevance_score": query_relevance_score,
        "credibility_score": credibility_score,
    }


# ============================================================
# DEDUPLICATION
# ============================================================

def _normalize_url(
    url: str,
) -> str:
    """Normalize a URL for duplicate detection."""

    try:

        parsed = urlparse(
            str(
                url
                or ""
            ).strip()
        )


        return (
            f"{parsed.scheme.lower()}://"
            f"{parsed.netloc.lower()}"
            f"{parsed.path.rstrip('/')}"
        )


    except Exception:
        return str(
            url
            or ""
        ).strip().lower()


def _deduplicate_results(
    results: list[dict],
) -> list[dict]:
    """Remove duplicate URLs."""

    unique = []
    seen = set()


    for result in results:

        key = _normalize_url(
            result.get(
                "url",
                "",
            )
        )


        if not key:
            continue


        if key in seen:
            continue


        seen.add(
            key
        )

        unique.append(
            result
        )


    return unique


# ============================================================
# RELEVANCE FILTER
# ============================================================

def _filter_by_relevance(
    query: str,
    results: list[dict],
) -> list[dict]:
    """
    Remove clearly weakly related results.

    For very short queries, filtering is intentionally relaxed.
    """

    query_terms = (
        _meaningful_query_terms(
            query
        )
    )


    # Do not aggressively filter a query with only one
    # meaningful term such as "time series".
    if len(
        query_terms
    ) <= 1:
        return results


    filtered = [
        result
        for result in results
        if result.get(
            "query_relevance_score",
            0.0,
        ) >= MIN_RELEVANCE_SCORE
    ]


    # Never return nothing merely because the heuristic was
    # too strict. Fall back to the best available results.
    if filtered:
        return filtered


    return sorted(
        results,
        key=lambda item: (
            item.get(
                "query_relevance_score",
                0.0,
            ),
            item.get(
                "credibility_score",
                0.0,
            ),
        ),
        reverse=True,
    )[:max(
        1,
        min(
            3,
            len(
                results
            ),
        ),
    )]


# ============================================================
# DIVERSITY RANKING
# ============================================================

def _select_diverse_results(
    results: list[dict],
    max_results: int,
) -> list[dict]:
    """
    Select high-quality results while limiting domain dominance.
    """

    ranked = sorted(
        results,
        key=lambda item: (
            item.get(
                "credibility_score",
                0.0,
            ),
            item.get(
                "query_relevance_score",
                0.0,
            ),
            item.get(
                "specificity_score",
                0.0,
            ),
            item.get(
                "recency_score",
                0.0,
            )
            or 0.0,
        ),
        reverse=True,
    )


    selected = []
    domain_counts = {}


    # First preference: a strong primary source.
    for item in ranked:

        if (
            item.get(
                "source_level"
            )
            == "primary"
        ):

            selected.append(
                item
            )

            domain = item.get(
                "domain",
                "",
            )

            domain_counts[
                domain
            ] = 1

            break


    # Then maximize source diversity.
    for item in ranked:

        if len(
            selected
        ) >= max_results:
            break


        if item in selected:
            continue


        domain = item.get(
            "domain",
            "",
        )


        if (
            domain_counts.get(
                domain,
                0,
            )
            >= MAX_RESULTS_PER_DOMAIN
        ):
            continue


        selected.append(
            item
        )


        domain_counts[
            domain
        ] = (
            domain_counts.get(
                domain,
                0,
            )
            + 1
        )


    # Fill remaining slots if diversity rules leave capacity.
    if len(
        selected
    ) < max_results:

        for item in ranked:

            if len(
                selected
            ) >= max_results:
                break


            if item in selected:
                continue


            selected.append(
                item
            )


    return selected[
        :max_results
    ]


# ============================================================
# PUBLIC SEARCH FUNCTION
# ============================================================

def web_search(
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> list[dict]:
    """
    Search the web and return normalized, ranked source metadata.

    Pipeline:

        query
          ↓
        DDGS
          ↓
        normalize
          ↓
        relevance scoring
          ↓
        weak-result filtering
          ↓
        credibility scoring
          ↓
        source diversity
          ↓
        final results
    """

    query = _clean_text(
        query
    )


    if not query:

        logger.warning(
            "Web search skipped because query was empty."
        )

        return []


    max_results = max(
        1,
        int(
            max_results
        ),
    )


    logger.info(
        "Web search started | "
        "query_chars=%d | "
        "max_results=%d",
        len(
            query
        ),
        max_results,
    )


    raw_results = _run_ddgs_search(
        query,
        max_results=max_results,
    )


    if not raw_results:

        logger.warning(
            "Web search completed with zero results."
        )

        return []


    normalized = []


    for raw_result in raw_results:

        result = _normalize_result(
            query,
            raw_result,
        )


        if result is None:
            continue


        normalized.append(
            result
        )


    if not normalized:

        logger.warning(
            "Web search returned no normalized results."
        )

        return []


    # Remove exact duplicate URLs.
    normalized = _deduplicate_results(
        normalized
    )


    # Remove results that are clearly unrelated.
    normalized = _filter_by_relevance(
        query,
        normalized,
    )


    # Rank by relevance + credibility + specificity.
    selected = _select_diverse_results(
        normalized,
        max_results,
    )


    logger.info(
        "Web search completed | "
        "results=%d | "
        "selected=%d",
        len(
            normalized
        ),
        len(
            selected
        ),
    )


    # Log the strongest source domains for diagnostics,
    # without logging full source contents.
    top_domains = [
        item.get(
            "domain",
            "",
        )
        for item in selected[:5]
    ]


    logger.info(
        "Top source domains: %s",
        ", ".join(
            top_domains
        ),
    )


    return selected