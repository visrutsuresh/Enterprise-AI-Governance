import os
import threading
import time

import requests
from dotenv import load_dotenv

load_dotenv()

LANE_URL = os.environ["PRIVATE_LANE_URL"]      # the private Modal endpoint
LANE_TOKEN = os.environ["PRIVATE_LANE_TOKEN"]

# one GPU serves one request at a time; parallel graph nodes queue here instead of
# hammering Modal into autoscaling a second cold container
_LANE_LOCK = threading.Lock()


def call_model(prompt: str, max_new_tokens: int = 1024) -> str:
    # one lane, one model: governed assets never touch a cloud model
    last_err = None
    for attempt in range(2):  # one retry: a container swap mid-run surfaces as a stray 5xx/404
        with _LANE_LOCK:
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
