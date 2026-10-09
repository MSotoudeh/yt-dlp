from huggingface_hub import HfApi, hf_hub_url, get_token
from huggingface_hub.file_download import get_hf_file_metadata
from huggingface_hub import hf_hub_download
import json
api=HfApi()
token=get_token()
print("LOCAL_HF_AUTH_PRESENT",bool(token))
models=[
 ("c1tech-small","C1Tech/whisper_small_persian","model.safetensors"),
 ("amir-ct2","AmirMohseni/whisper-large-v3-persian-ct2-int8","model.bin"),
 ("persian-v4","nezamisafa/whisper-persian-v4","model-00001-of-00002.safetensors"),
]
for key,repo,weight in models:
 try:
  info=api.model_info(repo)
  print("MODEL_META",key,"GATED",info.gated)
  meta=get_hf_file_metadata(hf_hub_url(repo,weight),token=token)
  print("WEIGHT_ACCESS",key,True,"SIZE_BYTES",meta.size)
 except Exception as e:
  print("WEIGHT_ACCESS",key,False,"ERROR_TYPE",type(e).__name__,"HTTP_STATUS",getattr(getattr(e,"response",None),"status_code","unavailable"))
try:
 f=hf_hub_download(repo_id="nezamisafa/whisper-persian-v4",filename="config.json")
 data=json.loads(open(f,encoding="utf-8").read())
 print("PERSIAN_V4_ARCH",data.get("model_type"),"D_MODEL",data.get("d_model"),"DECODER_LAYERS",data.get("decoder_layers"))
except Exception as e:
 print("PERSIAN_V4_CONFIG_ERROR",type(e).__name__)
