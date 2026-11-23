"""QR drawing for the projector page (FR-1.5)."""
from __future__ import annotations

import base64
import io

import qrcode


def qr_png_data_uri(text: str) -> str:
    """Draw `text` as a QR and return it as a `data:image/png;base64,...` URI.

    Error correction M and a 4-module quiet zone are the settings tested in the tools report (2.3);
    a data URI lets the projector JSON carry the image, so no image file or route is needed.
    """
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4)
    qr.add_data(text)
    qr.make(fit=True)
    buffer = io.BytesIO()
    qr.make_image().save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
