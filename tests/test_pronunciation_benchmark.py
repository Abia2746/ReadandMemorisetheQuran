import unittest
from pronunciation_benchmark import evaluate_teacher_labels, teacher_review_release_gate


class BenchmarkSafetyTests(unittest.TestCase):
    def test_false_alarm_and_abstention_are_not_hidden(self):
        rows = [
            {"sample_id": "a", "speaker_id":"s1", "device":"ipad",
             "phenomenon":"kasrah", "truth":"issue", "prediction":"issue"},
            {"sample_id": "b", "speaker_id":"s1", "device":"ipad",
             "phenomenon":"fathah", "truth":"correct", "prediction":"issue"},
            {"sample_id": "c", "speaker_id":"s2", "device":"android",
             "phenomenon":"dammah", "truth":"issue", "prediction":"correct"},
            {"sample_id": "d", "speaker_id":"s2", "device":"android",
             "phenomenon":"madd", "truth":"correct", "prediction":"correct"},
            {"sample_id": "e", "speaker_id":"s2", "device":"android",
             "phenomenon":"ghunnah", "truth":"issue", "prediction":"uncertain"},
        ]
        result = evaluate_teacher_labels(rows)
        self.assertEqual(result["counts"], {
            "tp":1,"fp":1,"tn":1,"fn":1,"abstain":1})
        self.assertEqual(result["coverage"],0.8)
        self.assertEqual(result["precision_of_error_flags"],0.5)
        self.assertEqual(result["error_detection_recall_assessed_only"],0.5)
        self.assertEqual(result["false_alarm_rate_assessed_only"],0.5)
        self.assertFalse(teacher_review_release_gate(result)["engineering_gate_passed"])

    def test_empty_or_synthetic_high_score_cannot_claim_teacher_approval(self):
        empty = evaluate_teacher_labels([])
        self.assertFalse(teacher_review_release_gate(empty)["engineering_gate_passed"])
        rows = [
            {"sample_id":str(i),"device":"iphone","phenomenon":"vowel",
             "truth":"issue" if i%2 else "correct",
             "prediction":"issue" if i%2 else "correct"}
            for i in range(600)
        ]
        high = teacher_review_release_gate(evaluate_teacher_labels(rows))
        self.assertFalse(high["teacher_level_accuracy_established"])
        # Passing an engineering threshold would still require a human audit.
        self.assertTrue(high["engineering_gate_passed"])

    def test_duplicate_samples_and_missing_truth_are_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_teacher_labels([
                {"sample_id":"1","truth":"issue","prediction":"issue"},
                {"sample_id":"1","truth":"correct","prediction":"correct"}])
        with self.assertRaises(ValueError):
            evaluate_teacher_labels([
                {"sample_id":"1","truth":"perhaps","prediction":"issue"}])


if __name__ == "__main__":
    unittest.main()
