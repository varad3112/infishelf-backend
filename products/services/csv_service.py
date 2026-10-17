"""
Service module for handling Bulk CSV Upload and Template generation for Products.
Provides robust parsing, validation, error-reporting, and safe batch creation.
"""
import io
import csv
import logging
from decimal import Decimal
from django.core.cache import cache
from products.models import Product
from products.serializers import ProductSerializer

logger = logging.getLogger(__name__)

# Standard header mapping aliases to forgive slight CSV column naming differences
HEADER_ALIASES = {
    'name': ['name', 'product_name', 'title', 'item_name'],
    'brand': ['brand', 'brand_name', 'company', 'manufacturer'],
    'category': ['category', 'category_name', 'department', 'aisle'],
    'price': ['price', 'unit_price', 'mrp', 'cost'],
    'description': ['description', 'desc', 'details', 'about'],
    'image_url': ['image_url', 'image', 'photo_url', 'img_url', 'packshot'],
    'tags': ['tags', 'tag_list', 'keywords', 'labels'],
}


def _resolve_header(row_dict: dict, canonical_field: str) -> str | None:
    """Finds matching column in the row dictionary based on canonical aliases."""
    normalized_keys = {str(k).strip().lower().replace(' ', '_'): k for k in row_dict.keys() if k}
    for alias in HEADER_ALIASES.get(canonical_field, [canonical_field]):
        if alias in normalized_keys:
            val = row_dict.get(normalized_keys[alias])
            return str(val).strip() if val is not None else None
    return None


def parse_and_bulk_create_products(file_obj, user) -> dict:
    """
    Parses an uploaded CSV file, validates each row with ProductSerializer,
    and bulk-inserts valid records into the database.
    
    Returns a structured dictionary with success metrics, error details, and counts.
    """
    # 1. Read and decode the CSV content
    try:
        content = file_obj.read()
        if isinstance(content, bytes):
            # Attempt utf-8-sig first to gracefully strip Excel UTF-8 BOM
            try:
                decoded = content.decode('utf-8-sig')
            except UnicodeDecodeError:
                decoded = content.decode('latin-1')
        else:
            decoded = str(content)
    except Exception as e:
        logger.error(f"Failed to read/decode CSV file: {e}")
        return {
            "success": False,
            "created_count": 0,
            "failed_count": 0,
            "errors": [{"row": 0, "error": f"Failed to read file encoding: {str(e)}"}],
            "message": "Unable to read the uploaded CSV file. Please ensure it is saved in UTF-8 format."
        }

    csv_stream = io.StringIO(decoded)
    reader = csv.DictReader(csv_stream)

    if not reader.fieldnames:
        return {
            "success": False,
            "created_count": 0,
            "failed_count": 0,
            "errors": [{"row": 0, "error": "CSV file appears empty or missing header columns."}],
            "message": "The CSV file has no recognizable header row."
        }

    valid_products_to_create = []
    errors = []
    row_number = 1  # 1-indexed (header is row 1, first data row is 2)

    for row in reader:
        row_number += 1
        # Skip completely empty rows
        if not any(str(v).strip() for v in row.values() if v is not None):
            continue

        name = _resolve_header(row, 'name')
        brand = _resolve_header(row, 'brand')
        category = _resolve_header(row, 'category')
        price_raw = _resolve_header(row, 'price')
        description = _resolve_header(row, 'description') or ''
        image_url = _resolve_header(row, 'image_url') or ''
        tags_raw = _resolve_header(row, 'tags') or ''

        # Parse tags: supports semicolon, comma, or pipe separated strings
        tags = []
        if tags_raw:
            # Replace common delimiters with commas
            delimiters_normalized = tags_raw.replace(';', ',').replace('|', ',')
            tags = [t.strip() for t in delimiters_normalized.split(',') if t.strip()]

        # Clean Price
        try:
            if price_raw is None or price_raw == '':
                raise ValueError("Price is required")
            # Strip currency symbols if user pasted ₹, $, etc.
            clean_price_str = price_raw.replace('₹', '').replace('$', '').replace(',', '').strip()
            price_val = Decimal(clean_price_str)
        except Exception:
            errors.append({
                "row": row_number,
                "name": name or f"Row {row_number}",
                "errors": {"price": [f"Invalid price value '{price_raw}'. Must be a positive number."]}
            })
            continue

        item_data = {
            "name": name,
            "brand": brand,
            "category": category,
            "price": price_val,
            "description": description,
            "image_url": image_url,
            "tags": tags,
        }

        serializer = ProductSerializer(data=item_data)
        if serializer.is_valid():
            val_data = serializer.validated_data
            valid_products_to_create.append(
                Product(
                    created_by=user,
                    name=val_data['name'],
                    brand=val_data['brand'],
                    category=val_data['category'],
                    price=val_data['price'],
                    description=val_data.get('description', ''),
                    image_url=val_data.get('image_url', ''),
                    tags=val_data.get('tags', []),
                )
            )
        else:
            errors.append({
                "row": row_number,
                "name": name or f"Row {row_number}",
                "errors": serializer.errors
            })

    # Bulk create valid products
    created_count = 0
    if valid_products_to_create:
        try:
            Product.objects.bulk_create(valid_products_to_create, batch_size=500)
            created_count = len(valid_products_to_create)
            # Invalidate cached statistics and summaries
            cache.delete_many(["catalog:statistics", "catalog:summary"])
        except Exception as e:
            logger.error(f"Error performing Product.objects.bulk_create: {e}")
            return {
                "success": False,
                "created_count": 0,
                "failed_count": len(errors) + len(valid_products_to_create),
                "errors": [{"row": "Batch", "error": f"Database insertion error: {str(e)}"}],
                "message": f"Database insertion error during bulk upload: {str(e)}"
            }

    success_msg = f"Successfully uploaded {created_count} product(s)."
    if errors:
        success_msg += f" {len(errors)} row(s) had validation errors."

    return {
        "success": created_count > 0 or len(errors) == 0,
        "created_count": created_count,
        "failed_count": len(errors),
        "errors": errors[:50],  # Return up to first 50 error rows for manageable payload
        "message": success_msg,
    }


def generate_sample_csv_template() -> str:
    """Generates standard CSV template content for products."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "brand", "category", "price", "description", "image_url", "tags"])
    writer.writerow([
        "Himalayan Pink Rock Salt 1kg",
        "Tata Consumer",
        "Pantry & Cooking Essentials",
        "120.00",
        "100% natural, mineral-rich Himalayan pink rock salt for healthy daily seasoning.",
        "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=600&q=80",
        "Pink Salt, Organic, Mineral Rich, Cooking"
    ])
    writer.writerow([
        "Extra Virgin Cold Pressed Olive Oil 500ml",
        "Borges",
        "Pantry & Cooking Essentials",
        "650.00",
        "Finest Mediterranean olives cold-pressed for antioxidant-rich heart-healthy dressings.",
        "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?auto=format&fit=crop&w=600&q=80",
        "Olive Oil, Cold Pressed, Heart Healthy, Mediterranean"
    ])
    writer.writerow([
        "Sparkling Energy Drink 250ml Can",
        "Red Bull",
        "Beverages & Energy Drinks",
        "125.00",
        "Vitalizes body and mind with caffeine, taurine, and B-group vitamins.",
        "https://images.unsplash.com/photo-1622543925917-763c34d1a86e?auto=format&fit=crop&w=600&q=80",
        "Energy Drink, Caffeine, Taurine, Refreshing"
    ])
    writer.writerow([
        "Almond Breeze Unsweetened Vanilla Milk 1L",
        "Blue Diamond",
        "Dairy & Breakfast",
        "280.00",
        "Delicious, calcium-packed non-dairy plant-based beverage with no added sugars.",
        "https://images.unsplash.com/photo-1563636619-e9143da7973b?auto=format&fit=crop&w=600&q=80",
        "Almond Milk, Dairy-Free, Vegan, Plant Based"
    ])
    return output.getvalue()
