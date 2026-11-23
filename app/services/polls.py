"""F3 polls: one open poll at a time, one anonymous vote per device (FR-3.1-FR-3.4, D9, D28)."""
from __future__ import annotations

import sqlite3
from typing import Optional

from werkzeug.exceptions import NotFound

from app.clock import Clock
from app.errors import (AlreadyVotedError, InvalidPollError, PollAlreadyOpenError, PollClosedError)
from app.repositories.polls import Poll, PollRepository


class PollService:
    MIN_OPTIONS = 2
    MAX_OPTIONS = 4

    def __init__(self, polls: PollRepository, clock: Clock) -> None:
        self._polls = polls
        self._clock = clock

    def create(self, question: str, options: list[str]) -> Poll:
        question = question.strip()
        labels = [option.strip() for option in options if option.strip()]  # blank option fields are just unused
        if not question or not self.MIN_OPTIONS <= len(labels) <= self.MAX_OPTIONS:
            raise InvalidPollError()
        if self._polls.find_open() is not None:
            raise PollAlreadyOpenError()
        try:
            return self._polls.create(question, labels, self._clock.now())
        except sqlite3.IntegrityError as error:  # lost a race with another create: the unique index caught it
            raise PollAlreadyOpenError() from error

    def current(self) -> Optional[Poll]:
        return self._polls.find_open()

    def latest(self) -> Optional[Poll]:
        """The open poll, else the last closed one, so its results stay visible (FR-3.4)."""
        return self._polls.latest()

    def get(self, poll_id: int) -> Poll:
        poll = self._polls.get(poll_id)
        if poll is None:
            raise NotFound("This poll does not exist.")  # forged or stale id: plain 404, no new SRS message
        return poll

    def vote(self, poll_id: int, option_id: int, device_token: str) -> None:
        poll = self.get(poll_id)
        if not poll.is_open:
            raise PollClosedError()
        if option_id not in {option.id for option in poll.options}:
            raise InvalidPollError()  # an option of another poll, or a forged form
        if self._polls.has_voted(poll_id, device_token):
            raise AlreadyVotedError()
        try:
            self._polls.add_vote(poll_id, option_id, device_token, self._clock.now())
        except sqlite3.IntegrityError as error:  # two taps at once: the primary key keeps a single vote
            raise AlreadyVotedError() from error

    def close(self, poll_id: int) -> Poll:
        poll = self.get(poll_id)
        if poll.is_open:
            self._polls.close(poll_id, self._clock.now())
        return self.get(poll_id)
