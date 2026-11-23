"""Create a demo database filled with FICTIONAL data only (D21).

Usage:  python scripts/seed_demo.py [DB_PATH] [--force]
DB_PATH defaults to $DATABASE_PATH, then instance/app.db. Existing files are never overwritten without --force.

What it creates (through the app's own repositories and services, no raw SQL):
  - 3 closed past sessions with invented nicknames; the head count D is invented too (no photo is used);
    the third one is an "anomaly" on purpose, to show the D7 alert in the spreadsheet;
  - 1 closed poll with votes from random device tokens;
  - a few anonymous comments;
  - a peer list with obviously fake placeholder URLs (they do not exist: replace them before a real review).
It uses no file from docs/supplementary/ and needs no network and no API key.
"""
from __future__ import annotations

import argparse
import os
import random
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters.repo_fetcher import GitHubRepoFetcher  # noqa: E402  (only used to validate URLs, no network)
from app.db import Database  # noqa: E402
from app.repositories.checkins import CheckInRepository  # noqa: E402
from app.repositories.comments import CommentRepository  # noqa: E402
from app.repositories.polls import PollRepository  # noqa: E402
from app.repositories.sessions import SessionRepository  # noqa: E402
from app.repositories.settings import SettingsRepository  # noqa: E402
from app.services.comments import CommentService  # noqa: E402
from app.services.homework import HomeworkReviewer  # noqa: E402
from app.services.polls import PollService  # noqa: E402

DAY = 24 * 3600
NICKNAMES = [
    "Comet", "PixelFox", "Nimbus", "Quokka", "BlueHeron", "Zephyr", "Maple", "Orbit", "Tango", "Lynx",
    "Pebble", "Saturn", "Cactus", "Mosaic", "Falcon", "Echo", "Juniper", "Kiwi", "Delta", "Ember",
    "Willow", "Ripple", "Atlas", "Marble",
]
# (days ago, number of nicknames checking in, invented head count D)
SESSIONS = [(14, 18, 17), (7, 15, 16), (2, 20, 9)]  # last one: D far below N -> "anomaly"
COMMENTS = [
    "Could we see one more worked example of the class diagram?",
    "The projector text is a bit small from the back row.",
    "Suggestion: a 5-minute break in the middle of the lecture.",
    "Please share the slides before class.",
    "The sequence diagram part was very clear, thanks.",
]
POLL = ("Which topic should we revisit next week?", ["Class diagrams", "Sequence diagrams", "Test strategy"],
        [9, 5, 3])  # question, options, votes per option
PEER_URLS = [  # obviously fake placeholders
    "https://github.com/example-student-a/placeholder-homework",
    "https://github.com/example-student-b/placeholder-homework",
    "https://github.com/example-student-c/placeholder-homework",
]


class FixedClock:
    """Seeding writes in the past, so it needs a clock it can set."""

    def __init__(self, now: float) -> None:
        self.t = now

    def now(self) -> float:
        return self.t


def seed(db_path: str, now: float | None = None, seed_value: int = 2026) -> dict:
    """Fill a fresh database; return the counts created. `seed_value` makes the output reproducible."""
    import time

    rng = random.Random(seed_value)
    now = time.time() if now is None else now
    db = Database(db_path)
    db.init_schema()
    sessions, check_ins = SessionRepository(db), CheckInRepository(db)

    for days_ago, n, d in SESSIONS:
        opened = int(now) // DAY * DAY - days_ago * DAY + 10 * 3600  # 10:00 UTC, so dates look like lectures
        session = sessions.create(opened)
        for nickname in rng.sample(NICKNAMES, n):
            token = secrets.token_urlsafe(16)  # random device token, linked to no one
            at = opened + rng.uniform(60, 600)
            check_ins.save_nickname(token, nickname, at)
            check_ins.add(session.id, token, nickname, at)
        sessions.set_head_count(session.id, d, opened + 700)
        sessions.close(session.id, opened + 900)

    clock = FixedClock(now - 2 * DAY + 1000)
    polls = PollService(PollRepository(db), clock)
    question, options, votes = POLL
    poll = polls.create(question, options)
    for option, count in zip(poll.options, votes):
        for _ in range(count):
            polls.vote(poll.id, option.id, secrets.token_urlsafe(16))
    clock.t += 300
    polls.close(poll.id)

    comments = CommentService(CommentRepository(db), clock)
    for text in COMMENTS:
        clock.t += rng.uniform(30, 300)
        comments.post(text)

    reviewer = HomeworkReviewer(GitHubRepoFetcher(), llm=None, settings=SettingsRepository(db))  # llm unused here
    reviewer.set_peer_repos(PEER_URLS)
    return {"sessions": len(SESSIONS), "check_ins": sum(n for _, n, _ in SESSIONS), "poll_votes": sum(votes),
            "comments": len(COMMENTS), "peer_urls": len(PEER_URLS)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("db_path", nargs="?", default=os.environ.get("DATABASE_PATH") or "instance/app.db")
    parser.add_argument("--force", action="store_true", help="delete an existing database file first")
    args = parser.parse_args()
    path = Path(args.db_path)
    if path.exists():
        if not args.force:
            sys.exit(f"{path} already exists. Use --force to replace it (all its data is lost).")
        for suffix in ("", "-wal", "-shm"):
            Path(str(path) + suffix).unlink(missing_ok=True)
    counts = seed(str(path))
    print(f"Demo database written to {path}: " + ", ".join(f"{v} {k}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
