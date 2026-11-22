"""Run the 25 assigned questions against the existing index and save a resumable draft."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from urllib.error import HTTPError, URLError
from zipfile import ZipFile

import ask_meeting as agent

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'assigned_25_run.json'


def load_questions():
    if (ROOT / 'questions.json').is_file():
        raw = (ROOT / 'questions.json').read_bytes()
    else:
        with ZipFile(ROOT / 'Catalist_AI_Intern_Build_Test_Data.zip') as archive:
            raw = archive.read('questions.json')
    questions = json.loads(raw)['questions']
    expected = [f'Q{i:02}' for i in range(1, 26)]
    if [q['question_id'] for q in questions] != expected:
        raise ValueError('Expected the original Catalist questions Q01 through Q25 in order.')
    return questions


def ask_with_cooldown(db, team, question, key, model):
    # The agent already retries individual requests. Back off before restarting a question.
    delays = (120, 300)
    for attempt in range(len(delays) + 1):
        try:
            return agent.ask(db, team, question, key, model)
        except HTTPError as error:
            if error.code != 503 or attempt == len(delays):
                raise
            delay = delays[attempt]
            retry_after = (error.headers or {}).get('Retry-After', '')
            if retry_after.isdigit():
                delay = max(delay, int(retry_after))
            error.close()
            print(f'Gemini is unavailable. Waiting {delay} seconds before retrying this question. '
                  'Press Ctrl+C to stop and resume later.', flush=True)
            time.sleep(delay)


def run(db, questions, model, retry, only=None):
    if only:
        questions = [q for q in questions if q['question_id'] in only]
    signature = hashlib.sha256(Path(agent.__file__).read_bytes() + json.dumps(questions).encode()).hexdigest()
    state = {'model': model, 'review_model': agent.review_model(model), 'signature': signature,
             'answers': [], 'unanswered': {}}
    if OUTPUT.exists():
        state = json.loads(OUTPUT.read_text(encoding='utf-8'))
        if state['signature'] != signature or state['model'] != model:
            raise ValueError('Different agent, questions, or model. Rename the previous result to start a separate run.')
    complete = {r['question_id'] for r in state['answers']}
    pending = [q for q in questions if q['question_id'] not in complete
               and (retry or q['question_id'] not in state['unanswered'])]
    if pending:
        key = os.getenv('GEMINI_API_KEY') or getpass.getpass('Gemini API key (hidden): ').strip()
        if not key:
            raise ValueError('An API key is required for the live run.')
    for q in pending:
        ident = q['question_id']
        print(f"\n{ident}/Q25 | {q['team']} | {q['question']}", flush=True)
        try:
            result = ask_with_cooldown(db, q['team'], q['question'], key, model)
        except ValueError as error:
            result = {'insufficient': str(error)}
        if result.get('answer') and result.get('citations'):
            state['answers'].append({'question_id': ident, 'answer': result['answer'], 'citations': result['citations']})
            state['answers'].sort(key=lambda row: row['question_id'])
            state['unanswered'].pop(ident, None)
            print(result['answer'], flush=True)
        else:
            state['unanswered'][ident] = result.get('insufficient') or 'No cited answer returned.'
            print('Flagged:', state['unanswered'][ident], flush=True)
        temp = OUTPUT.with_suffix('.tmp')
        temp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
        temp.replace(OUTPUT)
    print(f"Saved {len(state['answers'])} cited answers; {len(state['unanswered'])} unanswered. File: {OUTPUT.name}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retry-unanswered', action='store_true')
    parser.add_argument('--output', default='assigned_25_run.json',
                        help='results file; use a new name to keep earlier runs')
    parser.add_argument('--only', default='', help='comma-separated question IDs, e.g. Q01,Q03')
    opts = parser.parse_args()
    OUTPUT = ROOT / opts.output
    only = {q.strip().upper() for q in opts.only.split(',') if q.strip()}
    model = 'models/' + os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite').removeprefix('models/')
    print('Using', model, '| reviewer:', agent.review_model(model), flush=True)
    try:
        with sqlite3.connect((ROOT/'meeting_memory.sqlite').as_uri()+'?mode=ro', uri=True) as connection:
            run(connection, load_questions(), model, opts.retry_unanswered, only)
    except (HTTPError, URLError, TimeoutError) as error:
        raise SystemExit(f'Provider connection stopped: {error}. Rerun the same command to resume.')
    except (OSError, sqlite3.Error, ValueError) as error:
        raise SystemExit(str(error))
