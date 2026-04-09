# ConfessionAI

This repository contains a reproducible paper package for the OffTheRails moral self-correction project on Christian reflective framing.

## Final deliverables

- Final paper draft: [paper/full_paper_draft_v3.md](paper/full_paper_draft_v3.md)
- Final PDF: [paper/full_paper_draft_v3.pdf](paper/full_paper_draft_v3.pdf)
- Final LaTeX: [paper/full_paper_draft_v3.tex](paper/full_paper_draft_v3.tex)
- Final reviewer-strengthened run: [results/pilot_qwen25_core80_1to5_minimal_v3_matched_sec](results/pilot_qwen25_core80_1to5_minimal_v3_matched_sec)

## What is in the repo

- `data/`
  - benchmark-aligned OffTheRails core tables
  - revision condition definitions
  - source provenance and source profiling artifacts
- `src/offtherails_pilot/`
  - prompts, parsing, scoring, dataset checks, rationale coding, IO helpers, and Ollama client
- `scripts/`
  - benchmark preparation
  - experiment runner and repair/summarize/audit scripts
  - rationale coding
  - paper artifact generation
- `paper/`
  - final draft, compiled PDF/LaTeX, generated appendix fragments, and figures
- `results/pilot_qwen25_core80_1to5_minimal_v3_matched_sec/`
  - final experiment outputs, bootstrap summaries, pairwise comparisons, worked cases, and audit report

## Main result

The final v3 run adds a matched secular reflective control. Under the benchmark-aligned continuous-primary evaluation:

- `christian_examen` is still the only condition with a robust permissibility improvement
- it outperforms the matched secular reflective control on permissibility
- the matched secular reflective control is stronger on intention, but it over-revises maximally

This supports a more disciplined claim than the original pilot: Christian examen appears especially effective for stable permissibility revision, while the broader family of confession-like reflective scaffolds may also help on intention-sensitive revision.

## Reproduce the package

```bash
python3 scripts/prepare_offtherails_core.py
python3 scripts/profile_offtherails_sources.py
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/run_pilot.py --run-id pilot_qwen25_core80_1to5_minimal_v3_matched_sec
python3 scripts/repair_results.py --run-dir results/pilot_qwen25_core80_1to5_minimal_v3_matched_sec --items-file data/items_offtherails_core.csv
python3 scripts/summarize_results.py --run-dir results/pilot_qwen25_core80_1to5_minimal_v3_matched_sec
python3 scripts/code_rationales.py --run-dir results/pilot_qwen25_core80_1to5_minimal_v3_matched_sec
python3 scripts/audit_experiment.py --run-dir results/pilot_qwen25_core80_1to5_minimal_v3_matched_sec --items-file data/items_offtherails_core.csv
python3 scripts/build_paper_artifacts.py --run-dir results/pilot_qwen25_core80_1to5_minimal_v3_matched_sec
pandoc paper/full_paper_draft_v3.md -s --number-sections -o paper/full_paper_draft_v3.tex --from markdown --to latex
pdflatex -interaction=nonstopmode -halt-on-error -output-directory paper paper/full_paper_draft_v3.tex
pdflatex -interaction=nonstopmode -halt-on-error -output-directory paper paper/full_paper_draft_v3.tex
```

## Notes

- The repository keeps the final paper-facing run and excludes older smoke and legacy runs from git.
- Binary correction metrics remain descriptive only on this OffTheRails subset because the supported human-rated core is one-sided under benchmark-aligned thresholds.
- The current paper is English-only and uses `qwen2.5:7b-instruct` through Ollama.
