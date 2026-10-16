# InfiShelf Backend — Intelligent Product & Category Management Platform 🚀

[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11-3776ab.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.0+-092e20.svg)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.15+-red.svg)](https://www.django-rest-framework.org/)
[![Swagger](https://img.shields.io/badge/OpenAPI%203.0-Swagger%20UI-85ea2d.svg)](http://localhost:8000/api/docs/)

> Scalable, production-ready Django REST Framework backend powering the **InfiShelf** Retail Product Catalog and AI-driven shelf management platform. Built for the Infilect Technical Assessment.

---

## 📑 Table of Contents
- [Architecture & Tech Stack](#-architecture--tech-stack)
- [Key Features](#-key-features)
- [Repository Structure](#-repository-structure)
- [Quick Start Guide](#-quick-start-guide)
- [Environment Configuration](#-environment-configuration)
- [Data Seeding](#-data-seeding)
- [API Documentation & Endpoints](#-api-documentation--endpoints)
- [AI Capabilities (Gemini Integration)](#-ai-capabilities-gemini-integration)
- [Security & Best Practices](#-security--best-practices)

---

## 🛠️ Architecture & Tech Stack

- **Backend Framework:** Django 5.0+ & Django REST Framework (DRF)
- **Authentication:** Stateless JSON Web Tokens (JWT) via `djangorestframework-simplejwt`
- **Database:** Supabase PostgreSQL with SSL (or local SQLite fallback)
- **AI / LLM Integration:** Google Gemini API (`gemini-1.5-flash` / `gemini-pro`) with resilient rule-based fallback
- **Search & Filtering:** `django-filter`, DRF `SearchFilter` and `OrderingFilter`
- **API Documentation:** Interactive OpenAPI 3.0 via `drf-spectacular` (Swagger UI & ReDoc)
- **Cross-Origin Security:** `django-cors-headers`

---

## ✨ Key Features

1. **JWT Authentication & Role Security:**
   - Registration with password confirmation and automatic token issuance.
   - Login issuing access (5 min) & refresh (1 day) tokens.
   - Public read-only catalog browsing; authentication required for product creation, modification, and deletion.

2. **Advanced Catalog Management (CRUD):**
   - Full RESTful CRUD operations on products.
   - Standardized JSON responses with count, total pages, current page, and results metadata.
   - Server-side filtering by category, brand, min/max price, and case-insensitive keyword search.
   - Comprehensive sorting (name, price asc/desc, newest).

3. **GenAI Product Description Generator:**
   - Endpoint: `POST /api/products/ai/generate-description/`
   - Generates professional, marketing-grade CPG retail descriptions and tags given product name, brand, and category.

4. **Natural Language Smart Search:**
   - Endpoint: `POST /api/products/ai/smart-search/`
   - Parses complex queries like *"healthy drinks under Rs. 100"* into structured filters (category, brand, price ceiling, keywords) and retrieves matching items.

---

## 📁 Repository Structure

```
backend/
├── accounts/                  # User registration, authentication & profile endpoints
│   ├── models.py
│   ├── serializers.py        # User & registration serializers
│   ├── views.py              # Register, login, me views
│   └── urls.py
├── products/                  # Core catalog & GenAI service app
│   ├── models.py              # Product model with indexed fields
│   ├── serializers.py        # Explicit field serializers with custom validations
│   ├── views.py              # ProductViewSet, AI smart search, AI description views
│   ├── filters.py            # ProductFilter (category, brand, min/max price)
│   ├── urls.py
│   ├── management/commands/  # Management commands
│   │   └── seed_products.py  # Automated database seeder (18 packaged goods items)
│   └── services/
│       └── ai_service.py     # Isolated Gemini AI service with graceful fallback
├── config/                    # Project root configuration
│   ├── settings.py           # Database URL, CORS, JWT, DRF config
│   ├── urls.py               # Root router, API schema, Swagger & ReDoc
│   └── wsgi.py / asgi.py
├── manage.py
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## 🚀 Quick Start Guide

### 1. Clone & Navigate
```bash
git clone https://github.com/varad3112/infishelf-backend.git
cd infishelf-backend
```

### 2. Create and Activate Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and configure your credentials:
```bash
cp .env.example .env
```
*(On Windows PowerShell: `Copy-Item .env.example .env`)*

### 5. Run Database Migrations
```bash
python manage.py migrate
```

### 6. Seed Sample Catalog Products
```bash
python manage.py seed_products
```
*Seeds 18 authentic FMCG/CPG products with local packshots across Beverages, Snacks, Personal Care, Dairy, and Home Care.*

### 7. Run the Development Server
```bash
python manage.py runserver
```
The API will be available at: **http://localhost:8000/**

---

## 📖 API Documentation & Endpoints

Interactive documentation is available out-of-the-box:
- **Swagger UI:** [http://localhost:8000/api/docs/](http://localhost:8000/api/docs/)
- **ReDoc:** [http://localhost:8000/api/redoc/](http://localhost:8000/api/redoc/)
- **OpenAPI Schema (JSON/YAML):** [http://localhost:8000/api/schema/](http://localhost:8000/api/schema/)

### Core Endpoint Summary

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/auth/register/` | Register new user & return JWT tokens | No |
| `POST` | `/api/auth/login/` | Authenticate & obtain access + refresh tokens | No |
| `POST` | `/api/auth/token/refresh/` | Refresh expired access token | No |
| `GET` | `/api/auth/me/` | Get current logged-in user profile | Bearer JWT |
| `GET` | `/api/products/` | List products with pagination, filters & search | No |
| `GET` | `/api/products/{id}/` | Retrieve single product details | No |
| `POST` | `/api/products/` | Create a new product | Bearer JWT |
| `PUT` | `/api/products/{id}/` | Update an existing product | Bearer JWT |
| `DELETE` | `/api/products/{id}/` | Delete a product | Bearer JWT |
| `GET` | `/api/products/categories/` | List all unique categories | No |
| `GET` | `/api/products/brands/` | List all unique brands | No |
| `POST` | `/api/products/ai/generate-description/` | Generate AI description and tags | Bearer JWT |
| `POST` | `/api/products/ai/smart-search/` | Natural language smart search | No |

---

## 🤖 AI Capabilities (Gemini Integration)

All AI interactions are encapsulated in `products/services/ai_service.py`:
- **Graceful Degradation:** If `GEMINI_API_KEY` is not provided or the Gemini API hits a rate limit, the system gracefully falls back to structured rule-based generation without throwing 500 errors.
- **Strict Response Cleaning:** Strips markdown fences (` ```json `) to ensure clean JSON parsing.
- **Timeout Protection:** Strict request timeouts prevent hung worker threads.

---

## 🔒 Security & Best Practices

- Secret key and credentials strictly loaded via environment variables (`django-environ`).
- `.env` and `db.sqlite3` are strictly ignored by `.gitignore`.
- Password validation enforces minimum length and complexity.
- Protected endpoints enforce JWT Bearer header checks.
