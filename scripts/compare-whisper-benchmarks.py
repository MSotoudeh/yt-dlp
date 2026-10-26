from pathlib import Path
import json, difflib, re
root=Path(r'C:\ProgramData\ytdlp-bot')
cpu=root/'bench-cpu-full';gpu=root/'bench-gpu-full'
a=json.loads((cpu/'cpu-metrics.json').read_text(encoding='utf-8'))
b=json.loads((gpu/'cuda-metrics.json').read_text(encoding='utf-8'))
s=(cpu/'cpu-transcript.txt').read_text(encoding='utf-8')
t=(gpu/'cuda-transcript.txt').read_text(encoding='utf-8')
norm=lambda x:re.findall(r'[^\W_]+',x.lower(),flags=re.UNICODE)
w1,w2=norm(s),norm(t)
seq=difflib.SequenceMatcher(a=w1,b=w2,autojunk=False)
changes=[(tag, ' '.join(w1[i:j])[:140], ' '.join(w2[k:l])[:140]) for tag,i,j,k,l in seq.get_opcodes() if tag!='equal']
summary=dict(cpu_seconds=a['total_seconds'],gpu_seconds=b['total_seconds'],cpu_inference=a['inference_seconds'],gpu_inference=b['inference_seconds'],speedup=round(a['total_seconds']/b['total_seconds'],3),cpu_segments=a['segments'],gpu_segments=b['segments'],cpu_words=len(w1),gpu_words=len(w2),matching_words=sum(j-i for tag,i,j,k,l in seq.get_opcodes() if tag=='equal'),difference_blocks=len(changes),word_similarity=round(seq.ratio(),4),sample_differences=changes[:15])
path=root/'benchmark-comparison.json';path.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
