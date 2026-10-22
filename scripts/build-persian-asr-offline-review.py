"""Create an offline, audio-synchronized human-review bundle for Persian ASR results.

No ASR inference or external API. Reference text remains blank until corrected by a human.
"""
from __future__ import annotations
import hashlib, json, zipfile
from pathlib import Path

ROOT=Path(r"C:\ProgramData\ytdlp-bot")
OUT=ROOT/"asr-six-gpu-20261021"
PREV=ROOT/"asr-four-models"
THREE=ROOT/"asr-three-gpu-20261009"
AUDIO=PREV/"input-16000.wav"
MODELS={
 "C1Tech Base":(PREV,"c1tech-cuda"),
 "Persian v4":(THREE,"persian-v4-cuda"),
 "CV17 INT8":(THREE,"amir-cv17-int8-cuda"),
 "MohammadGholizadeh Turbo":(OUT,"gholizadeh"),
 "Qwen3-ASR 0.6B":(OUT,"qwen06"),
 "Wav2Vec2 Persian V3":(OUT,"wav2vec"),
 "Givia Turbo":(OUT,"givia"),
}
def verified_transcripts():
 transcripts={}
 for label,(folder,stem) in MODELS.items():
  p=folder/(stem+".txt"); j=folder/(stem+".json")
  if not p.is_file() or not j.is_file():continue
  meta=json.loads(j.read_text(encoding="utf-8"))
  if meta.get("status")!="complete" or meta.get("chunks")!=19:continue
  lines=p.read_text(encoding="utf-8-sig").splitlines()
  if len(lines)!=19 or not all(s.strip() for s in lines):continue
  transcripts[label]={"segments":lines,"seconds":meta.get("seconds"),
       "characters":meta.get("characters"),"gpu_only":meta.get("gpu_only",meta.get("device")=="cuda")}
 return transcripts

PAGE=r"""<!doctype html>
<html lang="fa" dir="rtl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Persian ASR • Offline evidence review</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#101827;color:#ecf1f9;font:16px/1.7 Tahoma,Arial,sans-serif}
main{max-width:1150px;margin:auto;padding:20px}h1{font-size:23px;margin:0 0 8px}p{color:#c3cee1}small{color:#a8b7d0}
.top{padding:19px;border:1px solid #38465e;border-radius:14px;background:#172238;margin-bottom:15px}
.controls{display:flex;gap:9px;flex-wrap:wrap;align-items:center;margin:10px 0}
button,input,textarea{font:inherit}button{padding:8px 13px;border-radius:9px;border:1px solid #6d84a9;background:#2b3c58;color:white;cursor:pointer}
button:hover{background:#425a80}button:focus,textarea:focus{outline:2px solid #96c0ff}
audio{width:100%}textarea{width:100%;min-height:100px;padding:12px;border:1px solid #687da0;border-radius:8px;color:#f3f8ff;background:#111b2c}
.card{border:1px solid #38465e;border-radius:12px;padding:13px;margin:12px 0;background:#172238}
.transcripts{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}
.model{background:#111b2c;border:1px solid #334b6c;padding:12px;border-radius:10px;white-space:pre-wrap;overflow-wrap:anywhere}
.model strong{display:block;color:#a9d0ff;margin-bottom:6px}
.status{color:#c8d4e9}table{width:100%;border-collapse:collapse}td,th{padding:7px;text-align:right;border-bottom:1px solid #38465e}
.warn{border-right:3px solid #e5b562;padding:8px 12px;background:#2d2830}
@media(max-width:600px){main{padding:10px}.top{padding:12px}}
</style></head>
<body><main>
<div class="top">
<h1>آزمون آفلاین تشخیص گفتار فارسی — بازبینی با صوت اصلی</h1>
<p>هر ۱۹ بخش صوتی را گوش کن، متن صحیح را خودت در کادر «متن مرجع» بنویس، سپس خطای مدل‌ها محاسبه می‌شود. خروجی مدل‌ها لزوماً حقیقت نیست.</p>
<p class="warn">WER/CER فقط روی بخش‌هایی محاسبه می‌شود که متن مرجع انسانی دارند. همخوانی دو مدل با یکدیگر، معیار صحت نیست.</p>
<div class="controls">
<button id="prev">بخش قبلی</button><button id="next">بخش بعدی</button><button id="play">پخش بخش فعلی</button><button id="pause">توقف</button>
<span id="position" class="status"></span></div>
<audio id="audio" controls preload="metadata" src="input-16000.wav"></audio>
<div class="controls"><button id="export">دریافت JSON متن مرجع</button><button id="import">بارگذاری JSON قبلی</button><input id="upload" type="file" accept=".json" hidden></div>
</div>
<div class="card"><h2>نتیجه بخش‌های تصحیح‌شده</h2><div id="scores" class="status">هنوز متنی تصحیح نشده است.</div></div>
<section id="viewer"></section>
<p><small>مرجع: صوت 530 ثانیه، 16 kHz mono؛ 19 بخش، هر بخش تا 28 ثانیه. همه محاسبات در همین مرورگر انجام می‌شوند؛ هیچ سرویس خارجی استفاده نمی‌شود.</small></p>
</main>
<script>
const DATA=__INLINE_DATA__;
const $=id=>document.getElementById(id), names=Object.keys(DATA.models);
let current=0, gold=Array(19).fill(''), stopAt=null;
const audio=$('audio');
function h(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function normalize(s){return String(s||'').normalize('NFKC').replace(/ي/g,'ی').replace(/ك/g,'ک').replace(/[\u200c\u200d\u064b-\u065f]/g,'').replace(/[\u200e\u200f]/g,'').replace(/[^\p{L}\p{N}\s]/gu,' ').replace(/\s+/g,' ').trim().toLowerCase();}
function edit(a,b){let prev=Array.from({length:b.length+1},(_,i)=>i);for(let i=1;i<=a.length;i++){let next=[i];for(let j=1;j<=b.length;j++)next[j]=Math.min(prev[j]+1,next[j-1]+1,prev[j-1]+(a[i-1]===b[j-1]?0:1));prev=next;}return prev[b.length];}
function segmentScores(){let checked=gold.map((x,i)=>[x,i]).filter(x=>normalize(x[0]));if(!checked.length){$('scores').textContent='هنوز متنی تصحیح نشده است.';return;}let html='<p>تعداد بخش‌های دارای متن مرجع: '+checked.length+' از ۱۹</p><table><thead><tr><th>مدل</th><th>WER</th><th>CER</th></tr></thead><tbody>';
for(const name of names){let we=0,wn=0,ce=0,cn=0;for(const [ref,i] of checked){const r=normalize(ref),p=normalize(DATA.models[name].segments[i]);const rw=r.split(' '),pw=p? p.split(' '):[];we+=edit(rw,pw);wn+=rw.length;ce+=edit([...r],[...p]);cn+=r.length;}html+='<tr><td>'+h(name)+'</td><td>'+((100*we/wn).toFixed(2))+'%</td><td>'+((100*ce/cn).toFixed(2))+'%</td></tr>';} $('scores').innerHTML=html+'</tbody></table>';
}
function persist(){try{sessionStorage.setItem('asr_gold_v1',JSON.stringify(gold));}catch(e){}}
function render(){if(current<0)current=0;if(current>18)current=18;let start=current*28;const label='بخش '+(current+1)+' از ۱۹ · '+start+' تا '+Math.min(530.1,start+28)+' ثانیه';$('position').textContent=label;
let rows=names.map(n=>'<div class="model" dir="rtl"><strong>'+h(n)+'</strong>'+h(DATA.models[n].segments[current])+'</div>').join('');
$('viewer').innerHTML='<div class="card"><h2>'+label+'</h2><label for="gold">متن مرجع صحیح (از روی صوت)</label><textarea id="gold" placeholder="در صورت اطمینان، آنچه واقعاً در صوت گفته شده را بنویس...">'+h(gold[current])+'</textarea><div class="transcripts">'+rows+'</div></div>';
$('gold').addEventListener('input',e=>{gold[current]=e.target.value;persist();segmentScores();});segmentScores();
}
function play(){stopAt=Math.min(530.1,(current+1)*28);audio.currentTime=current*28;const p=audio.play();if(p&&p.catch)p.catch(()=>{});}
audio.addEventListener('timeupdate',()=>{if(stopAt!==null&&audio.currentTime>=stopAt){audio.pause();stopAt=null;}});
$('next').onclick=()=>{current=Math.min(18,current+1);render();};$('prev').onclick=()=>{current=Math.max(0,current-1);render();};$('play').onclick=play;$('pause').onclick=()=>{audio.pause();stopAt=null;};
$('export').onclick=()=>{const data={source:'m8ElotVbO6M',schema:'persian-asr-human-gold-v1',segment_seconds:28,references:gold};const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='persian_asr_gold_reference.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};
$('import').onclick=()=>$('upload').click();$('upload').onchange=async(e)=>{const f=e.target.files[0];if(!f)return;try{const data=JSON.parse(await f.text());if(!Array.isArray(data.references)||data.references.length!==19||data.source!=='m8ElotVbO6M')throw new Error('Wrong schema/source');gold=data.references.map(x=>String(x||''));persist();render();}catch(err){alert('فایل معتبر نیست: '+err.message);}};
try{const stored=sessionStorage.getItem('asr_gold_v1');if(stored){const arr=JSON.parse(stored);if(arr.length===19)gold=arr;}}catch(err){}
render();
</script></body></html>"""

def main():
 transcripts=verified_transcripts()
 if not transcripts:raise RuntimeError("No 19-chunk full transcript available")
 if not AUDIO.is_file():raise FileNotFoundError(AUDIO)
 assert AUDIO.stat().st_size>1_000_000
 meta={"source":"m8ElotVbO6M","source_audio_sha256":hashlib.sha256(AUDIO.read_bytes()).hexdigest(),
       "source_audio_seconds":530.1,"segment_seconds":28,"models":transcripts,
       "accuracy":"not measured: human-corrected reference required"}
 html=PAGE.replace("__INLINE_DATA__",json.dumps(meta,ensure_ascii=False).replace("<","\\u003c"))
 assert len([x for x in transcripts.values() if len(x["segments"])==19])==len(transcripts)
 zip_path=OUT/"Persian-ASR-GPU-Offline-Human-Review-20261022.zip"
 with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  z.writestr("index.html",html)
  z.write(AUDIO,"input-16000.wav")
  z.writestr("transcripts-and-metrics.json",json.dumps(meta,ensure_ascii=False,indent=2))
  for label,(folder,stem) in MODELS.items():
   if label in transcripts:
    z.write(folder/(stem+".txt"),"transcripts/"+stem+".txt")
    z.write(folder/(stem+".json"),"metrics/"+stem+".json")
  z.writestr("README.txt","Extract all files to one folder, then open index.html with a browser. Listen to each 28-second audio segment and enter a manually corrected reference. WER/CER are only calculated on corrected segments. No network requests. Download the JSON reference to retain your work.\n")
 with zipfile.ZipFile(zip_path) as z:
  assert z.testzip() is None
  assert "index.html" in z.namelist() and "input-16000.wav" in z.namelist()
 print("REVIEW_ZIP",zip_path.name,"SIZE_BYTES",zip_path.stat().st_size,"FULL_MODELS",list(transcripts.keys()),flush=True)

if __name__=="__main__":main()
