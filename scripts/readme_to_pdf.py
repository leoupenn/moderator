#!/usr/bin/env python3
"""Render README.md to README.pdf (fpdf2 + markdown). Run from repo root: python3 scripts/readme_to_pdf.py"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FONT_CANDIDATES = [
    Path("/Library/Fonts/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
]


def main() -> int:
    try:
        import markdown
        from fpdf import FPDF
        from fpdf.fonts import TextStyle
    except ImportError:
        print("Install: pip install fpdf2 markdown", file=sys.stderr)
        return 1

    font = next((p for p in FONT_CANDIDATES if p.is_file()), None)
    if font is None:
        print("No Unicode TTF found; install Arial Unicode or DejaVu Sans.", file=sys.stderr)
        return 1

    md_path = ROOT / "README.md"
    out_path = ROOT / "README.pdf"
    md = md_path.read_text(encoding="utf-8")
    body = markdown.markdown(md, extensions=["extra", "nl2br", "sane_lists"])
    html = f"<html><body>{body}</body></html>"

    pdf = FPDF()
    for st in ("", "B", "I", "BI"):
        pdf.add_font("U", st, str(font))

    code_style = TextStyle(font_family="U", font_size_pt=9)
    tag_styles = {
        "code": code_style,
        "pre": TextStyle(font_family="U", font_size_pt=9, t_margin=4),
    }

    pdf.set_font("U", size=11)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.write_html(html, font_family="U", tag_styles=tag_styles)
    pdf.output(str(out_path))
    print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
