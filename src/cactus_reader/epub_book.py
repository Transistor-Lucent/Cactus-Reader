"""EPUB comic reader: image pages are extracted in spine order."""

from __future__ import annotations

import html
import posixpath
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from PySide6.QtCore import QSize

from .book import Book, BookError, DrmProtectedError, EncodedImageSource, NoPagesError, Page
from .image_utils import image_dimensions, is_image_data, probe_qt_dimensions

_RASTER_EXTENSIONS = {
    ".jpg", ".jpeg", ".jpe", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff"
}
_XHTML_EXTENSIONS = {".xhtml", ".html", ".htm"}
_PREFIX_BYTES = 512 * 1024


class _ImageReferenceParser(HTMLParser):
    """Collect image references from an XHTML/SVG document in document order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value for name, value in attrs}
        if tag == "img" or tag == "input":
            src = values.get("src")
            if src and (tag == "img" or (values.get("type") or "").lower().startswith("image/")):
                self.refs.append(src)
        elif tag == "image":
            href = values.get("xlink:href") or values.get("href")
            if href:
                self.refs.append(href)
        elif tag == "object":
            data = values.get("data")
            if data and "image" in (values.get("type") or "").lower():
                self.refs.append(data)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _iter_children(element: ET.Element, name: str):
    for child in element:
        if _local_name(child.tag) == name:
            yield child


def _find_first(element: ET.Element, name: str) -> ET.Element | None:
    for child in element.iter():
        if _local_name(child.tag) == name:
            return child
    return None


def _resolve_href(base_file: str, href: str) -> str | None:
    if not href:
        return None
    parts = urlsplit(html.unescape(href.strip()))
    if parts.scheme or parts.netloc:
        return None
    raw = unquote(parts.path)
    if not raw:
        return None
    if raw.startswith("/"):
        raw = raw.lstrip("/")
        joined = posixpath.normpath(raw)
    else:
        joined = posixpath.normpath(posixpath.join(posixpath.dirname(base_file), raw))
    if joined.startswith("../") or joined == "..":
        return None
    return joined


class _ZipBook:
    def __init__(self, zf: zipfile.ZipFile) -> None:
        self.zf = zf
        self.names = set(zf.namelist())
        self.lower_names = {name.lower(): name for name in self.names}

    def actual_name(self, name: str) -> str | None:
        name = name.replace("\\", "/")
        if name in self.names:
            return name
        return self.lower_names.get(name.lower())

    def read(self, name: str) -> bytes | None:
        actual = self.actual_name(name)
        if actual is None:
            return None
        try:
            return self.zf.read(actual)
        except (KeyError, OSError, RuntimeError):
            return None

    def read_prefix(self, name: str, limit: int = _PREFIX_BYTES) -> bytes | None:
        actual = self.actual_name(name)
        if actual is None:
            return None
        try:
            info = self.zf.getinfo(actual)
            with self.zf.open(actual) as handle:
                return handle.read(min(max(1, info.file_size), limit))
        except (KeyError, OSError, RuntimeError):
            return None


def _entry_dimensions(zipbook: _ZipBook, name: str) -> tuple[int, int] | None:
    prefix = zipbook.read_prefix(name)
    if prefix is None:
        return None
    dims = image_dimensions(prefix)
    if dims is None and prefix and is_image_data(prefix):
        dims = probe_qt_dimensions(prefix)
    if dims is None:
        # Some JPEGs carry large metadata before the SOF marker.
        full = zipbook.read(name)
        if not full:
            return None
        dims = image_dimensions(full) or probe_qt_dimensions(full)
    return dims


def _encrypted_image_references(zf: zipfile.ZipFile) -> bool:
    try:
        raw = zf.read("META-INF/encryption.xml")
    except (KeyError, OSError, RuntimeError):
        return False
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return False
    for element in root.iter():
        if _local_name(element.tag) != "cipherreference":
            continue
        uri = element.attrib.get("URI") or element.attrib.get("uri") or ""
        path = unquote(urlsplit(uri).path).lower()
        if Path(path).suffix in _RASTER_EXTENSIONS:
            return True
    return False


def _parse_opf_metadata(opf_root: ET.Element) -> tuple[str, str]:
    title = ""
    authors: list[str] = []
    for element in opf_root.iter():
        name = _local_name(element.tag)
        text = "".join(element.itertext()).strip()
        if not text:
            continue
        if name == "title" and not title:
            title = " ".join(text.split())
        elif name == "creator":
            if text not in authors:
                authors.append(text)
    return title, "、".join(authors)


def _find_cover_path(
    opf_root: ET.Element, manifest: dict[str, dict[str, str]], opf_dir: str
) -> str | None:
    cover_ids: set[str] = set()
    for element in opf_root.iter():
        if _local_name(element.tag) == "meta":
            if (element.attrib.get("name") or "").lower() == "cover":
                value = element.attrib.get("content")
                if value:
                    cover_ids.add(value)
    candidates: list[str] = []
    for item_id, item in manifest.items():
        properties = (item.get("properties") or "").lower().split()
        if "cover-image" in properties:
            candidates.append(item.get("href") or "")
        if item_id in cover_ids:
            candidates.insert(0, item.get("href") or "")
    for href in candidates:
        resolved = _resolve_href(posixpath.join(opf_dir, "_"), href) if href else None
        if resolved is not None:
            return resolved
    return None


def parse_epub(path: Path) -> Book:
    try:
        zf = zipfile.ZipFile(path, "r")
    except (zipfile.BadZipFile, OSError) as exc:
        raise BookError("这不是有效的 EPUB 文件。") from exc

    closers: list[object] = [zf.close]
    try:
        zipbook = _ZipBook(zf)
        container = zipbook.read("META-INF/container.xml")
        if container:
            try:
                container_root = ET.fromstring(container)
                rootfile = _find_first(container_root, "rootfile")
                opf_name = rootfile.attrib.get("full-path") if rootfile is not None else None
            except ET.ParseError:
                opf_name = None
        else:
            opf_name = None
        if not opf_name:
            candidates = [name for name in zipbook.names if name.lower().endswith(".opf")]
            opf_name = candidates[0] if candidates else None
        actual_opf = zipbook.actual_name(opf_name or "")
        opf_bytes = zipbook.read(actual_opf) if actual_opf else None
        if opf_bytes is None:
            raise BookError("EPUB 中缺少内容清单（OPF）。")
        try:
            opf_root = ET.fromstring(opf_bytes)
        except ET.ParseError as exc:
            raise BookError("EPUB 的内容清单已损坏。") from exc
        opf_dir = posixpath.dirname(actual_opf)

        if _encrypted_image_references(zf):
            raise DrmProtectedError("这本 EPUB 含有 DRM 加密的图片，无法打开。")

        manifest: dict[str, dict[str, str]] = {}
        for item in opf_root.iter():
            if _local_name(item.tag) != "item":
                continue
            item_id = item.attrib.get("id")
            href = item.attrib.get("href")
            if item_id and href:
                manifest[item_id] = {
                    "href": href,
                    "media-type": (item.attrib.get("media-type") or "").lower(),
                    "properties": item.attrib.get("properties") or "",
                }

        spine_ids: list[str] = []
        for itemref in opf_root.iter():
            if _local_name(itemref.tag) == "itemref":
                idref = itemref.attrib.get("idref")
                if idref:
                    spine_ids.append(idref)
        # A malformed OPF may omit the spine.  Using manifest order is a better
        # failure mode than showing nothing.
        if not spine_ids:
            spine_ids = list(manifest)
            spine_ids.sort(
                key=lambda key: (manifest[key].get("href") or "").lower()
            )

        title, author = _parse_opf_metadata(opf_root)
        title = title or path.stem

        pages: list[Page] = []
        added_images: set[str] = set()
        seen_documents: set[str] = set()

        def add_image(image_name: str | None) -> bool:
            if not image_name or image_name in added_images:
                return False
            actual = zipbook.actual_name(image_name)
            if not actual:
                return False
            if Path(actual).suffix.lower() not in _RASTER_EXTENSIONS:
                return False
            dims = _entry_dimensions(zipbook, actual)
            if dims is None:
                return False
            width, height = dims
            added_images.add(actual)
            pages.append(
                Page(
                    width=width,
                    height=height,
                    source=EncodedImageSource(lambda name=actual: zipbook.read(name) or b""),
                    label=Path(actual).stem,
                )
            )
            return True

        def collect_from_document(document_name: str, recursion: int = 0) -> None:
            if recursion > 4:
                return
            raw = zipbook.read(document_name)
            if not raw:
                return
            parser = _ImageReferenceParser()
            try:
                parser.feed(raw.decode("utf-8", errors="replace"))
                parser.close()
            except Exception:
                return
            for href in parser.refs:
                target = _resolve_href(document_name, href)
                if not target:
                    continue
                actual = zipbook.actual_name(target)
                if not actual:
                    continue
                suffix = Path(actual).suffix.lower()
                if suffix in _RASTER_EXTENSIONS:
                    add_image(actual)
                elif suffix == ".svg":
                    collect_from_document(actual, recursion + 1)

        for idref in spine_ids:
            item = manifest.get(idref)
            if not item:
                continue
            target = _resolve_href(posixpath.join(opf_dir, "_"), item["href"])
            actual = zipbook.actual_name(target or "")
            if not actual or actual in seen_documents:
                continue
            media_type = item.get("media-type") or ""
            suffix = Path(actual).suffix.lower()
            if media_type.startswith("image/") or suffix in _RASTER_EXTENSIONS:
                add_image(actual)
            elif media_type in (
                "application/xhtml+xml",
                "text/html",
                "image/svg+xml",
            ) or suffix in _XHTML_EXTENSIONS or suffix == ".svg":
                seen_documents.add(actual)
                collect_from_document(actual)

        # Even when the cover is not in the spine, a comic reader should start
        # with it.  Avoid adding it twice when it was referenced normally.
        cover_path = _find_cover_path(opf_root, manifest, opf_dir)
        if cover_path:
            actual_cover = zipbook.actual_name(cover_path)
            if actual_cover and actual_cover not in added_images:
                cover_dims = _entry_dimensions(zipbook, actual_cover)
                if cover_dims:
                    width, height = cover_dims
                    pages.insert(
                        0,
                        Page(
                            width=width,
                            height=height,
                            source=EncodedImageSource(
                                lambda name=actual_cover: zipbook.read(name) or b""
                            ),
                            label=Path(actual_cover).stem,
                        ),
                    )

        if not pages:
            raise NoPagesError("这本 EPUB 中没有找到可显示的图片页面。")
        return Book(
            path=path,
            title=title,
            author=author,
            fmt="EPUB",
            pages=pages,
            closers=[zf.close],
        )
    except Exception:
        for closer in closers:
            try:
                closer()
            except Exception:
                pass
        raise
