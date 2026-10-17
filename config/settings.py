"""
Django settings for InfiShelf project.
"""
from pathlib import Path
from datetime import timedelta
import os
import dj_database_url
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from backend/.env or root .env
load_dotenv(BASE_DIR / '.env')
load_dotenv(BASE_DIR.parent / '.env')

# Quick-start development settings - unsuitable for production
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-infishelf-dev-key-change-in-prod')
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't')

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS if host.strip()]
render_external_hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME')
if render_external_hostname and render_external_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_external_hostname)
if '.onrender.com' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('.onrender.com')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'drf_spectacular',

    # Local InfiShelf apps
    'accounts',
    'products',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # High priority for CORS
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Production static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database Configuration (Supabase PostgreSQL with SQLite fallback)
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
DB_SCHEMA = os.getenv('DB_SCHEMA', '').strip()

if DATABASE_URL:
    # Port 6543 is PgBouncer Transaction Mode (requires conn_max_age=0)
    # Port 5432 is Supabase Session Mode Pooler / Direct DB (supports persistent connections)
    is_transaction_pooler = ':6543' in DATABASE_URL
    conn_age = 0 if is_transaction_pooler else int(os.getenv('CONN_MAX_AGE', '60'))

    db_config = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=conn_age,
        ssl_require=True
    )
    db_config['CONN_HEALTH_CHECKS'] = True

    # Configure TCP keepalives and connect timeout to prevent remote pooler socket drops
    options = db_config.setdefault('OPTIONS', {})
    options.update({
        'connect_timeout': 10,
        'keepalives': 1,
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 5,
    })

    # If a custom schema (e.g., 'infishelf') is configured, set PostgreSQL search_path
    if DB_SCHEMA:
        options['options'] = f'-c search_path={DB_SCHEMA},public'

    DATABASES = {
        'default': db_config
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Caching Configuration (Redis on Render / LocMemCache fallback for local dev)
REDIS_URL = os.getenv('REDIS_URL', '').strip()
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'KEY_PREFIX': 'infishelf',
            'TIMEOUT': 300,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'infishelf-local-cache',
            'KEY_PREFIX': 'infishelf',
            'TIMEOUT': 300,
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Media files (User uploaded packshots and images)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework Settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_PAGINATION_CLASS': 'config.pagination.StandardProductPagination',
    'PAGE_SIZE': 12,
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '120/minute',
        'user': '1200/minute',
    },
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'config.exceptions.custom_exception_handler',
}

# Simple JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# CORS Configuration
cors_origins_env = os.getenv('CORS_ALLOWED_ORIGINS', '')
if cors_origins_env:
    CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins_env.split(',') if origin.strip()]
else:
    CORS_ALLOWED_ORIGINS = [
        'http://localhost:5173',
        'http://localhost:3000',
        'http://127.0.0.1:5173',
        'http://127.0.0.1:3000',
    ]

# Allow any Vercel or Netlify preview / production URL automatically
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https:\/\/.*\.vercel\.app$",
    r"^https:\/\/.*\.netlify\.app$",
]

CORS_ALLOW_CREDENTIALS = True

# In debug mode, allow all origins smoothly
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True

# CSRF Trusted Origins for Render, Vercel, and Netlify
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:3000',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:3000',
    'https://*.vercel.app',
    'https://*.netlify.app',
    'https://*.onrender.com',
]
if render_external_hostname:
    CSRF_TRUSTED_ORIGINS.append(f'https://{render_external_hostname}')
for origin in CORS_ALLOWED_ORIGINS:
    if origin.startswith('http') and origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

# OpenAPI / Swagger Specification (drf-spectacular)
SPECTACULAR_SETTINGS = {
    'TITLE': 'InfiShelf API',
    'DESCRIPTION': 'Intelligent Product & Category Management Platform API (Infilect Tech Assignment)',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': '/api/',
}

# Gemini API Key
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '').strip()

# Structured Console Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} [{name}]: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'products': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
