"""Connection settings shared by everything that calls the backend."""
import os

from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")
# Generous: the backend waits for the language model before answering.
TIMEOUT_SECONDS = 60


class BackendUnavailable(Exception):
    """The backend could not be reached or answered with an unexpected error."""
