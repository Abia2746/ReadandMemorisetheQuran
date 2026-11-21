"""Public Pydantic v2 contracts for the planned Al-Mu'allim verse APIs.

These models are migration contracts. The Streamlit implementation does not yet
serve them. Never trust a language model to assign verified linguistic roots or
authenticated religious quotations without a separately vetted reference.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceState(str, Enum):
    source_supported = "source_supported"  # Supported by a retrieved transcription
    needs_review = "needs_review"          # Attribution/meaning not independently checked
    unavailable = "unavailable"            # Reliable source not available


class CompletionState(str, Enum):
    complete = "complete"
    partial = "partial"
    unavailable = "unavailable"


class RootState(str, Enum):
    lexicon_verified = "lexicon_verified"
    needs_review = "needs_review"
    not_applicable = "not_applicable"


class Reference(StrictModel):
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    author: str
    title: str
    verse: str = Field(pattern=r"^\\d{1,3}:\\d{1,3}$")
    url: HttpUrl
    provenance: Literal["third_party_transcription", "curated_edition", "hadith_database", "quran"]
    edition_verified: bool = False
    snippet: str | None = None
    transcription_hash: str | None = None


class QuranVerse(StrictModel):
    surah: int = Field(ge=1, le=114)
    ayah: int = Field(ge=1, le=286)
    arabic_uthmani: str = Field(min_length=2)
    text_source: str = "Quran.com Uthmani word API"
    translation: str
    translation_attribution: str
    translation_language: str = "en"


class VerseWord(StrictModel):
    word_id: str                     # e.g. "2:60:18", stable across screens
    index: int = Field(ge=1)
    arabic_uthmani: str = Field(min_length=1)
    literal_gloss: str
    transliteration: str | None = None
    root: str | None = None          # Arabic root, validated using a curated lexicon
    root_state: RootState = RootState.needs_review
    grammar: str | None = None       # e.g. "conjunction + adverbial noun"
    root_reference_id: str | None = None

    @model_validator(mode="after")
    def require_root_provenance(self):
        if self.root_state == RootState.not_applicable and self.root:
            raise ValueError("Particles/adverbial no-root entries must not have an invented root")
        if self.root_state == RootState.lexicon_verified and not self.root_reference_id:
            raise ValueError("A verified root requires a lexicon source identifier")
        return self


class TafsirClaim(StrictModel):
    claim_id: str
    section: Literal["meaning_context", "word_fiqh", "reflection"]
    text: str = Field(min_length=1)
    speaker: str | None = None
    kind: Literal["quran_text", "scholar_paraphrase", "early_report", "juristic_position", "reflection"]
    evidence_state: EvidenceState
    source_ids: list[str] = Field(default_factory=list)
    is_verbatim: bool = False
    quote_arabic: str | None = None

    @model_validator(mode="after")
    def require_evidence_for_quotes(self):
        if self.is_verbatim and (not self.quote_arabic or not self.source_ids):
            raise ValueError("Exact quotations require source IDs and original text")
        if re.search(r"\\[SOURCE\\s+\\d+\\]|\\[NOT VERIFIED", self.text):
            raise ValueError("Raw model citation markers must not reach API clients")
        return self


class TafsirSection(StrictModel):
    section: Literal["meaning_context", "word_fiqh", "reflection"]
    heading: str
    claims: list[TafsirClaim] = Field(default_factory=list)


class VerseTafsirResponse(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    prompt_version: str
    verse: QuranVerse
    sections: list[TafsirSection] = Field(default_factory=list)
    sources: list[Reference] = Field(default_factory=list)
    cross_references: list[str] = Field(default_factory=list)
    completion: CompletionState
    public_quality_notes: list[str] = Field(default_factory=list)
    generated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_grounding(self):
        allowed = {s.source_id for s in self.sources}
        for section in self.sections:
            for claim in section.claims:
                if claim.section != section.section:
                    raise ValueError("Claim assigned to a different display section")
                if set(claim.source_ids) - allowed:
                    raise ValueError("Claim references source IDs not returned by retrieval")
                if claim.evidence_state == EvidenceState.source_supported and not claim.source_ids:
                    raise ValueError("Source-supported claims require citations")
        return self


class TafsirVocabulary(StrictModel):
    arabic: str
    root: str | None = None
    root_state: RootState = RootState.needs_review
    root_reference_id: str | None = None
    literal_gloss: str
    source_ids: list[str] = Field(min_length=1)


class Drill(StrictModel):
    drill_id: str
    kind: Literal["idafah_preposition", "root_construction", "reverse_translation"]
    question: str
    expected_answer: str
    explanation: str
    hint: str | None = None
    text_origin: Literal["quran", "retrieved_tafsir", "original_practice"]
    source_ids: list[str] = Field(default_factory=list)
    self_grade: bool = True


class VerseStudyDrillsResponse(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    prompt_version: str
    surah: int = Field(ge=1, le=114)
    ayah: int = Field(ge=1, le=286)
    quran_vocabulary: list[VerseWord] = Field(default_factory=list)
    tafsir_vocabulary: list[TafsirVocabulary] = Field(default_factory=list)
    drills: list[Drill] = Field(default_factory=list)
    sources: list[Reference] = Field(default_factory=list)
    completion: CompletionState
    public_quality_notes: list[str] = Field(default_factory=list)
    generated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_words_and_drills(self):
        ids = [word.word_id for word in self.quran_vocabulary]
        indices = [word.index for word in self.quran_vocabulary]
        if len(set(ids)) != len(ids) or indices != list(range(1, len(indices) + 1)):
            raise ValueError("Quranic vocabulary must have ordered, unique canonical word IDs")
        known_roots = {
            word.root.replace(" ", "").replace("-", "")
            for word in self.quran_vocabulary if word.root and
            word.root_state == RootState.lexicon_verified
        }
        for word in self.tafsir_vocabulary:
            if word.root and word.root.replace(" ", "").replace("-", "") in known_roots:
                raise ValueError("Part B duplicates a verified root from Qur'an Part A")
        allowed_sources = {source.source_id for source in self.sources}
        for entry in self.tafsir_vocabulary:
            if set(entry.source_ids) - allowed_sources:
                raise ValueError("Tafsir vocabulary cites unavailable sources")
        for drill in self.drills:
            if set(drill.source_ids) - allowed_sources:
                raise ValueError("Drill cites unavailable sources")
            if drill.text_origin == "original_practice" and drill.source_ids:
                raise ValueError("Original practice text must not be attributed as scripture")
        if self.completion == CompletionState.complete:
            kinds = {item.kind for item in self.drills}
            if kinds != {"idafah_preposition", "root_construction", "reverse_translation"}:
                raise ValueError("Complete study response must include all three exercise types")
        return self
