# Square Converter — A4 → 1:1

Batch converter of A4 images (PNG, JPEG, PDF) to 1:1 square format.

## Files

| File | Description |
|------|-------------|
| `convert.py` | CLI script for local use |
| `app.py`     | Flask web app (drag & drop, ZIP download) |
| `requirements.txt` | Python dependencies |
| `Procfile` | For Railway / Render deploy |

---

## 1. Local CLI usage

### Install dependencies
```bash
pip install pillow pymupdf
```

### Run
```bash
# Add white padding (default)
python convert.py ./input ./output

# Crop to square instead
python convert.py ./input ./output --mode crop

# Set PDF resolution
python convert.py ./input ./output --dpi 200
```

---

## 2. Web App — local run

```bash
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

---

## 3. Deploy (free hosting options)

### Railway (Recommended — easiest)
1. Push project to a GitHub repo
2. Go to https://railway.app → New Project → Deploy from GitHub
3. Select your repo — Railway auto-detects Python + Procfile
4. Done. You get a public URL.
- Free tier: 500 hrs/month (enough for tools)

### Render
1. Push to GitHub
2. https://render.com → New Web Service → connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app --bind 0.0.0.0:$PORT`
5. Free tier available (sleeps after 15 min idle)

### Fly.io
```bash
pip install flyctl
flyctl auth login
flyctl launch   # auto-detects Flask
flyctl deploy
```
Free tier: 3 shared VMs, 160 GB outbound traffic/month.

---

## Notes

- PDF pages are converted one-by-one, named `doc_p001_square.png` etc.
- Max upload: 100 MB (configurable in `app.py`)
- Output is always RGB (printer-safe, no transparency)
