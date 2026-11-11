import unittest
from datetime import datetime
from decimal import Decimal

from av_lims.domain import (
    TRANSITIONS,
    LabRuleError,
    calculate,
    digest,
    evaluate_conformity,
    process_results,
    schedule_window,
    validate_method,
)


class TestLaboratoryRules(unittest.TestCase):
    def test_calculations_use_decimal_and_half_up_rounding(self):
        outputs = [{"code": "result", "expression": "x / y", "precision": 2, "uom": "MPa"}]
        rows = process_results(
            [{"code": "x"}, {"code": "y"}],
            outputs,
            [{"code": "x", "value": "2.345"}, {"code": "y", "value": "1"}],
        )
        self.assertEqual(rows[0]["value"], 2.35)

    def test_zero_is_valid_but_unrecorded_zero_is_not(self):
        outputs = [{"code": "result", "expression": "x", "precision": 0}]
        self.assertEqual(
            process_results([{"code": "x"}], outputs, [{"code": "x", "value": 0}])[0]["value"], 0
        )
        with self.assertRaises(LabRuleError):
            process_results([{"code": "x"}], outputs, [{"code": "x", "value": 0, "recorded": False}])

    def test_missing_unknown_and_duplicate_observations_are_rejected(self):
        for observations in [
            [],
            [{"code": "unknown", "value": 1}],
            [{"code": "x", "value": 1}, {"code": "x", "value": 2}],
        ]:
            with self.subTest(observations=observations), self.assertRaises(LabRuleError):
                process_results(
                    [{"code": "x"}], [{"code": "out", "expression": "x", "precision": 0}], observations
                )

    def test_safe_functions(self):
        self.assertEqual(calculate("mean(x, y) + sqrt(9)", {"x": 1, "y": 3}), Decimal(5))
        self.assertEqual(calculate("min(x, y) + max(x, y)", {"x": 1, "y": 3}), Decimal(4))

    def test_unsafe_syntax_rejected(self):
        for expression in [
            "__import__('os')",
            "x.real",
            "x[0]",
            "[x for x in y]",
            "(lambda: 1)()",
            "x()",
            "mean()",
            "mean(x=1)",
        ]:
            with self.subTest(expression=expression), self.assertRaises(LabRuleError):
                validate_method([{"code": "x"}], [{"code": "out", "expression": expression, "precision": 1}])

    def test_nonfinite_division_zero_and_large_exponents_rejected(self):
        for expression, values in [
            ("x / 0", {"x": 1}),
            ("x ** 1000000", {"x": 2}),
            ("x", {"x": "NaN"}),
            ("x", {"x": "Infinity"}),
            ("sqrt(x)", {"x": -1}),
        ]:
            with self.subTest(expression=expression), self.assertRaises(LabRuleError):
                calculate(expression, values)

    def test_distinct_codes_and_precision(self):
        for code, precision in [("x", 1), ("out", -1), ("out", 10), ("bad-code", 1)]:
            with self.subTest(code=code, precision=precision), self.assertRaises(LabRuleError):
                validate_method([{"code": "x"}], [{"code": code, "expression": "x", "precision": precision}])

    def test_conformity_is_separate_and_boundary_inclusive(self):
        limits = [{"code": "strength", "has_lower": 1, "lower_limit": 30, "has_upper": 1, "upper_limit": 40}]
        for value, expected in [(29.99, "Fail"), (30, "Pass"), (40, "Pass"), (40.01, "Fail")]:
            rows = evaluate_conformity([{"code": "strength", "value": value}], limits)
            self.assertEqual(rows[0]["outcome"], expected)
            self.assertEqual(rows[0]["value"], str(value))

    def test_invalid_specifications_rejected(self):
        for limits in [
            [],
            [{"code": "x"}],
            [{"code": "missing", "has_lower": 1, "lower_limit": 0}],
            [{"code": "x", "has_lower": 1, "lower_limit": 2, "has_upper": 1, "upper_limit": 1}],
        ]:
            with self.subTest(limits=limits), self.assertRaises(LabRuleError):
                evaluate_conformity([{"code": "x", "value": 1}], limits)

    def test_age_schedule_and_tolerance(self):
        due, start, end = schedule_window(datetime(2026, 1, 1, 8), 7 * 24, 2, 4)
        self.assertEqual(due, datetime(2026, 1, 8, 8))
        self.assertEqual(start, datetime(2026, 1, 8, 6))
        self.assertEqual(end, datetime(2026, 1, 8, 12))
        for args in [(0, 0, 0), (1, -1, 0), (1, 2, 0)]:
            with self.assertRaises(LabRuleError):
                schedule_window(datetime(2026, 1, 1), *args)

    def test_snapshot_digest_detects_changes_and_ignores_key_order(self):
        self.assertEqual(digest({"a": 1, "b": 2}), digest({"b": 2, "a": 1}))
        self.assertNotEqual(digest({"value": 1}), digest({"value": 2}))

    def test_release_roles_are_separated(self):
        self.assertEqual(TRANSITIONS["Lab QA Review"]["Accept"][2], "manager")
        self.assertEqual(TRANSITIONS["Lab Result Report"]["Approve"][2], "approver")
        self.assertEqual(TRANSITIONS["Lab Result Dispatch"]["Issue"][2], "lead")


if __name__ == "__main__":
    unittest.main()
