from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import random
from typing import Iterable


@dataclass(frozen=True)
class SignalDefinition:
    signal_id: str
    signal_type: str
    table_name: str
    coverage_ratio: float
    unit: str | None


@dataclass(frozen=True)
class TimeSegment:
    start: datetime
    end: datetime
    point_count: int


SIGNAL_PLAN = {
    "AI": {"count": 50, "ratio": 0.50, "table": "ai_mhr", "unit": "%"},
    "AO": {"count": 10, "ratio": 0.30, "table": "ao_mhr", "unit": "%"},
    "DI": {"count": 30, "ratio": 0.20, "table": "di_mhr", "unit": None},
    "DO": {"count": 10, "ratio": 0.20, "table": "do_mhr", "unit": None},
}

APPLICATION_SIGNALS = {
    "display-app-1": [f"AI-{index:03d}" for index in range(1, 11)],
    "display-app-2": [f"AO-{index:03d}" for index in range(1, 11)],
    "display-app-3": [f"DI-{index:03d}" for index in range(1, 11)],
}


def signal_random_seed(base_seed: int, signal_index: int, signal_id: str) -> int:
    for application_number, signal_ids in enumerate(APPLICATION_SIGNALS.values(), start=1):
        if signal_id in signal_ids:
            return base_seed + application_number * 100_003
    return base_seed + signal_index * 7_919


def build_signal_definitions() -> list[SignalDefinition]:
    definitions: list[SignalDefinition] = []
    for signal_type, plan in SIGNAL_PLAN.items():
        for index in range(1, plan["count"] + 1):
            definitions.append(
                SignalDefinition(
                    signal_id=f"{signal_type}-{index:03d}",
                    signal_type=signal_type,
                    table_name=str(plan["table"]),
                    coverage_ratio=float(plan["ratio"]),
                    unit=plan["unit"],
                )
            )
    return definitions


def seed_window(reference_year: int) -> tuple[datetime, datetime]:
    start = datetime(reference_year - 2, 1, 1, tzinfo=timezone.utc)
    end_exclusive = datetime(reference_year, 1, 1, tzinfo=timezone.utc)
    return start, end_exclusive


def _random_partition(total: int, count: int, rng: random.Random) -> list[int]:
    if count == 1:
        return [total]
    weights = [rng.random() + 0.01 for _ in range(count)]
    raw = [int(total * weight / sum(weights)) for weight in weights]
    for index in range(total - sum(raw)):
        raw[index % count] += 1
    return raw


def generate_segments(
    window_start: datetime,
    window_end_exclusive: datetime,
    coverage_ratio: float,
    interval_minutes: int,
    rng: random.Random,
    minimum_span_days: int = 7,
) -> list[TimeSegment]:
    total_units = int((window_end_exclusive - window_start).total_seconds() // (interval_minutes * 60))
    target_units = max(1, int(total_units * coverage_ratio))
    min_units = max(1, (minimum_span_days * 24 * 60) // interval_minutes)
    max_segments = max(1, min(6, target_units // min_units))
    segment_count = rng.randint(2 if max_segments >= 2 else 1, max_segments)

    remaining_segment_units = target_units - segment_count * min_units
    lengths = [min_units + value for value in _random_partition(remaining_segment_units, segment_count, rng)]
    gap_units = total_units - target_units
    gaps = _random_partition(gap_units, segment_count + 1, rng)

    segments: list[TimeSegment] = []
    cursor_units = gaps[0]
    interval = timedelta(minutes=interval_minutes)
    for index, length in enumerate(lengths):
        start = window_start + cursor_units * interval
        end = start + (length - 1) * interval
        segments.append(TimeSegment(start=start, end=end, point_count=length))
        cursor_units += length + gaps[index + 1]
    return segments


def intersect_periods(period_lists: Iterable[list[tuple[datetime, datetime]]]) -> list[tuple[datetime, datetime]]:
    iterator = iter(period_lists)
    try:
        result = list(next(iterator))
    except StopIteration:
        return []
    for periods in iterator:
        merged: list[tuple[datetime, datetime]] = []
        left_index = right_index = 0
        while left_index < len(result) and right_index < len(periods):
            left = result[left_index]
            right = periods[right_index]
            start = max(left[0], right[0])
            end = min(left[1], right[1])
            if start <= end:
                merged.append((start, end))
            if left[1] < right[1]:
                left_index += 1
            else:
                right_index += 1
        result = merged
        if not result:
            break
    return result
