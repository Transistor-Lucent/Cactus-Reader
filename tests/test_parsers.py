"""Parser smoke tests against the bundled sample comics."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from cactus_reader.book import BookError, DrmProtectedError, load_book

SAMPLES = Path(__file__).resolve().parent / "samples"


class ParserTests(unittest.TestCase):
    def test_epub_sample(self) -> None:
        book = load_book(SAMPLES / "cactus_sample.epub")
        try:
            self.assertEqual(book.page_count, 11)
            self.assertEqual(book.fmt, "EPUB")
            self.assertEqual(book.title, "Cactus Reader 示例漫画")
            self.assertEqual(book.author, "Cactus Studio")
            self.assertFalse(book.used_fallback)
            first = book.pages[0]
            self.assertEqual((first.width, first.height), (900, 1300))
            image = first.source.load_image(None)
            self.assertFalse(image.isNull())
            self.assertEqual((image.width(), image.height()), (900, 1300))
        finally:
            book.close()

    def test_mobi_sample(self) -> None:
        book = load_book(SAMPLES / "cactus_sample.mobi")
        try:
            self.assertEqual(book.page_count, 11)
            self.assertEqual(book.fmt, "MOBI")
            self.assertEqual(book.title, "Cactus Reader 示例漫画")
            self.assertFalse(book.used_fallback)
            image = book.pages[-1].source.load_image(None)
            self.assertFalse(image.isNull())
            self.assertGreater(image.width(), 500)
        finally:
            book.close()

    def test_kf8_azw3_sample_keeps_all_pages(self) -> None:
        # Calibre emits a mix of direct <img> pages and SVG <image> pages that
        # are stored in separate KF8 flow documents.  Missing those flow
        # references used to silently drop every second page.
        book = load_book(SAMPLES / "cactus_sample_kf8.azw3")
        try:
            self.assertEqual(book.page_count, 11)
            self.assertEqual(book.fmt, "MOBI")
            for page in book.pages:
                self.assertEqual((page.width, page.height), (900, 1300))
            image = book.pages[1].source.load_image(None)
            self.assertFalse(image.isNull())
        finally:
            book.close()

    def test_pdf_sample_is_rendered_page_by_page(self) -> None:
        book = load_book(SAMPLES / "cactus_sample.pdf")
        try:
            self.assertEqual(book.page_count, 5)
            self.assertEqual(book.fmt, "PDF")
            self.assertEqual(book.title, "Cactus Reader 示例漫画")
            self.assertEqual(book.author, "Cactus Studio")
            self.assertFalse(book.used_fallback)
            for page in book.pages:
                self.assertEqual((page.width, page.height), (900, 1300))
            image = book.pages[0].source.load_image(None)
            self.assertFalse(image.isNull())
            self.assertEqual((image.width(), image.height()), (1800, 2600))
        finally:
            book.close()

    def test_password_protected_pdf_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "protected.pdf"
            document = pymupdf.open()
            try:
                document.new_page(width=200, height=300)
                document.save(
                    target,
                    encryption=pymupdf.PDF_ENCRYPT_AES_256,
                    owner_pw="owner",
                    user_pw="secret",
                )
            finally:
                document.close()
            with self.assertRaises(DrmProtectedError):
                load_book(target)

    def test_broken_pdf_reports_a_readable_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "broken.pdf"
            target.write_bytes(b"not a pdf")
            with self.assertRaises(BookError):
                load_book(target)

    def test_missing_file(self) -> None:
        with self.assertRaises(BookError):
            load_book(SAMPLES / "does-not-exist.epub")

    def test_unsupported_format(self) -> None:
        target = SAMPLES / "not-a-comic.txt"
        target.write_text("hello", encoding="utf-8")
        try:
            with self.assertRaises(BookError):
                load_book(target)
        finally:
            target.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
