# 📚 InfiShelf — REST API Documentation

Comprehensive API reference and integration guide for **InfiShelf — Intelligent Product & Category Management Platform**.

---

## 🌐 1. Base URLs & Interactive Documentation

| Environment | Base URL |
|---|---|
| **Local Development** | `http://localhost:8000/api` |
| **Production (Live)** | `https://<your-backend-domain>.onrender.com/api` *(configured on deploy)* |

### 📖 Interactive Swagger & OpenAPI Specs
The backend automatically serves interactive OpenAPI 3.0 documentation via **`drf-spectacular`**:

- **Swagger UI:** [`/api/docs/`](http://localhost:8000/api/docs/) — Interactive test console.
- **Redoc:** [`/api/redoc/`](http://localhost:8000/api/redoc/) — Clean, searchable reference documentation.
- **OpenAPI Schema (JSON/YAML):** [`/api/schema/`](http://localhost:8000/api/schema/) — Raw OpenAPI 3.0 spec.

---

## 🔐 2. Authentication & Authorization

InfiShelf uses **stateless JSON Web Tokens (JWT)**.

- **Public Endpoints:** Catalog browsing (`GET /api/products/`), product details (`GET /api/products/{id}/`), AI smart search query, and user registration/login do **not** require authentication.
- **Protected Endpoints:** Product creation (`POST`), editing (`PUT`/`PATCH`), deletion (`DELETE`), and AI description generation require a valid JWT access token.

### Header Format
Include the token in the `Authorization` header on all protected requests:

```http
Authorization: Bearer <access_token>
```

---

## 🚪 3. Authentication Endpoints (`/api/auth/`)

### 3.1 Register User
Create a new user account.

- **Endpoint:** `POST /api/auth/register/`
- **Auth Required:** No

#### Request Body
```json
{
  "username": "retail_manager",
  "email": "manager@infilect.com",
  "password": "StrongPassword123!",
  "confirm_password": "StrongPassword123!"
}
```

#### Response: `201 Created`
```json
{
  "message": "User registered successfully",
  "user": {
    "id": 1,
    "username": "retail_manager",
    "email": "manager@infilect.com"
  },
  "tokens": {
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

---

### 3.2 Login (Obtain Tokens)
Authenticate existing user and obtain access + refresh tokens.

- **Endpoint:** `POST /api/auth/login/`
- **Auth Required:** No

#### Request Body
```json
{
  "username": "retail_manager",
  "password": "StrongPassword123!"
}
```

#### Response: `200 OK`
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "username": "retail_manager",
    "email": "manager@infilect.com"
  }
}
```

---

### 3.3 Refresh Access Token
Obtain a new access token using a valid refresh token.

- **Endpoint:** `POST /api/auth/refresh/`
- **Auth Required:** No

#### Request Body
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### Response: `200 OK`
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

---

### 3.4 Get Current User Profile
Retrieve profile data for the authenticated user.

- **Endpoint:** `GET /api/auth/me/`
- **Auth Required:** Yes (`Bearer <token>`)

#### Response: `200 OK`
```json
{
  "id": 1,
  "username": "retail_manager",
  "email": "manager@infilect.com",
  "date_joined": "2026-10-15T10:00:00Z"
}
```

---

## 📦 4. Product Catalog Endpoints (`/api/products/`)

### 4.1 List & Search Products
Retrieve a paginated list of products with multi-dimensional filtering, searching, and sorting.

- **Endpoint:** `GET /api/products/`
- **Auth Required:** No

#### Query Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `search` | `string` | — | Text search across `name`, `brand`, and `description`. |
| `category` | `string` | — | Filter by exact category (e.g. `Beverages & Energy Drinks`). |
| `brand` | `string` | — | Filter by brand name (e.g. `Coca-Cola`, `Unilever`). |
| `min_price` | `decimal` | — | Filter products with price $\ge$ `min_price`. |
| `max_price` | `decimal` | — | Filter products with price $\le$ `max_price`. |
| `ordering` | `string` | `-created_at` | Sort field: `price`, `-price`, `name`, `-name`, `created_at`, `-created_at`. |
| `page` | `integer` | `1` | Page number. |
| `page_size` | `integer` | `12` | Products per page (allowed: 1 to 50). |

#### Example Request
```http
GET /api/products/?category=Beverages+%26+Energy+Drinks&max_price=5.00&ordering=price&page=1 HTTP/1.1
Host: localhost:8000
```

#### Response: `200 OK`
```json
{
  "count": 28,
  "total_pages": 3,
  "current_page": 1,
  "next": "http://localhost:8000/api/products/?category=Beverages&page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "Red Bull Sugarfree Energy Drink 250ml",
      "brand": "Red Bull",
      "category": "Beverages & Energy Drinks",
      "description": "Functional beverage that vitalizes body and mind without sugar.",
      "price": "2.49",
      "image_url": "https://images.unsplash.com/photo-1551024709-8f23befc6f87?auto=format&fit=crop&w=600&q=80",
      "tags": ["sugar-free", "energy", "caffeine", "beverage"],
      "created_at": "2026-10-15T08:30:00Z",
      "updated_at": "2026-10-15T08:30:00Z"
    },
    {
      "id": 2,
      "name": "Monster Energy Ultra White 500ml",
      "brand": "Monster Energy",
      "category": "Beverages & Energy Drinks",
      "description": "Crisp and refreshing citrus flavor with zero sugar and zero calories.",
      "price": "2.99",
      "image_url": "https://images.unsplash.com/photo-1622543925917-763c34d1a86e?auto=format&fit=crop&w=600&q=80",
      "tags": ["zero-sugar", "energy", "citrus"],
      "created_at": "2026-10-15T08:35:00Z",
      "updated_at": "2026-10-15T08:35:00Z"
    }
  ]
}
```

---

### 4.2 Retrieve Product Details
Get detailed metadata for a specific product by ID.

- **Endpoint:** `GET /api/products/{id}/`
- **Auth Required:** No

#### Response: `200 OK`
```json
{
  "id": 1,
  "name": "Red Bull Sugarfree Energy Drink 250ml",
  "brand": "Red Bull",
  "category": "Beverages & Energy Drinks",
  "description": "Functional beverage that vitalizes body and mind without sugar.",
  "price": "2.49",
  "image_url": "https://images.unsplash.com/photo-1551024709-8f23befc6f87?auto=format&fit=crop&w=600&q=80",
  "tags": ["sugar-free", "energy", "caffeine"],
  "created_at": "2026-10-15T08:30:00Z",
  "updated_at": "2026-10-15T08:30:00Z"
}
```

#### Error: `404 Not Found`
```json
{
  "detail": "Product with ID 999 not found."
}
```

---

### 4.3 Create Product
Add a new product to the catalog.

- **Endpoint:** `POST /api/products/`
- **Auth Required:** Yes (`Bearer <token>`)

#### Request Body
```json
{
  "name": "Coca-Cola Zero Sugar Cans (Pack of 12)",
  "brand": "Coca-Cola",
  "category": "Beverages & Energy Drinks",
  "description": "Delicious zero-sugar sparkling refreshment with authentic Coca-Cola taste.",
  "price": 7.99,
  "image_url": "https://images.unsplash.com/photo-1629203851122-3726ecdf080e?auto=format&fit=crop&w=600&q=80",
  "tags": ["soda", "zero-sugar", "multipack", "coca-cola"]
}
```

#### Response: `201 Created`
```json
{
  "id": 3,
  "name": "Coca-Cola Zero Sugar Cans (Pack of 12)",
  "brand": "Coca-Cola",
  "category": "Beverages & Energy Drinks",
  "description": "Delicious zero-sugar sparkling refreshment with authentic Coca-Cola taste.",
  "price": "7.99",
  "image_url": "https://images.unsplash.com/photo-1629203851122-3726ecdf080e?auto=format&fit=crop&w=600&q=80",
  "tags": ["soda", "zero-sugar", "multipack", "coca-cola"],
  "created_at": "2026-10-15T09:12:00Z",
  "updated_at": "2026-10-15T09:12:00Z"
}
```

#### Error: `400 Bad Request` (Validation Failed)
```json
{
  "errors": {
    "price": ["Price must be greater than zero."],
    "image_url": ["Enter a valid URL starting with http:// or https://."]
  }
}
```

---

### 4.4 Update Product (Full / Partial)
Update product details.

- **Endpoint:** `PUT /api/products/{id}/` (Full replace) or `PATCH /api/products/{id}/` (Partial update)
- **Auth Required:** Yes (`Bearer <token>`)

#### Request Body (`PATCH`)
```json
{
  "price": 6.99,
  "tags": ["soda", "zero-sugar", "multipack", "discounted"]
}
```

#### Response: `200 OK`
```json
{
  "id": 3,
  "name": "Coca-Cola Zero Sugar Cans (Pack of 12)",
  "brand": "Coca-Cola",
  "category": "Beverages & Energy Drinks",
  "description": "Delicious zero-sugar sparkling refreshment with authentic Coca-Cola taste.",
  "price": "6.99",
  "image_url": "https://images.unsplash.com/photo-1629203851122-3726ecdf080e?auto=format&fit=crop&w=600&q=80",
  "tags": ["soda", "zero-sugar", "multipack", "discounted"],
  "updated_at": "2026-10-15T09:30:00Z"
}
```

---

### 4.5 Delete Product
Remove a product from the catalog.

- **Endpoint:** `DELETE /api/products/{id}/`
- **Auth Required:** Yes (`Bearer <token>`)

#### Response: `204 No Content`
*(Empty response body)*

---

## 🤖 5. GenAI Integration Endpoints (`/api/products/ai/`)

### 5.1 AI Description & Tag Generator
Uses LLM (Google Gemini) to craft an engaging, SEO-optimized e-commerce product description and generate relevant retail tags based on product name, brand, and category.

- **Endpoint:** `POST /api/products/ai/generate-description/`
- **Auth Required:** Yes (`Bearer <token>`)

#### Request Body
```json
{
  "name": "Ariel Matic Front Load Liquid Detergent 2L",
  "brand": "Ariel",
  "category": "Home & Fabric Care"
}
```

#### Response: `200 OK`
```json
{
  "description": "Formulated specifically for front-loading washing machines, Ariel Matic Liquid Detergent provides cutting-edge stain removal in a single wash. Its deep-penetrating liquid formula dissolves rapidly without leaving powdery residue on garments, keeping colors brilliant and whites impeccably crisp.",
  "suggested_tags": [
    "liquid detergent",
    "front load",
    "stain removal",
    "fabric care",
    "household essentials"
  ]
}
```

#### Fallback / Resilience Behavior
If the external GenAI service is throttled or unreachable, the endpoint returns a clean template description with status `200 OK` and a `fallback: true` flag, guaranteeing the frontend form never hangs.

---

### 5.2 AI Natural Language Smart Search
Transforms unstructured human search queries (e.g., *"refreshing cold drink under $3 without sugar"*) into structured filters and finds semantic matches.

- **Endpoint:** `POST /api/products/ai/smart-search/`
- **Auth Required:** No

#### Request Body
```json
{
  "query": "refreshing cold drink under $3 without sugar"
}
```

#### Response: `200 OK`
```json
{
  "interpreted_intent": {
    "category": "Beverages & Energy Drinks",
    "max_price": 3.00,
    "keywords": ["refreshing", "drink", "sugar-free"]
  },
  "count": 2,
  "results": [
    {
      "id": 1,
      "name": "Red Bull Sugarfree Energy Drink 250ml",
      "brand": "Red Bull",
      "price": "2.49"
    },
    {
      "id": 2,
      "name": "Monster Energy Ultra White 500ml",
      "brand": "Monster Energy",
      "price": "2.99"
    }
  ]
}
```

---

## ⚠️ 6. Error Handling & HTTP Status Codes

InfiShelf APIs adhere to standard REST HTTP response codes:

| Status Code | Description | Payload Structure |
|---|---|---|
| `200 OK` | Request succeeded. | Resource object or paginated list. |
| `201 Created` | Resource created. | Newly created resource object. |
| `204 No Content` | Resource deleted. | Empty body. |
| `400 Bad Request` | Validation failure or malformed payload. | `{"errors": {"field": ["reason"]}}` |
| `401 Unauthorized` | Missing or expired JWT token. | `{"detail": "Authentication credentials were not provided."}` |
| `403 Forbidden` | Insufficient permissions for operation. | `{"detail": "You do not have permission to perform this action."}` |
| `404 Not Found` | Requested resource ID does not exist. | `{"detail": "Resource not found."}` |
| `500 Internal Error` | Unhandled server exception. | `{"detail": "Internal server error. Please try again later."}` |

---

## 🧪 7. Testing APIs with cURL

### Register a User
```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username":"cpg_admin","email":"admin@infishelf.com","password":"SecurePassword123!"}'
```

### Search Products
```bash
curl -X GET "http://localhost:8000/api/products/?search=chocolate&ordering=-price" \
  -H "Accept: application/json"
```

### Generate AI Description
```bash
curl -X POST http://localhost:8000/api/products/ai/generate-description/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"name":"Chobani Greek Yogurt Mixed Berry 150g","brand":"Chobani","category":"Dairy & Breakfast"}'
```
