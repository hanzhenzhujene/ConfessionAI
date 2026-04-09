# OffTheRails Source Profile

## Experiment 2

- All item cells in long-format table: `160`
- Supported item cells with >=20 human ratings: `80`
- Sparse item cells excluded from reliable aggregation: `80`
- Supported group size range: `21` to `23`
- Supported cells by split: `{'0': 16, '1': 16, '2': 16, '3': 16, '4': 16}`
- Supported permissibility balance: `{'pos': 54, 'amb': 26}`
- Supported intention balance: `{'amb': 56, 'neg': 24}`

Interpretation: the well-supported Experiment 2 subset is exactly the current 80-item core, and it is not decision-balanced enough for binary-primary self-correction claims.

## Experiment 1

- Row count: `3200`
- Columns: `['worker_id', 'scenario_id', 'rating', 'structure', 'type', 'strength']`

Experiment 1 contains target-event valence ratings (rating/structure/type/strength), not direct permissibility and intention judgments. It is not a drop-in replacement for the self-correction benchmark.

## Recommendation

Use Experiment 2 core items with benchmark-aligned 1-5 prompts for continuous-primary analysis.
Do not promote binary net correction gain to the headline result on this subset.
If a binary-primary main experiment is required, use a different evaluation set or add new human annotation for a more balanced set of dilemmas.
