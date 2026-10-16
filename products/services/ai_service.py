"""
GenAI and Search Services for InfiShelf products.
Powered by Google Gemini (gemini-3.5-flash-lite) for low-latency, high-efficiency,
and maximum free-tier quota longevity.
"""
import os
import re
import json
import hashlib
import logging
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from products.models import Product

logger = logging.getLogger(__name__)

# Single lightweight, high-efficiency model for maximum quota endurance
ACTIVE_GEMINI_MODEL = "gemini-3.5-flash-lite"

# Try importing google.generativeai safely
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google.generativeai not installed; using dynamic fallback.")


# ---------------------------------------------------------------------------
# 1. Gemini Client Configuration
# ---------------------------------------------------------------------------

def get_gemini_model():
    """
    Initializes and returns a configured Gemini GenerativeModel using
    gemini-3.5-flash-lite for maximum operational uptime and longevity.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY', '')
    if not api_key or not GENAI_AVAILABLE:
        return None

    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(ACTIVE_GEMINI_MODEL)
    except Exception as e:
        logger.error(f"Error configuring Gemini with {ACTIVE_GEMINI_MODEL}: {e}")
        return None


# ---------------------------------------------------------------------------
# 2. Dynamic AI Description & Tag Generation
# ---------------------------------------------------------------------------

def generate_product_description(name: str, brand: str, category: str) -> dict:
    """
    Generates an engaging, retail-ready product description and semantic tags
    using Gemini (gemini-3.5-flash-lite).
    Uses SHA-256 caching (7 days) to preserve quota and eliminate redundant API calls.
    """
    normalized_key = f"{name.strip().lower()}:{brand.strip().lower()}:{category.strip().lower()}"
    cache_key = f"ai_desc:{hashlib.sha256(normalized_key.encode('utf-8')).hexdigest()}"

    cached = cache.get(cache_key)
    if cached:
        cached_copy = dict(cached)
        cached_copy["source"] = "cache"
        logger.info(f"⚡ [Cache Hit] Returning cached AI description for '{name}' (<5ms).")
        return cached_copy

    result = None
    model = get_gemini_model()
    if model:
        result = _generate_with_gemini(model, name, brand, category)

    if not result:
        # Dynamic fallback derived from input parameters without hardcoding
        result = {
            "description": (
                f"Discover {name} by {brand}. A standout selection in {category}, "
                f"thoughtfully crafted to deliver exceptional quality, superior taste or performance, "
                f"and outstanding consumer value on the retail shelf."
            ),
            "tags": [brand.lower(), category.lower(), "quality", "popular"],
            "source": "dynamic_fallback"
        }

    # Cache for 7 days (604800 seconds)
    cache.set(cache_key, result, timeout=604800)
    return result


def _generate_with_gemini(model, name: str, brand: str, category: str):
    """Queries Gemini API and extracts clean JSON response."""
    prompt = f"""You are an expert e-commerce retail copywriter.
Write a concise, compelling product description (2 to 3 sentences, 40-70 words) for:
- Product Name: {name}
- Brand: {brand}
- Category: {category}

Also suggest 4 to 6 relevant search tags as a JSON array.
Respond strictly in valid JSON format with no additional text:
{{
  "description": "...",
  "tags": ["tag1", "tag2", "tag3", "tag4"]
}}"""
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text)
            text = re.sub(r"```$", "", text).strip()

        data = json.loads(text)
        desc = data.get("description", "").strip()
        tags = data.get("tags", [])
        if desc:
            return {
                "description": desc,
                "tags": tags if isinstance(tags, list) else [],
                "source": "gemini"
            }
    except Exception as e:
        logger.warning(f"Gemini description generation error: {e}")
    return None


# ---------------------------------------------------------------------------
# 3. Dynamic Natural Language Query Parsing
# ---------------------------------------------------------------------------

def parse_natural_language_query(query: str) -> dict:
    """
    Parses a user natural language query using Gemini LLM (gemini-3.5-flash-lite).
    Extracts category aisle, brand, min/max price, semantic keywords, and summary.
    Cached for 24 hours to preserve API quota. Falls back seamlessly to regex heuristics if offline.
    """
    clean_query = query.strip()
    cache_key = f"ai_search:{hashlib.sha256(clean_query.lower().encode('utf-8')).hexdigest()}"

    cached = cache.get(cache_key)
    if cached:
        logger.info(f"⚡ [Cache Hit] Returning cached smart search intent for: '{clean_query}'")
        return cached

    # Fetch live distinct categories from the database for dynamic prompt grounding
    try:
        db_categories = list(Product.objects.values_list('category', flat=True).distinct())
    except Exception:
        db_categories = []

    parsed = None
    model = get_gemini_model()
    if model:
        parsed = _parse_query_with_gemini(model, clean_query, db_categories)

    if not parsed:
        parsed = _heuristic_parse_query(clean_query, db_categories)

    # Cache parsed intent for 24 hours (86400 seconds)
    cache.set(cache_key, parsed, timeout=86400)
    return parsed


def _parse_query_with_gemini(model, query: str, db_categories: list):
    """Uses Gemini to parse user query into structured search intent."""
    prompt = f"""You are an expert retail search intent parser for an e-commerce catalog.
User search query: "{query}"

Available product categories in catalog:
{json.dumps(db_categories)}

Extract the search intent and respond strictly with valid JSON with no markdown wrapping:
{{
  "category": "<exact category string from the list above, or null if none clearly match>",
  "brand": "<brand name mentioned in query like Coca-Cola or Dove, or null>",
  "max_price": <numeric max price or null>,
  "min_price": <numeric min price or null>,
  "keywords": ["<core search terms without prepositions or prices>"],
  "summary": "<1-sentence friendly summary of what the shopper wants>"
}}"""
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text)
            text = re.sub(r"```$", "", text).strip()

        data = json.loads(text)
        keywords = data.get("keywords") or []
        if isinstance(keywords, str):
            keywords = [keywords]

        return {
            "query": query,
            "category": data.get("category"),
            "brand": data.get("brand"),
            "max_price": data.get("max_price"),
            "min_price": data.get("min_price"),
            "keywords": keywords,
            "extracted_search": " ".join(keywords) if keywords else query,
            "summary": data.get("summary", f"Search for {query}"),
            "source": "gemini"
        }
    except Exception as e:
        logger.warning(f"Gemini natural language parsing error: {e}")
        return None


def _heuristic_parse_query(query: str, db_categories: list) -> dict:
    """Offline heuristic fallback using regex and database token matching."""
    max_price = _extract_max_price(query)
    min_price = _extract_min_price(query)
    category = _detect_category_from_tokens(query, db_categories)
    cleaned_term = _clean_search_keywords(query)
    keywords = [w for w in cleaned_term.split() if len(w) > 2]

    return {
        "query": query,
        "category": category,
        "brand": None,
        "max_price": max_price,
        "min_price": min_price,
        "keywords": keywords,
        "extracted_search": cleaned_term,
        "summary": f"Search matching '{query}'",
        "source": "heuristic_fallback"
    }


def _detect_category_from_tokens(text: str, db_categories: list):
    """Detects category using token intersection."""
    query_tokens = set(re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()))
    if not query_tokens:
        return None

    for cat in db_categories:
        cat_tokens = set(re.findall(r'\b[a-zA-Z]{3,}\b', cat.lower()))
        for q_word in query_tokens:
            q_stem = q_word.rstrip('s')
            for c_word in cat_tokens:
                c_stem = c_word.rstrip('s')
                if q_stem == c_stem or q_stem in c_word or c_stem in q_word:
                    return cat

    return None


def _extract_max_price(text: str):
    """Extracts upper price bounds (e.g. 'under $5', 'less than 10')."""
    match = re.search(r'(?:under|below|less than|<)\s*\$?([0-9]+(?:\.[0-9]{1,2})?)', text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def _extract_min_price(text: str):
    """Extracts lower price bounds (e.g. 'above $5', 'more than 10')."""
    match = re.search(r'(?:above|over|more than|>)\s*\$?([0-9]+(?:\.[0-9]{1,2})?)', text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def _clean_search_keywords(text: str) -> str:
    """Strips prepositions and price expressions to isolate search keywords."""
    cleaned = re.sub(r'(?:under|below|less than|above|over|more than|<|>)\s*\$?[0-9]+(?:\.[0-9]{1,2})?', '', text, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b(?:for|with|in|and|show|me|find)\b', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else text


# ---------------------------------------------------------------------------
# 4. Dynamic Query Builder for Smart Search
# ---------------------------------------------------------------------------

def build_smart_search_queryset(base_queryset, parsed_filters: dict):
    """
    Applies category, brand, price, and semantic keyword filters to base queryset.
    Uses intelligent relaxation so shoppers find relevant products rather than empty results.
    """
    qs = base_queryset

    # 1. Price Bounds (Hard constraints)
    if parsed_filters.get("max_price") is not None:
        qs = qs.filter(price__lte=parsed_filters["max_price"])

    if parsed_filters.get("min_price") is not None:
        qs = qs.filter(price__gte=parsed_filters["min_price"])

    # 2. Category Filter
    cat = parsed_filters.get("category")
    if cat:
        qs = qs.filter(category__iexact=cat)

    # 3. Brand Filter
    brand = parsed_filters.get("brand")
    if brand:
        qs = qs.filter(brand__icontains=brand)

    # 4. Semantic Keyword Stems
    keywords = parsed_filters.get("keywords") or []
    extracted = parsed_filters.get("extracted_search", "")

    search_terms = []
    if keywords and isinstance(keywords, list):
        search_terms.extend(keywords)
    elif extracted:
        search_terms.extend(extracted.split())

    stop_words = {
        'under', 'below', 'less', 'than', 'above', 'over', 'more',
        'for', 'with', 'show', 'find', 'the', 'and', 'all', 'any'
    }

    keyword_query = Q()
    has_keywords = False

    for item in search_terms:
        for token in str(item).split():
            word = token.strip().lower()
            if len(word) <= 2 or word in stop_words or re.match(r'^\$?[0-9]+(?:\.[0-9]{1,2})?$', word):
                continue
            if brand and word in brand.lower():
                continue
            if cat and word in cat.lower():
                continue

            stem = word.rstrip('s') if len(word) > 3 else word
            keyword_query |= (
                Q(name__icontains=stem) |
                Q(brand__icontains=stem) |
                Q(description__icontains=stem) |
                Q(tags__icontains=stem)
            )
            has_keywords = True

    if has_keywords:
        refined_qs = qs.filter(keyword_query)
        if refined_qs.exists() or (not cat and not brand):
            return refined_qs

    return qs

