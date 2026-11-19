import unittest
from tajweed_review import RULES, normalize_review


class TajweedReviewTests(unittest.TestCase):
    words = [
        {"ayah": 60, "ar": "فَقُلْنَا"},
        {"ayah": 60, "ar": "اضْرِبْ"},
    ]

    def test_every_rule_has_a_visible_status(self):
        result = normalize_review({}, self.words)
        self.assertEqual(len(result["rules"]), 16)
        self.assertTrue(all(r["status"] == "uncertain" for r in result["rules"]))
        self.assertEqual(result["observations"], [])

    def test_observation_requires_time_word_evidence_and_correction(self):
        result = normalize_review({
            "rule_reviews": [{
                "rule_id": 3, "status": "possible_issue", "word_i": 1,
                "time_s": 4.4,
                "evidence": "Possible short vowel substitution",
                "correction": "Compare the second consonant with the reference",
            }]
        }, self.words, duration_s=6.0)
        self.assertEqual(len(result["observations"]), 1)
        self.assertEqual(result["observations"][0]["arabic"], "اضْرِبْ")
        self.assertEqual(result["observations"][0]["time_s"], 4.4)
        self.assertEqual(result["rules"][2]["status"], "possible_issue")

    def test_missing_evidence_does_not_imply_error(self):
        result = normalize_review({
            "rule_reviews": [{
                "rule_id": 1, "status": "possible_issue", "word_i": 0,
                "evidence": "", "correction": "Try again",
            }]
        }, self.words)
        self.assertEqual(result["rules"][0]["status"], "uncertain")
        self.assertEqual(result["observations"], [])

    def test_timestamp_outside_audio_is_rejected(self):
        result = normalize_review({
            "rule_reviews": [{
                "rule_id": 1, "status": "possible_issue", "word_i": 0,
                "time_s": 99,
                "evidence": "Possible letter substitution", "correction": "Repeat"
            }]
        }, self.words, duration_s=5)
        self.assertEqual(result["rules"][0]["status"], "uncertain")

    def test_generic_no_issue_cannot_certify_correct(self):
        result = normalize_review({
            "rule_reviews": [{"rule_id": 15, "status": "no_clear_issue"}]
        }, self.words)
        self.assertEqual(result["rules"][14]["status"], "uncertain")


if __name__ == "__main__":
    unittest.main()
