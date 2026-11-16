"""Render the current public Agent Disco rankings as a GitHub README."""

import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import re
from urllib.request import urlopen


LEADERBOARD = 'https://agentdisco.dev/best-mcp-servers'
PUBLIC_SNAPSHOT = 'https://agentdisco.dev/data/leaderboard.json'
README = Path(__file__).resolve().parents[1] / 'README.md'
QUALITY_LABELS = {
    'measured': '{score}',
    'partial-estimate': '{score} (partly estimated)',
    'median-estimate': '≈{score} (unranked median)',
    'unavailable': '—',
}


def cell(value):
    return re.sub(r'([\\`*_\[\]<>|])', r'\\\1', ' '.join(value.split()))


def score_text(value):
    if type(value) not in (int, float) or not 0 <= value <= 100:
        raise ValueError('Scores must be numbers between 0 and 100')
    # Match the website's toFixed(1), including exact half-way scores.
    return str(Decimal(value).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))


def render(snapshot):
    rows = snapshot['rows']
    if (snapshot['status']['ok'] is not True
            or len(rows) != 100
            or len({row['id'] for row in rows}) != 100
            or [row['indexRank'] for row in rows] != list(range(1, 101))):
        raise ValueError('Expected a successful snapshot with 100 unique ranked products')
    captured_at = datetime.fromisoformat(snapshot['capturedAt'].replace('Z', '+00:00'))
    if captured_at.tzinfo is None:
        raise ValueError('The snapshot timestamp must include a time zone')
    observed = captured_at.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    lines = [
        '# Best MCP Servers · Top 100 Leaderboard',
        '',
        'Agent Disco ranks MCP servers, AI apps and connectors by how visible they are across AI assistants.',
        f'[Explore the interactive leaderboard]({LEADERBOARD}).',
        '',
        f'**Snapshot:** {observed}',
        '',
        '| Rank | Product | Discoverability /100 | Quality (beta) /100 |',
        '| ---: | --- | ---: | ---: |',
    ]
    for row in rows:
        quality_score = score_text(row['qualityScore']) if row['qualityScore'] is not None else '—'
        quality = QUALITY_LABELS[row['qualityState']].format(score=quality_score)
        lines.append(f"| {row['indexRank']} | {cell(row['name'])} | {score_text(row['indexScore'])} | {quality} |")

    lines.extend([
        '',
        '## How to read the rankings',
        '',
        f'- **Discoverability** determines row order. It reflects public Claude and ChatGPT directory placement, Google search demand, reviewed GitHub stars and verified availability on other assistants. Agent usage and task success require separate measurements. [Methodology]({LEADERBOARD}#methodology)',
        f'- **Quality (beta)** combines readiness and tool-definition evidence. A partial estimate includes one assessed input. An unranked median is an estimate based on no assessed inputs. [Quality methodology]({LEADERBOARD}#methodology-quality)',
        '',
    ])
    return '\n'.join(lines), observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Use a saved copy of the public snapshot')
    args = parser.parse_args()
    if args.source:
        snapshot = json.loads(args.source.read_text(encoding='utf-8'))
    else:
        with urlopen(PUBLIC_SNAPSHOT, timeout=30) as response:
            snapshot = json.load(response)

    rendered, observed = render(snapshot)
    existing = README.read_text(encoding='utf-8') if README.exists() else ''
    previous = re.search(r'^\*\*Snapshot:\*\* (.+)$', existing, re.M)
    if previous and observed < previous.group(1):
        raise ValueError('The public snapshot is older than the current README')
    if existing != rendered:
        README.write_text(rendered, encoding='utf-8')
    print(f'Leaderboard snapshot {observed}')


if __name__ == '__main__':
    main()
