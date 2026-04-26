"""
config.py – IndiaShop Flask Configuration
"""

import os
from datetime import timedelta


class Config:
    # ── App ────────────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "india-shop-secret-change-in-prod")
    DEBUG      = os.environ.get("DEBUG", "True") == "True"

    # ── MySQL ──────────────────────────────────────────────────────────────────
    MYSQL_HOST     = os.environ.get("MYSQL_HOST",     "localhost")
    MYSQL_PORT     = int(os.environ.get("MYSQL_PORT", 3306))
    MYSQL_USER     = os.environ.get("MYSQL_USER",     "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "password")
    MYSQL_DB       = os.environ.get("MYSQL_DB",       "india_shop")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://"
        f"{os.environ.get('MYSQL_USER','root')}:"
        f"{os.environ.get('MYSQL_PASSWORD','password')}@"
        f"{os.environ.get('MYSQL_HOST','localhost')}:"
        f"{os.environ.get('MYSQL_PORT','3306')}/"
        f"{os.environ.get('MYSQL_DB','india_shop')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # ── JWT ────────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY            = os.environ.get("JWT_SECRET_KEY", "jwt-india-shop-2025")
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(hours=2)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION        = ["headers"]
    JWT_HEADER_NAME           = "Authorization"
    JWT_HEADER_TYPE           = "Bearer"

    # ── Brevo (Email) ──────────────────────────────────────────────────────────
    BREVO_API_KEY     = os.environ.get(
        "BREVO_API_KEY",
        "")
    SENDER_EMAIL      = os.environ.get("SENDER_EMAIL",  "contact@fliq.us.cc")
    SENDER_NAME       = os.environ.get("SENDER_NAME",   "indiaShop")
    OTP_EXPIRE_MINUTES = 15

    # ── Pagination ─────────────────────────────────────────────────────────────
    PRODUCTS_PER_PAGE = 20

    # ── CORS ───────────────────────────────────────────────────────────────────
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False


config_map = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "default":     DevelopmentConfig,
}
