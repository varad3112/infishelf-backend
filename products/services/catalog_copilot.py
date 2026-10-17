"""
Conversational Analytics Copilot ("Chat with Your Catalog") for InfiShelf.
Powered by Google Gemini (gemini-3.5-flash-lite) and safe, deterministic Django ORM aggregations.
Zero raw SQL execution.
"""
import functools
import hashlib
import json
import logging
import operator
import os
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional
from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg, Min, Max, Sum, Count, Q
from products.models import Product

logger = logging.getLogger(__name__)

ACTIVE_GEMINI_MODEL = "gemini-3.5-flash-lite"

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    GENAI_AVAILABLE = False


def get_gemini_model():
    """Initializes and returns configured Gemini GenerativeModel."""
    api_key = getattr(settings, 'GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY', '')
    if not api_key or not GENAI_AVAILABLE or genai is None:
        return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(ACTIVE_GEMINI_MODEL)
    except Exception as e:
        logger.error(f"Error configuring Gemini for Copilot: {e}")
        return None


def ask_catalog_copilot(query: str, history: list | None = None) -> dict:
    """
    Main entrypoint for Conversational Analytics Copilot.
    1. Checks SHA-256 query cache.
    2. Uses Gemini to parse query into safe structured intent.
    3. Executes safe Django ORM queries (counts, averages, group-bys, filtered lists).
    4. Uses Gemini to synthesize an executive, formatted answer.
    5. Returns structured answer, statistics, matched product cards, and token usage.
    """
    clean_query = query.strip()
    if not clean_query:
        return {
            "answer": "Please ask a question about your catalog, products, prices, or categories.",
            "data": None,
            "products": [],
            "tokens": {"prompt_tokens": 0, "candidate_tokens": 0, "total_tokens": 0},
            "source": "empty_query"
        }

    # Caching (1 hour cache for exact identical query)
    cache_key = f"copilot:{hashlib.sha256(clean_query.lower().encode('utf-8')).hexdigest()}"
    cached_res = cache.get(cache_key)
    if cached_res:
        logger.info("⚡ [Cache Hit] Returning cached Copilot response for '%s' (<5ms, 0 tokens consumed).", clean_query)
        cached_copy = dict(cached_res)
        cached_copy["source"] = "cache"
        return cached_copy

    # Fetch live distinct categories and brands for prompt grounding
    try:
        db_categories = list(Product.objects.values_list('category', flat=True).distinct())
        db_brands = list(Product.objects.values_list('brand', flat=True).distinct()[:30])
        total_skus = Product.objects.count()
    except Exception as e:
        logger.error(f"Error reading database catalog metadata: {e}")
        db_categories = []
        db_brands = []
        total_skus = 0

    model = get_gemini_model()
    tokens_tracker = {"prompt_tokens": 0, "candidate_tokens": 0, "total_tokens": 0}

    # Step 1: Parse query intent
    intent = None
    if model:
        intent = _parse_intent_with_gemini(model, clean_query, db_categories, db_brands, total_skus, tokens_tracker)

    if not intent:
        intent = _heuristic_intent_fallback(clean_query, db_categories, db_brands)

    # Step 2: Safe ORM Execution
    orm_result = _execute_safe_orm(intent, clean_query)

    # Step 3: Synthesize conversational executive response
    answer_text = None
    if model:
        answer_text = _synthesize_with_gemini(model, clean_query, intent, orm_result, tokens_tracker)

    if not answer_text:
        answer_text = _heuristic_synthesis_fallback(clean_query, intent, orm_result)

    # Structured response payload
    response_payload = {
        "answer": answer_text,
        "intent_type": intent.get("intent_type", "general"),
        "raw_stats": orm_result.get("stats"),
        "products": orm_result.get("products", []),
        "tokens": tokens_tracker,
        "source": "gemini" if model else "deterministic_engine"
    }

    # Cache response for 1 hour (3600 seconds)
    cache.set(cache_key, response_payload, timeout=3600)
    return response_payload


# ---------------------------------------------------------------------------
# Intent Parsing with Gemini
# ---------------------------------------------------------------------------

def _parse_intent_with_gemini(model, query: str, db_categories: list, db_brands: list, total_skus: int, tokens_tracker: dict) -> dict | None:
    prompt = f"""You are the query intent parser for InfiShelf Product Catalog Copilot.
Available Categories in Catalog: {json.dumps(db_categories)}
Sample Brands: {json.dumps(db_brands[:20])}
Total Catalog SKUs: {total_skus}

User question: "{query}"

Analyze the question and output STRICT JSON only (no markdown, no backticks, no comments) adhering to:
{{
  "intent_type": "aggregation" | "filter_list" | "comparison" | "overview" | "missing_attributes",
  "group_by": "category" | "brand" | null,
  "metric": "avg_price" | "count" | "min_price" | "max_price" | "total_value" | null,
  "filters": {{
    "category": "<exact category string from list above or null>",
    "brand": "<brand name mentioned in query or null>",
    "min_price": <number or null>,
    "max_price": <number or null>,
    "search_text": "<text to search in name/description or null>"
  }},
  "ordering": "-price" | "price" | "-count" | "-avg_price" | "avg_price" | "-created_at" | null,
  "limit": <integer 1 to 10>
}}"""

    try:
        resp = model.generate_content(prompt)
        _record_tokens(resp, tokens_tracker, "Intent Parsing")

        text = resp.text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text)
            text = re.sub(r"```$", "", text).strip()

        data = json.loads(text)
        return data
    except Exception as e:
        logger.warning(f"Failed to parse copilot intent with Gemini: {e}")
        return None


# ---------------------------------------------------------------------------
# Safe Deterministic Django ORM Execution Engine
# ---------------------------------------------------------------------------

def _execute_safe_orm(intent: dict, raw_query: str) -> dict:
    """
    Executes strictly bounded Django ORM queries without raw SQL.
    """
    intent_type = intent.get("intent_type", "general")
    group_by = intent.get("group_by")
    raw_filters = intent.get("filters")
    filters = raw_filters if isinstance(raw_filters, dict) else {}
    ordering = intent.get("ordering") or "-price"
    limit = max(1, min(int(intent.get("limit") or 5), 10))

    # Base QuerySet
    qs = Product.objects.all()

    # Apply safe filters
    cat = filters.get("category")
    if cat:
        qs = qs.filter(category__iexact=cat.strip())

    brand = filters.get("brand")
    if brand:
        qs = qs.filter(brand__icontains=brand.strip())

    min_p = filters.get("min_price")
    if min_p is not None:
        try:
            qs = qs.filter(price__gte=Decimal(str(min_p)))
        except Exception:
            pass

    max_p = filters.get("max_price")
    if max_p is not None:
        try:
            qs = qs.filter(price__lte=Decimal(str(max_p)))
        except Exception:
            pass

    search_txt = filters.get("search_text")
    if search_txt:
        qs = qs.filter(
            functools.reduce(
                operator.or_,
                [
                    Q(name__icontains=search_txt),
                    Q(description__icontains=search_txt),
                    Q(tags__contains=[search_txt.lower()]),
                ],
            )
        )

    # Special intent: Missing attributes / tags
    if intent_type == "missing_attributes":
        qs = qs.filter(
            functools.reduce(
                operator.or_,
                [
                    Q(tags=[]),
                    Q(tags__isnull=True),
                    Q(description__isnull=True),
                    Q(description=""),
                ],
            )
        )

    # Execute Aggregations
    stats_data = {}
    matched_products = []

    # 1. Grouped Aggregations (e.g., "Which category has highest average price?", "Brand with most SKUs")
    if group_by in ("category", "brand"):
        field = group_by
        order_field = '-avg_price' if 'avg' in str(ordering) else ('-count' if 'count' in str(ordering) else '-count')
        grouped_results = (
            qs.values(field)
            .annotate(
                count=Count('id'),
                avg_price=Avg('price'),
                min_price=Min('price'),
                max_price=Max('price')
            )
            .order_by(order_field)[:limit]
        )
        formatted_groups = []
        for g in grouped_results:
            formatted_groups.append({
                field: g[field],
                "count": g["count"],
                "avg_price": round(float(g["avg_price"] or 0), 2),
                "min_price": round(float(g["min_price"] or 0), 2),
                "max_price": round(float(g["max_price"] or 0), 2),
            })
        stats_data["group_by"] = field
        stats_data["groups"] = formatted_groups

        # Grab representative products for the top group to show cards
        if formatted_groups:
            top_val = formatted_groups[0].get(field)
            filter_kwargs = {field: top_val}
            sample_prods = qs.filter(**filter_kwargs).order_by('-price')[:4]
            matched_products = _serialize_mini_products(sample_prods)

    # 2. Global Catalog Overview
    elif intent_type == "overview" or "catalog" in raw_query.lower() and "total" in raw_query.lower():
        total_count = qs.count()
        aggs = qs.aggregate(
            avg_p=Avg('price'),
            min_p=Min('price'),
            max_p=Max('price'),
            total_val=Sum('price')
        )
        stats_data["overview"] = {
            "total_products": total_count,
            "average_price": round(float(aggs['avg_p'] or 0), 2),
            "min_price": round(float(aggs['min_p'] or 0), 2),
            "max_price": round(float(aggs['max_p'] or 0), 2),
            "total_value": round(float(aggs['total_val'] or 0), 2),
        }
        # Grab top 4 most expensive products
        matched_products = _serialize_mini_products(qs.order_by('-price')[:4])

    # 3. Filtered Product List or Comparison
    else:
        total_matched = qs.count()
        aggs = qs.aggregate(
            avg_p=Avg('price'),
            min_p=Min('price'),
            max_p=Max('price')
        )
        stats_data["filter_summary"] = {
            "total_matches": total_matched,
            "average_price": round(float(aggs['avg_p'] or 0), 2) if aggs['avg_p'] else 0,
            "min_price": round(float(aggs['min_p'] or 0), 2) if aggs['min_p'] else 0,
            "max_price": round(float(aggs['max_p'] or 0), 2) if aggs['max_p'] else 0,
        }

        # Safe ordering whitelist
        safe_ordering = '-price'
        if ordering in ('price', '-price', 'created_at', '-created_at', 'name', '-name'):
            safe_ordering = ordering

        items = qs.order_by(safe_ordering)[:limit]
        matched_products = _serialize_mini_products(items)

    return {
        "stats": stats_data,
        "products": matched_products
    }


def _serialize_mini_products(queryset) -> list:
    """Serializes minimal product metadata for interactive in-chat cards."""
    results = []
    for p in queryset:
        results.append({
            "id": str(p.id),
            "name": p.name,
            "brand": p.brand,
            "category": p.category,
            "price": float(p.price),
            "image_url": p.image_url,
            "tags": p.tags or []
        })
    return results


# ---------------------------------------------------------------------------
# Executive Response Synthesis with Gemini
# ---------------------------------------------------------------------------

def _synthesize_with_gemini(model, user_query: str, intent: dict, orm_result: dict, tokens_tracker: dict) -> str | None:
    prompt = f"""You are the senior Catalog Intelligence Copilot for InfiShelf, an enterprise retail merchandising platform.
The user asked: "{user_query}"

Deterministic catalog database query results:
{json.dumps(orm_result, indent=2)}

Task:
Write a crisp, authoritative, professional executive answer (2 to 4 sentences or concise bullet points).
- State the exact direct answer clearly first (with INR ₹ currency symbol).
- Highlight key patterns, averages, or top drivers based on the data.
- Mention 1 or 2 specific products if provided.
- Do not make up numbers not present in the data.
- Maintain a modern, confident enterprise tone."""

    try:
        resp = model.generate_content(prompt)
        _record_tokens(resp, tokens_tracker, "Response Synthesis")
        return resp.text.strip()
    except Exception as e:
        logger.warning(f"Failed to synthesize response with Gemini: {e}")
        return None


# ---------------------------------------------------------------------------
# Token Tracker Helper
# ---------------------------------------------------------------------------

def _record_tokens(response, tracker: dict, step_name: str):
    """Extracts and accumulates token metrics from Gemini response."""
    usage = getattr(response, 'usage_metadata', None)
    if usage:
        p_tokens = getattr(usage, 'prompt_token_count', 0)
        c_tokens = getattr(usage, 'candidates_token_count', 0)
        t_tokens = getattr(usage, 'total_token_count', 0) or (p_tokens + c_tokens)
        tracker["prompt_tokens"] += p_tokens
        tracker["candidate_tokens"] += c_tokens
        tracker["total_tokens"] += t_tokens

        logger.info(
            "📊 [Copilot Token Usage - %s] Prompt: %d | Candidate: %d | Step Total: %d (Cumulative: %d)",
            step_name, p_tokens, c_tokens, t_tokens, tracker["total_tokens"]
        )


# ---------------------------------------------------------------------------
# Deterministic Fallbacks (When Gemini / Internet is Offline)
# ---------------------------------------------------------------------------

def _heuristic_intent_fallback(query: str, db_categories: list, db_brands: list) -> dict:
    q = query.lower()
    filters: Dict[str, Any] = {}
    intent: Dict[str, Any] = {
        "intent_type": "filter_list",
        "group_by": None,
        "metric": None,
        "filters": filters,
        "ordering": "-price",
        "limit": 5
    }

    if "category" in q and ("average" in q or "highest" in q or "expensive" in q or "most" in q):
        intent["intent_type"] = "aggregation"
        intent["group_by"] = "category"
        intent["metric"] = "avg_price"
        intent["ordering"] = "-avg_price"
        return intent

    if "brand" in q and ("most" in q or "count" in q or "skus" in q or "sku" in q):
        intent["intent_type"] = "aggregation"
        intent["group_by"] = "brand"
        intent["metric"] = "count"
        intent["ordering"] = "-count"
        return intent

    if "overview" in q or "total" in q or "entire catalog" in q or "inventory value" in q:
        intent["intent_type"] = "overview"
        return intent

    if "missing" in q and ("tag" in q or "description" in q):
        intent["intent_type"] = "missing_attributes"
        return intent

    # Check for category match
    for cat in db_categories:
        if cat.lower() in q:
            filters["category"] = cat
            break

    # Check for brand match
    for b in db_brands:
        if b.lower() in q:
            filters["brand"] = b
            break

    # Price heuristics
    price_match = re.search(r'(?:above|over|more than|>|>=)\s*₹?\s*(\d+)', q)
    if price_match:
        filters["min_price"] = float(price_match.group(1))

    price_under = re.search(r'(?:under|below|less than|<|<=)\s*₹?\s*(\d+)', q)
    if price_under:
        filters["max_price"] = float(price_under.group(1))

    return intent


def _heuristic_synthesis_fallback(query: str, intent: dict, orm_result: dict) -> str:
    stats = orm_result.get("stats", {})
    products = orm_result.get("products", [])

    if stats.get("groups"):
        group_field = stats.get("group_by", "category")
        top = stats["groups"][0]
        val = top.get(group_field)
        avg_p = top.get("avg_price", 0)
        cnt = top.get("count", 0)
        return (
            f"Based on real-time catalog analytics, **{val}** leads with an average unit price of ₹{avg_p} "
            f"across {cnt} active SKUs. Detailed breakdown by {group_field} is summarized below."
        )

    if "overview" in stats:
        ov = stats["overview"]
        return (
            f"Your InfiShelf catalog currently tracks **{ov.get('total_products', 0)} active SKUs** "
            f"with a cumulative catalog inventory value of ₹{ov.get('total_value', 0):,} "
            f"and an overall average unit price of ₹{ov.get('average_price', 0)}."
        )

    matched_count = len(products)
    return (
        f"Found {matched_count} matching SKUs in your catalog matching your criteria. "
        f"You can review the items below or click any card for detailed pricing and tag analytics."
    )
