"""Regression tests for Persian ASR review packaging, independent of GPU/network."""
import importlib.util
import json
from pathlib import Path


def load_builder():
    src=Path(__file__).resolve().parents[1]/"scripts"/"build-persian-asr-offline-review.py"
    spec=importlib.util.spec_from_file_location("review_builder",src)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_requires_complete_19_segments(tmp_path):
    mod=load_builder()
    (tmp_path/"sample.txt").write_text("\n".join(["سلام دنیا"]*19),encoding="utf-8")
    (tmp_path/"sample.json").write_text(json.dumps({"status":"complete","chunks":19,"seconds":42}),encoding="utf-8")
    mod.MODELS={"Sample":(tmp_path,"sample")}
    good=mod.verified_transcripts()
    assert len(good["Sample"]["segments"])==19
    assert good["Sample"]["seconds"]==42
    (tmp_path/"sample.txt").write_text("\n".join(["سلام دنیا"]*18),encoding="utf-8")
    assert not mod.verified_transcripts()
    (tmp_path/"sample.txt").write_text("\n".join(["سلام دنیا"]*19),encoding="utf-8")
    (tmp_path/"sample.json").write_text(json.dumps({"status":"failed","chunks":19}),encoding="utf-8")
    assert not mod.verified_transcripts()


def test_missing_or_empty_chunk_is_rejected(tmp_path):
    mod=load_builder()
    mod.MODELS={"Sample":(tmp_path,"sample")}
    (tmp_path/"sample.txt").write_text("\n".join(["سلام"]*18+[""]),encoding="utf-8")
    (tmp_path/"sample.json").write_text(json.dumps({"status":"complete","chunks":19}),encoding="utf-8")
    assert not mod.verified_transcripts()


def test_inline_page_contains_human_gold_and_no_external_script():
    mod=load_builder()
    assert "__INLINE_DATA__" in mod.PAGE
    assert "persian_asr_gold_reference.json" in mod.PAGE
    assert "WER" in mod.PAGE and "CER" in mod.PAGE
    assert "https://" not in mod.PAGE
    assert "<script src=" not in mod.PAGE
