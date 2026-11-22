"""Assemble answers.json from the 25-question run and the brief, and check it like the grader.

    python make_answers.py                      # uses assigned_25_run.json and brief_TS3012.json
    python make_answers.py --run other_run.json

Checks every citation the way Catalist describes: the quote must be at least six words
and appear inside one speaker turn of the cited meeting (case and spacing ignored).
It also flags answers that cite fewer than two meetings or more than three quotes,
and questions that have no answer yet. Nothing is sent to Gemini.
"""
import argparse
import json
import re
import sqlite3
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent


def squash(text):
    return ' '.join(text.lower().split())


def question_ids():
    path = ROOT / 'questions.json'
    raw = path.read_bytes() if path.is_file() else ZipFile(ROOT / 'Catalist_AI_Intern_Build_Test_Data.zip').read('questions.json')
    return [q['question_id'] for q in json.loads(raw)['questions']]


def check_citation(db, citation):
    meeting, quote = citation.get('meeting_id', ''), citation.get('quote', '')
    if len(quote.split()) < 6:
        return 'quote has fewer than six words'
    turns = [t for (t,) in db.execute('SELECT original FROM turns WHERE meeting=?', (meeting,))]
    if not turns:
        return f'unknown meeting {meeting!r}'
    if not any(squash(quote) in squash(t) for t in turns):
        return 'quote not found inside one speaker turn'
    return None


def answer_issues(db, a):
    cites = a['citations']
    issues = []
    if not 1 <= len(cites) <= 3:
        issues.append(f'{len(cites)} citations (need 1 to 3)')
    if len({c['meeting_id'] for c in cites}) < 2:
        issues.append('cites only one meeting; the task says every answer needs two')
    for n, c in enumerate(cites, 1):
        issue = check_citation(db, c)
        if issue:
            issues.append(f'citation {n}: {issue}')
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', nargs='+', default=['assigned_25_run.json'],
                        help='one or more run files; per question, the first answer passing every check wins')
    parser.add_argument('--brief', default='brief_TS3012.json')
    args = parser.parse_args()
    runs = [(name, json.loads((ROOT / name).read_text(encoding='utf-8'))) for name in args.run]
    brief_path = ROOT / args.brief
    brief = json.loads(brief_path.read_text(encoding='utf-8')) if brief_path.exists() else None

    problems = []
    with sqlite3.connect((ROOT / 'meeting_memory.sqlite').as_uri() + '?mode=ro', uri=True) as db:
        answers, source = {}, {}
        for qid in question_ids():
            candidates = [(name, a) for name, run in runs for a in run['answers'] if a['question_id'] == qid]
            if not candidates:
                reasons = [run.get('unanswered', {}).get(qid) for _, run in runs]
                problems.append(f"{qid}: no answer ({next((r for r in reasons if r), 'not run yet')})")
                continue
            scored = [(answer_issues(db, a), name, a) for name, a in candidates]
            issues, name, a = next((c for c in scored if not c[0]), scored[0])
            answers[qid], source[qid] = a, name
            problems.extend(f'{qid}: {i}' for i in issues)
        if brief and brief.get('short_text'):
            for line in brief['short_text'].splitlines():
                m = re.match(r'\s+\[(\w+), Speaker [A-D], [\d:]+\] "(.*)"$', line)
                if m:
                    issue = check_citation(db, dict(meeting_id=m[1], quote=m[2]))
                    if issue:
                        problems.append(f'short brief: {issue}')
        if brief:
            for section, points in brief['sections'].items():
                for p in points:
                    for c in p['citations']:
                        issue = check_citation(db, c)
                        if issue:
                            problems.append(f'brief {section}: {issue}')
        else:
            problems.append(f'brief: {args.brief} not found (run python brief.py TS3012)')

    out = dict(answers=[dict(question_id=q, answer=answers[q]['answer'], citations=[
                    dict(meeting_id=c['meeting_id'], quote=c['quote']) for c in answers[q]['citations']])
                        for q in question_ids() if q in answers],
               brief=(brief.get('short_text') or brief['text']) if brief else '')
    (ROOT / 'answers.json').write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    if len(runs) > 1:
        print('Answer sources:', ', '.join(f'{q}<-{source[q]}' for q in sorted(source)))
    print(f"Wrote answers.json: {len(out['answers'])}/25 answers, brief {'included' if brief else 'MISSING'}.")
    print('All checks passed.' if not problems else f'{len(problems)} issue(s):')
    for p in problems:
        print('  -', p)


if __name__ == '__main__':
    main()
