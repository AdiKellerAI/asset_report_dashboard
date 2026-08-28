import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    DATABASE_URL = os.environ.get("DATABASE_URL", "")
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")
    APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
    RENTCAST_API_KEY = os.environ.get("RENTCAST_API_KEY", "")
