"""
validate_outputs.py

Validates model-generated JSON strings according to exact structural
and value constraints using only the Python standard library.
"""

from __future__ import annotations

import json
import math
from typing import Any
import unittest


EXPECTED_KEYS = frozenset({"title", "probability", "reason"})


def validate_outputs(
    raw_outputs: list[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    Validates a list of strings returned by a language model against the schema:
      {"title": string, "probability": number, "reason": string}

    Criteria:
      - Must parse as valid JSON.
      - Root must be a JSON object (dict).
      - Must contain exactly three keys: 'title', 'probability', 'reason'.
      - 'title' must be a string.
      - 'probability' must be a numeric value (int or float, not bool, not NaN/Inf)
        between 0.0 and 1.0 (inclusive).
      - 'reason' must be a string with len <= 200 characters.

    Returns:
      A tuple (valid_entries, failure_counts):
        - valid_entries: list of parsed valid dictionaries.
        - failure_counts: dict mapping failure category to occurrence count.
    """
    valid_entries: list[dict[str, Any]] = []
    failure_counts: dict[str, int] = {}

    def record_failure(kind: str) -> None:
        failure_counts[kind] = failure_counts.get(kind, 0) + 1

    for raw in raw_outputs:
        # Check input type
        if not isinstance(raw, str):
            record_failure("invalid_input_type")
            continue

        # 1. Parse JSON
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            record_failure("json_decode_error")
            continue

        # 2. Must be a JSON Object (dict in Python)
        if not isinstance(parsed, dict):
            record_failure("not_a_json_object")
            continue

        # 3. Exactly the three expected keys
        if set(parsed.keys()) != EXPECTED_KEYS:
            record_failure("invalid_keys")
            continue

        # 4. 'title' must be a string
        if not isinstance(parsed["title"], str):
            record_failure("invalid_title_type")
            continue

        # 5. 'probability' must be a real number (reject bools, NaN, Infinity)
        prob = parsed["probability"]
        # In Python, bool is a subclass of int (isinstance(True, int) is True)
        if isinstance(prob, bool) or not isinstance(prob, (int, float)):
            record_failure("invalid_probability_type")
            continue

        if math.isnan(prob) or math.isinf(prob):
            record_failure("invalid_probability_type")
            continue

        if not (0.0 <= prob <= 1.0):
            record_failure("probability_out_of_range")
            continue

        # 6. 'reason' must be a string and at most 200 characters
        reason = parsed["reason"]
        if not isinstance(reason, str):
            record_failure("invalid_reason_type")
            continue

        if len(reason) > 200:
            record_failure("reason_too_long")
            continue

        # Valid entry
        valid_entries.append(parsed)

    return valid_entries, failure_counts


# =====================================================================
# Unit Test Suite
# =====================================================================


class TestValidateOutputs(unittest.TestCase):
    def test_01_valid_standard(self):
        raw = '{"title": "How to learn Telugu in 30 days", "probability": 0.85, "reason": "Clear value proposition and timeline."}'
        valid, failures = validate_outputs([raw])
        self.assertEqual(len(valid), 1)
        self.assertEqual(failures, {})
        self.assertEqual(valid[0]["title"], "How to learn Telugu in 30 days")
        self.assertEqual(valid[0]["probability"], 0.85)

    def test_02_valid_boundary_values(self):
        # Boundary cases: probability 0.0 and 1.0; reason exactly 200 characters
        boundary_min = json.dumps({"title": "Min Prob", "probability": 0.0, "reason": "X" * 200})
        boundary_max = json.dumps({"title": "Max Prob", "probability": 1.0, "reason": ""})
        valid, failures = validate_outputs([boundary_min, boundary_max])
        self.assertEqual(len(valid), 2)
        self.assertEqual(failures, {})

    def test_03_naive_breaker_boolean_probability(self):
        # Naive implementations doing isinstance(val, (int, float)) and 0 <= val <= 1
        # will erroneously accept boolean True because in Python bool subclasses int (True == 1).
        raw = '{"title": "Sneaky Boolean", "probability": true, "reason": "Looks good"}'
        valid, failures = validate_outputs([raw])
        self.assertEqual(len(valid), 0)
        self.assertEqual(failures.get("invalid_probability_type"), 1)

    def test_04_naive_breaker_json_array_root(self):
        # Naive implementations doing parsed = json.loads(...) followed by parsed.keys()
        # crash with AttributeError: 'list' object has no attribute 'keys'.
        raw = '[{"title": "Array Root", "probability": 0.5, "reason": "Inside an array"}]'
        valid, failures = validate_outputs([raw])
        self.assertEqual(len(valid), 0)
        self.assertEqual(failures.get("not_a_json_object"), 1)

    def test_05_naive_breaker_non_string_reason_type(self):
        # Naive implementations doing len(data["reason"]) > 200 crash with
        # TypeError: object of type 'int' has no len().
        raw = '{"title": "Numeric Reason", "probability": 0.7, "reason": 12345}'
        valid, failures = validate_outputs([raw])
        self.assertEqual(len(valid), 0)
        self.assertEqual(failures.get("invalid_reason_type"), 1)

    def test_06_naive_breaker_json_null_root(self):
        # Naive implementations crash with AttributeError: 'NoneType' object has no attribute 'keys'.
        raw = "null"
        valid, failures = validate_outputs([raw])
        self.assertEqual(len(valid), 0)
        self.assertEqual(failures.get("not_a_json_object"), 1)

    def test_07_invalid_syntax_json_decode_error(self):
        raw = '{"title": "Broken JSON", "probability": 0.6, "reason": "missing brace"'
        valid, failures = validate_outputs([raw])
        self.assertEqual(len(valid), 0)
        self.assertEqual(failures.get("json_decode_error"), 1)

    def test_08_invalid_keys_missing_or_extra(self):
        # Missing 'reason', extra 'score'
        raw = '{"title": "Missing Field", "probability": 0.5, "score": 99}'
        valid, failures = validate_outputs([raw])
        self.assertEqual(len(valid), 0)
        self.assertEqual(failures.get("invalid_keys"), 1)

    def test_09_probability_out_of_range(self):
        raw_high = '{"title": "Over 1", "probability": 1.05, "reason": "Exceeds 1.0"}'
        raw_low = '{"title": "Negative", "probability": -0.01, "reason": "Below 0.0"}'
        valid, failures = validate_outputs([raw_high, raw_low])
        self.assertEqual(len(valid), 0)
        self.assertEqual(failures.get("probability_out_of_range"), 2)

    def test_10_reason_too_long_201_characters(self):
        raw = json.dumps({"title": "Long Reason", "probability": 0.5, "reason": "A" * 201})
        valid, failures = validate_outputs([raw])
        self.assertEqual(len(valid), 0)
        self.assertEqual(failures.get("reason_too_long"), 1)

    def test_11_batch_invariant(self):
        # Ensure that valid count + sum of failures equals the total input length
        batch = [
            '{"title": "Good", "probability": 0.5, "reason": "Valid"}',
            '{"title": "Bad Prob", "probability": 2.0, "reason": "Out of range"}',
            "not json",
            '{"title": 123, "probability": 0.5, "reason": "Title not string"}',
            '{"title": "True Prob", "probability": true, "reason": "Boolean trap"}',
        ]
        valid, failures = validate_outputs(batch)
        self.assertEqual(len(valid) + sum(failures.values()), len(batch))
        self.assertEqual(len(valid), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
