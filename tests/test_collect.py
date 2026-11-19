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
