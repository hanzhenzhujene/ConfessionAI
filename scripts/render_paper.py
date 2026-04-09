#!/usr/bin/env python3
"""Render the paper to NeurIPS-style LaTeX and PDF."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER_DIR = ROOT / "paper"
MARKDOWN_PATH = PAPER_DIR / "full_paper_draft_v3.md"
TEX_PATH = PAPER_DIR / "full_paper_draft_v3.tex"
STYLE_USEPACKAGE = r"\usepackage[preprint,nonatbib]{paper/neurips_2023}"
XPARSE_USEPACKAGE = r"\usepackage{xparse}"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, cwd=ROOT)


def inject_neurips_style(tex_path: Path) -> None:
    text = tex_path.read_text(encoding="utf-8")
    citeproc_marker = "% definitions for citeproc citations"
    if XPARSE_USEPACKAGE not in text and citeproc_marker in text:
        text = text.replace(citeproc_marker, XPARSE_USEPACKAGE + "\n" + citeproc_marker, 1)
    elif XPARSE_USEPACKAGE in text and citeproc_marker in text:
        xparse_index = text.index(XPARSE_USEPACKAGE)
        citeproc_index = text.index(citeproc_marker)
        if xparse_index > citeproc_index:
            text = text.replace(XPARSE_USEPACKAGE + "\n", "", 1)
            text = text.replace(citeproc_marker, XPARSE_USEPACKAGE + "\n" + citeproc_marker, 1)

    marker = r"\title{"
    if STYLE_USEPACKAGE not in text:
        if marker not in text:
            raise RuntimeError("Could not find title marker in generated LaTeX.")
        text = text.replace(marker, STYLE_USEPACKAGE + "\n\n" + marker, 1)
    tex_path.write_text(text, encoding="utf-8")


def main() -> None:
    run(
        [
            "pandoc",
            str(MARKDOWN_PATH),
            "-s",
            "--citeproc",
            "--number-sections",
            "-o",
            str(TEX_PATH),
            "--from",
            "markdown",
            "--to",
            "latex",
        ]
    )
    inject_neurips_style(TEX_PATH)
    for _ in range(3):
        run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-output-directory",
                "paper",
                str(TEX_PATH),
            ]
        )


if __name__ == "__main__":
    main()
