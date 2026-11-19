"""Reject documentary originals and image assets from the public project."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.pdf', '.xlsx', '.xls', '.zip', '.mp4'}
PRIVATE_NAMES = {'evidence.json', 'workbook-extraction.json', 'import-manifest.json', 'import_historical.py'}
ALLOWED_HISTORY = {'id', 'apple_id', 'country', 'country_name', 'category', 'category_name', 'chart_type', 'date', 'rank', 'source', 'source_name', 'url', 'original_status', 'quality', 'status', 'divergent', 'historical_time_text', 'date_precision'}


def check(root=ROOT):
    problems = []
    for path in root.rglob('*'):
        if not path.is_file() or any(p in {'.git', '__pycache__', 'artifacts', 'node_modules'} for p in path.relative_to(root).parts):
            continue
        if path.suffix.lower() in FORBIDDEN or path.name in PRIVATE_NAMES or any(p in {'documents', 'originals', 'media'} for p in path.relative_to(root).parts):
            problems.append(str(path.relative_to(root)))
        if 'responses' in path.relative_to(root).parts:
            problems.append('Não é permitido arquivar respostas completas da Apple: ' + str(path.relative_to(root)))
        if path.suffix == '.json' and path.relative_to(root).parts[0] in {'archive', 'public'}:
            data = json.loads(path.read_text())
            def prohibited_keys(value):
                if isinstance(value, dict):
                    forbidden = {'resultIds', 'feed', 'entry', 'evidence_path', 'sequence_sha256',
                                 'sequence_changed', 'sha256', 'attempts', 'headers', 'raw_body'}
                    return bool(set(value) & forbidden) or any(prohibited_keys(v) for v in value.values())
                return isinstance(value, list) and any(prohibited_keys(v) for v in value)
            if prohibited_keys(data):
                problems.append('Listas ou metadados de respostas completas: ' + str(path.relative_to(root)))
    historical = root / 'archive/historical/history.json'
    if historical.exists():
        for record in json.loads(historical.read_text()):
            if set(record) - ALLOWED_HISTORY:
                problems.append('Campos não autorizados no histórico normalizado')
                break
    return problems


if __name__ == '__main__':
    issues = check()
    if issues:
        raise SystemExit('Conteúdo não permitido no projeto público: ' + ', '.join(issues))
    print('Verificação concluída: apenas registos do podcast; sem listas completas, imagens ou documentos originais.')

