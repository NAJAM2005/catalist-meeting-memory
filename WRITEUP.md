# Meeting-memory agent: write-up

**What it does.** It answers questions about one team's past meetings in one to three sentences with exact quotes, and writes a cited brief before a team's final meeting. Data: 138 AMI transcripts, 48,148 speaker turns.

## Architecture
1. **Ingest (code only).** Split each transcript into speaker turns and store them verbatim in SQLite with an FTS5 index over overlapping 12-turn windows. Unchanged files are skipped by hash.
2. **Retrieve (code).** Search only the named team's meetings. Each part of the question gets its own search, with spoken variants ("price" → "sell for"). Extra searches follow decision language, promised checks and prices split across turns.
3. **Read and decide (model).** Gemini reads the turns in meeting order and returns an answer with 1–3 **turn IDs**, or asks for another search (up to 3).
4. **Cite and check (code).** Python copies each quote from the database, so the model never types one. It rejects unknown IDs, quotes under six words, prices without a unit, and citations from a single meeting.
5. **Review (model).** A second call checks each claim against the cited turns and their neighbours: who said it, when, amounts, and whether every part is answered. Gaps trigger a focused search, with at most 5 drafts.
6. **Brief.** One call per earlier meeting, then a merge. Python keeps only turns from meetings a–c, and one more call picks the 10 points for the first screen.

## Model vs code
**Never touches an LLM:** storage, indexing, search, quote insertion, citation checks, the a–c restriction on the brief, and merging and verifying `answers.json`. These have exact answers. Code does them for free, in milliseconds, the same way every time, and a quote copied by code can't be paraphrased or invented.
**Uses the model:** spontaneous speech is full of hedges, interruptions, "you guys" and reversals, so deciding what a turn *means* needs language understanding. That covers choosing search terms, telling a proposal from a decision, and judging whether a quote supports a claim.

## How it knows what is current
Evidence is always shown in meeting and turn order, and the writer is told to answer "in the end" questions from the **last** relevant decision. For "changed its mind" questions, a decision-history step retrieves both sides of every switch, and a later repetition of the same position counts as a confirmation, not a new reversal. In the brief, a later decision replaces an earlier one and is listed under "what changed". An action counts as done once a later meeting shows it delivered. References like "the thing you asked about" are resolved by reading neighbouring turns and following a promise to its later report.

## Results
- **Assigned questions:** 25/25 answered, and all 72 quotes match the transcripts word for word. 22/25 cite two meetings.
- **Own evaluation:** 10 questions, each needing two meetings. Correct / partial / wrong went **4/2/4 → 4/5/1 → 7/2/1 → 8/2/0** across four versions; the last is the submitted code (`EVALUATION.md`). These questions shaped development, so they aren't held out. **A fresh team (ES2005), never used before**, got 2 of 3 parts stated: it cited the charging stand but didn't mention it in the answer.

## Three failures
1. **A confirmation taken for a reversal (Q13):** it named meeting d instead of c. Fixed with decision history.
2. **Attribution lost in a retry (Q18):** a rewrite dropped C's quote and credited D. Fixed by selecting evidence separately for each part.
3. **My two-meeting rule backfired (Q15):** all three facts are only in ES2016d. With three citation slots, the rule swapped the removal quote for an unrelated selling-price turn. Still open. The fix is to require a second meeting only when one supports a requested part.

The logs also exposed a bug: in 20 of 25 questions, the question's opening background sentence was treated as a claim to prove.

## Tools and where they broke
I used plain Python, SQLite FTS5 and the Gemini REST API, with no agent framework. The loop is about 100 lines, and every step can be inspected. I chose keyword search over embeddings because the speech is literal ("twelve and a half Euros"), and it found 20 of 21 reference turns. **Where it broke:**
- The free tier (500 requests a day, plus frequent 503 and 429 errors) made a 25-question run take hours, so runs became resumable checkpoints.
- Flash-Lite as reviewer both rejects correct drafts (Q01, Q03, Q25 still cite one meeting) and lets loose reasons through (Q18).
- Merging three meetings into a brief needed Gemini 4 Hydrogen, which timed out at the default 90 s.
- Some retrieval handlers came from specific failures and may overfit.

## Cost and scale
- **Ingest:** 138 meetings in 0.6–0.7 s, 19 MB, **zero model calls**. 1,000 meetings: about 5 s, about 140 MB, $0.
- **Answering:** about 4–15 calls per question, estimated from request counts (I didn't log tokens). Team scoping keeps the cost flat as teams are added. One team building up years of meetings would need per-meeting summaries at ingest and a time filter.
- **For production at 10,000+ meetings:** a server search engine plus embeddings for paraphrased questions; decisions and actions extracted at ingest; a stronger reviewer; token and latency logging; and this evaluation set re-run on every change.
