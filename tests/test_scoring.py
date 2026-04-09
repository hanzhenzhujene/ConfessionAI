import unittest

from offtherails_pilot.parsing import try_parse_first_pass, try_parse_revision
from offtherails_pilot.dataset_checks import evaluate_analysis_profile
from offtherails_pilot.prompts import REVISION_CONDITIONS
from offtherails_pilot.rationale_coding import code_rationale
from offtherails_pilot.scoring import (
    add_scoring_fields,
    binary_label_from_gold_mean,
    status_against_gold,
    summarize_rows,
)


class ParsingTests(unittest.TestCase):
    def test_first_pass_json_parses(self):
        status, parsed = try_parse_first_pass(
            '{"permissibility_agreement": 5, "negative_outcome_intended_agreement": 2, "confidence": 4, "rationale_short": "The harm is incidental, not intended."}',
            rating_scale_max=5,
        )
        self.assertEqual(status, "ok")
        self.assertEqual(parsed["confidence"], 4)

    def test_free_form_text_is_rejected(self):
        status, _parsed = try_parse_first_pass(
            'Here is the answer: {"permissibility_agreement": 5, "negative_outcome_intended_agreement": 2, "confidence": 4, "rationale_short": "Too much prose."}',
            rating_scale_max=5,
        )
        self.assertEqual(status, "invalid")

    def test_revision_json_parses(self):
        status, parsed = try_parse_revision(
            '{"first_focus": "outcome", "neglected_factor": "intention", "permissibility_agreement": 3, "negative_outcome_intended_agreement": 5, "confidence": 3, "rationale_short": "I first emphasized outcomes and neglected intention."}',
            rating_scale_max=5,
            require_reflection_fields=True,
        )
        self.assertEqual(status, "ok")
        self.assertEqual(parsed["neglected_factor"], "intention")

    def test_revision_minimal_json_parses_without_reflection_fields(self):
        status, parsed = try_parse_revision(
            '{"permissibility_agreement": 3, "negative_outcome_intended_agreement": 5, "confidence": 3, "rationale_short": "I reconsidered the case and revised the judgment."}',
            rating_scale_max=5,
        )
        self.assertEqual(status, "ok")
        self.assertEqual(parsed["first_focus"], "")
        self.assertEqual(parsed["neglected_factor"], "")

    def test_revision_enum_normalization(self):
        status, parsed = try_parse_revision(
            '{"first_focus": "means_side_effect", "neglected_factor": "side_effect", "permissibility_agreement": 3, "negative_outcome_intended_agreement": 2, "confidence": 3, "rationale_short": "I initially focused on the structure and then normalized the side effect label."}',
            rating_scale_max=5,
            require_reflection_fields=True,
        )
        self.assertEqual(status, "ok")
        self.assertEqual(parsed["neglected_factor"], "means_side_effect")

    def test_revision_key_aliases(self):
        status, parsed = try_parse_revision(
            '{"first_focus": "outcome", "neglected_factor": "none", "permissibility_agreement": 5, "negative_outcome_intention_agreement": 2, "confidence": 4, "rationale_short": "The alias key should still parse correctly."}',
            rating_scale_max=5,
            require_reflection_fields=True,
        )
        self.assertEqual(status, "ok")
        self.assertEqual(parsed["negative_outcome_intended_agreement"], 2)

    def test_revision_missing_reflection_fields_fails_when_required(self):
        status, _parsed = try_parse_revision(
            '{"permissibility_agreement": 3, "negative_outcome_intended_agreement": 5, "confidence": 3, "rationale_short": "I reconsidered the case and revised the judgment."}',
            rating_scale_max=5,
            require_reflection_fields=True,
        )
        self.assertEqual(status, "invalid")


class ScoringTests(unittest.TestCase):
    def test_binary_gold_thresholds(self):
        self.assertEqual(binary_label_from_gold_mean(1.9, scale_max=5), (0, 1))
        self.assertEqual(binary_label_from_gold_mean(4.0, scale_max=5), (1, 1))
        self.assertEqual(binary_label_from_gold_mean(3.0, scale_max=5), (None, 0))
        self.assertEqual(binary_label_from_gold_mean(5.0, scale_max=7), (1, 1))

    def test_status_against_gold(self):
        self.assertEqual(status_against_gold(5, 1, 1, scale_max=5), "correct")
        self.assertEqual(status_against_gold(2, 1, 1, scale_max=5), "wrong")
        self.assertEqual(status_against_gold(3, 1, 1, scale_max=5), "ambiguous_excluded")
        self.assertEqual(status_against_gold(4, None, 0, scale_max=7), "ambiguous_excluded")

    def test_add_scoring_fields(self):
        row = {
            "permissibility_first": 2,
            "permissibility_final": 5,
            "negative_intended_first": 2,
            "negative_intended_final": 5,
            "gold_perm_mean": 4.8,
            "gold_intent_mean": 4.2,
            "gold_scale_max": 5,
            "gold_perm_binary": 1,
            "gold_intent_binary": 1,
            "binary_eval_perm": 1,
            "binary_eval_intent": 1,
            "parse_status_revision": "ok",
        }
        scored = add_scoring_fields(row)
        self.assertEqual(scored["perm_status_before"], "wrong")
        self.assertEqual(scored["perm_status_after"], "correct")
        self.assertEqual(scored["perm_corrected"], 1)
        self.assertEqual(scored["intent_corrected"], 1)
        self.assertEqual(scored["changed_any_answer"], 1)
        self.assertEqual(scored["perm_distance_improved"], 1)

    def test_summarize_rows_continuous_fields(self):
        rows = [
            {
                "revision_condition_id": "generic_reconsider",
                "parse_status_revision": "ok",
                "perm_status_before": "correct",
                "perm_status_after": "correct",
                "intent_status_before": "correct",
                "intent_status_after": "correct",
                "perm_corrected": 0,
                "perm_flipped_wrong": 0,
                "intent_corrected": 0,
                "intent_flipped_wrong": 0,
                "changed_any_answer": 1,
                "perm_distance_improved": 1,
                "perm_distance_worsened": 0,
                "perm_distance_first": 1.0,
                "perm_distance_final": 0.0,
                "intent_distance_improved": 0,
                "intent_distance_worsened": 1,
                "intent_distance_first": 0.0,
                "intent_distance_final": 1.0,
            }
        ]
        summary = summarize_rows(rows, ["revision_condition_id"])[0]
        self.assertEqual(summary["perm_distance_net_improvement_rate"], 1.0)
        self.assertEqual(summary["perm_distance_mean_delta"], -1.0)
        self.assertEqual(summary["intent_distance_net_improvement_rate"], -1.0)
        self.assertEqual(summary["intent_distance_mean_delta"], 1.0)


class DatasetChecksTests(unittest.TestCase):
    def test_binary_primary_rejects_one_sided_dataset(self):
        issues = evaluate_analysis_profile(
            [
                {
                    "gold_scale_max": "5",
                    "gold_perm_binary": "1",
                    "gold_intent_binary": "0",
                    "binary_eval_perm": "1",
                    "binary_eval_intent": "1",
                }
            ],
            analysis_profile="binary_primary",
        )
        self.assertTrue(any("one-sided" in issue for issue in issues))

    def test_continuous_primary_accepts_benchmark_aligned_one_sided_dataset(self):
        issues = evaluate_analysis_profile(
            [
                {
                    "gold_scale_max": "5",
                    "gold_perm_binary": "1",
                    "gold_intent_binary": "0",
                    "binary_eval_perm": "1",
                    "binary_eval_intent": "1",
                }
            ],
            analysis_profile="continuous_primary",
        )
        self.assertEqual(issues, [])


class RationaleCodingTests(unittest.TestCase):
    def test_rationale_keyword_coding(self):
        codes = code_rationale(
            "I initially focused on outcomes and overlooked intention. The harm was avoidable and used as a means."
        )
        self.assertEqual(codes["outcome"], 1)
        self.assertEqual(codes["intention"], 1)
        self.assertEqual(codes["structure"], 1)
        self.assertEqual(codes["responsibility"], 1)
        self.assertEqual(codes["meta_revision"], 1)


class PromptConditionTests(unittest.TestCase):
    def test_matched_secular_reflective_condition_exists(self):
        conditions = {
            condition["revision_condition_id"]: condition for condition in REVISION_CONDITIONS
        }
        self.assertIn("matched_secular_reflective", conditions)
        self.assertIn("christian_examen", conditions)
        matched_words = len(
            conditions["matched_secular_reflective"]["condition_instruction"].split()
        )
        examen_words = len(
            conditions["christian_examen"]["condition_instruction"].split()
        )
        self.assertEqual(
            conditions["matched_secular_reflective"]["condition_instruction"].count("."),
            conditions["christian_examen"]["condition_instruction"].count("."),
        )
        self.assertLessEqual(abs(matched_words - examen_words), 2)


if __name__ == "__main__":
    unittest.main()
