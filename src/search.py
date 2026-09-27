import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from ddgs import DDGS

from src.errors import SearchError
from src.logger import get_logger


logger = get_logger("search")


def get_domain(url: str) -> str:
    """Return a normalized domain from a URL."""
    try:
        domain = urlparse(url).netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:
        return ""


def get_source_type(domain: str) -> str:
    """Classify a source using its domain."""
    domain = (domain or "").lower()

    if domain.endswith(".gov") or ".gov." in domain:
        return "government"

    if domain.endswith(".edu") or ".edu." in domain:
        return "academic"

    academic_domains = (
        "arxiv.org",
        "nature.com",
        "science.org",
        "sciencedirect.com",
        "springer.com",
        "acm.org",
        "ieee.org",
    )

    if any(
        domain == item or domain.endswith("." + item)
        for item in academic_domains
    ):
        return "academic"

    research_domains = (
        "nasa.gov",
        "who.int",
        "worldbank.org",
        "oecd.org",
        "imf.org",
    )

    if any(
        domain == item or domain.endswith("." + item)
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
        domain == item or domain.endswith("." + item)
        for item in company_domains
    ):
        return "official_company"

    technical_domains = (
        "github.com",
        "gitlab.com",
    )

    if any(
        domain == item or domain.endswith("." + item)
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
        domain == item or domain.endswith("." + item)
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
        domain == item or domain.endswith("." + item)
        for item in industry_domains
    ):
        return "industry_research"

    return "general_web"


def get_domain_reputation(domain: str) -> float:
    """Return a heuristic domain reputation score in [0, 1]."""
    domain = (domain or "").lower()

    if (
        domain.endswith(".gov")
        or ".gov." in domain
        or domain.endswith(".edu")
        or ".edu." in domain
        or domain in {
            "arxiv.org",
            "nature.com",
            "science.org",
            "sciencedirect.com",
            "springer.com",
            "acm.org",
            "ieee.org",
            "nasa.gov",
            "who.int",
            "worldbank.org",
            "oecd.org",
            "imf.org",
        }
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
        domain == item or domain.endswith("." + item)
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
        domain == item or domain.endswith("." + item)
        for item in reputable_news
    ):
        return 0.85

    if domain in {"github.com", "gitlab.com"} or domain.endswith(
        ".github.com"
    ):
        return 0.75

    industry = {
        "gartner.com",
        "mckinsey.com",
        "deloitte.com",
        "accenture.com",
    }

    if any(
        domain == item or domain.endswith("." + item)
        for item in industry
    ):
        return 0.70

    return 0.40


def get_source_level(source_type: str) -> str:
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
        if source_type in primary_types
        else "secondary"
    )


def estimate_recency_score(result: dict):
    """
    Estimate recency from an available date field.

    DDGS providers do not always return reliable machine-readable
    publication dates, so None is returned when no usable date exists.
    """
    date_value = (
        result.get("date")
        or result.get("published")
        or result.get("published_date")
    )

    if not date_value:
        return None

    try:
        date_text = str(date_value).strip()

        if date_text.endswith("Z"):
            date_text = date_text[:-1] + "+00:00"

        published = datetime.fromisoformat(date_text)

        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)

        age_days = max(
            0,
            (now - published.astimezone(timezone.utc)).days,
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

    except (TypeError, ValueError, OverflowError):
        return None


def estimate_query_relevance(
    query: str,
    result: dict,
) -> float:
    """Estimate how closely a result matches the search query."""
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
        "study",
        "research",
    }

    query_terms = {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            str(query).lower(),
        )
        if len(token) >= 3 and token not in stop_words
    }

    if not query_terms:
        return 0.50

    text = " ".join(
        str(result.get(key, "") or "")
        for key in ("title", "snippet")
    ).lower()

    result_terms = set(
        re.findall(r"[a-z0-9]+", text)
    )

    overlap = (
        len(query_terms & result_terms)
        / len(query_terms)
    )

    if overlap >= 0.70:
        return 1.00

    if overlap >= 0.50:
        return 0.85

    if overlap >= 0.30:
        return 0.70

    if overlap >= 0.15:
        return 0.55

    return 0.40


def estimate_specificity(result: dict) -> float:
    """Estimate how specifically a search result describes its topic."""
    text = " ".join(
        str(result.get(key, "") or "")
        for key in ("title", "snippet")
    ).strip()

    length = len(text)

    if length >= 500:
        return 0.90

    if length >= 250:
        return 0.80

    if length >= 100:
        return 0.65

    return 0.50


def calculate_credibility_score(
    domain_reputation: float,
    recency_score,
    specificity_score: float,
    source_level: str,
    query_relevance_score: float = 0.50,
) -> float:
    """
    Calculate a heuristic credibility score.

    Credibility is a ranking signal, not proof that a source is true.
    """
    primary_bonus = (
        0.10
        if source_level == "primary"
        else 0.0
    )

    if recency_score is None:
        score = (
            domain_reputation * 0.70
            + specificity_score * 0.20
            + primary_bonus
        )
    else:
        score = (
            domain_reputation * 0.55
            + recency_score * 0.20
            + specificity_score * 0.15
            + primary_bonus
        )

    return round(
        min(score, 1.0),
        2,
    )


def get_quality_label(score: float) -> str:
    """Convert a credibility score into a readable quality label."""
    if score >= 0.85:
        return "high"

    if score >= 0.65:
        return "good"

    if score >= 0.50:
        return "moderate"

    return "low"


def estimate_source_quality(url: str) -> str:
    """Return a simple quality label for a source URL."""
    domain = get_domain(url)
    score = get_domain_reputation(domain)

    return get_quality_label(score)


def _clean_text(value) -> str:
    """Normalize a search-result text field."""
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def _run_ddgs_search(
    query: str,
    max_results: int = 8,
):
    """
    Execute DDGS safely.

    Search-provider failures are converted into an empty result set
    so one failed search cannot crash the complete research workflow.
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
            type(exc).__name__,
            str(exc),
        )

        return []


def web_search(
    query: str,
    max_results: int = 8,
) -> list[dict]:
    """
    Search the web and return normalized source metadata.

    Search failures are intentionally converted into an empty list
    so one failed parallel search cannot crash the research graph.
    """
    query = _clean_text(query)

    if not query:
        logger.warning(
            "Web search skipped because query was empty"
        )
        return []

    logger.info(
        "Web search started | query_chars=%d | max_results=%d",
        len(query),
        max_results,
    )

    results = _run_ddgs_search(
        query,
        max_results=max_results,
    )

    normalized = []

    for result in results:
        title = _clean_text(
            result.get("title", "")
        )

        url = _clean_text(
            result.get("href")
            or result.get("url")
            or ""
        )

        snippet = _clean_text(
            result.get("body")
            or result.get("snippet")
            or ""
        )

        if not url:
            continue

        domain = get_domain(url)

        source_type = get_source_type(
            domain
        )

        source_level = get_source_level(
            source_type
        )

        domain_reputation = get_domain_reputation(
            domain
        )

        recency_score = estimate_recency_score(
            result
        )

        query_relevance_score = estimate_query_relevance(
            query,
            {
                "title": title,
                "snippet": snippet,
            },
        )

        specificity_score = estimate_specificity(
            {
                "title": title,
                "snippet": snippet,
            }
        )

        credibility_score = calculate_credibility_score(
            domain_reputation=domain_reputation,
            recency_score=recency_score,
            specificity_score=specificity_score,
            source_level=source_level,
            query_relevance_score=query_relevance_score,
        )

        normalized.append(
            {
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
        )

    normalized.sort(
        key=lambda item: (
            item["credibility_score"],
            item["query_relevance_score"],
            item["specificity_score"],
        ),
        reverse=True,
    )

    selected = []
    domain_counts = {}

    # Prefer at least one primary source whenever possible.
    for item in normalized:
        if item["source_level"] == "primary":
            selected.append(item)
            domain_counts[item["domain"]] = 1
            break

    # Apply source diversity.
    for item in normalized:
        if len(selected) >= max_results:
            break

        if item in selected:
            continue

        domain = item["domain"]
        count = domain_counts.get(domain, 0)

        if count >= 2:
            continue

        selected.append(item)
        domain_counts[domain] = count + 1

    # Fill remaining capacity with the best remaining sources.
    if len(selected) < max_results:
        for item in normalized:
            if len(selected) >= max_results:
                break

            if item not in selected:
                selected.append(item)

    logger.info(
        "Web search completed | results=%d | selected=%d",
        len(normalized),
        len(selected),
    )

    return selected[:max_results]