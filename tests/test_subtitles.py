from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from ytdlp_tool.subtitles import (
    SubtitleUnavailableError,
    select_subtitle,
    validate_youtube_url,
    vtt_to_text,
)


def test_accepts_standard_youtube_urls():
    assert validate_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert validate_youtube_url("https://youtu.be/dQw4w9WgXcQ")


def test_rejects_non_youtube_urls():
    with pytest.raises(ValueError):
        validate_youtube_url("https://example.com/watch?v=dQw4w9WgXcQ")


def test_explicit_language_prefers_manual_subtitles():
    manual = {"en": [{"url": "manual"}]}
    automatic = {"en": [{"url": "auto"}]}
    assert select_subtitle(manual, automatic, "en") == ("en", "manual")


def test_auto_selection_requires_original_language_not_english_or_persian_translation():
    manual = {"fa": [{}], "en": [{}]}
    automatic = {"fa": [{}], "it-orig": [{}], "en": [{}]}
    assert select_subtitle(manual, automatic, "auto", "it") == ("it-orig", "automatic")
    with pytest.raises(SubtitleUnavailableError, match="original"):
        select_subtitle(manual, {"fa": [{}], "en": [{}]}, "auto", "it")


def test_when_original_language_unknown_use_original_tag_only():
    assert select_subtitle({}, {"fa": [{}], "de-orig": [{}]}, "auto") == ("de-orig", "automatic")
    assert select_subtitle({"de": [{}]}, {"fa": [{}], "de-orig": [{}]}, "auto") == ("de", "manual")
    for manual, automatic in [
        ({"fa": [{}]}, {"en": [{}]}),
        ({}, {"en": [{}], "fa": [{}]}),
        ({"it": [{}], "de": [{}]}, {}),
        ({}, {"fa-orig": [{}], "en-orig": [{}]}),
    ]:
        with pytest.raises(SubtitleUnavailableError, match="Original"):
            select_subtitle(manual, automatic, "auto")


def test_declared_nonpersian_speech_uses_manual_original_not_translated_fa():
    assert select_subtitle({"fa": [{}], "de": [{}]}, {"fa": [{}]}, "auto", "de") == ("de", "manual")
    assert select_subtitle({}, {"de": [{}], "fa": [{}]}, "auto", "de") == ("de", "automatic")




def test_original_spoken_language_beats_english_translation():
    assert select_subtitle({"en": [{}]}, {"fa": [{}], "en": [{}]}, "auto", "fa") == ("fa", "automatic")
    assert select_subtitle({"fa": [{}], "en": [{}]}, {"fa": [{}]}, "auto", "fa-IR") == ("fa", "manual")


def test_original_track_precedes_translation_variant():
    manual = {}
    auto = {"en": [{}], "fa": [{}], "fa-orig": [{}], "en-US-orig": [{}]}
    assert select_subtitle(manual, auto, "auto", "fa") == ("fa-orig", "automatic")
    assert select_subtitle(manual, auto, "fa") == ("fa-orig", "automatic")


def test_explicit_language_override_ignores_original_language():
    assert select_subtitle({"fa": [{}], "en": [{}]}, {"fa": [{}]}, "en", "fa") == ("en", "manual")

def test_missing_explicit_language_does_not_fallback():
    with pytest.raises(SubtitleUnavailableError):
        select_subtitle({"it": [{}]}, {"fa": [{}]}, "en")


def test_vtt_to_text_removes_headers_timestamps_and_duplicate_caption_lines():
    content = """WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello world\n\n00:00:01.000 --> 00:00:02.000\nHello world\nNext line\n"""
    assert vtt_to_text(content) == "Hello world\nNext line\n"


def test_vtt_to_srt_numbers_cues_and_uses_comma_milliseconds():
    from ytdlp_tool.subtitles import vtt_to_srt

    content = """WEBVTT\n\n00:00:00.000 --> 00:00:01.250\nHello\n\n00:00:01.250 --> 00:00:02.500\nWorld\n"""
    expected = "1\n00:00:00,000 --> 00:00:01,250\nHello\n\n2\n00:00:01,250 --> 00:00:02,500\nWorld\n"
    assert vtt_to_srt(content) == expected
