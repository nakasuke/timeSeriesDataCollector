from __future__ import annotations

from datetime import datetime, timezone
import math
import os
import random

from psycopg import sql

from .core import APPLICATION_SIGNALS, build_signal_definitions, generate_segments, seed_window, signal_random_seed
from .db import connection
from . import graph


def _profile() -> tuple[str, int]:
    profile = os.getenv("SEED_PROFILE", "demo").lower()
    if profile == "full":
        return profile, 1
    return "demo", 60


def seed_postgres() -> dict:
    profile, interval_minutes = _profile()
    random_seed = int(os.getenv("SEED_RANDOM", "20260918"))
    reference_year = datetime.now(timezone.utc).year
    window_start, window_end = seed_window(reference_year)
    seed_key = f"v1:{reference_year}:{profile}:{random_seed}"

    with connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT completed_at, row_count FROM seed_run WHERE seed_key = %s", (seed_key,))
        existing = cursor.fetchone()
        if existing and existing[0] is not None:
            return {"seed_key": seed_key, "row_count": existing[1], "skipped": True}
        cursor.execute(
            "INSERT INTO seed_run(seed_key, profile) VALUES (%s, %s) ON CONFLICT (seed_key) DO UPDATE SET started_at=now(), completed_at=NULL",
            (seed_key, profile),
        )
        conn.commit()

    total_rows = 0
    for signal_index, definition in enumerate(build_signal_definitions()):
        # The ten signals used by each display application share their random
        # range layout. This keeps the ranges random while guaranteeing that
        # each prototype screen has common periods it can actually display.
        signal_seed = signal_random_seed(random_seed, signal_index, definition.signal_id)
        rng = random.Random(signal_seed)
        segments = generate_segments(
            window_start, window_end, definition.coverage_ratio, interval_minutes, rng
        )
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO signal_catalog(signal_id, name, signal_type, table_name, unit, expected_interval_sec, coverage_ratio)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (signal_id) DO UPDATE SET
                  name=EXCLUDED.name, signal_type=EXCLUDED.signal_type, table_name=EXCLUDED.table_name,
                  unit=EXCLUDED.unit, expected_interval_sec=EXCLUDED.expected_interval_sec,
                  coverage_ratio=EXCLUDED.coverage_ratio
                """,
                (
                    definition.signal_id,
                    f"{definition.signal_type} signal {definition.signal_id}",
                    definition.signal_type,
                    definition.table_name,
                    definition.unit,
                    interval_minutes * 60,
                    definition.coverage_ratio,
                ),
            )
            cursor.execute("DELETE FROM signal_availability WHERE data_id = %s", (definition.signal_id,))
            for segment_index, segment in enumerate(segments):
                phase = rng.random() * math.pi
                table_identifier = sql.Identifier(definition.table_name)
                if definition.signal_type in {"AI", "AO"}:
                    value_expression = sql.SQL(
                        "50.0 + 35.0 * sin(extract(epoch from sample_time) / 86400.0 + %s) + (random() - 0.5) * 4.0"
                    )
                    value_params = [phase]
                else:
                    value_expression = sql.SQL("CASE WHEN random() > 0.5 THEN 1.0 ELSE 0.0 END")
                    value_params = []
                insert_query = sql.SQL(
                    "INSERT INTO {}(date_time, data_id, value, quality) "
                    "SELECT sample_time, %s, {}, 'GOOD' "
                    "FROM generate_series(%s::timestamptz, %s::timestamptz, %s::interval) sample_time "
                    "ON CONFLICT (data_id, date_time) DO NOTHING"
                ).format(table_identifier, value_expression)
                cursor.execute(
                    insert_query,
                    [definition.signal_id, *value_params, segment.start, segment.end, f"{interval_minutes} minutes"],
                )
                cursor.execute(
                    """
                    INSERT INTO signal_availability(data_id, start_time, end_time, point_count)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (data_id, start_time, end_time)
                    DO UPDATE SET point_count=EXCLUDED.point_count, updated_at=now()
                    """,
                    (definition.signal_id, segment.start, segment.end, segment.point_count),
                )
                total_rows += segment.point_count
            conn.commit()

    with connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            "UPDATE seed_run SET completed_at=now(), row_count=%s WHERE seed_key=%s",
            (total_rows, seed_key),
        )
        conn.commit()
    return {"seed_key": seed_key, "row_count": total_rows, "skipped": False}


def seed_graph() -> None:
    graph.submit("g.V().drop().iterate()")
    graph.submit(
        "g.addV('Plant').property('plant_id','plant-1').property('name','Prototype Plant').property('timezone','Asia/Tokyo').iterate()"
    )
    graph.submit(
        "g.addV('Database').property('database_id','plant-data').property('name','PostgreSQL plant_data').iterate()"
    )
    for table_name in ("ai_mhr", "ao_mhr", "di_mhr", "do_mhr"):
        graph.submit(
            """
            db=g.V().has('Database','database_id','plant-data').next();
            table=g.addV('Table').property('table_id',tableId).property('name',tableName).next();
            db.addEdge('CONTAINS',table)
            """,
            {"tableId": f"plant-data:{table_name}", "tableName": table_name},
        )
    for definition in build_signal_definitions():
        graph.submit(
            """
            plant=g.V().has('Plant','plant_id','plant-1').next();
            table=g.V().has('Table','table_id',tableId).next();
            signal=g.addV('Signal').property('signal_id',signalId).property('name',signalName)
              .property('signal_type',signalType).property('expected_interval_sec',intervalSec).next();
            plant.addEdge('HAS_SIGNAL',signal); signal.addEdge('STORED_IN',table)
            """,
            {
                "tableId": f"plant-data:{definition.table_name}",
                "signalId": definition.signal_id,
                "signalName": f"{definition.signal_type} signal {definition.signal_id}",
                "signalType": definition.signal_type,
                "intervalSec": _profile()[1] * 60,
            },
        )
    for app_number, (application_id, signal_ids) in enumerate(APPLICATION_SIGNALS.items(), start=1):
        graph.submit(
            "g.addV('Application').property('application_id',appId).property('name',appName).property('type','DISPLAY').iterate()",
            {"appId": application_id, "appName": f"表示アプリ {app_number}"},
        )
        for signal_id in signal_ids:
            graph.submit(
                """
                app=g.V().has('Application','application_id',appId).next();
                signal=g.V().has('Signal','signal_id',signalId).next();
                app.addEdge('USES',signal)
                """,
                {"appId": application_id, "signalId": signal_id},
            )
