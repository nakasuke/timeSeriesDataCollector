from datetime import datetime, timezone
import random
import unittest

from app.core import (
    APPLICATION_SIGNALS,
    build_signal_definitions,
    generate_segments,
    intersect_periods,
    seed_window,
    signal_random_seed,
)


class CoreTests(unittest.TestCase):
    def test_signal_counts(self):
        definitions = build_signal_definitions()
        self.assertEqual(100, len(definitions))
        counts = {kind: sum(item.signal_type == kind for item in definitions) for kind in ("AI", "AO", "DI", "DO")}
        self.assertEqual({"AI": 50, "AO": 10, "DI": 30, "DO": 10}, counts)

    def test_display_applications_have_ten_distinct_signals(self):
        self.assertEqual(3, len(APPLICATION_SIGNALS))
        self.assertTrue(all(len(signal_ids) == 10 for signal_ids in APPLICATION_SIGNALS.values()))
        flattened = [signal_id for signal_ids in APPLICATION_SIGNALS.values() for signal_id in signal_ids]
        self.assertEqual(30, len(set(flattened)))
        self.assertEqual(signal_random_seed(7, 0, "AI-001"), signal_random_seed(7, 9, "AI-010"))
        self.assertNotEqual(signal_random_seed(7, 0, "AI-001"), signal_random_seed(7, 10, "AO-001"))

    def test_random_segments_obey_ratio_and_minimum_span(self):
        start, end = seed_window(2026)
        segments = generate_segments(start, end, 0.5, 60, random.Random(1))
        total_units = int((end - start).total_seconds() // 3600)
        self.assertEqual(int(total_units * 0.5), sum(segment.point_count for segment in segments))
        self.assertTrue(all(segment.point_count >= 7 * 24 for segment in segments))
        self.assertTrue(all(left.end < right.start for left, right in zip(segments, segments[1:])))

    def test_period_intersection(self):
        utc = timezone.utc
        t = lambda day: datetime(2025, 1, day, tzinfo=utc)
        result = intersect_periods([[(t(1), t(10)), (t(20), t(25))], [(t(5), t(22))]])
        self.assertEqual([(t(5), t(10)), (t(20), t(22))], result)


if __name__ == "__main__":
    unittest.main()
