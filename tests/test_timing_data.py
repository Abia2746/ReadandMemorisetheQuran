import unittest
from timing_data import matched_word_segments


class SourceMatchedTimingsTests(unittest.TestCase):
    def test_yasser_aligned_2_60_uses_32_words(self):
        segments = matched_word_segments(
            2, 60, "Yasser_Ad-Dussary_128kbps", 32, start_index=11
        )
        self.assertEqual(len(segments), 32)
        self.assertEqual(segments[0]["word_idx"], 11)
        self.assertEqual(segments[0]["start"], 0)
        self.assertEqual(segments[1]["word_idx"], 12)
        self.assertEqual(segments[-1]["word_idx"], 42)
        self.assertGreater(segments[-1]["end"], 20000)

    def test_never_use_yasser_on_another_folder(self):
        self.assertEqual(
            matched_word_segments(2, 60, "Alafasy_128kbps", 32), []
        )

    def test_count_mismatch_disables_word_following(self):
        self.assertEqual(
            matched_word_segments(2, 60, "Yasser_Ad-Dussary_128kbps", 31), []
        )

    def test_source_mishary64_exists(self):
        segments = matched_word_segments(2, 60, "Alafasy_64kbps", 32)
        self.assertEqual(len(segments), 32)
        self.assertTrue(all(s["end"] > s["start"] for s in segments))

    def test_missing_ayah_does_not_fabricate_timestamps(self):
        self.assertEqual(
            matched_word_segments(2, 999, "Yasser_Ad-Dussary_128kbps", 32), []
        )


if __name__ == "__main__":
    unittest.main()
