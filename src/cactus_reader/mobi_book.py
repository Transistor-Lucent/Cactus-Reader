"""A small, focused MOBI/KF8-comic extractor.

Comic MOBI files store each page as an image resource record.  This module
reads the Palm database table, decompresses the Mobipocket markup when needed,
and follows that markup's image references so that only actual comic pages are
shown (skipping spacer images, thumbnails and other resources).
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from .book import Book, BookError, DrmProtectedError, EncodedImageSource, NoPagesError, Page
from .image_utils import image_dimensions, is_image_data, probe_qt_dimensions

_IMAGE_PREFIX = 512 * 1024
# KF8 commonly puts raster images in <img> tags but wraps others in inline
# <svg><image xlink:href="kindle:embed:..."/></svg> blocks.  Both tags carry
# page images and must be honoured in document order.
_IMAGE_TAG_RE = re.compile(rb"<(?:img|image)\b[^>]*>", re.IGNORECASE | re.DOTALL)
_RECINDEX_RE = re.compile(rb"""recindex\s*=\s*["']?(\d+)""", re.IGNORECASE)
_EMBED_RE = re.compile(rb"""kindle:embed:([0-9A-Va-v]+)""", re.IGNORECASE)
_FLOW_RE = re.compile(rb"""kindle:flow:([0-9A-Va-v]+)""", re.IGNORECASE)
_SKIP_PREFIXES = (
    b"FLIS",
    b"FCIS",
    b"SRCS",
    b"RESC",
    b"FONT",
    b"CRES",
    b"PAGE",
    b"CMET",
    b"CONT",
    b"kind",
    b"DATP",
    b"FDST",
)


@dataclass
class _Resource:
    record: int
    offset: int
    length: int
    is_image: bool = False
    width: int = 0
    height: int = 0

    @property
    def dimension_key(self) -> tuple[int, int] | None:
        if self.width > 0 and self.height > 0:
            return self.width, self.height
        return None


class _PalmFile:
    def __init__(self, handle: BinaryIO, path: Path) -> None:
        self.handle = handle
        self.path = path
        header = handle.read(78)
        if len(header) < 78:
            raise BookError("这不是有效的 MOBI 文件。")
        if header[60:68] not in (b"BOOKMOBI", b"TEXtREAd"):
            raise BookError("这不是有效的 MOBI 文件。")
        self.record_count = struct.unpack_from(">H", header, 76)[0]
        if self.record_count < 1:
            raise BookError("MOBI 文件没有记录。")
        table = handle.read(8 * self.record_count)
        if len(table) < 8 * self.record_count:
            raise BookError("MOBI 记录表已损坏。")
        self.offsets: list[int] = []
        for index in range(self.record_count):
            offset = struct.unpack_from(">L", table, index * 8)[0]
            self.offsets.append(int(offset))
        self.file_size = self._file_size()
        if any(off < 78 or off > self.file_size for off in self.offsets):
            raise BookError("MOBI 记录偏移已损坏。")
        if self.offsets != sorted(self.offsets):
            raise BookError("MOBI 记录偏移顺序无效。")

    def _file_size(self) -> int:
        current = self.handle.tell()
        self.handle.seek(0, 2)
        size = self.handle.tell()
        self.handle.seek(current)
        return size

    def record_bounds(self, index: int) -> tuple[int, int]:
        if index < 0 or index >= self.record_count:
            raise IndexError(index)
        start = self.offsets[index]
        end = self.offsets[index + 1] if index + 1 < self.record_count else self.file_size
        if end < start:
            raise BookError("MOBI 记录长度无效。")
        return start, end

    def read_record(self, index: int, limit: int | None = None) -> bytes:
        start, end = self.record_bounds(index)
        length = end - start
        if limit is not None:
            length = min(length, limit)
        self.handle.seek(start)
        return self.handle.read(length)

    def read_at(self, offset: int, length: int) -> bytes:
        self.handle.seek(offset)
        return self.handle.read(length)


def _be16(data: bytes, offset: int) -> int:
    if offset + 2 > len(data):
        return 0
    return struct.unpack_from(">H", data, offset)[0]


def _be32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        return 0
    return struct.unpack_from(">L", data, offset)[0]


def _parse_exth(rec0: bytes, header_length: int) -> dict[int, list[bytes]]:
    result: dict[int, list[bytes]] = {}
    flags = _be32(rec0, 0x80)
    if not flags & 0x40:
        return result
    position = 16 + header_length
    if rec0[position:position + 4] != b"EXTH":
        return result
    length = _be32(rec0, position + 4)
    count = _be32(rec0, position + 8)
    if length < 12 or position + length > len(rec0) or count > 10000:
        return result
    cursor = position + 12
    end = position + length
    for _ in range(count):
        if cursor + 8 > end:
            break
        kind = _be32(rec0, cursor)
        size = _be32(rec0, cursor + 4)
        if size < 8 or cursor + size > end:
            break
        result.setdefault(kind, []).append(rec0[cursor + 8:cursor + size])
        cursor += size
    return result


def _exth_text(exth: dict[int, list[bytes]], kind: int, encoding: str) -> str | None:
    values = exth.get(kind)
    if not values:
        return None
    try:
        return values[0].decode(encoding, errors="replace").strip()
    except Exception:
        return None


def _exth_int(exth: dict[int, list[bytes]], kind: int) -> int | None:
    values = exth.get(kind)
    if not values:
        return None
    raw = values[0]
    if len(raw) == 4:
        return struct.unpack(">L", raw)[0]
    if len(raw) == 2:
        return struct.unpack(">H", raw)[0]
    if len(raw) == 1:
        return raw[0]
    try:
        return int(raw.decode("ascii", errors="ignore"))
    except ValueError:
        return None


def _palmdoc_decompress(data: bytes) -> bytes:
    out = bytearray()
    cursor = 0
    length = len(data)
    while cursor < length:
        value = data[cursor]
        cursor += 1
        if value == 0:
            out.append(0)
        elif value <= 8:
            take = min(value, length - cursor)
            out.extend(data[cursor:cursor + take])
            cursor += take
        elif value <= 0x7F:
            out.append(value)
        elif value <= 0xBF:
            if cursor >= length:
                break
            value2 = data[cursor]
            cursor += 1
            distance = (((value << 8) | value2) >> 3) & 0x7FF
            count = (value2 & 0x07) + 3
            if distance <= 0:
                continue
            if distance <= len(out):
                for _ in range(count):
                    out.append(out[-distance])
            else:
                # Corrupt back-reference.  Stop rather than producing garbage.
                break
        else:
            out.extend((0x20, value ^ 0x80))
    return bytes(out)


def _trim_trailing_entry(data: bytes, flags: int) -> bytes:
    if not data:
        return data
    multibyte = flags & 1
    trailer_count = 0
    shifted = flags >> 1
    while shifted > 1:
        if shifted & 2:
            trailer_count += 1
        shifted >>= 1

    def tail_size(chunk: bytes) -> int:
        number = 0
        for byte in chunk[-4:]:
            if byte & 0x80:
                number = 0
            number = (number << 7) | (byte & 0x7F)
        return number

    for _ in range(trailer_count):
        remove = tail_size(data)
        if remove <= 0 or remove > len(data):
            break
        data = data[:-remove]
    if multibyte and data:
        remove = (data[-1] & 3) + 1
        if remove <= len(data):
            data = data[:-remove]
    return data


def _mobi_text(rec0: bytes, palm: _PalmFile, compression: int, text_records: int,
               header_length: int, min_version: int) -> bytes:
    if compression not in (1, 2) or text_records <= 0:
        return b""
    flags = 0
    if header_length >= 0xE4 and min_version >= 5:
        flags = _be16(rec0, 0xF2)
    chunks: list[bytes] = []
    for record_index in range(1, min(text_records + 1, palm.record_count)):
        raw = palm.read_record(record_index)
        if compression == 2:
            raw = _trim_trailing_entry(raw, flags)
            raw = _palmdoc_decompress(raw)
        chunks.append(raw)
    return b"".join(chunks)


def _from_base32(value: bytes) -> int:
    number = 0
    for byte in value:
        if 48 <= byte <= 57:
            digit = byte - 48
        elif 65 <= byte <= 86:
            digit = byte - 65 + 10
        elif 97 <= byte <= 118:
            digit = byte - 97 + 10
        else:
            continue
        number = number * 32 + digit
    return number


def _parse_flows(rec0: bytes, palm: _PalmFile, header_length: int,
                 markup: bytes) -> dict[int, bytes]:
    """Split the KF8 raw markup into its FDST flow documents.

    KF8 stores CSS and inline SVG documents after the XHTML text and refers to
    them as ``kindle:flow:XXXX``.  The FDST record maps each flow number to a
    byte range in the raw markup, which lets us follow the reference from a
    page's <img> tag to the actual SVG/raster image.
    """
    if header_length < 0xC8:
        return {}
    fdst_record = _be32(rec0, 0xC0)
    fdst_count = _be32(rec0, 0xC4)
    if (fdst_count <= 1 or fdst_record in (0, 0xFFFFFFFF)
            or fdst_record >= palm.record_count):
        return {}
    data = palm.read_record(fdst_record)
    if data[:4] != b"FDST":
        return {}
    count = _be32(data, 8)
    if count <= 1 or count > 10000 or 12 + 8 * count > len(data):
        return {}
    starts = [_be32(data, 12 + 8 * index) for index in range(count)]
    if starts[0] != 0 or starts != sorted(starts):
        return {}
    flows: dict[int, bytes] = {}
    total = len(markup)
    for number in range(1, count):
        start = starts[number]
        end = starts[number + 1] if number + 1 < count else total
        if 0 <= start < end <= total:
            flows[number] = markup[start:end]
    return flows


def _refs_in_flow(flow: bytes, flows: dict[int, bytes],
                  active: frozenset[int] = frozenset()) -> list[int]:
    """Image references inside one flow document, in document order."""
    result: list[int] = []
    for match in _IMAGE_TAG_RE.finditer(flow):
        tag = match.group(0)
        recindex = _RECINDEX_RE.search(tag)
        if recindex:
            result.append(int(recindex.group(1)))
            continue
        embed = _EMBED_RE.search(tag)
        if embed:
            result.append(_from_base32(embed.group(1)))
            continue
        flow_ref = _FLOW_RE.search(tag)
        if flow_ref and len(active) < 8:
            number = _from_base32(flow_ref.group(1))
            nested = flows.get(number)
            if nested is not None and number not in active:
                result.extend(_refs_in_flow(nested, flows, active | {number}))
    return result


def _image_refs(markup: bytes, flows: dict[int, bytes] | None = None) -> list[int]:
    """Return 1-based resource indices in reading order.

    A KF8 page often says ``<img src="kindle:flow:0003...">`` and the matching
    flow document contains the real ``kindle:embed`` image.  Resolving that
    indirection is what keeps alternating <img>/<image> pages in book order
    instead of collecting only the direct references.
    """
    result: list[int] = []
    seen: set[int] = set()
    found = False
    for match in _IMAGE_TAG_RE.finditer(markup):
        tag = match.group(0)
        numbers: list[int] = []
        recindex = _RECINDEX_RE.search(tag)
        if recindex:
            numbers = [int(recindex.group(1))]
        else:
            embed = _EMBED_RE.search(tag)
            if embed:
                numbers = [_from_base32(embed.group(1))]
            else:
                flow_ref = _FLOW_RE.search(tag)
                if flow_ref and flows:
                    flow = flows.get(_from_base32(flow_ref.group(1)))
                    if flow is not None:
                        numbers = _refs_in_flow(flow, flows)
        found = found or bool(numbers)
        for number in numbers:
            if number >= 1 and number not in seen:
                seen.add(number)
                result.append(number)
    # Some KF8 files put kindle:embed references in CSS rather than <img> tags.
    if not found:
        for match in _EMBED_RE.finditer(markup):
            number = _from_base32(match.group(1))
            if number >= 1 and number not in seen:
                seen.add(number)
                result.append(number)
    return result


def _read_resource(palm: _PalmFile, record_index: int) -> _Resource:
    start, end = palm.record_bounds(record_index)
    length = end - start
    prefix = palm.read_record(record_index, limit=min(length, _IMAGE_PREFIX))
    if not is_image_data(prefix):
        return _Resource(record_index, start, length)
    dims = image_dimensions(prefix)
    if dims is None:
        full = palm.read_at(start, length)
        dims = image_dimensions(full) or probe_qt_dimensions(full)
    if dims is None:
        return _Resource(record_index, start, length)
    width, height = dims
    return _Resource(record_index, start, length, True, width, height)


def _decode_name(raw: bytes, encoding: str) -> str:
    try:
        return raw.decode(encoding, errors="replace").strip()
    except Exception:
        return ""


def parse_mobi(path: Path) -> Book:
    try:
        handle = open(path, "rb")
    except OSError as exc:
        raise BookError("无法打开 MOBI 文件。") from exc
    try:
        palm = _PalmFile(handle, path)
        rec0 = palm.read_record(0)
        if len(rec0) < 24:
            raise BookError("MOBI 文件头已损坏。")
        compression = _be16(rec0, 0)
        text_length = _be32(rec0, 4)
        text_records = _be16(rec0, 8)
        crypto = _be16(rec0, 12)
        if crypto:
            raise DrmProtectedError("这本 MOBI 受 DRM 保护，无法打开。")

        mobi_magic = rec0[16:20]
        if mobi_magic != b"MOBI":
            raise BookError("这是旧的 PalmDOC 文件，不是图文 MOBI 漫画。")

        header_length = _be32(rec0, 0x14)
        codepage = _be32(rec0, 0x1C)
        # 0x68 is the minimum reader version; it gates the newer trailing
        # entry layout used by Mobipocket's text records.
        min_version = _be32(rec0, 0x68)
        encoding = "utf-8" if codepage == 65001 else "cp1252"
        exth = _parse_exth(rec0, header_length)

        title_offset = _be32(rec0, 0x54)
        title_length = _be32(rec0, 0x58)
        full_name = b""
        if title_offset and title_length and title_offset + title_length <= len(rec0):
            full_name = rec0[title_offset:title_offset + title_length]
        title = (
            _exth_text(exth, 503, encoding)
            or _decode_name(full_name, encoding)
            or path.stem
        )
        author = _exth_text(exth, 100, encoding) or ""

        first_resource = _be32(rec0, 0x6C)
        if first_resource in (0, 0xFFFFFFFF) or first_resource >= palm.record_count:
            first_resource = min(palm.record_count, text_records + 1)
        if first_resource >= palm.record_count:
            raise NoPagesError("这本 MOBI 中没有图片页面。")

        resources: list[_Resource] = []
        for record_index in range(first_resource, palm.record_count):
            start, end = palm.record_bounds(record_index)
            prefix = palm.read_record(record_index, limit=min(end - start, 16))
            if prefix.startswith(b"BOUNDARY") or prefix.startswith(b"INDX"):
                # A hybrid file's KF8 section follows the KF7 section.  We
                # already have the KF7 resources, so stop at the boundary.
                if resources:
                    break
                continue
            if prefix in (b"",) or any(prefix.startswith(tag) for tag in _SKIP_PREFIXES):
                resources.append(_Resource(record_index, start, end - start))
                continue
            resources.append(_read_resource(palm, record_index))

        image_resources = {res.record: res for res in resources if res.is_image}
        if not image_resources:
            raise NoPagesError("这本 MOBI 中没有找到图片页面。")

        cover_record: int | None = None
        cover_offset = _exth_int(exth, 201)
        if cover_offset is not None and 0 <= cover_offset < len(resources) + 1:
            candidate = first_resource + cover_offset
            if candidate in image_resources:
                cover_record = candidate

        thumb_record: int | None = None
        thumb_offset = _exth_int(exth, 202)
        if thumb_offset is not None and 0 <= thumb_offset < len(resources) + 1:
            candidate = first_resource + thumb_offset
            if candidate in image_resources:
                thumb_record = candidate

        raw_markup = _mobi_text(
            rec0, palm, compression, text_records, header_length, min_version
        )
        # The text_length field covers the XHTML body only.  KF8 flow
        # documents (CSS and inline SVGs) are appended afterwards, so split
        # those off the full raw markup before trimming the body.
        flows = _parse_flows(rec0, palm, header_length, raw_markup)
        markup = raw_markup
        if markup and text_length and text_length < len(markup):
            markup = markup[:text_length]
        selected: list[int] = []
        seen: set[int] = set()
        for resource_number in _image_refs(markup, flows):
            if 1 <= resource_number <= len(resources):
                resource = resources[resource_number - 1]
                if resource.is_image and resource.record not in seen:
                    selected.append(resource.record)
                    seen.add(resource.record)

        if not selected:
            # No usable markup (or HUFF/CDIC text): fall back to resource
            # order, skipping spacer images and the thumbnail.
            for resource in resources:
                if not resource.is_image:
                    continue
                if resource.width <= 32 and resource.height <= 32:
                    continue
                if thumb_record is not None and resource.record == thumb_record:
                    continue
                selected.append(resource.record)
                seen.add(resource.record)

        if cover_record is not None and cover_record not in seen:
            selected.insert(0, cover_record)
        if not selected:
            raise NoPagesError("这本 MOBI 中没有找到可显示的漫画页面。")

        pages: list[Page] = []
        for record_index in selected:
            resource = image_resources.get(record_index)
            if resource is None:
                continue
            start, length = resource.offset, resource.length
            pages.append(
                Page(
                    width=resource.width,
                    height=resource.height,
                    source=EncodedImageSource(
                        lambda offset=start, size=length: palm.read_at(offset, size)
                    ),
                    label="",
                )
            )
        if not pages:
            raise NoPagesError("这本 MOBI 中没有找到可显示的漫画页面。")

        return Book(
            path=path,
            title=title or path.stem,
            author=author,
            fmt="MOBI",
            pages=pages,
            closers=[handle.close],
        )
    except Exception:
        try:
            handle.close()
        except Exception:
            pass
        raise
