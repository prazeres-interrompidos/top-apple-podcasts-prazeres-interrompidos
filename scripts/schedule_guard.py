"""Retry a missed scheduled collection without repeating a completed slot."""
import datetime as dt
import json
import os
from pathlib import Path

from collect import ROOT, LISBON, expected_slot


def decision(root=ROOT, event='schedule', now=None):
    if event not in {'schedule', 'push'}:
        return {'collect': True, 'slot': '', 'reason': 'Recolha manual solicitada.'}
    now = now or dt.datetime.now(dt.timezone.utc)
    slot = expected_slot(now)
    if dt.datetime.fromisoformat(slot).date() != now.astimezone(LISBON).date():
        return {'collect': False, 'slot': '', 'reason': 'Antes das 06h00: ainda não há ronda automática de hoje.'}
    years = {dt.datetime.fromisoformat(slot).year, now.year}
    for year in years:
        for path in sorted((root / 'archive/runs' / str(year)).glob('*.json')):
            try:
                run = json.loads(path.read_text())
                if run.get('trigger') not in {'schedule', 'push'} or run.get('scope') != 'global':
                    continue
                if run.get('scheduled_for_lisbon') != slot or run.get('status') not in {'completed', 'partial'}:
                    continue
                finished = dt.datetime.fromisoformat(run.get('finished_at_utc', '').replace('Z', '+00:00'))
                if finished.tzinfo is None or finished > now:
                    continue
                expected = run.get('coverage_expected')
                counts = run.get('collection_summary', {}).get('apple_ids', {})
                checked = counts.get('checked', 0)
                healthy = checked - counts.get('error', 0) - counts.get('empty', 0)
                if type(expected) is int and expected > 0 and checked >= expected and healthy > 0:
                    return {'collect': False, 'slot': slot, 'reason': 'Esta ronda já terminou; sem novas consultas à Apple.'}
            except (ValueError, TypeError, AttributeError):
                continue
    return {'collect': True, 'slot': slot, 'reason': 'Ronda por concluir; executar a recolha.'}


def main():
    result = decision(event=os.environ.get('MONITOR_TRIGGER', 'manual_local'))
    if output := os.environ.get('GITHUB_OUTPUT'):
        with Path(output).open('a') as stream:
            stream.write(f"collect={str(result['collect']).lower()}\nslot={result['slot']}\n")
    print(result['reason'])


if __name__ == '__main__':
    main()
