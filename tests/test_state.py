from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from loopledger.state import LoopState, load_state


class StateTests(unittest.TestCase):
    def test_none_returns_empty_state(self) -> None:
        self.assertEqual(load_state(None), LoopState())

    def test_valid_state_is_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "ignored": ["loop-a"],
                        "resolved": ["<message@example>"],
                        "snoozed_until": {"loop-b": "2026-02-10"},
                    }
                ),
                encoding="utf-8",
            )
            state = load_state(path)
        self.assertEqual(state.ignored, frozenset({"loop-a"}))
        self.assertEqual(state.resolved, frozenset({"<message@example>"}))
        self.assertEqual(state.snoozed_until["loop-b"], datetime(2026, 2, 10, tzinfo=UTC))

    def test_missing_state_file_is_actionable(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not exist"):
            load_state(Path("missing-state.json"))

    def test_invalid_json_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not valid JSON"):
                load_state(path)

    def test_schema_and_field_types_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            path.write_text('{"version": 2}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "version set to 1"):
                load_state(path)
            path.write_text('{"version": 1, "ignored": "loop-a"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "array of IDs"):
                load_state(path)
            path.write_text('{"version": 1, "snoozed_until": []}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must map"):
                load_state(path)

    def test_invalid_snooze_date_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            path.write_text(
                '{"version": 1, "snoozed_until": {"loop": "not-a-date"}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "invalid snooze"):
                load_state(path)


if __name__ == "__main__":
    unittest.main()
