"""Offline evaluation of locally-run Persian ASR against user-corrected chunks.

This script neither uploads audio nor calls any API. The only way a model
is approved is an explicitly supplied human-corrected reference and an
adequately sized evaluation sample.
"""
from __future__ import annotations
import argparse
import json
import re
import unicodedata
from pathlib import Path

MODELS=("c1tech-cpu","c1tech-cuda","buzz-cpu-native","buzz-cuda-native","qwen-cpu","qwen-cuda","shenava-koochik-cpu")

def normalize(text: str)->str:
    mapping=str.maketrans("يىك٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹","ییک01234567890123456789")
    text=text.translate(mapping).replace("\u200c"," ").replace("\u200d"," ")
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in text).split())

def distance(a,b):
    old=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        nxt=[i]
        for j,y in enumerate(b,1):
            nxt.append(min(old[j]+1,nxt[-1]+1,old[j-1]+(x!=y)))
        old=nxt
    return old[-1]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--reference",type=Path,required=True)
    p.add_argument("--source-dir",type=Path,default=Path(r"C:\ProgramData\ytdlp-bot\asr-four-models"))
    p.add_argument("--max-wer",type=float,default=3.0,help="Provisional acceptance threshold, percentage, default 3")
    p.add_argument("--min-reviewed-chunks",type=int,default=5,help="At least 140 seconds of validated audio")
    p.add_argument("--report",type=Path)
    args=p.parse_args()
    src=json.loads(args.reference.read_text(encoding="utf-8"))
    if src.get("source")!="m8ElotVbO6M" or src.get("segment_seconds")!=28:
        raise ValueError("Incorrect source audio / segment duration for this evaluation")
    gold={int(k):normalize(v) for k,v in src["corrected"].items() if normalize(v)}
    if any(i<0 or i>=19 for i in gold):raise ValueError("Chunk indices must be 0..18")
    ready=len(gold)>=args.min_reviewed_chunks
    report={"source":src["source"],"reviewed_chunks":len(gold),"reviewed_seconds_approx":min(len(gold)*28,530),
            "minimum_review_met":ready,"acceptance_max_wer_percent":args.max_wer,
            "acceptance_limit_note":"Provisional, not user-confirmed. Check critical scientific terms and numbers manually.",
            "models":[]}
    for model in MODELS:
        path=args.source_dir/(model+".txt")
        if not path.is_file():continue
        lines=path.read_text(encoding="utf-8").splitlines()
        if len(lines)!=19:continue
        we=wc=ce=cc=0
        segment_scores=[]
        for i,correct in sorted(gold.items()):
            ref_words=correct.split()
            hyp=normalize(lines[i])
            hyp_words=hyp.split()
            word_errors=distance(ref_words,hyp_words)
            cer_errors=distance(correct.replace(" ",""),hyp.replace(" ",""))
            we+=word_errors;wc+=len(ref_words)
            ce+=cer_errors;cc+=len(correct.replace(" ",""))
            segment_scores.append({"chunk":i,"wer":round(100*word_errors/max(1,len(ref_words)),2)})
        wer=(100*we/wc) if wc else None
        cer=(100*ce/cc) if cc else None
        report["models"].append({"model":model,"wer_percent":round(wer,2) if wer is not None else None,
              "cer_percent":round(cer,2) if cer is not None else None,
              "automated_gate":"numerical_pass_pending_semantic_review" if ready and wer is not None and wer<=args.max_wer else (
                  "fail_threshold" if ready else "insufficient_gold"),
              "by_chunk":segment_scores})
    report["models"].sort(key=lambda v:v["wer_percent"] if v["wer_percent"] is not None else float("inf"))
    output=json.dumps(report,ensure_ascii=False,indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(output,encoding="utf-8")
    print(output)
if __name__=="__main__":main()
