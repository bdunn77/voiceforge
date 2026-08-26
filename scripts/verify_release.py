from pathlib import Path
import re, subprocess, sys
R=Path(__file__).resolve().parents[1]
SKIP={'.git','.venv','.local','__pycache__','.pytest_cache','.ruff_cache'}
bad=[]
for p in R.rglob('*'):
 rel=p.relative_to(R)
 if any(part in SKIP for part in rel.parts):
  continue
 if p.is_file() and (p.stat().st_size>10_000_000 or p.suffix.lower() in {'.pth','.pt','.ckpt','.mp3','.wav','.mp4'}):
  bad.append(str(rel))
 if p.is_file():
  text=p.read_text(encoding='utf-8',errors='ignore')
  if re.search(r'C:\\Users\\bgami|vv_[A-Za-z0-9_-]{8,}|Bearer\s+[A-Za-z0-9._-]{12,}',text,re.I):
   bad.append(str(rel))
if bad:
 raise SystemExit('Blocked release files/patterns: '+', '.join(sorted(set(bad))))
subprocess.run([sys.executable,'-m','py_compile',str(R/'app.py'),str(R/'scripts'/'setup_lipsync.py'),str(R/'scripts'/'enhance.py')],check=True)
print('release verification passed')
