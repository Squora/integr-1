import os

API_KEY = os.getenv("API_KEY", "supersecretapikey")

def verify_api_key(key: str) -> bool:
    return key == API_KEY