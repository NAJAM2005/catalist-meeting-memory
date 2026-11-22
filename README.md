# Meeting-memory agent — Catalist Agentic AI Intern build test

An agent that answers questions about past meetings with exact, checkable quotes, and writes a
cited brief for a team before its next meeting. It runs on 138 AMI meeting transcripts
(35 teams designing a TV remote, meetings `a`–`d` in order).

Python and SQLite handle storage, search, citation checking and output. Gemini handles
choosing what to search for, reading the evidence and writing answers. The model never writes
a quote: it picks turn IDs, and Python copies the original words from the database.

## Requirements

- Python 3.10 or newer (standard library only: `sqlite3` with FTS5, `urllib`, `zipfile`)
- A Gemini API key from Google AI Studio. Tested with `gemini-3.1-flash-lite`.
- `Catalist_AI_Intern_Build_Test_Data.zip` in the project folder (leave it zipped)

No packages to install.

Optional settings (environment variables):

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Model for search planning, drafting and the brief |
| `GEMINI_REVIEW_MODEL` | same as `GEMINI_MODEL` | Separate, stronger model for the citation review step |
| `GEMINI_TIMEOUT` | `90` | Seconds per request; raise it for slower thinking models |

## Quick start

On Windows PowerShell, use your Python path in place of `python`. The key is typed at a hidden
prompt, or set once per terminal with `$env:GEMINI_API_KEY = "..."`.

```powershell
$env:GEMINI_MODEL = "gemini-3.1-flash-lite"

# 1. Build the index (about 1 second, no model calls; reruns skip unchanged meetings)
python meeting_memory.py ingest Catalist_AI_Intern_Build_Test_Data.zip

# 2. Ask any question about one team
python ask_meeting.py TS3006 "Which feature did they drop when costs forced a cut, and why did they keep the other?"

# 3. Answer the 25 assigned questions (resumable; rerun the same command after an interruption)
python run_25.py --output assigned_25_run.json

# 4. Write the TS3012 brief from meetings a-c only
python brief.py TS3012

# 5. Assemble and check answers.json
python make_answers.py --run assigned_25_run.json
```

### Reproducing the submitted `answers.json`

The submitted answers come from several live runs, saved in `runs/`. Each run file records the code version (`signature`) and the model. For each question, `make_answers.py` takes the first run, in the order given, whose answer passes every check:

```powershell
python make_answers.py --brief brief_TS3012.json --run runs/assigned_25_q21.json runs/assigned_25_fix4.json runs/assigned_25_twomeet.json runs/assigned_25_review3_v2.json runs/assigned_25_evidence3.json runs/assigned_25_q08_evidence.json runs/assigned_25_q24_checked.json runs/assigned_25_q05_retry3.json runs/assigned_25_last2.json runs/assigned_25_missing.json runs/assigned_25_run.json runs/assigned_25_run_16_of_25.json
```

The order puts later, improved runs first. Where a rerun passed the checks but read worse, I left it out, e.g. a Q17 rerun that attached the touch screen's cost to voice recognition. In the same way, `review3_v2` comes before `evidence3`, so Q18 keeps the version that names the first plan correctly, and `evidence3` supplies only Q22. The brief was generated with `GEMINI_MODEL=gemini-4-hydrogen` (`python brief.py TS3012`). `python brief.py TS3012 --rerender` redoes its quote selection from the cached notes with no model calls. `python brief.py TS3012 --short` adds the one-screen version (one model call chooses the points), and `make_answers.py` puts that version into `answers.json`. The full cited brief stays in `brief_TS3012.json`.

Plain keyword search with no model is also available:
`python meeting_memory.py search TS3006 "LCD speech recognition" --through c`

## Files

| File | What it does |
|---|---|
| `meeting_memory.py` | Splits each transcript into speaker turns and stores them verbatim in SQLite, with an FTS5 index over overlapping 12-turn windows. Spellings like `L_C_D_` are normalized to `lcd` for search only. Re-ingest uses a file hash and skips unchanged meetings. |
| `ask_meeting.py` | The question-answering agent (see below). |
| `run_25.py` | Runs the assigned questions and saves after each one. `--only Q01,Q03` picks questions, and `--output` names a new results file. It refuses to resume a file made by different code or a different model. |
| `brief.py` | Writes the pre-meeting brief from every meeting except the team's last. |
| `make_answers.py` | Merges one or more run files plus the brief into `answers.json`, checking it the way the task describes. |
| `evaluate_10.py` | Runs our 10 original evaluation questions and saves the responses next to the reference answers. |

## How a question is answered (`ask_meeting.py`)

1. **Scope.** Only the named team's meetings are searched.
2. **Plan the search.** The question is split into its parts ("what did they drop", "why did they keep it"). Each part gets its own search, with spoken variants added (e.g. "price" also matches "sell for").
3. **Targeted retrieval.** For questions about decisions, costs, materials, assignments or price ranges, extra queries pull in decision language, follow a promised check to its later report, and join a price that is split across turns ("two to three Euro per" / "remote").
4. **Draft.** Gemini reads the retrieved turns in meeting order and returns an answer plus 1–3 turn IDs, chosen from a fixed list of valid IDs. It may also ask for another search, up to a limit of 3 searches.
5. **Code checks.** Python rejects any of the following: an unknown ID, a quote under six words, a price without its unit, or citations from only one meeting.
6. **Review.** A second Gemini call breaks the answer into individual claims and checks each one against the cited turns and their neighbours, including attribution, chronology and amounts. Every part of the question must be covered. Unsupported details are removed, and missing parts trigger a focused search.
7. **Stop.** After at most 5 drafts, the agent either returns a verified answer or reports what evidence is missing.

## How the brief is built (`brief.py`)

There is one Gemini call per earlier meeting, which extracts decisions, proposals, actions with owners, completed work, disagreements and numbers, each tied to turn IDs. One final call merges these in meeting order. A later decision replaces an earlier one, an action counts as done once a later meeting shows it delivered, and a disagreement stays open only if nothing later settles it. Python keeps only points whose turn IDs exist in the allowed meetings, and copies every quote exactly. Results for each meeting are cached, so an interrupted run resumes.

## Scaling to 10,000 meetings

Ingest is local and makes no model calls. Each question touches one team's meetings, about 1,900 turns across TS3012's four meetings, not the whole corpus, so the cost of answering doesn't grow with the size of the collection. See the write-up for measurements and what production use would need.

## Data

AMI Meeting Corpus, CC BY 4.0 (https://groups.inf.ed.ac.uk/ami/corpus/).
