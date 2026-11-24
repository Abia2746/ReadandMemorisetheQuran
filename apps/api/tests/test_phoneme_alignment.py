"""Tests for alignment accuracy and honest rule-metric reporting."""
import pytest
from app.services.phoneme_alignment import align_phone_sequence, align_approved_verse
from app.services.phoneme_evaluation import phoneme_error_rate, evaluate_human_labelled_errors


def test_exact_sequence_never_certifies_tajweed():
    result = align_phone_sequence(["b", "a", "s"], ["b", "a", "s"])
    assert result["edit_distance"] == 0
    assert result["verified_tajweed"] is False
    assert all(x["outcome"] == "uncertain" for x in result["events"])


def test_one_short_vowel_substitution_is_candidate_only():
    result = align_phone_sequence(["b", "a", "s"], ["b", "i", "s"])
    assert result["edit_distance"] == 1
    assert result["events"][1]["kind"] == "substitution_candidate"
    assert result["events"][1]["expected"] == "a"
    assert result["events"][1]["observed"] == "i"
    assert result["events"][1]["outcome"] == "uncertain"


def test_shaddah_doubled_consonant_candidate():
    result = align_phone_sequence(["a", "d", "d", "a"], ["a", "d", "a"])
    assert result["edit_distance"] == 1
    assert any(e["kind"] == "deletion_candidate" for e in result["events"])


def test_madd_long_vowel_candidate():
    result = align_phone_sequence(["a", "aa", "m"], ["a", "m"])
    assert result["edit_distance"] == 1


def test_ghunnah_symbol_candidate():
    result = align_phone_sequence(["n~", "a"], ["n", "a"])
    assert result["edit_distance"] == 1


def test_makharij_consonant_candidate():
    result = align_phone_sequence(["s_emph", "a"], ["s", "a"])
    assert result["edit_distance"] == 1


def test_reference_must_be_trusted_server_entry():
    result = align_approved_verse({}, 1, 1, [{"phone": "a"}])
    assert result["status"] == "reference_unavailable"
    result = align_approved_verse(
        {"verse_phone_references": {"1:1": ["b", "i"]}}, 1, 1,
        [{"phone": "b", "approx_start_ms": 0, "approx_end_ms": 80},
         {"phone": "i", "approx_start_ms": 80, "approx_end_ms": 150}]
    )
    assert result["status"] == "candidate_alignment"
    assert result["verified_tajweed"] is False


def test_per_counts_edits():
    result = phoneme_error_rate(["a", "b", "c"], ["a", "d", "c"])
    assert result["per"] == pytest.approx(1/3)


def test_metrics_not_fabricated_for_unmeasured_features():
    result = evaluate_human_labelled_errors([
        {"feature": "fathah", "teacher_error": True, "model_flag": True,
         "heldout_speaker": "S1"},
        {"feature": "fathah", "teacher_error": False, "model_flag": True,
         "heldout_speaker": "S2"},
        {"feature": "fathah", "teacher_error": False, "model_flag": False,
         "heldout_speaker": "S3"},
    ])
    assert result["features"]["fathah"]["false_corrections"] == 1
    assert result["features"]["fathah"]["precision"] == .5
    assert result["features"]["kasrah"]["status"] == "not_evaluated"
    assert result["certified"] is False


def test_no_independent_labels_means_no_accuracy_claim():
    with pytest.raises(ValueError):
        evaluate_human_labelled_errors([])


def test_rolling_window_excludes_unheard_verse_edges():
    ref = {"verse_phone_references": {"1:1": ["a", "b", "c", "d"]}}
    result = align_approved_verse(ref, 1, 1, [{"phone": "b"}, {"phone": "c"}])
    assert [e["reference_index"] for e in result["events"]] == [1, 2]
    assert result["edit_distance"] == 0


@pytest.mark.parametrize("heard", [[], ["a"], ["x"], ["a", "b"]])
def test_unlocated_or_repeated_windows_abstain(heard):
    ref = {"verse_phone_references": {"1:1": ["a", "b", "a", "b"]}}
    result = align_approved_verse(ref, 1, 1, [{"phone": p} for p in heard])
    assert result["status"] == "uncertain_location"
    assert result["events"] == []


def test_abstention_counts_against_end_to_end_error_detection():
    rows = [dict(feature="madd", teacher_error=True, heldout_speaker="test", model_flag=flag)
            for flag in [True, None]]
    result = evaluate_human_labelled_errors(rows)["features"]["madd"]
    assert result["recall"] == 1
    assert result["coverage"] == result["end_to_end_recall"] == 0.5


def test_phone_confusions_include_correct_and_substituted_tokens():
    rates = phoneme_error_rate(["ب", "َ", "ت", "ُ"], ["ب", "ِ", "ت", "ُ"])
    assert rates["aligned_phone_pairs"]["َ"] == {"ِ": 1}
    assert rates["aligned_phone_pairs"]["ب"] == {"ب": 1}


def test_double_review_counts_only_independently_scored_rows():
    rows = [dict(feature="ghunnah", teacher_error=True, model_flag=None,
                 heldout_speaker="fixture", second_teacher_error=value)
            for value in [None, True, False]]
    score = evaluate_human_labelled_errors(rows)["features"]["ghunnah"]
    assert score["double_reviewed"] == 2
    assert score["teacher_disagreement_rate"] == .5
    assert score["precision"] is None
