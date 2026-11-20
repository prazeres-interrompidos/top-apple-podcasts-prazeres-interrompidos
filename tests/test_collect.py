import importlib.util
import json
from pathlib import Path
import unittest
import datetime as dt
import tempfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('collect', Path(__file__).resolve().parents[1] / 'scripts/collect.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class ChartTests(unittest.TestCase):
    @staticmethod
    def observation(rank, date='2026-11-19', country='pt', category='1482', source='apple_ids', suffix='morning'):
        return {'id': suffix + ':' + country + ':' + category + ':' + source, 'run_id': suffix,
                'apple_id': c.APPLE_ID, 'country': country, 'category': category,
                'date': date, 'rank': rank, 'status': 'ranked', 'source': source,
                'url': c.source_url(country, category, source), 'quality': 'comprovado_na_lista'}

    def test_three_checks_retain_only_the_daily_best_and_keep_failures_honest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'archive/runs/2026/run.json'
            run = {'id': 'run', 'scope': 'global', 'status': 'completed',
                   'retention_policy': 'daily_best_positions_v1'}
            for rank, slot in [(8, 'morning'), (3, 'afternoon'), (6, 'evening')]:
                run['observations'] = [self.observation(rank, suffix=slot)]
                c.save_run(path, run, root)
            # An error at a later check cannot erase or turn the result into zero.
            run.update(status='partial', errors=1, observations=[
                {'apple_id': c.APPLE_ID, 'country': 'pt', 'category': '1482',
                 'source': 'apple_ids', 'status': 'error', 'rank': None}])
            c.save_run(path, run, root)
            daily = json.loads((root / 'archive/daily/2026/2026-11-19.json').read_text())
            self.assertEqual(len(daily['observations']), 1)
            self.assertEqual(daily['observations'][0]['rank'], 3)
            self.assertEqual(daily['observations'][0]['selected_observation_id'], 'afternoon:pt:1482:apple_ids')
            summary = json.loads(path.read_text())
            self.assertEqual(summary['observations'], [])
            self.assertEqual(summary['collection_summary']['apple_ids']['error'], 1)
            self.assertEqual(summary['status'], 'partial')

    def test_daily_best_separates_dates_countries_categories_and_prefers_ids_on_ties(self):
        rows = [self.observation(3, source='apple_rss'), self.observation(3),
                self.observation(10, date='2026-11-20'), self.observation(1, country='mz'),
                self.observation(5, category='1301')]
        selected = c.daily_best(rows)
        self.assertEqual(len(selected), 4)
        portugal_books = next(r for r in selected if r['date'] == '2026-11-19' and r['country'] == 'pt' and r['category'] == '1482')
        self.assertEqual(portugal_books['source'], 'apple_ids')
        self.assertTrue(all(r['aggregation'] == 'minimum_observed_rank' for r in selected))
        self.assertEqual(c.daily_best(selected), selected)

    def test_rss_fallback_is_per_failed_category_and_never_for_valid_absence(self):
        rows = [{'source': 'apple_ids', 'country': 'pt', 'category': category, 'status': status}
                for category, status in [('1482', 'ranked'), ('1301', 'not_found'), ('26', 'error')]]
        rows.append({'source': 'apple_ids', 'country': 'mz', 'category': '1482', 'status': 'empty'})
        self.assertEqual(c.fallback_jobs(rows), [('mz', '1482'), ('pt', '26')])

    def test_diagnostic_run_cannot_modify_the_daily_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run = {'id': 'diagnostic', 'scope': 'diagnostic', 'retention_policy': 'daily_best_positions_v1',
                   'observations': [self.observation(1)]}
            path = root / 'archive/runs/2026/test.json'
            c.save_run(path, run, root)
            self.assertFalse((root / 'archive/daily').exists())
            self.assertEqual(json.loads(path.read_text())['observations'], [])

    def test_schedule_slots_cover_three_lisbon_times_and_daylight_saving(self):
        for hour in [6, 13, 20]:
            for month, offset in [(7, 1), (11, 0)]:
                now = dt.datetime(2026, month, 19, hour-offset, 15, tzinfo=dt.timezone.utc)
                slot = dt.datetime.fromisoformat(c.expected_slot(now))
                self.assertEqual(slot.hour, hour)
                self.assertEqual(slot.utcoffset(), dt.timedelta(hours=offset))
        before_first = dt.datetime(2026, 11, 19, 5, 59, tzinfo=dt.timezone.utc)
        self.assertEqual(c.expected_slot(before_first), '2026-11-18T20:00:00+00:00')

    def test_public_history_keeps_original_historical_rows_and_aggregates_automatic_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            historical = root / 'archive/historical'
            historical.mkdir(parents=True)
            original = [{'id': 'historic-2023', 'source': 'historical', 'source_name': 'Arquivo histórico',
                         'date': '2023-01-09', 'country': 'pt', 'category': None, 'rank': 2}]
            c.dump(historical / 'history.json', original)
            c.dump(historical / 'consultations.json', [])
            c.dump(historical / 'peaks.json', [{'id': 'peak-2024', 'rank': 2, 'country': 'pt', 'last_charted_date': '2024-12-10'}])
            c.dump(root / 'config.json', {'countries': [], 'schedule': {'times': ['06:00', '13:00', '20:00']}})
            run = {'id': 'run', 'scope': 'global', 'started_at_utc': '2026-11-19T13:00:00+00:00',
                   'observations': [self.observation(8), self.observation(3, suffix='afternoon')]}
            c.dump(root / 'archive/runs/2026/legacy.json', run)
            c.build_public(root)
            result = json.loads((root / 'public/history.json').read_text())
            self.assertEqual(result[0], original[0])
            self.assertEqual(len(result), 2)
            self.assertEqual(result[1]['rank'], 3)
            self.assertEqual(json.loads((historical / 'history.json').read_text()), original)
            self.assertEqual(len(json.loads((root / 'public/peaks.json').read_text())), 1)

    def test_network_responses_are_never_written_to_disk(self):
        class Response:
            status = 200
            headers = {}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, limit):
                return json.dumps({'resultIds': ['987654321', c.APPLE_ID, '123456789']}).encode()

        with tempfile.TemporaryDirectory() as folder, patch.object(c, 'throttle'), \
                patch.object(c.urllib.request, 'urlopen', return_value=Response()):
            result = c.fetch_observation('pt', '1482', 'apple_ids', 'test', {'pt': 'Portugal'}, Path(folder))
            self.assertEqual(result['rank'], 2)
            self.assertEqual(list(Path(folder).rglob('*')), [])
            self.assertNotIn('987654321', json.dumps(result))
            self.assertNotIn('evidence_path', result)
            self.assertNotIn('attempts', result)

    def test_retry_does_not_store_error_body_or_mark_success_as_failed(self):
        class Response:
            headers = {'Retry-After': '0'}
            def __init__(self, status, body):
                self.status, self.body = status, body
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, limit):
                return self.body

        responses = [Response(503, b'body that must never be archived'),
                     Response(200, json.dumps({'resultIds': [c.APPLE_ID]}).encode())]
        with tempfile.TemporaryDirectory() as folder, patch.object(c, 'throttle'), \
                patch.object(c.time, 'sleep'), patch.object(c.urllib.request, 'urlopen', side_effect=responses):
            result = c.fetch_observation('pt', '1482', 'apple_ids', 'test', {'pt': 'Portugal'}, Path(folder))
            self.assertEqual(result['status'], 'ranked')
            self.assertNotIn('error', result)
            self.assertEqual(list(Path(folder).rglob('*')), [])

    def test_archive_keeps_positions_and_divergences_without_complete_lists(self):
        positive = {'id': 'kept', 'apple_id': c.APPLE_ID, 'source': 'apple_ids', 'rank': 3,
                    'status': 'ranked', 'country': 'pt', 'category': '1482', 'date': '2026-11-18',
                    'divergent': True, 'divergence_note': 'Different ranks',
                    'evidence_path': 'archive/responses/old.gz', 'headers': {'x-cache': 'old'},
                    'attempts': [{'raw_body': 'other programmes'}], 'sequence_sha256': 'old',
                    'resultIds': ['12345', c.APPLE_ID]}
        absent = {'apple_id': c.APPLE_ID, 'source': 'apple_rss', 'rank': None, 'status': 'not_found'}
        failed = {'apple_id': c.APPLE_ID, 'source': 'apple_ids', 'rank': None, 'status': 'error'}
        run = {'id': 'run', 'status': 'partial', 'errors': 1, 'observations': [positive, absent, failed]}
        result = c.compact_run(run)
        self.assertEqual([r['id'] for r in result['observations']], ['kept'])
        self.assertTrue(result['observations'][0]['divergent'])
        self.assertEqual(result['collection_summary']['apple_rss']['not_found'], 1)
        self.assertEqual(result['collection_summary']['apple_ids']['error'], 1)
        self.assertEqual(result['status'], 'partial')
        self.assertNotIn('archive/responses', json.dumps(result))
        self.assertNotIn('12345', json.dumps(result))
        self.assertEqual(c.compact_run(result), result)

    def test_running_checkpoints_also_exclude_raw_data_and_absences(self):
        run = {'id': 'run', 'status': 'running', 'observations': [
            {'apple_id': c.APPLE_ID, 'source': 'apple_ids', 'status': 'empty', 'rank': None, 'feed': {'entry': []}},
            {'apple_id': c.APPLE_ID, 'source': 'apple_rss', 'status': 'ranked', 'rank': 7,
             'date': '2026-11-18', 'raw_body': 'secret-other-programmes'},
        ]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'run.json'
            c.save_run(path, run)
            result = json.loads(path.read_text())
            self.assertEqual(len(result['observations']), 1)
            self.assertEqual(result['observations'][0]['rank'], 7)
            self.assertNotIn('secret-other-programmes', path.read_text())
            self.assertEqual(result['collection_summary']['apple_ids']['empty'], 1)

    def test_guard_rejects_complete_lists_and_response_archives(self):
        spec = importlib.util.spec_from_file_location('privacy', c.ROOT / 'scripts/check_public_data.py')
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'archive/responses').mkdir(parents=True)
            (root / 'archive/responses/old.gz').write_bytes(b'old archive')
            self.assertTrue(guard.check(root))
            (root / 'archive/responses/old.gz').unlink()
            (root / 'archive/old.json').write_text(json.dumps({'resultIds': ['1', '2']}))
            self.assertTrue(guard.check(root))

    def test_only_apple_sources_and_user_records_are_presented(self):
        self.assertTrue(c.allowed_public_record({'source': 'apple_ids', 'url': 'https://itunes.apple.com/chart'}))
        self.assertTrue(c.allowed_public_record({'source': 'historical', 'source_name': 'Arquivo histórico enviado'}))
        self.assertFalse(c.allowed_public_record({'source_name': 'Podscan', 'url': 'https://podscan.fm/charts/pt'}))
        self.assertFalse(c.allowed_public_record({'source': 'apple_ids', 'url': 'https://apple.com.example.org/chart'}))
        self.assertFalse(c.allowed_public_record({'source_name': 'Outra fonte'}))

    def test_id_matching_not_title(self):
        result = c.parse_payload(json.dumps({'resultIds': ['1', c.APPLE_ID, '16336198450']}).encode(), 'apple_ids', '1482')
        self.assertEqual(result['rank'], 2)

    def test_absence_is_not_zero_or_inferred_rank(self):
        result = c.parse_payload(b'{"resultIds":["1","2"]}', 'apple_ids', '26')
        self.assertIsNone(result['rank'])
        self.assertEqual(result['count'], 2)
        self.assertEqual(result['status'], 'not_found')

    def test_empty_is_inconclusive(self):
        self.assertEqual(c.parse_payload(b'{"resultIds":[]}', 'apple_ids', '26')['quality'], 'nao_verificavel')

    def test_duplicate_and_wrong_schema_rejected(self):
        for data in [b'{"resultIds":["1","1"]}', b'{"results":[]}', b'{"resultIds":["invalid"]}']:
            with self.assertRaises(ValueError):
                c.parse_payload(data, 'apple_ids', '26')

    def test_invalid_category_cannot_silently_become_general(self):
        with self.assertRaises(ValueError):
            c.source_url('pt', '999999', 'apple_ids')
        with self.assertRaises(ValueError):
            c.parse_payload(b'{"feed":{"title":{"label":"Top podcasts"}}}', 'apple_rss', '1482')

    def test_rss_singleton_and_updated_raw(self):
        data = {'feed': {'title': {'label': 'Top Books'}, 'updated': {'label': '2026-11-18T10:04:20-07:00'},
                         'entry': {'id': {'attributes': {'im:id': c.APPLE_ID}}}}}
        r = c.parse_payload(json.dumps(data).encode(), 'apple_rss', '1482')
        self.assertEqual(r['rank'], 1)
        self.assertEqual(r['source_updated_raw'], '2026-11-18T10:04:20-07:00')

    def test_depth_does_not_create_false_conflict(self):
        a = {'country': 'pt', 'category': '26', 'status': 'ranked', 'rank': 225, 'count': 250, 'divergent': False}
        b = {'country': 'pt', 'category': '26', 'status': 'not_found', 'rank': None, 'count': 200, 'divergent': False}
        c.mark_divergences([a,b])
        self.assertFalse(a['divergent'])
        a['rank'] = 150
        c.mark_divergences([a,b])
        self.assertTrue(a['divergent'])

    def test_lisbon_daylight_saving(self):
        summer = c.expected_slot(dt.datetime(2026,7,3,13,0,tzinfo=dt.timezone.utc))
        winter = c.expected_slot(dt.datetime(2026,11,18,14,0,tzinfo=dt.timezone.utc))
        self.assertTrue(summer.endswith('+01:00'))
        self.assertTrue(winter.endswith('+00:00'))
        self.assertIn('T13:00:00', summer)


if __name__ == '__main__':
    unittest.main()
