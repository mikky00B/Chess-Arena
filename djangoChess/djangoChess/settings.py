"""Django settings for djangoChess project."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

ENVIRONMENT = os.getenv("DJANGO_ENV", "development")
if ENVIRONMENT == "production":
    env_file = BASE_DIR / ".env.production"
elif ENVIRONMENT == "sepolia":
    env_file = BASE_DIR / ".env.sepolia"
else:
    env_file = BASE_DIR / ".env"

if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if ENVIRONMENT in {"production", "sepolia"}:
        raise ValueError("SECRET_KEY must be set in environment")
    SECRET_KEY = "dev-only-insecure-secret-key-change-before-production"

DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "main.apps.MainConfig",
    "channels",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "main.middleware.RequestIDMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "djangoChess.urls"
WSGI_APPLICATION = "djangoChess.wsgi.application"
ASGI_APPLICATION = "djangoChess.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if ENVIRONMENT == "test" or os.getenv("PYTEST_CURRENT_TEST"):
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [("127.0.0.1", 6379)]},
        }
    }

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "lobby"
LOGOUT_REDIRECT_URL = "login"

BLOCKCHAIN_RPC_URL = os.getenv("BLOCKCHAIN_RPC_URL")
BLOCKCHAIN_NETWORK = os.getenv("BLOCKCHAIN_NETWORK", "anvil")
JUDGE_PRIVATE_KEY = os.getenv("JUDGE_PRIVATE_KEY")
CHESS_CONTRACT_ADDRESS = os.getenv("CHESS_CONTRACT_ADDRESS", "")
CHAIN_ID = int(os.getenv("CHAIN_ID", "31337"))

NETWORK_CONFIGS = {
    "anvil": {"chain_id": 31337, "explorer_url": None, "name": "Anvil Local"},
    "base-sepolia": {
        "chain_id": 84532,
        "explorer_url": "https://sepolia.basescan.org",
        "name": "Base Sepolia Testnet",
    },
    "base": {"chain_id": 8453, "explorer_url": "https://basescan.org", "name": "Base"},
}
CURRENT_NETWORK_CONFIG = NETWORK_CONFIGS.get(BLOCKCHAIN_NETWORK, NETWORK_CONFIGS["anvil"])

if ENVIRONMENT == "production":
    assert not DEBUG, "DEBUG must be False in production"
    assert SECRET_KEY and len(SECRET_KEY) >= 50, "Invalid SECRET_KEY in production"
    assert BLOCKCHAIN_RPC_URL and BLOCKCHAIN_RPC_URL.startswith(
        "https://"
    ), "Invalid RPC URL in production"
    assert (
        JUDGE_PRIVATE_KEY
        and len(JUDGE_PRIVATE_KEY) == 66
        and JUDGE_PRIVATE_KEY.startswith("0x")
    ), "Invalid JUDGE_PRIVATE_KEY format in production"
    assert CHESS_CONTRACT_ADDRESS and len(CHESS_CONTRACT_ADDRESS) == 42, "Invalid contract address in production"
    assert BLOCKCHAIN_NETWORK == "base", "Production must use base network"
    assert CHAIN_ID == 8453, "Production chain ID must be 8453"

    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

elif ENVIRONMENT == "sepolia":
    assert BLOCKCHAIN_NETWORK == "base-sepolia", "Sepolia must use base-sepolia network"
    assert CHAIN_ID == 84532, "Sepolia chain ID must be 84532"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "django.log",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"] if not DEBUG else ["console"],
            "level": "INFO",
        },
        "main": {
            "handlers": ["console", "file"] if not DEBUG else ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
        },
    },
}

(BASE_DIR / "logs").mkdir(exist_ok=True)

logger = logging.getLogger(__name__)
logger.info("=" * 50)
logger.info("Starting Django Chess dApp")
logger.info("Environment: %s", ENVIRONMENT)
logger.info("Debug Mode: %s", DEBUG)
logger.info("Network: %s (%s)", BLOCKCHAIN_NETWORK, CURRENT_NETWORK_CONFIG["name"])
logger.info("Chain ID: %s", CHAIN_ID)
logger.info("RPC URL: %s", BLOCKCHAIN_RPC_URL)
if CHESS_CONTRACT_ADDRESS:
    logger.info("Contract: %s", CHESS_CONTRACT_ADDRESS)
else:
    logger.warning("Contract address not set. Deploy contract first.")
logger.info("=" * 50)
