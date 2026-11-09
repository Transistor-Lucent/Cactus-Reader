"""Image probing and decoding helpers shared by the parsers and the view."""

from __future__ import annotations

import io
import struct
from typing import Optional

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize
from PySide6.QtGui import QImage, QImageReader


def image_dimensions(data: bytes) -> tuple[int, int] | None:
    """Read pixel dimensions from the image header without decoding it.

    Supports the formats comics actually use: JPEG, PNG, GIF, BMP, WebP and
    TIFF.  Returns ``None`` for anything else (the caller can ask Qt instead).
    """
    if not data:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return _positive(struct.unpack_from(">II", data, 16))
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return _positive(struct.unpack_from("<HH", data, 6))
    if data[:2] == b"\xff\xd8":
        return _jpeg_dimensions(data)
    if data[:2] == b"BM" and len(data) >= 26:
        width = struct.unpack_from("<i", data, 18)[0]
        height = abs(struct.unpack_from("<i", data, 22)[0])
        return _positive((width, height))
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return _webp_dimensions(data)
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return _tiff_dimensions(data)
    return None


def _positive(size: tuple[int, int]) -> tuple[int, int] | None:
    width, height = int(size[0]), int(size[1])
    return (width, height) if width > 0 and height > 0 else None


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    pos = 2
    length = len(data)
    while pos + 9 <= length:
        if data[pos] != 0xFF:
            pos += 1
            continue
        while pos < length and data[pos] == 0xFF:
            pos += 1
        if pos >= length:
            break
        marker = data[pos]
        pos += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if marker == 0xDA:  # Start of scan; SOF should have come earlier.
            break
        if pos + 2 > length:
            break
        segment_len = struct.unpack_from(">H", data, pos)[0]
        if segment_len < 2 or pos + segment_len > length:
            break
        if (
            marker in range(0xC0, 0xD0)
            and marker not in (0xC4, 0xC8, 0xCC)
            and segment_len >= 7
        ):
            height, width = struct.unpack_from(">HH", data, pos + 3)
            return _positive((width, height))
        pos += segment_len
    return None


def _webp_dimensions(data: bytes) -> tuple[int, int] | None:
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return _positive((width, height))
    if chunk == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
        width = struct.unpack_from("<H", data, 26)[0] & 0x3FFF
        height = struct.unpack_from("<H", data, 28)[0] & 0x3FFF
        return _positive((width, height))
    if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        bits = int.from_bytes(data[21:25], "little")
        width = 1 + (bits & 0x3FFF)
        height = 1 + ((bits >> 14) & 0x3FFF)
        return _positive((width, height))
    return None


def _tiff_dimensions(data: bytes) -> tuple[int, int] | None:
    try:
        endian = "<" if data[:2] == b"II" else ">"
        if len(data) < 8:
            return None
        offset = struct.unpack_from(endian + "I", data, 4)[0]
        if offset + 2 > len(data):
            return None
        count = struct.unpack_from(endian + "H", data, offset)[0]
        width = height = None
        for index in range(count):
            pos = offset + 2 + index * 12
            if pos + 12 > len(data):
                break
            tag, kind, _count, value = struct.unpack_from(endian + "HHII", data, pos)
            if tag not in (256, 257):
                continue
            if kind == 3:
                number = struct.unpack_from(endian + "H", data, pos + 8)[0]
            else:
                number = value
            if tag == 256:
                width = number
            else:
                height = number
        if width and height:
            return int(width), int(height)
    except (struct.error, IndexError, ValueError):
        pass
    return None


def is_image_data(data: bytes) -> bool:
    if len(data) < 12:
        return False
    return (
        data.startswith(b"\x89PNG\r\n\x1a\n")
        or data.startswith(b"\xff\xd8\xff")
        or data[:6] in (b"GIF87a", b"GIF89a")
        or data[:2] == b"BM"
        or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
    )


def decode_image(data: bytes, target_px: QSize | None = None) -> QImage:
    """Decode image bytes, optionally asking Qt to scale during decoding."""
    if not data:
        raise ValueError("empty image data")
    # QBuffer does not take ownership of the QByteArray; keep a local
    # reference alive for as long as the reader uses the buffer.
    payload = QByteArray(data)
    buffer = QBuffer(payload)
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    reader.setAutoTransform(True)
    if not reader.canRead():
        raise ValueError("unrecognised image data")
    source_size = reader.size()
    if (
        target_px is not None
        and source_size.isValid()
        and target_px.width() > 0
        and target_px.height() > 0
        and (target_px.width() < source_size.width() or target_px.height() < source_size.height())
    ):
        scaled = _fit_size(source_size, target_px)
        if scaled is not None:
            reader.setScaledSize(scaled)
    image = reader.read()
    if image.isNull():
        raise ValueError(reader.errorString() or "cannot decode image")
    return image


def probe_qt_dimensions(data: bytes) -> tuple[int, int] | None:
    """Ask Qt for dimensions for formats not covered by header parsing."""
    payload = QByteArray(data)
    buffer = QBuffer(payload)
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    size = reader.size()
    if size.isValid() and size.width() > 0 and size.height() > 0:
        return size.width(), size.height()
    image = reader.read()
    if not image.isNull():
        return image.width(), image.height()
    return None


def _fit_size(source: QSize, target: QSize) -> QSize:
    if source.width() <= 0 or source.height() <= 0:
        return target
    scale = min(target.width() / source.width(), target.height() / source.height())
    width = max(1, round(source.width() * scale))
    height = max(1, round(source.height() * scale))
    return QSize(width, height)
