from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from psycopg import sql

from .core import intersect_periods
from .db import close_pool, connection, fetch_all, open_pool
from . import graph
from .models import AvailableRangeRequest, DataQueryRequest, HealthResponse
from .seed import seed_graph, seed_postgres


STATIC_DIR = Path(__file__).parent / "static"
ALLOWED_TABLES = {"ai_mhr", "ao_mhr", "di_mhr", "do_mhr"}


def _startup() -> None:
    """Run blocking database drivers outside uvicorn's event-loop thread."""
    open_pool()
    try:
        graph.connect_with_retry()
        seed_postgres()
        seed_graph()
    except Exception:
        graph.close()
        close_pool()
        raise


def _shutdown() -> None:
    graph.close()
    close_pool()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # gremlin-python's synchronous Client owns an aiohttp event loop. Calling
    # it directly inside FastAPI/uvloop raises "Cannot run the event loop while
    # another loop is running", so all blocking startup/shutdown work runs in
    # a worker thread.
    await asyncio.to_thread(_startup)
    try:
        yield
    finally:
        await asyncio.to_thread(_shutdown)


app = FastAPI(title="Plant Data Prototype API", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/apps/{application_id}", include_in_schema=False)
def display_application(application_id: str):
    if application_id not in {"display-app-1", "display-app-2", "display-app-3"}:
        raise HTTPException(404, "application not found")
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/v1/health", response_model=HealthResponse)
def health():
    fetch_all("SELECT 1 AS ok")
    graph.submit("g.V().limit(1).count()")
    return HealthResponse()


@app.get("/api/v1/applications")
def get_applications():
    return {"items": graph.applications()}


@app.get("/api/v1/applications/{application_id}/signals")
def get_application_signals(application_id: str):
    signal_ids = graph.application_signals(application_id)
    if not signal_ids:
        raise HTTPException(404, "application not found or has no signals")
    rows = fetch_all(
        "SELECT signal_id, name, signal_type, table_name, unit, expected_interval_sec, coverage_ratio "
        "FROM signal_catalog WHERE signal_id = ANY(%s) ORDER BY signal_id",
        (signal_ids,),
    )
    return {"application_id": application_id, "items": rows}


@app.get("/api/v1/signals")
def get_signals(signal_type: str | None = None):
    if signal_type is None:
        rows = fetch_all("SELECT * FROM signal_catalog ORDER BY signal_id")
    else:
        rows = fetch_all("SELECT * FROM signal_catalog WHERE signal_type=%s ORDER BY signal_id", (signal_type.upper(),))
    return {"items": rows, "count": len(rows)}


@app.post("/api/v1/available-range")
def available_range(request: AvailableRangeRequest):
    unique_ids = list(dict.fromkeys(request.signal_ids))
    rows = fetch_all(
        "SELECT signal_id, table_name FROM signal_catalog WHERE signal_id = ANY(%s)",
        (unique_ids,),
    )
    found = {row["signal_id"]: row for row in rows}
    missing = [signal_id for signal_id in unique_ids if signal_id not in found]
    if missing and not request.allow_partial:
        raise HTTPException(409, detail={"code": "RANGE_NOT_READY", "missing_signal_ids": missing})
    ready_ids = [signal_id for signal_id in unique_ids if signal_id in found]
    period_lists = []
    signal_status = []
    for signal_id in unique_ids:
        if signal_id not in found:
            signal_status.append({"signal_id": signal_id, "status": "SIGNAL_NOT_FOUND"})
            continue
        periods = fetch_all(
            "SELECT start_time, end_time FROM signal_availability WHERE data_id=%s ORDER BY start_time",
            (signal_id,),
        )
        period_lists.append([(row["start_time"], row["end_time"]) for row in periods])
        signal_status.append({"signal_id": signal_id, "table_name": found[signal_id]["table_name"], "status": "READY"})
    common = intersect_periods(period_lists) if ready_ids else []
    if request.range_hint:
        common = [
            (max(start, request.range_hint.start_time), min(end, request.range_hint.end_time))
            for start, end in common
            if max(start, request.range_hint.start_time) <= min(end, request.range_hint.end_time)
        ]
    return {
        "common_valid_periods": [{"start_time": start, "end_time": end} for start, end in common],
        "signals": signal_status,
        "partial": bool(missing),
        "warnings": [f"Excluded unknown signal: {signal_id}" for signal_id in missing],
    }


@app.post("/api/v1/data/query")
def query_data(request: DataQueryRequest):
    catalog = fetch_all(
        "SELECT signal_id, table_name FROM signal_catalog WHERE signal_id = ANY(%s)",
        (request.signal_ids,),
    )
    by_table: dict[str, list[str]] = {}
    for row in catalog:
        if row["table_name"] not in ALLOWED_TABLES:
            continue
        by_table.setdefault(row["table_name"], []).append(row["signal_id"])
    series = []
    with connection() as conn, conn.cursor() as cursor:
        for table_name, signal_ids in by_table.items():
            for signal_id in signal_ids:
                query = sql.SQL(
                    "SELECT date_time, value, quality FROM {} WHERE data_id=%s AND date_time BETWEEN %s AND %s "
                    "ORDER BY date_time LIMIT %s"
                ).format(sql.Identifier(table_name))
                cursor.execute(query, (signal_id, request.start_time, request.end_time, request.max_points_per_signal))
                points = [
                    {"date_time": row[0], "value": row[1], "quality": row[2]}
                    for row in cursor.fetchall()
                ]
                series.append({"signal_id": signal_id, "points": points})
    return {"series": series}
