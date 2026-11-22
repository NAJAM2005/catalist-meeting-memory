"""Run with the same interpreter as ask_meeting.py. Scores are assigned by the reader."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from urllib.error import URLError
import ask_meeting as agent

ROOT = Path(__file__).resolve().parent
# Only team and question are passed to the agent. References use zero-based turn numbers.
CASES = [
 ('ES2016','Which fashion theme did D report in meeting c, and which fruit and colour did C show in the final prototype?', 'Fruit and vegetables; a yellow banana.', ['ES2016c-6','ES2016d-6']),
 ('ES2016','What selling price did A describe at kickoff, and what per-unit cost did A say they were supposed to meet in the final meeting?', 'About €25 selling price and €12.50 cost.', ['ES2016a-58','ES2016d-189']),
 ('TS3009','What worldwide profit aim and unit selling price did the project manager announce at kickoff, and what logo did C describe on the final prototype?', '€50 million worldwide profit aim, €25 selling price, double R logo.', ['TS3009a-143','TS3009d-34']),
 ('TS3009','Why did C originally favor titanium for the fixed parts, and what advantage for the case shape did C identify once titanium was dropped?', 'Strong appearance; a double curve became possible.', ['TS3009c-320','TS3009d-443']),
 ('TS3006','Which age group did A identify as the new market, and what feel did D say was fashionable for that audience in the subsequent trend presentation?', 'Customers below forty; a spongy feel.', ['TS3006b-111','TS3006c-39']),
 ('TS3006','What fraction of the selling price was production meant to cost, and how much did A say dropping direct number keys could save?', 'Half of selling price; €4.50 by skipping nine buttons.', ['TS3006a-162','TS3006d-39']),
 ('IS1008','Why did manufacturing rule out titanium for the case, and how did C say the chosen material would let customers vary its colour?', 'Manufacturing said titanium could not make the curved case; the wood could be stained different colours.', ['IS1008c-7','IS1008d-19']),
 ('IS1008','Who introduced themselves as project manager at kickoff, and whom did that speaker name for the prototype presentation in the final meeting?', 'Speaker A, Shrida Daseri; Christine and Agnes.', ['IS1008a-1','IS1008d-3']),
 ('TS3012','What production target did A give at kickoff, and what base colour and customization option did A propose to meet it in the final meeting?', 'About €12.50; deliver black with separately purchased covers.', ['TS3012a-104','TS3012d-43']),
 ('TS3012','Who preferred the curved shape in meeting c, and which speaker suggested losing the curve in the final meeting?', 'B preferred the curve; C suggested losing it (A agreed next).', ['TS3012c-465','TS3012d-119'])
]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, choices=range(1,11), default=10,
                        help='maximum number of remaining cases to run this session')
    args = parser.parse_args()
    version = hashlib.sha256(Path(agent.__file__).read_bytes()).hexdigest()[:12]
    out = ROOT / f'evaluation_{version}.json'
    records = json.loads(out.read_text(encoding='utf8')) if out.exists() else []
    done = {r['id'] for r in records}
    pending = [(i,c) for i,c in enumerate(CASES,1) if i not in done][:args.limit]
    if not pending:
        print('All ten runs are saved in', out.name)
        return
    key = os.getenv('GEMINI_API_KEY') or getpass.getpass('Gemini API key (hidden): ').strip()
    model = agent.choose_model(key)
    if records and records[0]['model'] != model:
        raise SystemExit('Resume with the same model: ' + records[0]['model'])
    with sqlite3.connect((ROOT/'meeting_memory.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        for i,(team,question,reference,refs) in pending:
            print(f'\nEvaluation {i}/10: {question}', flush=True)
            try:
                response = agent.ask(db,team,question,key,model)
            except (URLError,TimeoutError) as error:
                raise SystemExit(f'Provider error: {error}. Rerun to resume.') from error
            except ValueError as error:
                response = {'failure':str(error)}
            records.append(dict(id=i,model=model,team=team,question=question,response=response,
                                reference=reference,reference_turns=refs,answer_score=None,citation_score=None))
            temp = out.with_suffix('.tmp')
            temp.write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf8')
            temp.replace(out)
            print(json.dumps(response,ensure_ascii=False),flush=True)
    print('Saved',len(records),'of 10 in',out.name)

if __name__=='__main__':
    main()
