import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

LANE_URL = os.environ["PRIVATE_LANE_URL"]      # the private Modal endpoint
LANE_TOKEN = os.environ["PRIVATE_LANE_TOKEN"]

# The client-side lane lock is gone (2026-07-28, vLLM swap): the lane now
# continuous-batches up to 8 requests inside its single container, so parallel
# inspectors genuinely run in parallel. max_containers=1 on the Modal side is
# what still prevents a second billed GPU; extra requests queue there, not here.


def call_model(prompt: str, max_new_tokens: int = 1024) -> str:
    # one lane, one model: governed assets never touch a cloud model
    last_err = None
    for attempt in range(2):  # one retry: a container swap mid-run surfaces as a stray 5xx/404
        try:
            resp = requests.post(
                LANE_URL,
                json={"prompt": prompt, "token": LANE_TOKEN, "max_new_tokens": max_new_tokens},
                timeout=900,  # cold lane can take minutes; must outlive the Modal-side load
            )
            resp.raise_for_status()
            return resp.json()["text"]
        except requests.RequestException as e:
            last_err = e
        time.sleep(10)
    raise last_err


def think(prompt: str, max_new_tokens: int = 1024) -> str:
    # alias kept so agent code reads like #1
    return call_model(prompt, max_new_tokens)
