# Experiment Audit

- Findings: `22`

## [WARN] High over-revision in christian_examen

over_revision_rate=0.650. This condition changes answers frequently and may be measuring prompt-induced volatility rather than correction.

## [WARN] High over-revision in christian_identity_only

over_revision_rate=0.988. This condition changes answers frequently and may be measuring prompt-induced volatility rather than correction.

## [WARN] High over-revision in generic_reconsider

over_revision_rate=1.000. This condition changes answers frequently and may be measuring prompt-induced volatility rather than correction.

## [WARN] High over-revision in matched_secular_reflective

over_revision_rate=1.000. This condition changes answers frequently and may be measuring prompt-induced volatility rather than correction.

## [WARN] High over-revision in moral_checklist

over_revision_rate=1.000. This condition changes answers frequently and may be measuring prompt-induced volatility rather than correction.

## [WARN] High over-revision in secular_self_examination

over_revision_rate=0.912. This condition changes answers frequently and may be measuring prompt-induced volatility rather than correction.

## [WARN] Intention gold labels are one-sided

Intention gold labels are pos=0, neg=24, ambiguous=56. Binary self-correction on intention is not decision-balanced.

## [WARN] Many items are excluded from binary scoring

Ambiguous binary items: permissibility=26, intention=56. Continuous distance metrics are more trustworthy than binary correction rates on this subset.

## [WARN] Permissibility and intention are elicited jointly

The current protocol asks the model to rate permissibility and intention in one JSON response. OffTheRails originally elicits these judgments separately, so this is a benchmark adaptation rather than a direct reproduction.

## [WARN] Permissibility gold labels are one-sided

Permissibility gold labels are pos=54, neg=0, ambiguous=26. Binary self-correction on permissibility is not decision-balanced.

## [WARN] Too few intention errors for christian_examen

intent_n_wrong_before=0. Intention correction metrics are not decision-stable on this run.

## [WARN] Too few intention errors for christian_identity_only

intent_n_wrong_before=0. Intention correction metrics are not decision-stable on this run.

## [WARN] Too few intention errors for generic_reconsider

intent_n_wrong_before=0. Intention correction metrics are not decision-stable on this run.

## [WARN] Too few intention errors for matched_secular_reflective

intent_n_wrong_before=0. Intention correction metrics are not decision-stable on this run.

## [WARN] Too few intention errors for moral_checklist

intent_n_wrong_before=0. Intention correction metrics are not decision-stable on this run.

## [WARN] Too few intention errors for secular_self_examination

intent_n_wrong_before=0. Intention correction metrics are not decision-stable on this run.

## [WARN] Too few permissibility errors for christian_examen

perm_n_wrong_before=0. Net correction gain is not statistically meaningful at this denominator.

## [WARN] Too few permissibility errors for christian_identity_only

perm_n_wrong_before=0. Net correction gain is not statistically meaningful at this denominator.

## [WARN] Too few permissibility errors for generic_reconsider

perm_n_wrong_before=0. Net correction gain is not statistically meaningful at this denominator.

## [WARN] Too few permissibility errors for matched_secular_reflective

perm_n_wrong_before=0. Net correction gain is not statistically meaningful at this denominator.

## [WARN] Too few permissibility errors for moral_checklist

perm_n_wrong_before=0. Net correction gain is not statistically meaningful at this denominator.

## [WARN] Too few permissibility errors for secular_self_examination

perm_n_wrong_before=0. Net correction gain is not statistically meaningful at this denominator.
