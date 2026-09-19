from __future__ import annotations

import os
import time

from gremlin_python.driver.client import Client


GREMLIN_URL = os.getenv("GREMLIN_URL", "ws://localhost:8182/gremlin")
_client: Client | None = None


def connect_with_retry(attempts: int = 30) -> None:
    global _client
    last_error: Exception | None = None
    for _ in range(attempts):
        candidate: Client | None = None
        try:
            candidate = Client(GREMLIN_URL, "g")
            candidate.submit("g.V().limit(1).count()").all().result()
            _client = candidate
            return
        except Exception as error:
            last_error = error
            if candidate is not None:
                candidate.close()
            time.sleep(2)
    raise RuntimeError("Gremlin Server is not available") from last_error


def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def submit(script: str, bindings: dict | None = None) -> list:
    if _client is None:
        raise RuntimeError("Graph client is not connected")
    return _client.submit(script, bindings or {}).all().result()


def application_signals(application_id: str) -> list[str]:
    result = submit(
        "g.V().has('Application','application_id',appId).out('USES').values('signal_id').order().fold()",
        {"appId": application_id},
    )
    return list(result[0]) if result else []


def applications() -> list[dict]:
    rows = submit(
        "g.V().hasLabel('Application').project('application_id','name').by('application_id').by('name').fold()"
    )
    return sorted(list(rows[0]), key=lambda item: item["application_id"]) if rows else []
