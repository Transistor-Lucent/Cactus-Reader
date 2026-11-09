"""Book model, format dispatch and the PyMuPDF safety net."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from .image_utils import decode_image

log = logging.getLogger(__name__)


class BookError(Exception):
    """A problem that can be explained to the reader."""


class DrmProtectedError(BookError):
    pass


class NoPagesError(BookError):
    pass


class PageSource(Protocol):
    def load_image(self, target_px: QSize | None) -> QImage: ...


class EncodedImageSource:
    """Loads an image lazily from a getter, so huge books stay cheap in RAM."""

    def __init__(self, getter: Callable[[], bytes]) -> None:
        self._getter = getter

    def load_image(self, target_px: QSize | None) -> QImage:
        return decode_image(self._getter(), target_px)


class RenderedPageSource:
    """Fallback page source backed by a PyMuPDF document page."""

    def __init__(self, document, page_number: int, page_width: float, page_height: float) -> None:
        self._document = document
        self._page_number = page_number
        self._page_width = max(1.0, page_width)
        self._page_height = max(1.0, page_height)

    def load_image(self, target_px: QSize | None) -> QImage:
        import pymupdf

        page = self._document.load_page(self._page_number)
        if target_px is not None and target_px.width() > 0 and target_px.height() > 0:
            scale = min(target_px.width() / self._page_width, target_px.height() / self._page_height)
        else:
            scale = 2.0
        scale = max(0.4, min(scale, 4.0))
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False
        )
        image = QImage(
            pixmap.samples,
            pixmap.width,
            pixmap.height,
            pixmap.stride,
            QImage.Format.Format_RGB888,
        )
        return image.copy()


@dataclass
class Page:
    width: int
    height: int
    source: PageSource
    label: str = ""

    @property
    def aspect(self) -> float:
        if self.height <= 0:
            return 1.0
        return self.width / self.height


@dataclass
class Book:
    path: Path
    title: str
    author: str
    fmt: str
    pages: list[Page]
    closers: list[Callable[[], None]] = field(default_factory=list)
    used_fallback: bool = False

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def close(self) -> None:
        while self.closers:
            closer = self.closers.pop()
            try:
                closer()
            except Exception:
                log.debug("Ignoring close error", exc_info=True)


def load_book(path: str | Path) -> Book:
    """Load an EPUB/MOBI comic, with a rendered-page fallback for odd files."""
    book_path = Path(path).expanduser().resolve()
    if not book_path.exists():
        raise BookError(f"文件不存在：\n{book_path}")
    if not book_path.is_file():
        raise BookError(f"这不是一个文件：\n{book_path}")

    suffix = book_path.suffix.lower()
    supported = (".epub", ".mobi", ".prc", ".azw", ".azw3")
    if suffix not in supported:
        raise BookError("仅支持 EPUB 和 MOBI 格式的漫画。")
    custom_error: Exception | None = None
    book: Book | None = None

    try:
        if suffix == ".epub":
            from .epub_book import parse_epub

            book = parse_epub(book_path)
        else:
            # KF8/AZW files use the same Palm database container.  If our
            # lightweight extractor cannot find pages, the MuPDF fallback
            # below will take over.
            from .mobi_book import parse_mobi

            book = parse_mobi(book_path)
    except DrmProtectedError:
        raise
    except Exception as exc:  # corrupted or unusual structure: try MuPDF
        custom_error = exc
        log.info("Primary parser failed for %s: %s", book_path, exc)

    if book is not None and book.page_count > 0:
        return book
    if book is not None:
        book.close()

    try:
        book = _load_with_fitz(book_path)
    except DrmProtectedError:
        raise
    except Exception as exc:
        log.info("Fallback parser failed for %s: %s", book_path, exc)
        if isinstance(custom_error, BookError):
            raise custom_error
        raise BookError(
            "无法读取这本漫画。文件可能已损坏、受 DRM 保护，或使用了暂不支持的排版方式。"
        ) from exc

    if book.page_count <= 0:
        book.close()
        raise NoPagesError("这本漫画中没有可显示的页面。")
    return book


def _load_with_fitz(path: Path) -> Book:
    import pymupdf

    try:
        document = pymupdf.open(str(path))
    except Exception as exc:
        raise BookError("无法使用备用渲染器打开此文件。") from exc
    if document.needs_pass:
        document.close()
        raise DrmProtectedError("这本漫画受密码或 DRM 保护，无法打开。")
    if document.page_count <= 0:
        document.close()
        raise NoPagesError("这本漫画中没有可显示的页面。")

    metadata = document.metadata or {}
    fmt = str(metadata.get("format") or path.suffix.lstrip(".")).upper()
    if fmt not in ("EPUB", "MOBI", "KF8", "AZW3"):
        fmt = "MOBI" if path.suffix.lower() in (".mobi", ".prc", ".azw", ".azw3") else "EPUB"
    title = (metadata.get("title") or "").strip() or path.stem
    author = (metadata.get("author") or "").strip()

    pages: list[Page] = []
    for number in range(document.page_count):
        page = document.load_page(number)
        rect = page.rect
        width = max(1, int(round(rect.width)))
        height = max(1, int(round(rect.height)))
        pages.append(
            Page(
                width=width,
                height=height,
                source=RenderedPageSource(document, number, rect.width, rect.height),
            )
        )
    return Book(
        path=path,
        title=title,
        author=author,
        fmt=fmt,
        pages=pages,
        closers=[document.close],
        used_fallback=True,
    )
