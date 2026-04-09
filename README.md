# ConfessionAI

Can a model be prompted not just to **answer**, but to **revisit its own moral judgment better**?

This repository contains the final paper package, code, and experiment artifacts for a study of **moral self-correction** on OffTheRails. The core idea is simple and useful:

> A prompt can make a model revise more without revising better.

This project asks whether **Christian reflective framing**, especially an examen-like prompt, helps models revise moral judgments in a more useful way after the first pass.

## The memorable result

The strongest result from the final v3 run is not “Christian prompts beat everything.”

It is narrower and more interesting:

- `christian_examen` is the **only** tested condition with a robust **permissibility** improvement.
- It still beats a **matched secular reflective control** on permissibility.
- That matched secular control is actually **better on intention**, but it also **over-revises maximally**.
- `christian_identity_only` performs much worse, which means the effect is **not** just “add Christian language.”

The practical takeaway is:

> For moral revision, **more self-reflection is not enough**.  
> The shape of the reflective scaffold matters.

And the more precise instrumental read is:

> Christian examen appears especially good for **stable permissibility revision**, while the broader family of confession-like reflective prompts may help with **intention-sensitive revision**.

## Why this repo is interesting

Most moral-evaluation papers ask whether a model gets the answer right on the first try.

This one focuses on a more realistic question:

- The model answers once.
- You ask it to reconsider.
- Does it get **better**, or just become **more volatile**?

That distinction turns out to matter a lot. In this repo’s final run, several prompts caused heavy revision but worse permissibility performance. So one of the clearest lessons is:

> **Revision quality is its own capability.**  
> It should not be treated as an automatic byproduct of first-pass competence.

## Final deliverables

- Final paper draft: [paper/full_paper_draft_v3.md](paper/full_paper_draft_v3.md)
- Final PDF: [paper/full_paper_draft_v3.pdf](paper/full_paper_draft_v3.pdf)
- Final LaTeX: [paper/full_paper_draft_v3.tex](paper/full_paper_draft_v3.tex)
- Final reviewer-strengthened run: [results/pilot_qwen25_core80_1to5_minimal_v3_matched_sec](results/pilot_qwen25_core80_1to5_minimal_v3_matched_sec)

## What the final run shows

The main benchmark is the human-rated OffTheRails Experiment 2 core subset, using the benchmark-aligned `1-5` scale and a `continuous_primary` evaluation profile.

In the final v3 run:

- `christian_examen` improves permissibility with `mean delta = -0.131`, `95% CI [-0.242, -0.020]`
- `matched_secular_reflective` has `perm delta = 0.115`, `95% CI [-0.018, 0.250]`
- paired comparison on permissibility gives `christian_examen - matched_secular_reflective = -0.247`, `95% CI [-0.370, -0.134]`
- paired comparison on intention gives `christian_examen - matched_secular_reflective = 0.137`, `95% CI [0.003, 0.269]`
- over-revision is `0.650` for `christian_examen` versus `1.000` for `matched_secular_reflective`

So the interesting pattern is not a one-line win. It is a tradeoff structure:

- Christian examen looks best when you care about **revising permissibility judgments without losing stability**
- matched secular reflection looks stronger when you care about **intention revision**, but it gets there by revising everything

## Repo structure

- `data/`
  - OffTheRails core tables
  - revision condition definitions
  - source provenance and profiling artifacts
- `src/offtherails_pilot/`
  - prompts, parsing, scoring, dataset checks, rationale coding, IO helpers, and Ollama client
- `scripts/`
  - benchmark preparation
  - pilot runner
  - repair, summarize, audit, rationale coding, and paper-artifact generation
- `paper/`
  - final manuscript, compiled PDF/LaTeX, figures, and generated appendix fragments
- `results/pilot_qwen25_core80_1to5_minimal_v3_matched_sec/`
  - final experiment outputs, bootstrap summaries, pairwise comparisons, worked cases, and audit report

## Reproduce the final package

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

## Important caveats

- This benchmark subset is **not** balanced enough for binary-primary self-correction claims, so the paper uses continuous distance-to-human-mean as the main metric.
- The current paper is based on a **single model**: `qwen2.5:7b-instruct` through Ollama.
- The rationale coding is **exploratory**, not a proof of internal mechanism.
- The current contribution is best read as a result about **revision scaffolding**, not theological superiority.

## If you only remember three things

- **More revision is not the same as better revision.**
- **Christian identity alone is not enough.**
- **The structure of self-examination changes what kind of correction you get.**
