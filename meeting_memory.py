"""Search Catalist's AMI transcripts locally (Python 3.10+, SQLite FTS5).

Run beside Catalist_AI_Intern_Build_Test_Data.zip:
    python meeting_memory.py ingest Catalist_AI_Intern_Build_Test_Data.zip
    python meeting_memory.py search TS3006 "LCD speech recognition"
    python meeting_memory.py search TS3012 "cost" --through c

Search displays evidence windows per meeting. Original speech is kept verbatim.
"""

import argparse
import hashlib
import re
import sqlite3
from pathlib import PurePosixPath
from zipfile import ZipFile

HEADER = re.compile(r"^(\d\d:\d\d:\d\d) Speaker ([A-D])\s*$", re.MULTILINE)


def normalize(text):
    return re.sub(r"\b(?:[A-Za-z]_){2,}", lambda m: m[0].replace("_", ""), text).lower()


def ingest(db, archive):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS meetings(id TEXT PRIMARY KEY, team TEXT, digest TEXT);
        CREATE INDEX IF NOT EXISTS team_index ON meetings(team, id);
        CREATE TABLE IF NOT EXISTS turns(meeting TEXT, seq INTEGER, stamp TEXT,
            speaker TEXT, original TEXT, PRIMARY KEY(meeting, seq));
        CREATE VIRTUAL TABLE IF NOT EXISTS passages USING fts5(scope, words, start UNINDEXED);
    """)
    changed = 0
    with ZipFile(archive) as files, db:
        for name in sorted(files.namelist()):
            if not re.fullmatch(r"transcripts/\w+[a-d]\.txt", name):
                continue
            meeting = PurePosixPath(name).stem
            raw = files.read(name)
            digest = hashlib.sha256(raw).hexdigest()
            if db.execute("SELECT digest FROM meetings WHERE id=?", (meeting,)).fetchone() == (digest,):
                continue
            source = raw.decode("utf-8-sig").replace("\r\n", "\n")
            headers = list(HEADER.finditer(source))
            if not headers:
                raise ValueError(f"No speaker turns in {meeting}")
            rows = []
            for i, match in enumerate(headers):
                end = headers[i+1].start() if i+1 < len(headers) else len(source)
                rows.append((meeting, i, *match.groups(), source[match.end():end].strip()))
            db.execute("DELETE FROM turns WHERE meeting=?", (meeting,))
            db.execute("DELETE FROM passages WHERE scope MATCH ?", (meeting,))
            db.executemany("INSERT INTO turns VALUES(?,?,?,?,?)", rows)
            for start in range(0, len(rows), 6):
                words = " ".join(row[-1] for row in rows[start:start+12])
                db.execute("INSERT INTO passages VALUES(?,?,?)", (meeting, normalize(words), start))
            db.execute("INSERT OR REPLACE INTO meetings VALUES(?,?,?)", (meeting, meeting[:-1], digest))
            changed += 1
    print(f"{changed} meetings indexed or updated.")
    print("Total meetings and turns:", *(db.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                                          for t in ("meetings", "turns")))


def search(db, team, query, through):
    terms = re.findall(r"[a-z0-9]+", normalize(query))
    if not terms:
        raise ValueError("Enter at least one search word.")
    for meeting, in db.execute("SELECT id FROM meetings WHERE team=? AND id<=? ORDER BY id",
                               (team, team + through)):
        expression = f'scope:"{meeting}" AND words:(' + " OR ".join(terms) + ")"
        hits = db.execute("SELECT start FROM passages WHERE passages MATCH ? ORDER BY rank LIMIT 3",
                          (expression,))
        sequences = sorted({i for start, in hits for i in range(start, start+12)})
        if sequences:
            print(f"\n{meeting}")
        for seq in sequences:
            row = db.execute("SELECT stamp,speaker,original FROM turns WHERE meeting=? AND seq=?",
                             (meeting, seq)).fetchone()
            if row:
                print(*row, sep=" | ")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ingest").add_argument("zip")
    lookup = commands.add_parser("search")
    lookup.add_argument("team")
    lookup.add_argument("keywords")
    lookup.add_argument("--through", choices=list("abcd"), default="d")
    args = parser.parse_args()
    with sqlite3.connect("meeting_memory.sqlite") as connection:
        if args.command == "ingest":
            ingest(connection, args.zip)
        else:
            search(connection, args.team.upper(), args.keywords, args.through)
