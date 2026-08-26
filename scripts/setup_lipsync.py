"""Explicit optional installer; no third-party source or weights are bundled."""
import argparse, hashlib, os, re, shutil, subprocess, sys, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DEST=ROOT/'.local'/'lipsync'; REPO=DEST/'Wav2Lip'
COMMIT='bac9a81e63ecc153202353372e5724b83d9e6322'
ASSETS=[
 ('https://huggingface.co/camenduru/Wav2Lip/resolve/main/checkpoints/wav2lip_gan.pth',REPO/'checkpoints'/'wav2lip_gan.pth','ca9ab7b7b812c0e80a6e70a5977c545a1e8a365a6c49d5e533023c034d7ac3d8'),
 ('https://huggingface.co/camenduru/Wav2Lip/resolve/main/face_detection/detection/sfd/s3fd.pth',REPO/'face_detection'/'detection'/'sfd'/'s3fd.pth','619a31681264d3f7f7fc7a16a42cbbe8b23f31a256f75a366e5a1bcd59b33543'),
 ('https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth',DEST/'weights'/'GFPGANv1.4.pth','e2cd4703ab14f4d01fd1383a8a8b266f9a5833dacee8e6a79d3bf21a1b6be5ad')]
def call(args): print('+',' '.join(map(str,args)));subprocess.run(list(map(str,args)),check=True,shell=False)
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1048576),b''):h.update(c)
 return h.hexdigest()
def fetch(url,dst,expected):
 dst.parent.mkdir(parents=True,exist_ok=True)
 if dst.exists() and digest(dst)==expected:return print('Verified',dst.name)
 tmp=dst.with_suffix(dst.suffix+'.download');tmp.unlink(missing_ok=True);urllib.request.urlretrieve(url,tmp)
 if digest(tmp)!=expected:tmp.unlink(missing_ok=True);raise RuntimeError('Checksum mismatch: '+dst.name)
 os.replace(tmp,dst);print('Verified',dst.name)
def patch():
 p=REPO/'audio.py';s=p.read_text(encoding='utf-8')
 if 'from scipy.io import wavfile' not in s:s=s.replace('from scipy import signal','from scipy import signal\nfrom scipy.io import wavfile')
 s=s.replace('librosa.output.write_wav(path, wav, sr=sr)','wavfile.write(path, sr, wav.astype(np.int16))')
 s=s.replace('librosa.filters.mel(hp.sample_rate, hp.n_fft, n_mels=hp.num_mels,','librosa.filters.mel(sr=hp.sample_rate, n_fft=hp.n_fft, n_mels=hp.num_mels,')
 p.write_text(s,encoding='utf-8')
 for q in REPO.rglob('*.py'):
  s=q.read_text(encoding='utf-8',errors='ignore');s=re.sub(r'np\.float(?![0-9])','float',s);s=re.sub(r'np\.int(?![0-9])','int',s);q.write_text(s,encoding='utf-8')
def main():
 a=argparse.ArgumentParser();a.add_argument('--accept-wav2lip-license',action='store_true');a.add_argument('--cuda',action='store_true');o=a.parse_args()
 if not o.accept_wav2lip_license:raise SystemExit('Read https://github.com/Rudrabha/Wav2Lip and rerun with --accept-wav2lip-license if you accept its terms.')
 if not shutil.which('git'):raise SystemExit('Git is required.')
 if not REPO.exists():call(['git','clone','https://github.com/Rudrabha/Wav2Lip.git',REPO])
 call(['git','-C',REPO,'fetch','--depth','1','origin',COMMIT]);call(['git','-C',REPO,'checkout','--detach',COMMIT])
 index='https://download.pytorch.org/whl/cu128' if o.cuda else 'https://download.pytorch.org/whl/cpu'
 call([sys.executable,'-m','pip','install','torch','torchvision','--index-url',index])
 call([sys.executable,'-m','pip','install','-r',ROOT/'requirements'/'lipsync.txt'])
 # BasicSR 1.4.2 imports a torchvision module removed by newer torchvision.
 # Patch the installed compatibility import without bundling BasicSR itself.
 site=subprocess.run([sys.executable,'-c','import site; print(site.getsitepackages()[0])'],check=True,capture_output=True,text=True).stdout.strip()
 degradations=Path(site)/'basicsr'/'data'/'degradations.py'
 if degradations.exists():
  text=degradations.read_text(encoding='utf-8')
  text=text.replace('from torchvision.transforms.functional_tensor import rgb_to_grayscale','from torchvision.transforms.functional import rgb_to_grayscale')
  degradations.write_text(text,encoding='utf-8')
 patch()
 for x in ASSETS:fetch(*x)
 print('Optional lip-sync installed. Restart VoiceForge.')
if __name__=='__main__':main()
