import os

import requests
from dotenv import load_dotenv

load_dotenv()

LANE_URL = os.environ["PRIVATE_LANE_URL"]      # the Qwen3 Modal endpoint
LANE_TOKEN = os.environ["PRIVATE_LANE_TOKEN"]


def call_model(prompt: str, max_new_tokens: int = 1024) -> str:
    # one lane, one model: contracts never touch a cloud model
    resp = requests.post(
        LANE_URL,
        json={"prompt": prompt, "token": LANE_TOKEN, "max_new_tokens": max_new_tokens},
        timeout=900,  # cold lane can take minutes; must outlive the Modal-side load
    )
    resp.raise_for_status()
    return resp.json()["text"]


def think(prompt: str, max_new_tokens: int = 1024) -> str:
    # alias kept so agent code reads like #1
    return call_model(prompt, max_new_tokens)
