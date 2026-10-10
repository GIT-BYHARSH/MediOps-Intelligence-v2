"""Shared database connection for all analysis scripts and notebooks."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

# Read the secrets from the .env file in the project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def get_engine():
    """Return a SQLAlchemy engine connected to the mediops database."""
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        database=os.environ["DB_NAME"],
    )
    return create_engine(url)