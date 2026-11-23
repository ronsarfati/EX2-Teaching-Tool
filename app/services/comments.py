"""F2 comments: anonymous, with no session check, so they work during and after class (FR-2.1-FR-2.4, D8, D29)."""
from __future__ import annotations

from app.clock import Clock
from app.errors import CommentTooLongError, EmptyCommentError
from app.repositories.comments import Comment, CommentRepository


class CommentService:
    MAX_LEN = 500  # D31 (OI-11)

    def __init__(self, comments: CommentRepository, clock: Clock) -> None:
        self._comments = comments
        self._clock = clock

    def post(self, text: str) -> Comment:
        text = text.strip()
        if not text:
            raise EmptyCommentError()
        if len(text) > self.MAX_LEN:
            raise CommentTooLongError()
        return self._comments.add(text, self._clock.now())

    def recent(self, limit: int = 100) -> list[Comment]:
        return self._comments.list_recent(limit)
