"""Generate small, self-contained comic samples used by the test suite.

The generated pages are deliberately simple but look like comic pages.  The
EPUB is also fed to Calibre's ``ebook-convert`` by the developer to produce a
real MOBI sample, while the PDF is built directly with PyMuPDF.  The test
suite itself never requires Calibre.
"""

from __future__ import annotations

import io
import math
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "samples"

PALETTE = [
    ("#101820", "#f3c969", "#e86f51"),
    ("#1b2a41", "#e9d8a6", "#7bdff2"),
    ("#231942", "#f4acb7", "#ffcad4"),
    ("#0b3d2e", "#c9e4ca", "#f2c14e"),
    ("#31221b", "#f7d4bc", "#d1495b"),
    ("#20232a", "#a8dadc", "#e63946"),
    ("#2b2d42", "#edf2f4", "#ef233c"),
    ("#1d3557", "#a8dadc", "#e9c46a"),
    ("#333d29", "#dde5b6", "#bc6c25"),
    ("#3a0ca3", "#b8c0ff", "#f72585"),
    ("#22223b", "#c9ada7", "#f2e9e4"),
]


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except Exception:
                continue
    return ImageFont.load_default()


def make_page(index: int, total: int, width: int = 900, height: int = 1300) -> bytes:
    bg, ink, accent = PALETTE[(index - 1) % len(PALETTE)]
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    # Paper-like margin and inner frame.
    margin = 54
    draw.rounded_rectangle(
        (margin, margin, width - margin, height - margin),
        radius=22,
        fill="#0b0d10",
        outline=accent,
        width=5,
    )
    draw.rounded_rectangle(
        (margin + 20, margin + 20, width - margin - 20, height - margin - 20),
        radius=14,
        outline="#3b4652",
        width=2,
    )

    # Comic panels with tiny cactus silhouettes.
    top = margin + 70
    body_bottom = height - margin - 150
    usable = body_bottom - top
    gap = 26
    panel_h = (usable - gap) // 2
    panel_w = width - 2 * margin - 80
    left = margin + 40
    for row in range(2):
        y0 = top + row * (panel_h + gap)
        draw.rounded_rectangle(
            (left, y0, left + panel_w, y0 + panel_h),
            radius=14,
            fill=ink if row == 0 else "#f5f1e8",
            outline="#f8f8f2",
            width=3,
        )
        # Ground line and cactus.
        base_y = y0 + panel_h - 54
        draw.line((left + 38, base_y, left + panel_w - 38, base_y), fill=accent, width=6)
        cx = left + 110 + (row * 230) + (index * 47) % max(1, panel_w - 360)
        ch = panel_h * (0.42 + 0.08 * (index % 3))
        pot_top = base_y - 48
        draw.rounded_rectangle(
            (cx - 58, base_y - 58, cx + 58, base_y + 30),
            radius=12,
            fill="#b86b46",
            outline="#42210f",
            width=4,
        )
        draw.rounded_rectangle(
            (cx - 32, pot_top - ch, cx + 32, pot_top + 10),
            radius=30,
            fill="#4f9f63",
            outline="#132a1a",
            width=4,
        )
        draw.rounded_rectangle(
            (cx - 88, pot_top - ch * 0.58, cx - 54, pot_top - ch * 0.18),
            radius=18,
            fill="#4f9f63",
            outline="#132a1a",
            width=4,
        )
        draw.rounded_rectangle(
            (cx + 54, pot_top - ch * 0.72, cx + 88, pot_top - ch * 0.27),
            radius=18,
            fill="#4f9f63",
            outline="#132a1a",
            width=4,
        )
        # Speech bubble / burst.
        bx = left + panel_w - 230
        by = y0 + 34
        draw.ellipse((bx, by, bx + 180, by + 92), fill="#fffdf4", outline="#101820", width=3)
        draw.polygon(
            [(bx + 35, by + 80), (bx + 64, by + 114), (bx + 82, by + 82)],
            fill="#fffdf4",
        )
        msg = ["PAGE TURN", "NEXT PANEL", "DEEP BREATH", "KEEP GOING"][(index + row) % 4]
        draw.text((bx + 22, by + 27), msg, font=_font(22, True), fill="#101820")
        # Decorative city/stars.
        for k in range(10):
            sx = left + 30 + (k * 83 + index * 31) % (panel_w - 60)
            sy = y0 + 28 + (k * 47) % max(1, panel_h - 160)
            r = 4 + (k + index) % 5
            draw.ellipse((sx - r, sy - r, sx + r, sy + r), fill=accent)

    # Bottom caption band.
    band_top = height - margin - 134
    draw.rounded_rectangle(
        (margin + 40, band_top, width - margin - 40, height - margin - 34),
        radius=12,
        fill=accent,
    )
    label = f"{index:02d} / {total:02d}"
    font = _font(44, True)
    tw = draw.textlength(label, font=font)
    draw.text(((width - tw) / 2, band_top + 23), label, font=font, fill="#07110b")
    small_font = _font(20)
    title = "CACTUS READER  ·  SAMPLE COMIC"
    tw2 = draw.textlength(title, font=small_font)
    draw.text(((width - tw2) / 2, margin + 20), title, font=small_font, fill=accent)

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88, optimize=True)
    return out.getvalue()


def make_epub(path: Path, pages: int = 11) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    title = "Cactus Reader 示例漫画"
    author = "Cactus Studio"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            zipfile.ZipInfo("mimetype"),
            "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
""",
        )
        manifest = []
        spine = []
        for i in range(1, pages + 1):
            img_name = f"page_{i:03d}.jpg"
            zf.writestr(f"OEBPS/Images/{img_name}", make_page(i, pages))
            manifest.append(
                f'    <item id="img{i}" href="Images/{img_name}" media-type="image/jpeg"/>'
            )
            # Alternate between a plain img page and an SVG wrapped page.
            xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:xlink="http://www.w3.org/1999/xlink">
<head>
  <title>Page {i}</title>
  <style>
    html, body {{ margin:0; padding:0; height:100%; background:#000; }}
    body {{ display:flex; align-items:center; justify-content:center; }}
    img, svg {{ max-width:100%; max-height:100%; }}
  </style>
</head>
<body>
  <div>
    {'<img src="../Images/' + img_name + '" alt="Page ' + str(i) + '"/>' if i % 2 else '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 1300" height="100%" preserveAspectRatio="xMidYMid meet"><image width="900" height="1300" xlink:href="../Images/' + img_name + '"/></svg>'}
  </div>
</body>
</html>
"""
            zf.writestr(f"OEBPS/Text/page_{i:03d}.xhtml", xhtml)
            manifest.append(
                f'    <item id="page{i}" href="Text/page_{i:03d}.xhtml" media-type="application/xhtml+xml"/>'
            )
            spine.append(f'    <itemref idref="page{i}"/>')

        opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid" xml:lang="zh-CN">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">urn:uuid:cactus-reader-sample-{pages}</dc:identifier>
    <dc:title>{escape(title)}</dc:title>
    <dc:creator>{escape(author)}</dc:creator>
    <dc:language>zh-CN</dc:language>
    <meta property="dcterms:modified">2026-01-01T00:00:00Z</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
{chr(10).join(manifest)}
  </manifest>
  <spine>
{chr(10).join(spine)}
  </spine>
</package>
"""
        zf.writestr("OEBPS/content.opf", opf)
        nav = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>目录</title></head>
<body><nav epub:type="toc"><ol><li><a href="Text/page_001.xhtml">开始阅读</a></li></ol></nav></body>
</html>
"""
        zf.writestr("OEBPS/nav.xhtml", nav)
    return path


def make_pdf(path: Path, pages: int = 5) -> Path:
    """Build a scan-like PDF whose pages contain the same comic artwork."""
    import pymupdf

    path.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    try:
        for index in range(1, pages + 1):
            page = document.new_page(width=900, height=1300)
            page.insert_image(
                pymupdf.Rect(0, 0, 900, 1300),
                stream=make_page(index, pages),
            )
        document.set_metadata(
            {
                "title": "Cactus Reader 示例漫画",
                "author": "Cactus Studio",
                "subject": "Cactus Reader PDF sample",
            }
        )
        document.save(path, garbage=4, deflate=True)
    finally:
        document.close()
    return path


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    epub = make_epub(OUT / "cactus_sample.epub")
    pdf = make_pdf(OUT / "cactus_sample.pdf")
    print(epub)
    print(pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
