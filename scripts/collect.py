"""Apple chart positions for this podcast only; response bodies stay in memory."""
import argparse
import concurrent.futures
import datetime as dt
import email.utils
import json
import os
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import uuid
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
APPLE_ID = '1633619845'
CATEGORIES = {'1482': 'Livros', '1301': 'Arte', '26': 'Top Geral de Programas'}
REPO = 'https://github.com/prazeres-interrompidos/top-apple-podcasts-prazeres-interrompidos'
RAW = 'https://raw.githubusercontent.com/prazeres-interrompidos/top-apple-podcasts-prazeres-interrompidos/main/'
LISBON = ZoneInfo('Europe/Lisbon')
SCHEDULE_HOURS = (6, 13, 20)
_gate = threading.Lock()
_next_request = 0.0


def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def parse_payload(raw, source, genre):
    if genre not in CATEGORIES:
        raise ValueError('Categoria não catalogada')
    data = json.loads(raw)
    updated = None
    if source == 'apple_ids':
        entries = data.get('resultIds')
        if not isinstance(entries, list):
            raise ValueError('Resposta sem resultIds')
        ids = [str(item) for item in entries]
        limit = 250
    elif source == 'apple_rss':
        feed = data.get('feed')
        if not isinstance(feed, dict):
            raise ValueError('Resposta sem feed')
        title = feed.get('title', {}).get('label', '')
        term = {'1482': ('books', 'livros'), '1301': ('arts', 'arte')}.get(genre)
        if term and not any(word in title.lower() for word in term):
            raise ValueError('Categoria recebida não confirmada no título do feed')
        entries = feed.get('entry', [])
        if isinstance(entries, dict):
            entries = [entries]
        ids = [str(item['id']['attributes']['im:id']) for item in entries]
        updated = feed.get('updated', {}).get('label')
        limit = 200
    else:
        raise ValueError('Fonte desconhecida')
    if len(ids) > limit or any(not re.fullmatch(r'[0-9]+', v) for v in ids) or len(ids) != len(set(ids)):
        raise ValueError('Lista inválida: profundidade, IDs ou duplicações')
    rank = ids.index(APPLE_ID) + 1 if APPLE_ID in ids else None
    return {'count': len(ids), 'rank': rank, 'source_updated_raw': updated,
            'status': 'ranked' if rank else 'not_found' if ids else 'empty',
            'quality': 'comprovado_na_lista' if rank else 'ausente_na_lista' if ids else 'nao_verificavel'}


def source_url(country, genre, source):
    if not re.fullmatch('[a-z]{2}', country) or genre not in CATEGORIES:
        raise ValueError('Âmbito inválido')
    if source == 'apple_ids':
        return f'https://itunes.apple.com/WebObjects/MZStoreServices.woa/ws/charts?cc={country}&g={genre}&name=Podcasts&limit=250'
    if source == 'apple_rss':
        suffix = f'/genre={genre}' if genre != '26' else ''
        return f'https://itunes.apple.com/{country}/rss/toppodcasts/limit=200{suffix}/json'
    raise ValueError('Fonte desconhecida')


def throttle():
    global _next_request
    with _gate:
        delay = max(0, _next_request - time.monotonic())
        if delay:
            time.sleep(delay)
        _next_request = time.monotonic() + 0.5


def fetch_observation(country, genre, source, run_id, countries, root=ROOT):
    url = source_url(country, genre, source)
    record = {'id': f'{run_id}:{country}:{genre}:{source}', 'run_id': run_id,
              'apple_id': APPLE_ID, 'country': country, 'country_name': countries.get(country, country.upper()),
              'category': genre, 'category_name': CATEGORIES[genre], 'chart_type': 'shows',
              'source': source, 'url': url, 'requested_limit': 250 if source == 'apple_ids' else 200,
              'rank': None, 'count': None,
              'status': 'error', 'quality': 'nao_verificavel', 'divergent': False,
              'scope_basis': 'parametros_catalogados' if source == 'apple_ids' else 'titulo_do_feed',
              'parser_version': 1}
    for attempt in range(2):
        throttle()
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'PrazeresInterrompidos-Monitor/1.0 (public podcast chart research)'})
            try:
                response = urllib.request.urlopen(request, timeout=22)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                body = response.read(8_000_001)
                status = response.status
                retry_after = response.headers.get('Retry-After', '3')
            if len(body) > 8_000_000:
                raise ValueError('Resposta excede o limite de segurança de tamanho')
            record['http_status'] = status
            if status == 200:
                record.update(parse_payload(body, source, genre))
                record.pop('error', None)
                break
            record['error'] = f'HTTP {status}'
            if status not in [408, 429, 500, 502, 503, 504]:
                break
            retry = retry_after
            if not retry.isdigit():
                try:
                    retry = str(max(0, int((email.utils.parsedate_to_datetime(retry) - dt.datetime.now(dt.timezone.utc)).total_seconds())))
                except (ValueError, TypeError):
                    retry = '3'
            if int(retry) > 60:
                break
            time.sleep(min(60, max(3, int(retry))))
        except Exception as error:
            record['error'] = f'Consulta não verificável ({type(error).__name__})'
            if attempt == 0:
                time.sleep(3)
    record['observed_at_utc'] = utcnow()
    record['observed_at_lisbon'] = dt.datetime.fromisoformat(record['observed_at_utc']).astimezone(LISBON).isoformat()
    record['date'] = record['observed_at_lisbon'][:10]
    return record


# Explicit allowlists prevent full lists, other podcast IDs, raw response paths,
# HTTP headers and retry payloads from leaking into the permanent archive.
POSITION_FIELDS = {
    'id', 'run_id', 'apple_id', 'country', 'country_name', 'category',
    'category_name', 'chart_type', 'source', 'url', 'requested_limit', 'rank',
    'count', 'status', 'quality', 'divergent', 'divergence_note', 'scope_basis',
    'parser_version', 'http_status', 'source_updated_raw', 'observed_at_utc',
    'observed_at_lisbon', 'date',
    'fallback', 'aggregation', 'selected_observation_id',
}
RUN_FIELDS = {
    'id', 'started_at_utc', 'finished_at_utc', 'trigger', 'scheduled_for_lisbon',
    'workflow_url', 'coverage_expected', 'coverage_market_count', 'status',
    'scope', 'errors', 'empty_lists', 'ranked_observations', 'uncollected_count',
    'coverage_planned_market_count', 'interruption_note',
}


def compact_run(run):
    """Keep this podcast's positions and aggregate collection health only."""
    observations = run.get('observations', [])
    compact = {k: v for k, v in run.items() if k in RUN_FIELDS}
    compact['retention_policy'] = run.get('retention_policy', 'podcast_positions_only_v1')
    # Preserve the aggregate counts on repeated builds of an already compact run.
    summary = run.get('collection_summary')
    if summary is None:
        summary = {}
        for record in observations:
            source = record.get('source')
            status = record.get('status')
            if source in {'apple_ids', 'apple_rss'} and status in {'ranked', 'not_found', 'empty', 'error'}:
                counts = summary.setdefault(source, {'checked': 0, 'ranked': 0, 'not_found': 0, 'empty': 0, 'error': 0})
                counts['checked'] += 1
                counts[status] += 1
    compact['collection_summary'] = summary
    compact['observations'] = [
        {k: v for k, v in record.items() if k in POSITION_FIELDS}
        for record in observations
        if record.get('apple_id') == APPLE_ID and record.get('status') == 'ranked'
        and type(record.get('rank')) is int and record['rank'] > 0
    ]
    return compact


def daily_best(observations):
    """One best observed rank per Lisbon day/country/category; ties prefer IDs."""
    best = {}
    for record in observations:
        if record.get('apple_id') != APPLE_ID or record.get('source') not in {'apple_ids', 'apple_rss'}:
            continue
        if record.get('status') != 'ranked' or type(record.get('rank')) is not int or record['rank'] < 1:
            continue
        if not re.fullmatch('[a-z]{2}', record.get('country', '')) or record.get('category') not in CATEGORIES:
            continue
        try:
            date = dt.date.fromisoformat(record.get('date', '')).isoformat()
        except (ValueError, TypeError):
            continue
        key = (date, record['country'], record['category'])
        order = lambda r: (r['rank'], r['source'] != 'apple_ids', r.get('observed_at_utc', ''), r.get('id', ''))
        if key not in best or order(record) < order(best[key]):
            best[key] = record
    result = []
    for (date, country, category), record in sorted(best.items()):
        selected = {k: v for k, v in record.items() if k in POSITION_FIELDS}
        selected['selected_observation_id'] = record.get('selected_observation_id', record['id'])
        selected.update(id=f'daily:{date}:{country}:{category}', aggregation='minimum_observed_rank')
        result.append(selected)
    return result


def update_daily_archive(root, observations):
    by_date = {}
    for record in daily_best(observations):
        by_date.setdefault(record['date'], []).append(record)
    for date, positions in by_date.items():
        path = root / 'archive/daily' / date[:4] / (date + '.json')
        existing = json.loads(path.read_text())['observations'] if path.exists() else []
        dump(path, {'date': date, 'timezone': 'Europe/Lisbon', 'retention_policy': 'daily_best_positions_v1',
                    'observations': daily_best(existing + positions)})


def save_run(path, run, root=ROOT):
    compact = compact_run(run)
    if compact['retention_policy'] == 'daily_best_positions_v1':
        if run.get('scope') != 'diagnostic':
            update_daily_archive(root, compact['observations'])
        # New run files contain collection counters, never intermediate positions.
        compact['observations'] = []
    dump(path, compact)


def fallback_jobs(observations):
    return sorted({(r['country'], r['category']) for r in observations
                   if r['source'] == 'apple_ids' and r['status'] in {'error', 'empty'}})


def mark_divergences(observations):
    groups = {}
    for record in observations:
        groups.setdefault((record['country'], record['category']), []).append(record)
    for group in groups.values():
        ranked = [r for r in group if r['status'] == 'ranked']
        for a in ranked:
            for b in group:
                conflict = b['status'] == 'ranked' and b['rank'] != a['rank']
                conflict |= b['status'] == 'not_found' and a['rank'] <= b['count']
                if conflict:
                    a['divergent'] = b['divergent'] = True
                    a['divergence_note'] = b['divergence_note'] = 'Posições diferentes em consultas próximas; atualização da fonte sem hora comprovada.'


def expected_slot(now):
    local = now.astimezone(LISBON)
    slots = [local.replace(hour=hour, minute=0, second=0, microsecond=0) for hour in SCHEDULE_HOURS]
    return max([slot for slot in slots if slot <= local] or
               [slots[-1] - dt.timedelta(days=1)]).isoformat()


def allowed_public_record(record):
    """Show Apple observations and the user's historical records, retaining originals."""
    url = record.get('url')
    if url:
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not (parsed.hostname or '').endswith('.apple.com'):
            return False
    source = record.get('source', '')
    name = record.get('source_name', '').casefold()
    return source in {'apple_ids', 'apple_rss'} or name.startswith(('apple', 'arquivo'))


def build_public(root=ROOT):
    config = json.loads((root / 'config.json').read_text())
    historic = json.loads((root / 'archive/historical/history.json').read_text())
    runs = []
    ranked = [r for r in historic if allowed_public_record(r)]
    automatic = []
    latest_run = None
    for path in sorted((root / 'archive/runs').glob('*/*.json')):
        run = compact_run(json.loads(path.read_text()))
        observations = run['observations']
        if run.get('scope') != 'diagnostic':
            automatic.extend(observations)
        runs.append({k: v for k, v in run.items() if k != 'observations'})
        if run.get('scope') != 'diagnostic' and (not latest_run or run['started_at_utc'] > latest_run['started_at_utc']):
            latest_run = run
    for path in sorted((root / 'archive/daily').glob('*/*.json')):
        automatic.extend(json.loads(path.read_text())['observations'])
    best = daily_best(automatic)
    ranked.extend(best)
    if latest_run:
        latest_date = dt.datetime.fromisoformat(latest_run['started_at_utc']).astimezone(LISBON).date().isoformat()
        latest_run = dict(latest_run, observations=[r for r in best if r['date'] == latest_date])
    public = root / 'public'
    dump(public / 'history.json', ranked)
    dump(public / 'runs.json', sorted(runs, key=lambda x: x['started_at_utc'], reverse=True))
    dump(public / 'latest.json', {'schema_version': 3, 'apple_id': APPLE_ID, 'schedule': config['schedule'],
                                'aggregation': 'best_daily_by_country_category',
                                'run': latest_run, 'repository': REPO, 'raw_base': RAW,
                                'built_at_utc': utcnow()})
    dump(public / 'countries.json', config['countries'])
    consultations = json.loads((root / 'archive/historical/consultations.json').read_text())
    dump(public / 'historical-consultations.json', [r for r in consultations if allowed_public_record(r)])
    dump(public / 'peaks.json', json.loads((root / 'archive/historical/peaks.json').read_text()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', help='Lista opcional de mercados para execução manual de diagnóstico')
    parser.add_argument('--build-only', action='store_true')
    args = parser.parse_args()
    if args.build_only:
        build_public()
        return
    config = json.loads((ROOT / 'config.json').read_text())
    countries = {c['code']: c['name'] for c in config['countries']}
    chosen = list(countries) if not args.only else args.only.lower().split(',')
    if any(c not in countries for c in chosen):
        parser.error('Mercado não catalogado')
    # Portugal is deliberately first; each market keeps its own actual timestamp.
    chosen.sort(key=lambda c: (c != 'pt', c))
    start = utcnow()
    run_id = start[:19].replace(':', '').replace('-', '') + '-' + uuid.uuid4().hex[:6]
    trigger = os.environ.get('MONITOR_TRIGGER', 'manual_local')
    run = {'id': run_id, 'started_at_utc': start, 'trigger': trigger,
           'scheduled_for_lisbon': expected_slot(dt.datetime.fromisoformat(start)) if trigger == 'schedule' else None,
           'workflow_url': os.environ.get('MONITOR_RUN_URL'), 'coverage_expected': len(chosen) * 3,
           'coverage_market_count': len(chosen), 'observations': [], 'status': 'running',
           'retention_policy': 'daily_best_positions_v1', 'scope': 'diagnostic' if args.only else 'global'}
    run_path = ROOT / 'archive/runs' / start[:4] / (run_id + '.json')
    jobs = [(c, g, 'apple_ids') for c in chosen for g in CATEGORIES]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch_observation, c, g, s, run_id, countries) for c, g, s in jobs]
        for future in concurrent.futures.as_completed(futures):
            run['observations'].append(future.result())
            if len(run['observations']) % 30 == 0:
                save_run(run_path, run)
                print(f"Mercados: {len(run['observations'])}/{len(jobs)} respostas", flush=True)
    fallback = fallback_jobs(run['observations'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch_observation, c, g, 'apple_rss', run_id, countries)
                   for c, g in fallback]
        for future in concurrent.futures.as_completed(futures):
            record = future.result()
            record['fallback'] = True
            run['observations'].append(record)
    mark_divergences(run['observations'])
    run['finished_at_utc'] = utcnow()
    run['errors'] = sum(r['status'] == 'error' for r in run['observations'])
    run['empty_lists'] = sum(r['status'] == 'empty' for r in run['observations'])
    run['status'] = 'partial' if run['errors'] or run['empty_lists'] else 'completed'
    run['ranked_observations'] = sum(r['status'] == 'ranked' for r in run['observations'])
    run['observations'].sort(key=lambda r: (r['country'], r['category'], r['source']))
    save_run(run_path, run)
    build_public()
    print(json.dumps({k: v for k, v in run.items() if k != 'observations'}, ensure_ascii=False))


if __name__ == '__main__':
    main()

