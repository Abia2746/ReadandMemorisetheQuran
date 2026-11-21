"""Safeguards for the forever-free Qur'an reader and its 6,236 Hafs ayahs."""
from app.services.quran_metadata import AYAHS, SURAHS, valid_verse
from app.routers import quran as public_quran


def test_all_114_surahs_and_6236_ayahs():
    assert len(SURAHS) == 114
    assert len(AYAHS) == 115
    assert sum(AYAHS) == 6236
    assert valid_verse(1, 7)
    assert valid_verse(2, 286)
    assert valid_verse(114, 6)
    assert not valid_verse(1, 8)
    assert not valid_verse(2, 287)
    assert not valid_verse(114, 7)


def test_core_reader_routes_never_require_subscription_or_login():
    paths = {r.path: r for r in public_quran.router.routes}
    expected = {
        "/api/quran/chapters",
        "/api/quran/reciters",
        "/api/quran/verse/{surah}/{ayah}",
        "/api/quran/passage/{surah}/{start}",
        "/api/quran/timings/{surah}/{ayah}",
    }
    assert expected.issubset(paths)
    for route in expected:
        # FastAPI's dependency graph is empty for public Quran endpoints.
        assert not paths[route].dependant.dependencies


def test_reciter_folder_matches_licensed_timing_tracks():
    assert public_quran.RECITERS["dosari"]["folder"] == "Yasser_Ad-Dussary_128kbps"
    assert public_quran.RECITERS["alafasy"]["folder"] == "Alafasy_64kbps"
