import os
from dotenv import load_dotenv, set_key

ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")


def load_config() -> dict:
    load_dotenv(ENV_FILE)
    return {
        "PUBMED_API_KEY": os.getenv("PUBMED_API_KEY", ""),
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY", ""),
        "PUBMED_EMAIL": os.getenv("PUBMED_EMAIL", ""),
    }


def save_config(keys: dict) -> None:
    if not os.path.exists(ENV_FILE):
        open(ENV_FILE, "w").close()
    for key, value in keys.items():
        set_key(ENV_FILE, key, value)


def is_configured() -> bool:
    config = load_config()
    return bool(config["PUBMED_API_KEY"] and config["DEEPSEEK_API_KEY"])


def get_pubmed_key() -> str:
    return load_config()["PUBMED_API_KEY"]


def get_deepseek_key() -> str:
    return load_config()["DEEPSEEK_API_KEY"]


def get_email() -> str:
    return load_config()["PUBMED_EMAIL"]
