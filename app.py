"""Flask web app — A4 → 1:1, barcode-safe, separate success/redo ZIPs"""

import io, os, zipfile, json, urllib.parse
from pathlib import Path
from flask import Flask, request, send_file, render_template_string
from PIL import Image
import numpy as np
import fitz
from barcode_check import verify, PYZBAR_AVAILABLE, STATUS_OK, STATUS_SKIPPED

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024
SUPPORTED = {"png", "jpg", "jpeg", "pdf"}

HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Square Converter</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
:root{
  --bg:#0f0f11;--surface:#1a1a1f;--border:#2e2e38;
  --accent:#6c63ff;--accent2:#ff6584;--text:#e8e8f0;--muted:#7a7a8c;
  --ok:#4ade80;--warn:#facc15;--err:#f87171;--radius:14px;
}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);
  min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:40px 20px;}
.logo{font-size:13px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-bottom:8px;}
h1{font-size:clamp(1.6rem,4vw,2.4rem);font-weight:700;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:6px;}
.subtitle{color:var(--muted);font-size:.95rem;margin-bottom:40px;}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:32px;width:100%;max-width:660px;}
.drop-zone{border:2px dashed var(--border);border-radius:10px;padding:40px 24px;
  text-align:center;cursor:pointer;transition:border-color .2s,background .2s;position:relative;}
.drop-zone:hover,.drop-zone.active{border-color:var(--accent);background:rgba(108,99,255,.07);}
.drop-zone input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%;}
.drop-icon{font-size:2.5rem;margin-bottom:10px;}
.drop-label{font-size:1rem;font-weight:600;margin-bottom:4px;}
.drop-hint{font-size:.82rem;color:var(--muted);}
#file-list{margin-top:20px;display:flex;flex-direction:column;gap:8px;}
.file-item{display:flex;align-items:center;gap:10px;background:rgba(255,255,255,.04);
  border-radius:8px;padding:8px 12px;font-size:.875rem;}
.file-item .ext{background:var(--accent);color:#fff;font-size:.7rem;font-weight:700;
  border-radius:4px;padding:2px 6px;text-transform:uppercase;flex-shrink:0;}
.file-item .ext.pdf{background:#e34c35;}
.file-item .name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.file-item .size{color:var(--muted);font-size:.8rem;flex-shrink:0;}
.options{margin-top:24px;}
.options-row{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:12px;}
.opt-label{font-size:.85rem;color:var(--muted);min-width:52px;}
.mode-cards{display:flex;gap:8px;flex:1;flex-wrap:wrap;}
.mode-card input[type=radio]{display:none;}
.mode-card label{display:flex;flex-direction:column;gap:3px;padding:10px 14px;border-radius:9px;
  cursor:pointer;border:1.5px solid var(--border);font-size:.82rem;color:var(--muted);
  transition:all .15s;user-select:none;min-width:90px;}
.mode-card label strong{font-size:.88rem;color:var(--text);}
.mode-card input[type=radio]:checked+label{border-color:var(--accent);background:rgba(108,99,255,.12);color:var(--text);}
.mode-card input[type=radio]:checked+label strong{color:var(--accent);}
.badge{font-size:.65rem;font-weight:700;border-radius:3px;padding:1px 5px;
  text-transform:uppercase;display:inline-block;}
.badge-new{background:var(--accent2);color:#fff;}
.dpi-group{display:flex;align-items:center;gap:8px;}
.dpi-group select{background:rgba(255,255,255,.05);border:1px solid var(--border);
  color:var(--text);border-radius:8px;padding:6px 10px;font-size:.85rem;cursor:pointer;}
button[type=submit]{margin-top:24px;width:100%;padding:14px;
  background:linear-gradient(135deg,var(--accent),#8b5cf6);color:#fff;border:none;
  border-radius:10px;font-size:1rem;font-weight:700;cursor:pointer;
  transition:opacity .15s,transform .1s;}
button[type=submit]:hover{opacity:.9;}
button[type=submit]:active{transform:scale(.98);}
button[type=submit]:disabled{opacity:.4;cursor:not-allowed;}
#progress{display:none;margin-top:20px;text-align:center;color:var(--muted);font-size:.9rem;}
.spinner{width:28px;height:28px;border:3px solid var(--border);border-top-color:var(--accent);
  border-radius:50%;animation:spin .7s linear infinite;margin:0 auto 10px;}
@keyframes spin{to{transform:rotate(360deg);}}

/* Results */
#results{display:none;margin-top:24px;}
.result-section{margin-bottom:20px;}
.result-section h3{font-size:.8rem;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid var(--border);}
.result-section h3 .count{
  display:inline-flex;align-items:center;justify-content:center;
  width:20px;height:20px;border-radius:50%;font-size:.7rem;font-weight:700;
  margin-left:8px;vertical-align:middle;}
.count-ok{background:rgba(74,222,128,.2);color:var(--ok);}
.count-err{background:rgba(248,113,113,.2);color:var(--err);}

.log-item{display:flex;align-items:flex-start;gap:12px;padding:10px 14px;
  border-radius:9px;font-size:.83rem;margin-bottom:6px;border:1px solid;}
.log-item.ok{background:rgba(74,222,128,.05);border-color:rgba(74,222,128,.15);}
.log-item.err{background:rgba(248,113,113,.05);border-color:rgba(248,113,113,.15);}
.log-item .icon{flex-shrink:0;font-size:1.1rem;margin-top:1px;}
.log-item .body{flex:1;line-height:1.6;}
.log-item .filename{font-weight:600;color:var(--text);}
.log-item .arrow{color:var(--muted);margin:0 4px;}
.log-item .outname{color:var(--muted);font-size:.8rem;}
.log-item .bc-ok{color:var(--ok);font-size:.8rem;}
.log-item .bc-err{color:var(--err);font-size:.8rem;font-weight:600;}
.log-item .size-info{color:var(--muted);font-size:.78rem;}

.dl-row{display:flex;gap:10px;margin-top:6px;flex-wrap:wrap;}
.dl-btn{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:8px;
  font-size:.83rem;font-weight:600;cursor:pointer;border:none;text-decoration:none;
  transition:opacity .15s;}
.dl-btn:hover{opacity:.85;}
.dl-btn.primary{background:var(--accent);color:#fff;}
.dl-btn.secondary{background:rgba(255,255,255,.08);color:var(--text);border:1px solid var(--border);}
.dl-btn:disabled{opacity:.3;cursor:default;}

.tip{margin-top:28px;font-size:.8rem;color:var(--muted);text-align:center;line-height:1.7;}
.tip span{color:var(--accent);}
</style>
</head>
<body>
<div class="logo">Batch Tool</div>
<h1>Square Converter</h1>
<p class="subtitle">A4 → 1:1 &nbsp;·&nbsp; PNG / JPEG / PDF &nbsp;·&nbsp; Barcode-safe</p>
<div class="card">
  <form id="upload-form">
    <div class="drop-zone" id="drop-zone">
      <input type="file" name="files" id="file-input" multiple accept=".png,.jpg,.jpeg,.pdf">
      <div class="drop-icon">📂</div>
      <div class="drop-label">Перетащите файлы или нажмите</div>
      <div class="drop-hint">PNG · JPEG · PDF &nbsp;|&nbsp; до 100 МБ</div>
    </div>
    <div id="file-list"></div>
    <div class="options">
      <div class="options-row">
        <label class="opt-label">Режим:</label>
        <div class="mode-cards">
          <div class="mode-card">
            <input type="radio" name="mode" id="mode-smart" value="smart" checked>
            <label for="mode-smart"><strong>Smart 1:1</strong>Квадрат, без пустоты</label>
          </div>
          <div class="mode-card">
            <input type="radio" name="mode" id="mode-label" value="label">
            <label for="mode-label"><strong>102×150 мм</strong>Формат этикетки</label>
          </div>
          <div class="mode-card">
            <input type="radio" name="mode" id="mode-content" value="content">
            <label for="mode-content"><strong>Только контент</strong>Без паддинга</label>
          </div>
          <div class="mode-card">
            <input type="radio" name="mode" id="mode-pad" value="pad">
            <label for="mode-pad"><strong>Белые поля</strong>1:1 без потерь</label>
          </div>
          <div class="mode-card">
            <input type="radio" name="mode" id="mode-crop" value="crop">
            <label for="mode-crop"><strong>Обрезать</strong>По центру</label>
          </div>
        </div>
      </div>
      <div class="options-row">
        <label class="opt-label">DPI (PDF):</label>
        <div class="dpi-group">
          <select name="dpi">
            <option value="100">100</option>
            <option value="150" selected>150</option>
            <option value="200">200</option>
            <option value="300">300</option>
          </select>
        </div>
      </div>
    </div>
    <button type="submit" id="submit-btn" disabled>⬇ Конвертировать</button>
  </form>
  <div id="progress"><div class="spinner"></div>Обрабатываем и проверяем штрих-коды…</div>

  <div id="results">
    <!-- Filled by JS -->
  </div>
</div>
<p class="tip">
  Файлы без штрих-кода или с повреждённым баркодом <span>не попадают</span> в ZIP.<br>
  Успешные и проблемные файлы отображаются отдельно.
</p>

<script>
const input=document.getElementById('file-input'),zone=document.getElementById('drop-zone');
const list=document.getElementById('file-list'),btn=document.getElementById('submit-btn');
const form=document.getElementById('upload-form'),prog=document.getElementById('progress');
const results=document.getElementById('results');

function fmt(b){if(b<1024)return b+' B';if(b<1048576)return(b/1024).toFixed(1)+' KB';return(b/1048576).toFixed(1)+' MB';}

function renderList(files){
  list.innerHTML='';
  [...files].forEach(f=>{
    const ext=f.name.split('.').pop().toLowerCase();
    const el=document.createElement('div');el.className='file-item';
    el.innerHTML=`<span class="ext ${ext==='pdf'?'pdf':''}">${ext}</span>
      <span class="name" title="${f.name}">${f.name}</span>
      <span class="size">${fmt(f.size)}</span>`;
    list.appendChild(el);
  });
  btn.disabled=files.length===0;
}
input.addEventListener('change',()=>renderList(input.files));
zone.addEventListener('dragover',e=>{e.preventDefault();zone.classList.add('active');});
zone.addEventListener('dragleave',()=>zone.classList.remove('active'));
zone.addEventListener('drop',e=>{
  e.preventDefault();zone.classList.remove('active');
  const dt=new DataTransfer();
  [...e.dataTransfer.files].forEach(f=>dt.items.add(f));
  input.files=dt.files;renderList(input.files);
});

// Status icons & classes
const STATUS={
  ok:      {icon:'✓', cls:'ok'},
  skipped: {icon:'✓', cls:'ok'},
  not_found:{icon:'✗', cls:'err'},
  damaged:  {icon:'✗', cls:'err'},
  error:    {icon:'✗', cls:'err'},
};
const BC_MSG={
  ok:       s=>`<span class="bc-ok">🔲 ${s}</span>`,
  skipped:  ()=>`<span class="bc-ok" style="opacity:.5">Проверка пропущена</span>`,
  not_found:()=>`<span class="bc-err">⚠ Штрих-код не найден в файле</span>`,
  damaged:  s=>`<span class="bc-err">⚠ Не удалось прочитать штрих-код: ${s}</span>`,
  error:    s=>`<span class="bc-err">⚠ Ошибка: ${s}</span>`,
};

function buildResults(log, successBlob){
  const ok=log.filter(i=>i.status==='ok'||i.status==='skipped');
  const bad=log.filter(i=>i.status!=='ok'&&i.status!=='skipped');

  let html='';

  // ── Success section ──
  html+=`<div class="result-section">
    <h3>Готово к печати <span class="count count-ok">${ok.length}</span></h3>`;

  if(ok.length){
    const dlId='dl-success';
    html+=`<div class="dl-row">
      <button class="dl-btn primary" id="${dlId}" ${successBlob?'':'disabled'}>
        ⬇ Скачать ZIP (${ok.length} файл${ok.length===1?'':'ов'})
      </button>
    </div><br>`;
    ok.forEach(i=>{
      const st=STATUS[i.status]||STATUS.ok;
      const bcHtml=(BC_MSG[i.status]||BC_MSG.ok)(i.message||'');
      html+=`<div class="log-item ${st.cls}">
        <span class="icon">${st.icon}</span>
        <span class="body">
          <span class="filename">${i.name}</span>
          <span class="arrow">→</span>
          <span class="outname">Значение штрих-кода: <b style="color:var(--text)">${i.message||'—'}</b></span>
          <span class="size-info"> · ${i.size||''}</span><br>
          ${bcHtml}
        </span>
      </div>`;
    });
  } else {
    html+=`<div style="color:var(--muted);font-size:.85rem;padding:10px 0">Нет успешно обработанных файлов</div>`;
  }
  html+='</div>';

  // ── Redo section ──
  if(bad.length){
    html+=`<div class="result-section">
      <h3>Требуют переделки <span class="count count-err">${bad.length}</span></h3>`;
    bad.forEach(i=>{
      const st=STATUS[i.status]||STATUS.error;
      const bcHtml=(BC_MSG[i.status]||BC_MSG.error)(i.message||'');
      html+=`<div class="log-item ${st.cls}">
        <span class="icon">${st.icon}</span>
        <span class="body">
          <span class="filename">${i.name}</span><br>
          ${bcHtml}
        </span>
      </div>`;
    });
    html+='</div>';
  }

  results.innerHTML=html;
  results.style.display='block';

  // Wire download button
  if(successBlob && ok.length){
    document.getElementById('dl-success').addEventListener('click',()=>{
      const now=new Date(),pad=n=>String(n).padStart(2,'0');
      const ts=`${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}_${pad(now.getHours())}-${pad(now.getMinutes())}`;
      const url=URL.createObjectURL(successBlob);
      const a=document.createElement('a');a.href=url;a.download=ts+'.zip';a.click();
      URL.revokeObjectURL(url);
    });
  }
}

form.addEventListener('submit',async e=>{
  e.preventDefault();
  btn.disabled=true;
  results.style.display='none';
  prog.style.display='block';

  const fd=new FormData();
  [...input.files].forEach(f=>fd.append('files',f));
  fd.append('mode',document.querySelector('[name=mode]:checked').value);
  fd.append('dpi',document.querySelector('[name=dpi]').value);

  try{
    const resp=await fetch('/convert',{method:'POST',body:fd});
    prog.style.display='none';
    btn.disabled=false;

    if(!resp.ok){alert('Ошибка сервера: '+resp.status);return;}

    const logHeader=resp.headers.get('X-Conversion-Log');
    const log=logHeader?JSON.parse(decodeURIComponent(logHeader)):[];
    const blob=await resp.blob();
    const successBlob=blob.size>22?blob:null; // empty zip is ~22 bytes
    buildResults(log, successBlob);
  }catch(err){
    prog.style.display='none';
    btn.disabled=false;
    alert('Ошибка: '+err.message);
  }
});
</script>
</body>
</html>
"""

# ─── Image helpers ────────────────────────────────────────────────────────────

def ensure_rgb(img):
    return img.convert("RGB") if img.mode in ("RGBA","LA","P") else img

def pad_to_square(img, bg=(255,255,255)):
    img=ensure_rgb(img); w,h=img.size; size=max(w,h)
    out=Image.new("RGB",(size,size),bg); out.paste(img,((size-w)//2,(size-h)//2)); return out

def center_crop(img):
    img=ensure_rgb(img); w,h=img.size; size=min(w,h)
    return img.crop(((w-size)//2,(h-size)//2,(w+size)//2,(h+size)//2))

def find_content(img, padding_pct=0.03, threshold=200):
    """Find content bounding box and return cropped image."""
    img=ensure_rgb(img); gray=np.array(img.convert("L")); h,w=gray.shape
    rows=np.any(gray<threshold,axis=1); cols=np.any(gray<threshold,axis=0)
    if not rows.any() or not cols.any(): return img
    top=int(np.argmax(rows)); bottom=int(len(rows)-np.argmax(rows[::-1]))
    left=int(np.argmax(cols)); right=int(len(cols)-np.argmax(cols[::-1]))
    pad=int(max(bottom-top,right-left)*padding_pct)
    return img.crop((max(0,left-pad),max(0,top-pad),min(w,right+pad),min(h,bottom+pad)))

def smart_crop(img, padding_pct=0.03, threshold=200):
    """Smart crop + pad to 1:1 square."""
    return pad_to_square(find_content(img, padding_pct, threshold))

def to_label_size(img, w_mm=102, h_mm=150, padding_pct=0.03, threshold=200):
    """Smart crop + pad to 102x150mm label ratio."""
    cropped = find_content(img, padding_pct, threshold)
    cw, ch = cropped.size
    # Target ratio: 102:150 = 0.68
    target_ratio = w_mm / h_mm
    current_ratio = cw / ch
    if current_ratio > target_ratio:
        # Content is wider than label — match width, expand height
        new_w = cw
        new_h = int(cw / target_ratio)
    else:
        # Content is taller than label — match height, expand width
        new_h = ch
        new_w = int(ch * target_ratio)
    out = Image.new("RGB", (new_w, new_h), (255, 255, 255))
    out.paste(cropped, ((new_w - cw) // 2, (new_h - ch) // 2))
    return out

def content_only(img, padding_pct=0.03, threshold=200):
    """Smart crop only — no padding, original content ratio."""
    return find_content(img, padding_pct, threshold)

def process(img, mode):
    if mode=="smart":   return smart_crop(img)
    if mode=="label":   return to_label_size(img)
    if mode=="content": return content_only(img)
    if mode=="pad":     return pad_to_square(img)
    return center_crop(img)

def to_bytes(img, fmt="PNG"):
    buf=io.BytesIO()
    kw={"quality":99,"subsampling":0} if fmt=="JPEG" else {}
    img.save(buf,format=fmt,**kw)
    return buf.getvalue()

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
def index(): return render_template_string(HTML)

@app.post("/convert")
def convert():
    files=request.files.getlist("files")
    mode=request.form.get("mode","smart")
    dpi=int(request.form.get("dpi",150))
    if not files: return "No files",400

    zip_buf=io.BytesIO()
    log=[]

    with zipfile.ZipFile(zip_buf,"w",zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            ext=Path(f.filename).suffix.lower().lstrip(".")
            stem=Path(f.filename).stem
            if ext not in SUPPORTED: continue
            raw=f.read()

            pages=[]
            try:
                if ext=="pdf":
                    doc=fitz.open(stream=raw,filetype="pdf")
                    zoom=dpi/72.0; mat=fitz.Matrix(zoom,zoom)
                    for i,page in enumerate(doc):
                        pix=page.get_pixmap(matrix=mat,alpha=False)
                        img=Image.frombytes("RGB",(pix.width,pix.height),pix.samples)
                        sfx=f"_p{i+1:03d}" if len(doc)>1 else ""
                        pages.append((img,f"{stem}{sfx}_square.png",f"{f.filename} стр.{i+1}"))
                    doc.close()
                else:
                    img=Image.open(io.BytesIO(raw))
                    pages.append((img,f"{stem}_square.{'png' if ext not in ('jpg','jpeg') else ext}",f.filename))
            except Exception as e:
                log.append({"status":"error","name":f.filename,"message":str(e)})
                continue

            for orig,outname,label in pages:
                try:
                    sq=process(orig,mode)
                    vr=verify(orig,sq,label)

                    is_success = vr["status"] in (STATUS_OK, STATUS_SKIPPED)

                    if is_success:
                        if vr["original_codes"]:
                            # Name file after barcode value
                            barcode_val = vr["original_codes"][0]["data"].decode(errors="replace")
                            outname = f"{barcode_val}.png"
                            msg = barcode_val
                        else:
                            # pyzbar skipped — keep original stem name
                            outname = Path(outname).with_suffix(".png").name
                            msg = "проверка пропущена"
                        zf.writestr(outname, to_bytes(sq, "PNG"))
                        log.append({
                            "status":  vr["status"],
                            "name":    label,
                            "out":     outname,
                            "size":    f"{sq.size[0]}×{sq.size[1]}",
                            "message": msg,
                        })
                    else:
                        # NOT added to ZIP — goes to redo list
                        log.append({
                            "status":  vr["status"],
                            "name":    label,
                            "message": vr["message"],
                        })

                except Exception as e:
                    log.append({"status":"error","name":label,"message":str(e)})

    zip_buf.seek(0)
    response=send_file(zip_buf,mimetype="application/zip",
                       as_attachment=True,download_name="ready_to_print.zip")
    response.headers["X-Conversion-Log"]=urllib.parse.quote(json.dumps(log,ensure_ascii=False))
    return response

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port,debug=False)
