"""Contract regressions for the migration API (run from apps/api: pytest)."""
import pytest
from pydantic import ValidationError

from app.schemas.verse import (
    QuranVerse, VerseWord, TafsirClaim, TafsirSection,
    VerseTafsirResponse, VerseStudyDrillsResponse, Drill,
)


def test_no_invented_root_for_wa_idh():
    with pytest.raises(ValidationError):
        VerseWord(
            word_id="2:60:1", index=1, arabic_uthmani="وَإِذِ",
            literal_gloss="And when", root="و-ذ-ل", root_state="needs_review"
        )
    word = VerseWord(
        word_id="2:60:1", index=1, arabic_uthmani="وَإِذِ",
        literal_gloss="And when", root=None, root_state="not_applicable",
        grammar="conjunction + adverbial noun"
    )
    assert word.root is None


def test_unsupported_source_id_rejected():
    verse = QuranVerse(
        surah=2, ayah=60, arabic_uthmani="وَإِذِ ٱسْتَسْقَىٰ",
        translation="And when Moses requested water",
        translation_attribution="Illustrative test string, not full translation",
    )
    claim = TafsirClaim(
        claim_id="c1", section="meaning_context", text="A claim",
        kind="scholar_paraphrase", evidence_state="source_supported",
        source_ids=["invented_source"]
    )
    with pytest.raises(ValidationError):
        VerseTafsirResponse(
            prompt_version="test", verse=verse, completion="complete",
            sections=[TafsirSection(section="meaning_context", heading="Context", claims=[claim])]
        )


def test_incomplete_drills_cannot_be_marked_complete():
    drill = Drill(
        drill_id="d1", kind="idafah_preposition",
        question="Translate a phrase", expected_answer="Answer",
        explanation="Explanation", text_origin="original_practice"
    )
    with pytest.raises(ValidationError):
        VerseStudyDrillsResponse(
            prompt_version="test", surah=2, ayah=60,
            completion="complete", drills=[drill]
        )
