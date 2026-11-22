import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
spec = importlib.util.spec_from_file_location('schedule_guard', Path(__file__).resolve().parents[1] / 'scripts/schedule_guard.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class ScheduleGuardTests(unittest.TestCase):
    now = dt.datetime(2026, 11, 21, 6, 47, tzinfo=dt.timezone.utc)

    def save(self, root, **changes):
        run = {'trigger': 'schedule', 'scope': 'global', 'status': 'completed',
               'scheduled_for_lisbon': '2026-11-21T06:00:00+00:00',
               'finished_at_utc': '2026-11-21T06:05:00+00:00', 'coverage_expected': 522,
               'collection_summary': {'apple_ids': {'checked': 522, 'error': 0, 'empty': 0}}}
        run.update(changes)
        path = root / 'archive/runs/2026/test.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(run))

    def test_missing_round_is_recovered_in_the_same_nominal_slot(self):
        with tempfile.TemporaryDirectory() as folder:
            result = guard.decision(Path(folder), now=self.now)
            self.assertTrue(result['collect'])
            self.assertEqual(result['slot'], '2026-11-21T06:00:00+00:00')

    def test_completed_round_skips_retries_but_does_not_block_the_next_round(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.save(root)
            self.assertFalse(guard.decision(root, now=self.now)['collect'])
            afternoon = self.now.replace(hour=13)
            self.assertTrue(guard.decision(root, now=afternoon)['collect'])

    def test_finished_partial_round_with_real_responses_does_not_repeat_because_of_an_empty_country(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.save(root, status='partial', collection_summary={'apple_ids': {'checked': 522, 'error': 0, 'empty': 1}})
            self.assertFalse(guard.decision(root, now=self.now)['collect'])

    def test_unfinished_incomplete_or_total_failure_rounds_are_retried(self):
        for changes in [{'status': 'running'}, {'finished_at_utc': None},
                        {'collection_summary': {'apple_ids': {'checked': 300}}},
                        {'status': 'partial', 'collection_summary': {'apple_ids': {'checked': 522, 'error': 522}}}]:
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.save(root, **changes)
                self.assertTrue(guard.decision(root, now=self.now)['collect'])

    def test_manual_and_diagnostic_runs_do_not_suppress_the_scheduled_round(self):
        for changes in [{'trigger': 'workflow_dispatch'}, {'scope': 'diagnostic'}]:
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.save(root, **changes)
                self.assertTrue(guard.decision(root, now=self.now)['collect'])

    def test_manual_extras_remain_available_after_a_scheduled_collection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.save(root)
            self.assertTrue(guard.decision(root, event='workflow_dispatch', now=self.now)['collect'])

    def test_lisbon_summer_time_is_used_for_nominal_slots(self):
        with tempfile.TemporaryDirectory() as folder:
            summer = dt.datetime(2027, 7, 1, 5, 17, tzinfo=dt.timezone.utc)
            result = guard.decision(Path(folder), now=summer)
            self.assertEqual(result['slot'], '2027-07-01T06:00:00+01:00')

    def test_a_missing_morning_round_can_be_recovered_after_its_hour(self):
        with tempfile.TemporaryDirectory() as folder:
            result = guard.decision(Path(folder), now=self.now.replace(hour=9, minute=17))
            self.assertTrue(result['collect'])
            self.assertEqual(result['slot'], '2026-11-21T06:00:00+00:00')

    def test_no_automatic_collection_before_six_even_if_yesterday_is_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            for hour in (0, 1, 5):
                self.assertFalse(guard.decision(Path(folder), now=self.now.replace(hour=hour))['collect'])
            self.assertTrue(guard.decision(Path(folder), event='workflow_dispatch', now=self.now.replace(hour=1))['collect'])

    def test_a_push_recovery_and_a_scheduled_run_share_the_same_slot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertTrue(guard.decision(root, event='push', now=self.now)['collect'])
            self.save(root, trigger='push')
            self.assertFalse(guard.decision(root, event='schedule', now=self.now)['collect'])
            self.assertFalse(guard.decision(root, event='push', now=self.now)['collect'])

    def test_forty_eight_checks_still_collect_only_the_three_daily_slots(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            collected = []
            for hour in range(24):
                for minute in (17, 47):
                    now = self.now.replace(hour=hour, minute=minute)
                    result = guard.decision(root, now=now)
                    if result['collect']:
                        collected.append(result['slot'])
                        self.save(root, scheduled_for_lisbon=result['slot'],
                                  finished_at_utc=(now + dt.timedelta(minutes=5)).isoformat())
            self.assertEqual(collected, ['2026-11-21T06:00:00+00:00',
                                         '2026-11-21T13:00:00+00:00',
                                         '2026-11-21T20:00:00+00:00'])


if __name__ == '__main__':
    unittest.main()
