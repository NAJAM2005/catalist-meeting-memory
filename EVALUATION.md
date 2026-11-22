# Evaluation: 10 original questions

`evaluate_10.py` holds 10 questions I wrote across 5 teams. Each one needs facts from two different meetings, and each has a hand-checked reference answer and reference turns. Only the team and the question go to the agent. I graded every response by reading the cited quotes against the transcripts.

**Grades:** ✓ = every requested fact is right and supported by the cited quotes · ◐ = some requested facts right, at least one missing or wrong · ✗ = wrong, or no answer.

Four saved runs, from four versions of `ask_meeting.py`, are in `evaluation/`:
- **v1, baseline** (`evaluation_eb75c3621466.json`)
- **v2, retry rules + 3-search cap** (`evaluation_bc781f5d42e5.json`)
- **v3, per-part search + claim review** (`evaluation_81f54dbc9284.json`)
- **v4, final submitted code** (`evaluation_db1c10d4eb68.json`): adds the two-meeting rule, background sentences as context, decision history and the latest-turn rule. Run after the code was frozen.

| # | Team | What it tests | v1 | v2 | v3 | v4 final |
|---|---|---|---|---|---|---|
| 1 | ES2016 | Trend theme (c) + prototype fruit and colour (d) | ✓ | ✓ | ✓ | ✓ |
| 2 | ES2016 | Kickoff price (a) + cost target restated in (d) | ✗ no answer | ◐ said no cost target | ✓ €25 / €12.50 | ✓ |
| 3 | TS3009 | Profit aim and price (a) + logo (d) | ◐ logo not named | ◐ logo not named | ✓ double R | ✓ |
| 4 | TS3009 | Why titanium (c) + advantage once dropped (d) | ✗ | ✗ | ◐ reason right; advantage cited from before the drop | ✓ cites "you can double curve if you don't have titanium" |
| 5 | TS3006 | New market (b) + fashionable feel (c) | ✓ | ◐ feel taken from d, not the c presentation | ✓ under 40 / spongy | ✓ |
| 6 | TS3006 | Cost fraction (a) + saving from dropping keys (d) | ✗ no answer | ◐ wrong amount and speaker | ✓ half / €4.50 | ✓ |
| 7 | IS1008 | Why titanium ruled out (c) + how colour varies (d) | ◐ | ◐ | ◐ reason right; colour mechanism wrong (wood stain) | ◐ says "stained", but no cited quote shows it; adds a cost reason from a different speaker |
| 8 | IS1008 | Project manager identity (a) + presenters named (d) | ✓ | ✓ | ✗ no verified answer | ✓ Shrida Daseri; Christine and Agnes |
| 9 | TS3012 | Production target (a) + base colour and covers (d) | ✓ | ✓ | ✓ | ✓ |
| 10 | TS3012 | Who preferred the curve (c) + who suggested losing it (d) | ✗ | ✓ | ✓ | ◐ who suggested losing it: right (C); curve preference given to C ("one curve is fine") instead of B |
| | | **Correct / partial / wrong** | **4 / 2 / 4** | **4 / 5 / 1** | **7 / 2 / 1** | **8 / 2 / 0** |
| | | **Transcript searches** (from run logs) | 24 | 11 | 20 | 20 |

**A reference error the evaluation exposed (case 10):** my reference said A suggested losing the curve. The transcript shows C said it first ("I'd say lose the curve and the colour and", TS3012d-119), and A repeated it in the next turn (TS3012d-120). The agent was right and my reference was wrong, so case 10 is graded against the transcript.

**What the runs show**
- v1 → v2: the retry rules cut failures (4 → 1) and halved the searches, but several answers were only partly right.
- v2 → v3: searching each part of the question separately, plus a claim-by-claim review, turned partial answers into correct ones (4 → 7 correct). The searches rose again (11 → 20).
- v3's one failure (case 8) was answered correctly by v1 and v2. The stricter review rejected a correct answer, the same failure mode later seen in assigned Q01, Q03 and Q25.
- Unseen check: one further question on a team outside this set (ES2013) was answered correctly by v3. That came from a single live run and wasn't saved to a file.

- **v3 → v4 (final code):** 8 correct, 2 partial, none wrong. Case 8, which v3's strict review lost, is answered again, and case 4 now cites the turn where the double curve becomes possible. Overall, fully correct answers rose from 7 to 8: cases 4 and 8 improved, while case 10 regressed on speaker attribution. Both partials are evidence-selection problems: the right fact with a quote that doesn't show it (case 7), and a speaker's comment about something else read as a preference (case 10).
- **Caveat:** these questions were written before the later fixes, but I've seen them many times while developing, so they aren't a true held-out test. New questions on unseen teams are the next check.
