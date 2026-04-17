"""Shared offline mock LLM implementation for local development and testing."""
from __future__ import annotations

import random
import time

MOCK_RESPONSES = {
    "default": [
        "This is a mock AI response for deployment practice.",
        "Your request was processed successfully by the mock model.",
        "The production-ready agent is running with mock inference.",
    ],
    "docker": [
        "Docker packages your app so it runs consistently across environments."
    ],
    "deploy": [
        "Deployment publishes your service so others can access it."
    ],
    "health": ["Service is healthy and accepting traffic."],
}


def ask(question: str, delay: float = 0.08) -> str:
    """Return a deterministic-style response with a tiny latency simulation."""
    time.sleep(delay + random.uniform(0, 0.03))
    text = question.lower()
    for keyword, options in MOCK_RESPONSES.items():
        if keyword in text:
            return random.choice(options)
    return random.choice(MOCK_RESPONSES["default"])
