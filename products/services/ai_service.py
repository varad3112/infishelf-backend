"""
GenAI and Search Services for InfiShelf products.
Fully dynamic — queries categories directly from the database with zero hardcoded values.
"""
import os
import re
import json
import logging
from django.conf import settings
from django.db.models import Q
from products.models import Product

logger = logging.getLogger(__name__)

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
    Initializes and returns a configured Gemini GenerativeModel.
    Returns None if unconfigured.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY', '')
    if not api_key or not GENAI_AVAILABLE:
        return None

    try:
        genai.configure(api_key=api_key)
        for model_name in [
            'gemini-3.8-flash',
            'gemini-2.5-flash',
            'gemini-2.0-flash',
            'gemini-1.5-flash',
            'gemini-1.5-pro'
        ]:
            try:
                return genai.GenerativeModel(model_name)
            except Exception:
                continue
    except Exception as e:
        logger.error(f"Error configuring Gemini: {e}")

    return None


# ---------------------------------------------------------------------------
# 2. Dynamic AI Description Generation
# ---------------------------------------------------------------------------

def generate_product_description(name: str, brand: str, category: str) -> dict:
    """
    Generates a product description and tags using Gemini LLM.
    If offline or API limit reached, generates dynamic copy from input parameters.
    """
    model = get_gemini_model()
    if model:
        llm_result = _generate_with_gemini(model, name, brand, category)
        if llm_result:
            return llm_result

    # Purely dynamic fallback derived from input parameters without hardcoding
    return {
        "description": f"Discover {name} by {brand}. A standout selection in {category}, thoughtfully crafted to deliver exceptional quality, superior performance, and outstanding consumer value.",
        "tags": [brand.lower(), category.lower(), "quality", "popular"],
        "source": "dynamic_fallback"
    }


def _generate_with_gemini(model, name: str, brand: str, category: str):
    """Queries Gemini API and extracts JSON response."""
    prompt = f"""
You are an expert e-commerce retail copywriter.
Write a concise, compelling product description (2 to 3 sentences, 40-70 words) for:
- Product Name: {name}
- Brand: {brand}
- Category: {category}

Also suggest 4 to 6 relevant search tags as a JSON array.
Respond strictly in valid JSON format:
{{
  "description": "...",
  "tags": ["tag1", "tag2", "tag3", "tag4"]
}}
"""
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
        logger.warning(f"Gemini generation error: {e}")
    return None


# ---------------------------------------------------------------------------
# 3. Dynamic Natural Language Query Parsing
# ---------------------------------------------------------------------------

def parse_natural_language_query(query: str) -> dict:
    """
    Parses a user query dynamically using database records.
    """
    clean_query = query.strip()

    max_price = _extract_max_price(clean_query)
    min_price = _extract_min_price(clean_query)
    category = _detect_category_from_db(clean_query)
    search_term = _clean_search_keywords(clean_query)

    return {
        "query": clean_query,
        "extracted_search": search_term,
        "category": category,
        "max_price": max_price,
        "min_price": min_price
    }


def _detect_category_from_db(text: str):
    """
    Dynamically detects which category matches the user's query
    by inspecting actual categories stored in the database.
    Zero hardcoded category names.
    """
    query_tokens = set(re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()))
    if not query_tokens:
        return None

    # Fetch live distinct categories from the database
    db_categories = Product.objects.values_list('category', flat=True).distinct()

    for cat in db_categories:
        cat_tokens = set(re.findall(r'\b[a-zA-Z]{3,}\b', cat.lower()))

        # Check exact token intersection or stem matching
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
    Applies category, price, and keyword stem filters to a base queryset.
    """
    qs = base_queryset

    if parsed_filters.get("category"):
        qs = qs.filter(category__iexact=parsed_filters["category"])

    if parsed_filters.get("max_price") is not None:
        qs = qs.filter(price__lte=parsed_filters["max_price"])

    if parsed_filters.get("min_price") is not None:
        qs = qs.filter(price__gte=parsed_filters["min_price"])

    term = parsed_filters.get("extracted_search", "")
    if term:
        words = [w.strip() for w in term.split() if len(w.strip()) > 2]
        for word in words:
            stem = word.rstrip('s') if len(word) > 3 else word
            qs = qs.filter(
                Q(name__icontains=stem) |
                Q(brand__icontains=stem) |
                Q(description__icontains=stem) |
                Q(tags__icontains=stem)
            )

    return qs
