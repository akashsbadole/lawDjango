from pathlib import Path
import os

# Try to import python-decouple, fallback to basic environment variable handling
try:
    from decouple import config, Csv
    HAS_DECOUPLE = True
except ImportError:
    HAS_DECOUPLE = False
    
    def config(key, default=None, cast=None):
        """Fallback config function when python-decouple is not available"""
        value = os.environ.get(key, default)
        if cast and value is not None:
            if cast == bool:
                # Handle case where value might already be a bool
                if isinstance(value, bool):
                    return value
                return str(value).lower() in ('true', '1', 'yes', 'on')
            elif cast == int:
                return int(value)
            elif cast == float:
                return float(value)
            elif cast.__class__.__name__ == 'Csv' or (hasattr(cast, '__class__') and cast.__class__.__name__ == 'Csv'):
                return [v.strip() for v in str(value).split(',')] if value else []
        return value
    
    class Csv:
        """Fallback Csv class when python-decouple is not available"""
        def __init__(self):
            pass

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/dev/howto/deployment/checklist/

# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config("SECRET_KEY", default="django-insecure-0peo@#x9jur3!h$ryje!$879xww8y1y66jx!%*#ymhg&jkozs2")

# https://docs.djangoproject.com/en/dev/ref/settings/#debug
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DEBUG", default=True, cast=bool)

# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,0.0.0.0,127.0.0.1,testserver", cast=Csv())

# Environment
ENVIRONMENT = config("ENVIRONMENT", default="development")  # development, staging, production


# =============================================================================
# MULTI-TENANT SPECIFIC SETTINGS
# =============================================================================

# Tenant model configuration
TENANT_MODEL = "tenants.Tenant"

# Tenant detection settings
TENANT_DETECTION_METHOD = config("TENANT_DETECTION_METHOD", default="path")  # path, subdomain, header
TENANT_URL_PREFIX = config("TENANT_URL_PREFIX", default="app")  # URL prefix for path-based detection
TENANT_HEADER_NAME = config("TENANT_HEADER_NAME", default="X-Tenant-ID")  # Header name for header-based detection
TENANT_SUBDOMAIN_DOMAIN = config("TENANT_SUBDOMAIN_DOMAIN", default="lawfirm.com")  # Base domain for subdomain detection

# Tenant isolation settings
TENANT_ISOLATION_ENABLED = config("TENANT_ISOLATION_ENABLED", default=True, cast=bool)
TENANT_STRICT_ISOLATION = config("TENANT_STRICT_ISOLATION", default=True, cast=bool)  # Enforce strict tenant isolation
TENANT_SHARED_MODELS = config("TENANT_SHARED_MODELS", default="", cast=Csv())  # Models shared across tenants

# Default tenant settings
DEFAULT_TENANT_SLUG = config("DEFAULT_TENANT_SLUG", default="default")
DEFAULT_TENANT_NAME = config("DEFAULT_TENANT_NAME", default="Default Law Firm")
DEFAULT_TENANT_PLAN = config("DEFAULT_TENANT_PLAN", default="basic")

# Tenant cache configuration
TENANT_CACHE_TIMEOUT = config("TENANT_CACHE_TIMEOUT", default=300, cast=int)  # Cache timeout in seconds
TENANT_CACHE_PREFIX = config("TENANT_CACHE_PREFIX", default="tenant")
TENANT_CACHE_SETTINGS_TIMEOUT = config("TENANT_CACHE_SETTINGS_TIMEOUT", default=300, cast=int)

# Tenant-specific settings
TENANT_SETTINGS_CACHE_KEY = config("TENANT_SETTINGS_CACHE_KEY", default="tenant_settings_{tenant_id}")
TENANT_BRANDING_CACHE_KEY = config("TENANT_BRANDING_CACHE_KEY", default="tenant_branding_{tenant_id}")


# =============================================================================
# DATABASE CONFIGURATION FOR MULTI-TENANCY
# =============================================================================

# Database router configuration
DATABASE_ROUTERS = config("DATABASE_ROUTERS", default="tenants.routers.TenantRouter", cast=Csv())

# Connection settings for tenant isolation
DATABASE_CONNECTION_MAX_AGE = config("DATABASE_CONNECTION_MAX_AGE", default=60, cast=int)
DATABASE_CONNECTION_POOL_SIZE = config("DATABASE_CONNECTION_POOL_SIZE", default=10, cast=int)
DATABASE_CONNECTION_POOL_MAX_OVERFLOW = config("DATABASE_CONNECTION_POOL_MAX_OVERFLOW", default=20, cast=int)

# Query optimization settings
DATABASE_QUERY_TIMEOUT = config("DATABASE_QUERY_TIMEOUT", default=30, cast=int)
DATABASE_QUERY_CACHE_ENABLED = config("DATABASE_QUERY_CACHE_ENABLED", default=True, cast=bool)
DATABASE_QUERY_CACHE_TIMEOUT = config("DATABASE_QUERY_CACHE_TIMEOUT", default=300, cast=int)


# =============================================================================
# APPLICATION DEFINITION
# =============================================================================
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Third-party
    "allauth",
    "allauth.account",
    "crispy_forms",
    "crispy_bootstrap5",
    "debug_toolbar",
    # Core (must be first among local apps)
    "core",
    # Local
    "accounts",
    "pages",
    "tenants",
    "clients",
    "cases",
    "documents",
    "billing",
    "permissions",
    "subscriptions",
    "audit",
    "platform_admin",
    "import_export",
    "backup_restore",
    "lawyer_panel",
    "legal_research",
]


# =============================================================================
# MIDDLEWARE CONFIGURATION FOR MULTI-TENANCY
# =============================================================================
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # WhiteNoise
    "django.contrib.sessions.middleware.SessionMiddleware",
    "core.middleware.RedirectLoopDetectionMiddleware",  # Redirect loop detection (early)
    "tenants.middleware.TenantMiddleware",  # Tenant detection middleware (must be early)
    "subscriptions.middleware.SubscriptionMiddleware",  # Subscription validation middleware
    "platform_admin.middleware.SuperAdminAccessMiddleware",  # Super admin access control
    "django.middleware.common.CommonMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",  # Django Debug Toolbar
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.TenantContextMiddleware",  # Ensure tenant context (after auth)
    "audit.middleware.AuditMiddleware",  # Audit logging middleware (moved after auth)
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # django-allauth
]

# Session middleware configuration for tenants
SESSION_COOKIE_DOMAIN = config("SESSION_COOKIE_DOMAIN", default=None)  # Set to your domain for cross-subdomain sessions
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=not DEBUG, cast=bool)
SESSION_COOKIE_HTTPONLY = config("SESSION_COOKIE_HTTPONLY", default=True, cast=bool)
SESSION_COOKIE_SAMESITE = config("SESSION_COOKIE_SAMESITE", default="Lax")
SESSION_COOKIE_AGE = config("SESSION_COOKIE_AGE", default=1209600, cast=int)  # 2 weeks

# Authentication middleware updates
AUTHENTICATION_BACKENDS = config(
    "AUTHENTICATION_BACKENDS",
    default="django.contrib.auth.backends.ModelBackend,allauth.account.auth_backends.AuthenticationBackend",
    cast=Csv()
)

# Tenant-specific session settings
TENANT_SESSION_KEY = config("TENANT_SESSION_KEY", default="tenant_id")
TENANT_SESSION_ISOLATION = config("TENANT_SESSION_ISOLATION", default=True, cast=bool)


# =============================================================================
# URL CONFIGURATION
# =============================================================================
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "django_project.urls"

# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "django_project.wsgi.application"


# =============================================================================
# TEMPLATE CONFIGURATION FOR MULTI-TENANCY
# =============================================================================
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
            BASE_DIR / "templates" / "tenants",  # Tenant-specific templates
        ],
        "APP_DIRS": False,  # Must be False when custom loaders are defined
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "tenants.context_processors.tenant_settings",
                "subscriptions.context_processors.subscription_context",
                "audit.context_processors.audit_context",
            ],
            # Template loaders for tenant-specific templates
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
                "tenants.template_loaders.TenantTemplateLoader",  # Custom tenant template loader
            ],
        },
    },
]

# Template context processors for tenants
TENANT_TEMPLATE_CONTEXT_PROCESSORS = config(
    "TENANT_TEMPLATE_CONTEXT_PROCESSORS",
    default="tenants.context_processors.tenant_settings",
    cast=Csv()
)

# Template directories for tenants
TENANT_TEMPLATE_DIRS = config(
    "TENANT_TEMPLATE_DIRS",
    default=f"{BASE_DIR}/templates/tenants",
    cast=Csv()
)


# =============================================================================
# DATABASE CONFIGURATION FOR MULTI-TENANCY
# =============================================================================
# https://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": config("DB_ENGINE", default="django.db.backends.sqlite3"),
        "NAME": config("DB_NAME", default=str(BASE_DIR / "db.sqlite3")),
        "USER": config("DB_USER", default=""),
        "PASSWORD": config("DB_PASSWORD", default=""),
        "HOST": config("DB_HOST", default=""),
        "PORT": config("DB_PORT", default=""),
        "OPTIONS": config("DB_OPTIONS", default="", cast=dict) or {},
        "CONN_MAX_AGE": DATABASE_CONNECTION_MAX_AGE,
    }
}

# For Docker/PostgreSQL usage uncomment this and comment the DATABASES config above
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": config("DB_NAME", default="postgres"),
#         "USER": config("DB_USER", default="postgres"),
#         "PASSWORD": config("DB_PASSWORD", default="postgres"),
#         "HOST": config("DB_HOST", default="db"),  # set in docker-compose.yml
#         "PORT": config("DB_PORT", default=5432),  # default postgres port
#         "CONN_MAX_AGE": DATABASE_CONNECTION_MAX_AGE,
#     }
# }

# Database configuration for multi-tenancy
# Only add options that are compatible with the database engine
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    # SQLite-specific options
    pass  # SQLite doesn't support most of these options
else:
    # Options for PostgreSQL and other databases
    DATABASES["default"]["OPTIONS"].update({
        "isolation_level": config("DB_ISOLATION_LEVEL", default="READ COMMITTED"),
        "connect_timeout": config("DB_CONNECT_TIMEOUT", default=60, cast=int),
        "application_name": config("DB_APPLICATION_NAME", default="lawyer_multitenant"),
    })

# Password validation
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/dev/topics/i18n/
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "en-us"

# https://docs.djangoproject.com/en/dev/ref/settings/#time-zone
TIME_ZONE = "UTC"

# https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-USE_I18N
USE_I18N = True

# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True

# https://docs.djangoproject.com/en/dev/ref/settings/#locale-paths
LOCALE_PATHS = [BASE_DIR / "locale"]


# =============================================================================
# STATIC AND MEDIA FILE SETTINGS FOR MULTI-TENANCY
# =============================================================================
# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = BASE_DIR / "staticfiles"

# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/static/"

# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = [
    BASE_DIR / "static",
    BASE_DIR / "static" / "tenants",  # Tenant-specific static files
]

# Tenant-specific static file paths
TENANT_STATIC_URL = config("TENANT_STATIC_URL", default="/static/tenants/")
TENANT_STATIC_ROOT = config("TENANT_STATIC_ROOT", default=str(BASE_DIR / "staticfiles" / "tenants"))

# Media file organization by tenant
MEDIA_URL = config("MEDIA_URL", default="/media/")
MEDIA_ROOT = config("MEDIA_ROOT", default=str(BASE_DIR / "media"))

# Tenant-specific media file paths
TENANT_MEDIA_URL = config("TENANT_MEDIA_URL", default="/media/tenants/")
TENANT_MEDIA_ROOT = config("TENANT_MEDIA_ROOT", default=str(BASE_DIR / "media" / "tenants"))

# CDN configuration for tenant assets
CDN_ENABLED = config("CDN_ENABLED", default=False, cast=bool)
CDN_BASE_URL = config("CDN_BASE_URL", default="")
CDN_TENANT_PREFIX = config("CDN_TENANT_PREFIX", default="tenants")

# Storage configuration
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    "tenant_media": {
        "BACKEND": "tenants.storage.TenantMediaStorage",
        "OPTIONS": {
            "location": TENANT_MEDIA_ROOT,
            "base_url": TENANT_MEDIA_URL,
        },
    },
}

# Tenant file upload settings
TENANT_UPLOAD_MAX_SIZE = config("TENANT_UPLOAD_MAX_SIZE", default=10485760, cast=int)  # 10MB
TENANT_UPLOAD_ALLOWED_EXTENSIONS = config(
    "TENANT_UPLOAD_ALLOWED_EXTENSIONS",
    default="jpg,jpeg,png,gif,pdf,doc,docx,xls,xlsx,ppt,pptx",
    cast=Csv()
)


# Default primary key field type
# https://docs.djangoproject.com/en/stable/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# django-crispy-forms
# https://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


# =============================================================================
# EMAIL CONFIGURATION FOR MULTI-TENANCY
# =============================================================================
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")

# Email configuration
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")

# https://docs.djangoproject.com/en/dev/ref/settings/#default-from-email
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="root@localhost")

# Tenant-specific email settings
TENANT_EMAIL_FROM_NAME = config("TENANT_EMAIL_FROM_NAME", default="{company_name}")
TENANT_EMAIL_FROM_ADDRESS = config("TENANT_EMAIL_FROM_ADDRESS", default="noreply@{tenant_slug}.lawfirm.com")
TENANT_EMAIL_REPLY_TO = config("TENANT_EMAIL_REPLY_TO", default="support@{tenant_slug}.lawfirm.com")

# Email template context for tenants
TENANT_EMAIL_TEMPLATE_CONTEXT = config(
    "TENANT_EMAIL_TEMPLATE_CONTEXT",
    default="tenants.email_context.get_tenant_email_context",
)

# Email backend configuration for tenants
TENANT_EMAIL_BACKEND = config("TENANT_EMAIL_BACKEND", default=EMAIL_BACKEND)
TENANT_EMAIL_QUEUE_ENABLED = config("TENANT_EMAIL_QUEUE_ENABLED", default=True, cast=bool)
TENANT_EMAIL_BULK_SENDING = config("TENANT_EMAIL_BULK_SENDING", default=True, cast=bool)


# django-debug-toolbar
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html
# https://docs.djangoproject.com/en/dev/ref/settings/#internal-ips
INTERNAL_IPS = ["127.0.0.1"]

# https://docs.djangoproject.com/en/dev/topics/auth/customizing/#substituting-a-custom-user-model
AUTH_USER_MODEL = "accounts.CustomUser"

# django-allauth config
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1

# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
LOGIN_REDIRECT_URL = "home"

# https://django-allauth.readthedocs.io/en/latest/views.html#logout-account-logout
ACCOUNT_LOGOUT_REDIRECT_URL = "home"

# Custom login view for role-based redirects
ACCOUNT_LOGIN_VIEW = "accounts:login"

# https://django-allauth.readthedocs.io/en/latest/installation.html?highlight=backends
AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)
# https://django-allauth.readthedocs.io/en/latest/configuration.html
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE = False
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True


# =============================================================================
# SECURITY SETTINGS FOR MULTI-TENANCY
# =============================================================================
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-trusted-origins
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost:8000,http://127.0.0.1:8000",
    cast=Csv()
)

# Tenant isolation security
TENANT_SECURITY_ENABLED = config("TENANT_SECURITY_ENABLED", default=True, cast=bool)
TENANT_CROSS_TENANT_ACCESS_PREVENTION = config("TENANT_CROSS_TENANT_ACCESS_PREVENTION", default=True, cast=bool)
TENANT_DATA_ISOLATION_LEVEL = config("TENANT_DATA_ISOLATION_LEVEL", default="strict")  # strict, moderate, relaxed

# Session security settings
SESSION_SECURITY_ENABLED = config("SESSION_SECURITY_ENABLED", default=True, cast=bool)
SESSION_SECURITY_EXPIRE_AT_BROWSER_CLOSE = config("SESSION_SECURITY_EXPIRE_AT_BROWSER_CLOSE", default=False, cast=bool)
SESSION_SECURITY_WARN_AFTER = config("SESSION_SECURITY_WARN_AFTER", default=840, cast=int)  # 14 minutes
SESSION_SECURITY_EXPIRE_AFTER = config("SESSION_SECURITY_EXPIRE_AFTER", default=900, cast=int)  # 15 minutes

# Additional security settings
SECURE_BROWSER_XSS_FILTER = config("SECURE_BROWSER_XSS_FILTER", default=True, cast=bool)
SECURE_CONTENT_TYPE_NOSNIFF = config("SECURE_CONTENT_TYPE_NOSNIFF", default=True, cast=bool)
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = config("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True, cast=bool)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=False, cast=bool)
SECURE_REDIRECT_EXEMPT = config("SECURE_REDIRECT_EXEMPT", default="", cast=Csv())

# Tenant-specific security headers
TENANT_SECURITY_HEADERS = config("TENANT_SECURITY_HEADERS", default=True, cast=bool)
TENANT_CSP_ENABLED = config("TENANT_CSP_ENABLED", default=False, cast=bool)
TENANT_CSP_POLICY = config(
    "TENANT_CSP_POLICY",
    default="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self';"
)

# Rate limiting for tenant APIs
TENANT_RATE_LIMIT_ENABLED = config("TENANT_RATE_LIMIT_ENABLED", default=True, cast=bool)
TENANT_RATE_LIMIT_REQUESTS = config("TENANT_RATE_LIMIT_REQUESTS", default=1000, cast=int)
TENANT_RATE_LIMIT_WINDOW = config("TENANT_RATE_LIMIT_WINDOW", default=3600, cast=int)  # 1 hour


# =============================================================================
# CACHE CONFIGURATION FOR MULTI-TENANCY
# =============================================================================
# Cache configuration
CACHES = {
    "default": {
        "BACKEND": config("CACHE_BACKEND", default="django.core.cache.backends.locmem.LocMemCache"),
        "LOCATION": config("CACHE_LOCATION", default="unique-snowflake"),
        "TIMEOUT": config("CACHE_TIMEOUT", default=300, cast=int),
        "OPTIONS": config("CACHE_OPTIONS", default={}, cast=dict),
        "KEY_PREFIX": config("CACHE_KEY_PREFIX", default="lawyer"),
    }
}

# Redis configuration (if available)
REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/1")
REDIS_PASSWORD = config("REDIS_PASSWORD", default="")
REDIS_DB = config("REDIS_DB", default=1, cast=int)

# Tenant-specific cache keys
TENANT_CACHE_KEY_PREFIX = config("TENANT_CACHE_KEY_PREFIX", default="tenant_{tenant_id}")
TENANT_CACHE_ISOLATION = config("TENANT_CACHE_ISOLATION", default=True, cast=bool)

# Cache isolation between tenants
TENANT_CACHE_SEPARATOR = config("TENANT_CACHE_SEPARATOR", default="_")
TENANT_CACHE_VERSION = config("TENANT_CACHE_VERSION", default=1, cast=int)

# Redis/Memcached settings
if config("USE_REDIS_CACHE", default=False, cast=bool):
    CACHES["default"].update({
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "PASSWORD": REDIS_PASSWORD,
            "DB": REDIS_DB,
            "CONNECTION_POOL_KWARGS": {
                "max_connections": config("REDIS_MAX_CONNECTIONS", default=50, cast=int),
                "retry_on_timeout": True,
            }
        }
    })


# =============================================================================
# LOGGING CONFIGURATION FOR MULTI-TENANCY
# =============================================================================
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
        "tenant": {
            "format": "[{tenant_id}] {levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "filters": {
        "tenant_filter": {
            "()": "tenants.logging.TenantContextFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": config("LOG_FILE", default=str(BASE_DIR / "logs" / "django.log")),
            "maxBytes": config("LOG_FILE_MAX_SIZE", default=1024*1024*10, cast=int),  # 10MB
            "backupCount": config("LOG_FILE_BACKUP_COUNT", default=5, cast=int),
            "formatter": "verbose",
        },
        "tenant_file": {
            "class": "tenants.logging.TenantFileHandler",
            "formatter": "tenant",
            "filters": ["tenant_filter"],
        },
        "mail_admins": {
            "class": "django.utils.log.AdminEmailHandler",
            "level": "ERROR",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": config("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": True,
        },
        "tenants": {
            "handlers": ["console", "file", "tenant_file"],
            "level": config("TENANT_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "audit": {
            "handlers": ["console", "file"],
            "level": config("AUDIT_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "security": {
            "handlers": ["console", "file", "mail_admins"],
            "level": config("SECURITY_LOG_LEVEL", default="WARNING"),
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": config("ROOT_LOG_LEVEL", default="WARNING"),
    },
}

# Tenant-specific log files
TENANT_LOG_DIR = config("TENANT_LOG_DIR", default=str(BASE_DIR / "logs" / "tenants"))
TENANT_LOG_ENABLED = config("TENANT_LOG_ENABLED", default=True, cast=bool)
TENANT_LOG_FORMAT = config("TENANT_LOG_FORMAT", default="tenant_{tenant_id}.log")
TENANT_LOG_MAX_SIZE = config("TENANT_LOG_MAX_SIZE", default=1024*1024*5, cast=int)  # 5MB
TENANT_LOG_BACKUP_COUNT = config("TENANT_LOG_BACKUP_COUNT", default=3, cast=int)

# Audit logging settings
AUDIT_LOG_ENABLED = config("AUDIT_LOG_ENABLED", default=True, cast=bool)
AUDIT_LOG_RETENTION_DAYS = config("AUDIT_LOG_RETENTION_DAYS", default=90, cast=int)
AUDIT_LOG_SENSITIVE_DATA = config("AUDIT_LOG_SENSITIVE_DATA", default=False, cast=bool)

# Error reporting configuration
ERROR_REPORTING_ENABLED = config("ERROR_REPORTING_ENABLED", default=DEBUG, cast=bool)
TENANT_ERROR_REPORTING = config("TENANT_ERROR_REPORTING", default=True, cast=bool)


# =============================================================================
# THIRD-PARTY APP CONFIGURATIONS FOR MULTI-TENANCY
# =============================================================================
# django-allauth settings for tenants
ACCOUNT_ADAPTER = config("ACCOUNT_ADAPTER", default="tenants.adapters.TenantAccountAdapter")
SOCIALACCOUNT_ADAPTER = config("SOCIALACCOUNT_ADAPTER", default="tenants.adapters.TenantSocialAccountAdapter")
# Temporarily disable custom signup form to avoid circular import
# ACCOUNT_SIGNUP_FORM_CLASS = config("ACCOUNT_SIGNUP_FORM_CLASS", default="tenants.forms.TenantSignupForm")

# Django admin customization
ADMIN_ENABLED = config("ADMIN_ENABLED", default=True, cast=bool)
TENANT_ADMIN_ENABLED = config("TENANT_ADMIN_ENABLED", default=True, cast=bool)
TENANT_ADMIN_SITE_HEADER = config("TENANT_ADMIN_SITE_HEADER", default="{company_name} Administration")
TENANT_ADMIN_SITE_TITLE = config("TENANT_ADMIN_SITE_TITLE", default="{company_name} Admin")
TENANT_ADMIN_INDEX_TITLE = config("TENANT_ADMIN_INDEX_TITLE", default="{company_name} Administration")

# Celery configuration for tenants
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TASK_SERIALIZER = config("CELERY_TASK_SERIALIZER", default="json")
CELERY_RESULT_SERIALIZER = config("CELERY_RESULT_SERIALIZER", default="json")
CELERY_ACCEPT_CONTENT = config("CELERY_ACCEPT_CONTENT", default="json", cast=Csv())
CELERY_TIMEZONE = config("CELERY_TIMEZONE", default=TIME_ZONE)
CELERY_ENABLE_UTC = config("CELERY_ENABLE_UTC", default=True, cast=bool)

# Tenant-specific Celery settings
CELERY_TASK_ROUTES = {
    "tenants.tasks.*": {"queue": "tenants"},
    "billing.tasks.*": {"queue": "billing"},
    "audit.tasks.*": {"queue": "audit"},
    "backup_restore.tasks.*": {"queue": "backup"},
}
CELERY_TASK_DEFAULT_QUEUE = config("CELERY_TASK_DEFAULT_QUEUE", default="default")
CELERY_TASK_QUEUES = config("CELERY_TASK_QUEUES", default="default,tenants,billing,audit,backup", cast=Csv())


# =============================================================================
# AI RESEARCH ASSISTANT SETTINGS
# =============================================================================
# Google Gemini API Configuration
GOOGLE_GEMINI_API_KEY = config("GOOGLE_GEMINI_API_KEY", default="")

# AI Research Assistant Settings
AI_RESEARCH_ENABLED = config("AI_RESEARCH_ENABLED", default=True, cast=bool)
AI_RESEARCH_MAX_TOKENS = config("AI_RESEARCH_MAX_TOKENS", default=4000, cast=int)
AI_RESEARCH_TEMPERATURE = config("AI_RESEARCH_TEMPERATURE", default=0.3, cast=float)
AI_RESEARCH_TOP_P = config("AI_RESEARCH_TOP_P", default=0.8, cast=float)
AI_RESEARCH_TOP_K = config("AI_RESEARCH_TOP_K", default=40, cast=int)

# AI Research Rate Limiting
AI_RESEARCH_RATE_LIMIT_ENABLED = config("AI_RESEARCH_RATE_LIMIT_ENABLED", default=True, cast=bool)
AI_RESEARCH_RATE_LIMIT_REQUESTS = config("AI_RESEARCH_RATE_LIMIT_REQUESTS", default=50, cast=int)
AI_RESEARCH_RATE_LIMIT_WINDOW = config("AI_RESEARCH_RATE_LIMIT_WINDOW", default=3600, cast=int)  # 1 hour

# AI Research Costs and Usage Tracking
AI_RESEARCH_COST_TRACKING = config("AI_RESEARCH_COST_TRACKING", default=True, cast=bool)
AI_RESEARCH_COST_PER_INPUT_TOKEN = config("AI_RESEARCH_COST_PER_INPUT_TOKEN", default=0.000125, cast=float)  # Gemini Flash pricing
AI_RESEARCH_COST_PER_OUTPUT_TOKEN = config("AI_RESEARCH_COST_PER_OUTPUT_TOKEN", default=0.000375, cast=float)  # Gemini Flash pricing

# AI Research Security and Privacy
AI_RESEARCH_DATA_RETENTION_DAYS = config("AI_RESEARCH_DATA_RETENTION_DAYS", default=365, cast=int)
AI_RESEARCH_ANONYMIZE_DATA = config("AI_RESEARCH_ANONYMIZE_DATA", default=True, cast=bool)
AI_RESEARCH_ENABLE_LOGGING = config("AI_RESEARCH_ENABLE_LOGGING", default=True, cast=bool)

# =============================================================================
# ENVIRONMENT-SPECIFIC SETTINGS
# =============================================================================
# Development vs production settings
if ENVIRONMENT == "production":
    # Production-specific settings
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = "DENY"
    
    # Production email backend
    if not EMAIL_HOST:
        EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    
    # Production cache
    if not config("USE_REDIS_CACHE", default=False, cast=bool):
        CACHES["default"]["BACKEND"] = "django.core.cache.backends.filebased.FileBasedCache"
        CACHES["default"]["LOCATION"] = "/tmp/django_cache"
        
elif ENVIRONMENT == "staging":
    # Staging-specific settings
    DEBUG = config("STAGING_DEBUG", default=False, cast=bool)
    
    # Staging cache
    if not config("USE_REDIS_CACHE", default=False, cast=bool):
        CACHES["default"]["BACKEND"] = "django.core.cache.backends.locmem.LocMemCache"
        
else:  # development
    # Development-specific settings
    DEBUG = True
    INTERNAL_IPS = config("INTERNAL_IPS", default="127.0.0.1,localhost", cast=Csv())
    
    # Development cache
    CACHES["default"]["BACKEND"] = "django.core.cache.backends.dummy.DummyCache"

# Debug settings per tenant
TENANT_DEBUG_OVERRIDE = config("TENANT_DEBUG_OVERRIDE", default=False, cast=bool)
TENANT_DEBUG_ALLOWED_SLUGS = config("TENANT_DEBUG_ALLOWED_SLUGS", default="", cast=Csv())

# API configuration
API_ENABLED = config("API_ENABLED", default=True, cast=bool)
API_VERSION = config("API_VERSION", default="v1")
API_URL_PREFIX = config("API_URL_PREFIX", default="/api/")
API_RATE_LIMIT_ENABLED = config("API_RATE_LIMIT_ENABLED", default=True, cast=bool)
API_RATE_LIMIT_REQUESTS = config("API_RATE_LIMIT_REQUESTS", default=1000, cast=int)
API_RATE_LIMIT_WINDOW = config("API_RATE_LIMIT_WINDOW", default=3600, cast=int)


# =============================================================================
# PERFORMANCE SETTINGS
# =============================================================================
# Database connection pooling
DATABASE_CONNECTION_POOL_ARGS = config(
    "DATABASE_CONNECTION_POOL_ARGS",
    default={
        "max_overflow": DATABASE_CONNECTION_POOL_MAX_OVERFLOW,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    },
    cast=dict
)

# Query optimization
DATABASE_SELECT_RELATED = config("DATABASE_SELECT_RELATED", default=True, cast=bool)
DATABASE_PREFETCH_RELATED = config("DATABASE_PREFETCH_RELATED", default=True, cast=bool)
DATABASE_OPTIMIZE_QUERIES = config("DATABASE_OPTIMIZE_QUERIES", default=DEBUG, cast=bool)

# Caching strategies
CACHE_MIDDLEWARE_ALIAS = config("CACHE_MIDDLEWARE_ALIAS", default="default")
CACHE_MIDDLEWARE_SECONDS = config("CACHE_MIDDLEWARE_SECONDS", default=300, cast=int)
CACHE_MIDDLEWARE_KEY_PREFIX = config("CACHE_MIDDLEWARE_KEY_PREFIX", default="")
CACHE_MIDDLEWARE_ANONYMOUS_ONLY = config("CACHE_MIDDLEWARE_ANONYMOUS_ONLY", default=True, cast=bool)

# Performance monitoring
PERFORMANCE_MONITORING_ENABLED = config("PERFORMANCE_MONITORING_ENABLED", default=DEBUG, cast=bool)
PERFORMANCE_LOG_SLOW_QUERIES = config("PERFORMANCE_LOG_SLOW_QUERIES", default=True, cast=bool)
PERFORMANCE_SLOW_QUERY_THRESHOLD = config("PERFORMANCE_SLOW_QUERY_THRESHOLD", default=1000, cast=int)  # ms

# Background task settings
BACKGROUND_TASK_ENABLED = config("BACKGROUND_TASK_ENABLED", default=True, cast=bool)
BACKGROUND_TASK_RUN_EVERY_MINS = config("BACKGROUND_TASK_RUN_EVERY_MINS", default=5, cast=int)
BACKGROUND_TASK_MAX_ATTEMPTS = config("BACKGROUND_TASK_MAX_ATTEMPTS", default=3, cast=int)


# =============================================================================
# SETTINGS VALIDATION
# =============================================================================
def validate_tenant_settings():
    """
    Validate tenant-specific settings.
    
    Raises:
        ValueError: If any setting is invalid
    """
    errors = []
    
    # Validate tenant detection method
    if TENANT_DETECTION_METHOD not in ["path", "subdomain", "header"]:
        errors.append(f"Invalid TENANT_DETECTION_METHOD: {TENANT_DETECTION_METHOD}")
    
    # Validate tenant isolation level
    if TENANT_DATA_ISOLATION_LEVEL not in ["strict", "moderate", "relaxed"]:
        errors.append(f"Invalid TENANT_DATA_ISOLATION_LEVEL: {TENANT_DATA_ISOLATION_LEVEL}")
    
    # Validate cache configuration
    if config("USE_REDIS_CACHE", default=False, cast=bool) and not REDIS_URL:
        errors.append("REDIS_URL is required when USE_REDIS_CACHE is True")
    
    # Validate tenant directories
    try:
        os.makedirs(str(TENANT_LOG_DIR), exist_ok=True)
        os.makedirs(str(TENANT_MEDIA_ROOT), exist_ok=True)
        os.makedirs(str(TENANT_STATIC_ROOT), exist_ok=True)
    except Exception as e:
        errors.append(f"Failed to create tenant directories: {str(e)}")
    
    # Validate email settings for production
    if ENVIRONMENT == "production" and EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
        if not EMAIL_HOST or not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
            errors.append("Email configuration is incomplete for production")
    
    if errors:
        raise ValueError("Tenant settings validation failed:\n" + "\n".join(errors))

# Validate settings on startup
if config("VALIDATE_SETTINGS_ON_STARTUP", default=True, cast=bool):
    validate_tenant_settings()
