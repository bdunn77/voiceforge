"""Optional GFPGAN video post-process; model weights are user-installed."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
import cv2
from gfpgan import GFPGANer

def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: enhance.py INPUT.mp4 OUTPUT.mp4")
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    weights = Path(os.environ["VOICEFORGE_GFP_WEIGHTS"])
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    ffprobe = shutil.which("ffprobe") or "ffprobe"
    with tempfile.TemporaryDirectory(prefix="vf_enh_") as name:
        temp=Path(name); frames=temp/'frames'; restored=temp/'restored'; frames.mkdir(); restored.mkdir()
        audio=temp/'audio.m4a'; silent=temp/'silent.mp4'
        subprocess.run([ffmpeg,'-y','-i',str(src),str(frames/'%06d.png')],check=True,capture_output=True)
        subprocess.run([ffmpeg,'-y','-i',str(src),'-vn','-c:a','copy',str(audio)],check=True,capture_output=True)
        engine=GFPGANer(model_path=str(weights),upscale=1,arch='clean',channel_multiplier=2,bg_upsampler=None)
        names=sorted(frames.glob('*.png'))
        for i,path in enumerate(names,1):
            image=cv2.imread(str(path),cv2.IMREAD_COLOR)
            _,_,result=engine.enhance(image,has_aligned=False,only_center_face=False,paste_back=True)
            cv2.imwrite(str(restored/path.name),result)
            if i%25==0: print(f'restored {i}/{len(names)}',flush=True)
        probe=subprocess.run([ffprobe,'-v','error','-select_streams','v:0','-show_entries','stream=r_frame_rate','-of','csv=p=0',str(src)],check=True,capture_output=True,text=True)
        rate=probe.stdout.strip() or '25'
        subprocess.run([ffmpeg,'-y','-framerate',rate,'-i',str(restored/'%06d.png'),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p',str(silent)],check=True,capture_output=True)
        subprocess.run([ffmpeg,'-y','-i',str(silent),'-i',str(audio),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-shortest',str(dst)],check=True,capture_output=True)
if __name__=='__main__': main()
