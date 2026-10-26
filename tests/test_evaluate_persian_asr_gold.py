"""Deterministic tests for local-only Persian ASR gold-reference scoring."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"evaluate-persian-asr-gold.py"

def _load():
    spec=importlib.util.spec_from_file_location("persian_asr_gold",SCRIPT)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_farsi_normalizer_unifies_keyboard_variants():
    mod=_load()
    assert mod.normalize("مي‌شود و كلمه ۱۲۳!") == "می شود و کلمه 123"
    assert mod.normalize("عدد ١٢") == "عدد 12"

def test_edit_distance_words():
    mod=_load()
    assert mod.distance(["الف","ب"],["الف","ج"])==1
    assert mod.distance([],["الف","ب"])==2
    assert mod.distance(["الف","ب"],["الف","ب"])==0

def test_scoring_needs_enough_hand_corrected_chunks(tmp_path):
    data=tmp_path/"raw"
    data.mkdir()
    (data/"c1tech-cuda.txt").write_text(("سلام و درود\n"*19),encoding="utf-8")
    gold=tmp_path/"gold.json"
    gold.write_text(json.dumps({"source":"m8ElotVbO6M","segment_seconds":28,
         "corrected":{str(i):"سلام و درود" for i in range(5)}},ensure_ascii=False),encoding="utf-8")
    r=subprocess.run([sys.executable,str(SCRIPT),"--reference",str(gold),
          "--source-dir",str(data)],text=True,capture_output=True,check=True)
    output=json.loads(r.stdout)
    assert output["minimum_review_met"] is True
    assert output["models"][0]["wer_percent"]==0.0
    assert output["models"][0]["automated_gate"]=="numerical_pass_pending_semantic_review"

    gold.write_text(json.dumps({"source":"m8ElotVbO6M","segment_seconds":28,
         "corrected":{"0":"سلام و درود"}}),encoding="utf-8")
    r=subprocess.run([sys.executable,str(SCRIPT),"--reference",str(gold),
          "--source-dir",str(data)],text=True,capture_output=True,check=True)
    result=json.loads(r.stdout)
    assert result["minimum_review_met"] is False
    assert result["models"][0]["automated_gate"]=="insufficient_gold"
