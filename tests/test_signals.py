from __future__ import annotations

import unittest

from loopledger.signals import automation_reasons, is_automated, request_signal
from tests.helpers import raw_message


class SignalTests(unittest.TestCase):
    def test_explicit_request_and_deadline_are_explained(self) -> None:
        signal = request_signal(raw_message(body="Could you review this by Friday?"))
        self.assertGreaterEqual(signal.score, 7)
        self.assertIn("explicit_request", signal.reasons)
        self.assertIn("deadline_language", signal.reasons)
        self.assertIn("question_mark", signal.reasons)

    def test_question_without_request_scores_below_default_threshold(self) -> None:
        signal = request_signal(raw_message(body="Thoughts?"))
        self.assertEqual(signal.score, 2)
        self.assertEqual(signal.reasons, ("question_mark",))

    def test_decision_language_is_detected(self) -> None:
        signal = request_signal(raw_message(body="Approval is needed for the release."))
        self.assertEqual(signal.score, 2)
        self.assertIn("decision_or_review", signal.reasons)

    def test_follow_up_language_is_detected(self) -> None:
        signal = request_signal(raw_message(body="Following up because this is still pending."))
        self.assertEqual(signal.score, 2)
        self.assertIn("follow_up_language", signal.reasons)

    def test_chinese_request_is_detected(self) -> None:
        signal = request_signal(raw_message(body="麻烦确认是否可以在本周完成？请回复。"))
        self.assertGreaterEqual(signal.score, 8)
        self.assertIn("explicit_request", signal.reasons)

    def test_courtesy_only_is_excluded(self) -> None:
        signal = request_signal(raw_message(body="Thank you!"))
        self.assertEqual(signal.score, 0)
        self.assertEqual(signal.exclusions, ("courtesy_only",))

    def test_empty_content_is_excluded(self) -> None:
        signal = request_signal(raw_message(body="", subject=""))
        self.assertEqual(signal.exclusions, ("empty_content",))

    def test_quoted_request_does_not_count(self) -> None:
        signal = request_signal(
            raw_message(body="Thanks\nOn Monday, Morgan wrote:\nCould you reply?")
        )
        self.assertEqual(signal.score, 0)

    def test_automation_headers_are_explained(self) -> None:
        message = raw_message(
            auto_submitted="auto-generated",
            precedence="bulk",
            list_id="list.example",
        )
        reasons = automation_reasons(message)
        self.assertEqual(reasons[:3], ("auto_submitted", "bulk_precedence", "list_id"))
        self.assertTrue(is_automated(message))

    def test_automated_sender_subject_and_delivery_status(self) -> None:
        message = raw_message(
            sender="no-reply@service.example",
            subject="Automatic reply",
            content_types=("message/delivery-status",),
        )
        reasons = automation_reasons(message)
        self.assertIn("automated_sender", reasons)
        self.assertIn("automated_subject", reasons)
        self.assertIn("delivery_status", reasons)

    def test_normal_human_message_is_not_automated(self) -> None:
        self.assertFalse(is_automated(raw_message()))


if __name__ == "__main__":
    unittest.main()
