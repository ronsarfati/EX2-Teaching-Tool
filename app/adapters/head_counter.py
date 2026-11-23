"""Face counting on a class photo (FR-1.15, D7): the `HeadCounter` port and its OpenCV YuNet adapter."""
from __future__ import annotations

import io
import os
import threading
from typing import Optional, Protocol

import cv2
import numpy as np
from PIL import Image

from app.errors import DetectorUnavailableError, UnreadablePhotoError

MAX_PIXELS = 40_000_000  # a 12 MP phone photo is far below; a forged 16000x16000 PNG would need ~2 GB to decode
MAX_SIDE = 2000  # long side after resize: keeps one detection well under 1 s (NFR-3)


class HeadCounter(Protocol):
    def count_faces(self, image: bytes) -> int:
        """Number of faces on an encoded image; the bytes are only used in memory (FR-1.17)."""


class YuNetHeadCounter:
    """YuNet on the whole image (approach of tools_tests/head_count.py)."""

    def __init__(self, model_path: str, score_threshold: float = 0.4) -> None:
        self._model_path = model_path
        self._score_threshold = score_threshold
        self._detector: Optional[cv2.FaceDetectorYN] = None
        self._lock = threading.Lock()  # OpenCV detector objects are not thread-safe

    def count_faces(self, image: bytes) -> int:
        decoded = self._decode(image)
        with self._lock:
            detector = self._load_detector()
            height, width = decoded.shape[:2]
            detector.setInputSize((width, height))
            _, faces = detector.detect(decoded)
        return 0 if faces is None else len(faces)

    @staticmethod
    def _decode(image: bytes) -> np.ndarray:
        """Decode in memory (no temp file) and shrink so the long side is at most MAX_SIDE."""
        YuNetHeadCounter._check_dimensions(image)
        try:
            decoded = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
        except cv2.error as exc:
            raise UnreadablePhotoError() from exc
        if decoded is None:
            raise UnreadablePhotoError()
        scale = min(1.0, MAX_SIDE / max(decoded.shape[:2]))
        if scale < 1.0:
            decoded = cv2.resize(decoded, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        return decoded

    @staticmethod
    def _check_dimensions(image: bytes) -> None:
        """Refuse a huge image from its header alone, before any pixel is decoded (decompression bomb)."""
        try:
            with Image.open(io.BytesIO(image)) as header:  # lazy: reads the header, not the pixels
                width, height = header.size
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise UnreadablePhotoError() from exc
        if width * height > MAX_PIXELS:
            raise UnreadablePhotoError()

    def _load_detector(self) -> cv2.FaceDetectorYN:
        """Create the detector once (model load is the slow part); the caller holds the lock."""
        if self._detector is None:
            if not os.path.isfile(self._model_path):
                raise DetectorUnavailableError()
            try:
                self._detector = cv2.FaceDetectorYN.create(
                    self._model_path, "", (320, 320), self._score_threshold, 0.3, 5000
                )
            except cv2.error as exc:  # corrupt or wrong model file
                raise DetectorUnavailableError() from exc
        return self._detector
