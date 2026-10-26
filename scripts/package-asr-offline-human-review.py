"""Create an OFFLINE human-reviewed Persian ASR comparison ZIP (no inference API).

The package includes the source MP3, each eligible model's raw 28-s
transcript chunks and a standalone HTML player/editor with client-side
WER/CER on manually corrected chunks. No transcript is uploaded to web.
"""
from pathlib import Path
import argparse
import json
import shutil
import sqlite3
import sys
import zipfile

ROOT=Path(r"C:\ProgramData\ytdlp-bot")
ASR=ROOT/"asr-four-models"
DELIVERY=ROOT/"asr-benchmark-delivery"
LABELS=[
 ("c1tech-cpu","C1Tech · CPU"),
 ("c1tech-cuda","C1Tech · GPU"),
 ("buzz-cpu-native","BuzzASR · CPU"),
 ("buzz-cuda-native","BuzzASR · GPU"),
 ("qwen-cpu","Qwen3-ASR · CPU"),
 ("qwen-cuda","Qwen3-ASR · GPU"),
 ("shenava-koochik-cpu","Shenava Koochik · CPU"),
]
HTML=r"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>آزمایش آفلاین مدل‌های تشخیص گفتار فارسی</title>
<style>
body{font:16px/1.8 system-ui,Segoe UI,Tahoma,sans-serif;max-width:1150px;margin:auto;padding:18px;background:#f8fafc;color:#14253c}
header,.card{background:white;border:1px solid #dbe3ef;border-radius:12px;margin:16px 0;padding:18px}
textarea{width:99%;min-height:90px;padding:10px;font:17px/1.7 Tahoma;border:1px solid #8ba0b8;border-radius:6px;box-sizing:border-box}
button,select{font:inherit;background:#1158a1;color:white;border:0;border-radius:8px;padding:7px 14px;margin:3px;cursor:pointer}
button.secondary{background:#596b80}
.model{padding:7px 11px;border-top:1px solid #dfe5ed;white-space:pre-wrap}
small, .dim{color:#5a6980} .num{font-variant-numeric:tabular-nums;direction:ltr;display:inline-block}
#scores{background:#e8f3ff;padding:15px;border-radius:8px}audio{width:100%}
</style></head>
<body>
<header><h1>مقایسه محلی مدل‌های تشخیص گفتار فارسی</h1>
<p>این صفحه کاملاً آفلاین کار می‌کند. همه مدل‌ها روی لپ‌تاپ اجرا شده‌اند؛ در این بسته هیچ تماس API برای تشخیص گفتار وجود ندارد.</p>
<p>ابتدا روی زمان هر قطعه کلیک و فایل صوتی را گوش کن. سپس متن صحیح <strong>دقیقاً مطابق گفتار</strong> را در کادر همان قطعه بنویس. فقط قطعه‌های اصلاح‌شده در محاسبه خطا لحاظ می‌شوند.</p>
<audio controls preload="metadata" id="audio" src="audio.mp3"></audio>
<div><button onclick="calc()">محاسبه WER و CER</button><button onclick="download()">خروجی اصلاحات (JSON)</button><button class="secondary" onclick="downloadPlain()">متن مرجع (TXT)</button></div>
<div id="scores">هنوز متن مرجع اصلاح‌شده ثبت نشده است.</div>
<small>هدف آزمایشی پیشنهادی: WER کمتر از ۳٪؛ این حد هنوز توسط کاربر تأیید نشده است. تفاوت نگارش محاوره، اعداد و چسبندگی کلمات بر WER اثر می‌گذارد.</small>
</header>
<div id="chunks"></div>
<script id="DATA" type="application/json">__DATA__</script>
<script>
const payload=JSON.parse(document.getElementById("DATA").textContent), audio=document.getElementById("audio"),storeKey="persian_asr_human_reference_m8ElotVbO6M_v1";
let corrected={};try{corrected=JSON.parse(localStorage.getItem(storeKey)||"{}")}catch{}
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function go(n){audio.currentTime=n*28;audio.play()}
function save(n,val){corrected[n]=val;try{localStorage.setItem(storeKey,JSON.stringify(corrected))}catch{}}
const root=document.getElementById("chunks");
for(let i=0;i<payload.count;i++){
 let block=document.createElement("section");block.className="card";
 let h=document.createElement("h2");h.textContent="قطعه "+(i+1)+" / "+payload.count+" («"+(i*28)+"» ثانیه)";block.appendChild(h);
 let b=document.createElement("button");b.textContent="▶ پخش از این قطعه";b.onclick=()=>go(i);block.appendChild(b);
 for(let [key,label] of Object.entries(payload.labels)){
   const line=document.createElement("div");line.className="model";
   let strong=document.createElement("strong");strong.textContent=label;line.appendChild(strong);
   const t=document.createElement("div");t.textContent=payload.models[key]?.[i]??"(بدون خروجی)";line.appendChild(t);block.appendChild(line);
 }
 const label=document.createElement("label");label.textContent="متن صحیح پس از گوش‌دادن:";block.appendChild(label);
 const input=document.createElement("textarea");input.placeholder="متن صحیح را بنویس. کادر خالی یعنی ارزیابی نشده است.";input.value=corrected[i]??"";input.oninput=()=>save(i,input.value);block.appendChild(input);
 root.appendChild(block);
}
function norm(s){
 return String(s).toLowerCase().replace(/[يى]/g,"ی").replace(/ك/g,"ک").replace(/[\u200c\u200d]/g," ")
  .replace(/[۰-۹]/g,c=>String(c.charCodeAt(0)-1776)).replace(/[٠-٩]/g,c=>String(c.charCodeAt(0)-1632))
  .replace(/[^\p{L}\p{N}\s]/gu," ").replace(/\s+/g," ").trim();
}
function edit(a,b){const dp=new Uint32Array(b.length+1);for(let j=0;j<=b.length;j++)dp[j]=j;for(let i=1;i<=a.length;i++){let prior=dp[0];dp[0]=i;for(let j=1;j<=b.length;j++){let old=dp[j];dp[j]=Math.min(dp[j]+1,dp[j-1]+1,prior+(a[i-1]===b[j-1]?0:1));prior=old}}return dp[b.length]}
function calc(){
 const indexes=Object.keys(corrected).filter(k=>norm(corrected[k]).length>0);
 if(!indexes.length){document.getElementById("scores").textContent="هنوز متن مرجع اصلاح‌شده‌ای ثبت نشده است.";return}
 let html="<h2>مقایسه فقط روی "+indexes.length+" قطعه اصلاح‌شده</h2><table><thead><tr><th>مدل</th><th>WER</th><th>CER</th></tr></thead><tbody>";
 for(let [key,label] of Object.entries(payload.labels)){
 let wordErr=0,wordN=0,charErr=0,charN=0;
 for(let ix of indexes){
 const ref=norm(corrected[ix]),hyp=norm(payload.models[key]?.[ix]??"");
 const a=ref.split(" ").filter(Boolean),b=hyp.split(" ").filter(Boolean);
 wordErr+=edit(a,b);wordN+=a.length;
 const x=[...ref.replace(/\s/g,"")],y=[...hyp.replace(/\s/g,"")];
 charErr+=edit(x,y);charN+=x.length;
 }
 const pct=x=>isFinite(x)?x.toFixed(2)+"%":"نامشخص";
 html+="<tr><td>"+esc(label)+"</td><td class='num'>"+pct(wordErr/wordN*100)+"</td><td class='num'>"+pct(charErr/charN*100)+"</td></tr>";
 }
 document.getElementById("scores").innerHTML=html+"</tbody></table><p class='dim'>WER/CER فقط بر اساس متن مرجع نوشته‌شده توسط شما و نرمال‌سازی یکسان محاسبه شده‌اند.</p>";
}
function dataUrl(obj,mime){const blob=new Blob([obj],{type:mime});const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=mime.startsWith("application")?"persian_asr_gold_reference.json":"persian_asr_gold_reference.txt";a.click();setTimeout(()=>URL.revokeObjectURL(a.href),5000)}
function download(){dataUrl(JSON.stringify({source:"m8ElotVbO6M",segment_seconds:28,corrected},null,2),"application/json")}
function downloadPlain(){dataUrl(Object.keys(corrected).sort((a,b)=>a-b).filter(k=>norm(corrected[k])).map(k=>"["+k+"] "+corrected[k]).join("\n"),"text/plain")}
calc();
</script></body></html>"""

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--send",action="store_true")
 p.add_argument("--include-audio",action="store_true",default=True)
 args=p.parse_args()
 DELIVERY.mkdir(exist_ok=True)
 models={}
 labels={}
 for name,label in LABELS:
  text=ASR/(name+".txt")
  stat=ASR/(name+".json")
  if not(text.is_file() and stat.is_file()):continue
  try:
   status=json.loads(stat.read_text(encoding="utf-8"))
   if status.get("status")!="complete":continue
   lines=text.read_text(encoding="utf-8").splitlines()
   if len(lines)!=19 or len("".join(lines).strip())<200:continue
   models[name]=lines
   labels[name]=label
  except Exception:continue
 if len(models)<4:raise RuntimeError(f"Insufficient validated outputs ({len(models)})")
 source=list((ROOT/"transcribe-validation").rglob("*.mp3"))
 if len(source)!=1:raise RuntimeError("Source MP3 must be uniquely identified")
 audio=source[0]
 payload={"count":19,"labels":labels,"models":models}
 html=HTML.replace("__DATA__",json.dumps(payload,ensure_ascii=False).replace("</","<\\/"))
 output=DELIVERY/"Persian-ASR-offline-human-review.zip"
 with zipfile.ZipFile(output,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=5) as z:
  z.writestr("index.html",html.encode("utf-8"))
  z.write(audio,"audio.mp3")
  for name in models:
   z.write(ASR/(name+".txt"),f"transcripts/{name}.txt")
  z.writestr("manifest.json",json.dumps(payload,ensure_ascii=False,indent=2))
  z.writestr("README.txt","Offline human review: unzip all files, open index.html, play audio.mp3, fill corrected utterances, press WER/CER. No remote ASR API. Send back the downloaded corrected_reference.json to score models objectively. Original YouTube m8ElotVbO6M.")
 print("REVIEW_PACKAGE",output.name,output.stat().st_size,"MODELS",",".join(models),flush=True)
 if not args.send:return
 marker=DELIVERY/"delivered-human-review.flag"
 if marker.exists():print("ALREADY_SENT");return
 jobs=ROOT/"state"/"jobs.sqlite"
 with sqlite3.connect(jobs) as conn:
  rows=conn.execute("select distinct chat from jobs where mode=? and url like ?",("transcribe","%m8ElotVbO6M%")).fetchall()
 if len(rows)!=1:raise RuntimeError("No uniquely verified Telegram destination")
 import requests
 token=(ROOT/"telegram-token").read_text(encoding="utf-8").strip()
 with output.open("rb") as f:
  res=requests.post("https://api.telegram.org/bot"+token+"/sendDocument",data={"chat_id":rows[0][0],
   "caption":"بسته آفلاین بررسی دقت فارسی: ZIP را استخراج و index.html را باز کنید. فایل صوتی، خروجی مدل‌ها و محاسبه WER/CER با متن تصحیح‌شده داخل آن است."},
   files={"document":(output.name,f,"application/zip")},timeout=160)
 if res.status_code!=200 or not res.json().get("ok"):raise RuntimeError("Telegram send failed: HTTP "+str(res.status_code))
 marker.write_text("delivered",encoding="utf-8")
 print("DELIVERED_TO_VERIFIED_TELEGRAM",output.stat().st_size,flush=True)

if __name__=="__main__":main()
