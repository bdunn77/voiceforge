"""
VoiceForge - local voice cloning & TTS studio powered by Venice AI.
Runs entirely on your machine at http://127.0.0.1:8765

Requires: Python 3.10+, ffmpeg on PATH, yt-dlp (pip install yt-dlp).
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.parse import urlparse

import keyring
import requests
from flask import Flask, jsonify, request, send_file, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
VOICES_PATH = os.path.join(DATA_DIR, "voices.json")
MAX_UPLOAD = 250 * 1024 * 1024
MAX_TEXT = 5000
ALLOWED_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be", "www.youtu.be"}

KEY_SERVICE = "voiceforge"
KEY_NAME = "venice_api_key"
VENICE_API = "https://api.venice.ai/api/v1"
TTS_MODEL = "tts-chatterbox-hd"

# --- local lip-sync engine (Wav2Lip) ---
LS_ROOT = os.path.join(BASE_DIR, ".local", "lipsync")
LS_REPO = os.path.join(LS_ROOT, "Wav2Lip")
LS_CKPT = os.path.join(LS_REPO, "checkpoints", "wav2lip_gan.pth")
LS_S3FD = os.path.join(LS_REPO, "face_detection", "detection", "sfd", "s3fd.pth")
LS_ENHANCE = os.path.join(BASE_DIR, "scripts", "enhance.py")
LS_GFP = os.path.join(LS_ROOT, "weights", "GFPGANv1.4.pth")

os.makedirs(DATA_DIR, exist_ok=True)
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD


# ---------------- helpers ----------------

def fail(msg, code=400):
    return jsonify({"error": msg}), code


def load_voices():
    if not os.path.exists(VOICES_PATH):
        return []
    try:
        with open(VOICES_PATH, encoding="utf-8") as f:
            voices = json.load(f)
        if not isinstance(voices, list):
            raise ValueError("voice library must be a list")
        required = {"id", "name", "voice_id", "created_at"}
        if any(not isinstance(v, dict) or not required.issubset(v) for v in voices):
            raise ValueError("voice library has an invalid record")
        return voices
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("The local voice library is damaged. Back up or remove data/voices.json, then restart.") from exc


def save_voices(voices):
    tmp = VOICES_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(voices, f, indent=2)
    os.replace(tmp, VOICES_PATH)


def venice_key():
    return keyring.get_password(KEY_SERVICE, KEY_NAME)


def require_key():
    k = venice_key()
    if not k:
        raise RuntimeError("No Venice API key set. Add one in the Settings tab.")
    return k


def valid_youtube_url(value):
    try:
        parsed = urlparse(value)
        return parsed.scheme in ("http", "https") and (parsed.hostname or "").lower() in ALLOWED_YOUTUBE_HOSTS
    except ValueError:
        return False


def capabilities():
    reasons = []
    if not os.path.isdir(LS_REPO): reasons.append("Wav2Lip is not installed")
    if not os.path.isfile(LS_CKPT): reasons.append("Wav2Lip model is missing")
    if not os.path.isfile(LS_S3FD): reasons.append("face detector model is missing")
    try:
        import torch
        torch_info = {"installed": True, "cuda": bool(torch.cuda.is_available()),
                      "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"}
    except Exception:
        torch_info = {"installed": False, "cuda": False, "device": None}
        reasons.append("PyTorch is not installed")
    hq_reasons = list(reasons)
    if not os.path.isfile(LS_GFP): hq_reasons.append("GFPGAN model is missing")
    return {"lipsync": not reasons, "lipsync_reason": "; ".join(reasons),
            "hq": not hq_reasons, "hq_reason": "; ".join(hq_reasons), "torch": torch_info}


def checked_text(value):
    text = str(value or "").strip()
    if not text or len(text) > MAX_TEXT:
        raise RuntimeError("Text must contain between 1 and %d characters." % MAX_TEXT)
    return text


def tool(name):
    # Prefer the bundled copy inside .venv so upgrades apply immediately.
    bundled = os.path.join(BASE_DIR, ".venv", "Scripts", name + ".exe")
    p = bundled if os.path.exists(bundled) else shutil.which(name)
    if not p:
        raise RuntimeError("%s was not found. Install it first." % name)
    return p


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        tail = (r.stderr or "")[-800:]
        raise RuntimeError("command failed: %s\n%s" % (" ".join(cmd[:4]), tail))
    return r


def prepare_reference(src, dst, start=None, length=None):
    """Produce a clean single-speaker reference: mono 24 kHz, loudness-normalized.
    If the caller gives no range, auto-trim: skip leading noise, cap at 90 s."""
    ff = tool("ffmpeg")
    cmd = [ff, "-y"]
    if start:
        cmd += ["-ss", str(start)]
    cmd += ["-i", src]
    if length:
        cmd += ["-t", str(length)]
    else:
        det = run([ff, "-i", src, "-af",
                   "silencedetect=noise=-35dB:d=0.5", "-f", "null", "-"])
        m = re.search(r"silence_end: ([\\d.]+)", det.stderr)
        begin = max(0.0, float(m.group(1)) - 0.3) if m else 0.0
        cmd += ["-ss", "%.2f" % begin, "-t", "90"]
    cmd += ["-ac", "1", "-ar", "24000",
            "-af", "loudnorm=I=-16:LRA=11:TP=-1.5", dst]
    run(cmd)


def venice_upload(path):
    with open(path, "rb") as fh:
        resp = requests.post(
            VENICE_API + "/audio/voices",
            headers={"Authorization": "Bearer " + require_key()},
            files={"file": (os.path.basename(path), fh, "audio/wav")},
            data={"model": TTS_MODEL},
            timeout=300,
        )
    if resp.status_code != 200:
        raise RuntimeError("Venice rejected the voice upload (HTTP %s)." % resp.status_code)
    vid = resp.json().get("id")
    if not vid:
        raise RuntimeError("Venice did not return a voice handle.")
    return vid


def venice_speech(voice_handle, text, speed=1.0):
    resp = requests.post(
        VENICE_API + "/audio/speech",
        headers={"Authorization": "Bearer " + require_key(),
                 "Content-Type": "application/json"},
        json={"model": TTS_MODEL, "voice": voice_handle, "input": text,
              "speed": max(0.5, min(2.0, float(speed or 1.0)))},
        timeout=300,
    )
    if resp.status_code != 200:
        raise RuntimeError("Venice rejected speech generation (HTTP %s)." % resp.status_code)
    return resp.content


# ---------------- routes ----------------

@app.before_request
def protect_local_mutations():
    if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
        origin = request.headers.get("Origin")
        if origin and origin.rstrip("/") not in {"http://127.0.0.1:8765", "http://localhost:8765"}:
            return fail("Request origin is not allowed.", 403)


@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/capabilities")
def capability_status():
    return jsonify(capabilities())


@app.errorhandler(413)
def upload_too_large(_):
    return fail("Upload is too large (250 MB maximum).", 413)


@app.get("/api/settings/status")
def settings_status():
    return jsonify({"has_key": bool(venice_key())})


@app.post("/api/settings/key")
def set_key():
    key = ((request.json or {}).get("api_key") or "").strip()
    if len(key) < 20:
        return fail("That does not look like a valid Venice API key.")
    keyring.set_password(KEY_SERVICE, KEY_NAME, key)
    return jsonify({"ok": True})


@app.delete("/api/settings/key")
def clear_key():
    try:
        keyring.delete_password(KEY_SERVICE, KEY_NAME)
    except Exception:
        pass
    return jsonify({"ok": True})


@app.get("/api/voices")
def list_voices():
    try:
        return jsonify(load_voices())
    except RuntimeError as exc:
        return fail(str(exc), 500)


@app.post("/api/clone")
def clone_voice():
    """Clone from a YouTube URL or an uploaded audio file. Returns a voice handle."""
    tmpdir = None
    try:
        if request.files.get("file"):
            tmpdir = tempfile.mkdtemp(prefix="voiceforge_")
            src = os.path.join(tmpdir, "source.bin")
            request.files["file"].save(src)
        elif (request.form.get("url") or "").strip():
            tmpdir = tempfile.mkdtemp(prefix="voiceforge_")
            src = os.path.join(tmpdir, "source.mp3")
            url = request.form["url"].strip()
            if not valid_youtube_url(url):
                return fail("Only normal youtube.com and youtu.be links are accepted.")
            ytdlp = tool("yt-dlp")
            ff = tool("ffmpeg")
            base_cmd = [ytdlp, "--no-playlist", "--no-update",
                        "-x", "--audio-format", "mp3",
                        "--ffmpeg-location", ff, "-o", src]
            # Fallback ladder for YouTube 403/SABR failures:
            # 1) default bestaudio  2) android+web_embedded clients  3) combined fmt 18
            strategies = [
                base_cmd + ["-f", "bestaudio/best", url],
                base_cmd + ["-f", "bestaudio/best", "--extractor-args",
                            "youtube:player_client=android,web_embedded", url],
                base_cmd + ["-f", "18/bestaudio/best", "--extractor-args",
                            "youtube:player_client=android,web_embedded", url],
            ]
            last_err = None
            for attempt in strategies:
                try:
                    run(attempt, timeout=900)
                    last_err = None
                    break
                except RuntimeError as e:
                    last_err = e
                    if os.path.exists(src):
                        try:
                            os.remove(src)
                        except OSError:
                            pass
            if last_err:
                raise RuntimeError(
                    "Could not download audio from that link. "
                    "YouTube may be blocking this video or yt-dlp may need an update. Details: "
                    + str(last_err))
        else:
            return fail("Provide a YouTube 'url' or upload an audio 'file'.")

        ref = os.path.join(tmpdir, "reference.wav")
        prepare_reference(src, ref,
                          start=request.form.get("start") or None,
                          length=request.form.get("length") or None)
        return jsonify({"voice_id": venice_upload(ref)})
    except Exception as e:
        return fail(str(e), 500)
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


@app.post("/api/voices")
def add_voice():
    body = request.json or {}
    name = (body.get("name") or "").strip()
    handle = (body.get("voice_id") or "").strip()
    if not name or len(name) > 100 or not re.fullmatch(r"vv_[A-Za-z0-9_-]+", handle):
        return fail("A name and valid Venice voice handle are required.")
    voices = load_voices()
    voices.append({"id": uuid.uuid4().hex[:12], "name": name,
                   "voice_id": handle, "created_at": int(time.time())})
    save_voices(voices)
    return jsonify({"ok": True, "voices": voices})


@app.patch("/api/voices/<vid>")
def rename_voice(vid):
    name = ((request.json or {}).get("name") or "").strip()
    if not name:
        return fail("A non-empty 'name' is required.")
    voices = load_voices()
    row = next((v for v in voices if v["id"] == vid), None)
    if not row:
        return fail("Unknown voice.", 404)
    row["name"] = name
    save_voices(voices)
    return jsonify({"ok": True, "voices": voices})


@app.delete("/api/voices/<vid>")
def delete_voice(vid):
    voices = [v for v in load_voices() if v["id"] != vid]
    save_voices(voices)
    return jsonify({"ok": True, "voices": voices})


@app.post("/api/generate")
def generate():
    body = request.json or {}
    vid = (body.get("voice_id") or "").strip()
    text = (body.get("text") or "").strip()
    if not vid or not text:
        return fail("'voice_id' and 'text' are both required.")
    if len(text) > MAX_TEXT:
        return fail("Text is too long (5000 characters maximum).")
    row = next((v for v in load_voices() if v["id"] == vid), None)
    if not row:
        return fail("Unknown voice.", 404)
    tmpdir = tempfile.mkdtemp(prefix="voiceforge_gen_")
    try:
        wav = os.path.join(tmpdir, "out.wav")
        mp3 = os.path.join(tmpdir, "out.mp3")
        with open(wav, "wb") as f:
            f.write(venice_speech(row["voice_id"], text, body.get("speed", 1.0)))
        run([tool("ffmpeg"), "-y", "-i", wav,
             "-codec:a", "libmp3lame", "-q:a", "2", mp3])
        with open(mp3, "rb") as f:
            buf = io.BytesIO(f.read())
        return send_file(buf, mimetype="audio/mpeg",
                         download_name="voiceforge.mp3")
    except Exception as e:
        return fail(str(e), 500)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@app.post("/api/video")
def make_video():
    """HeyGen-style talking video from a cloned voice.
    Multipart: voice_id, text, speed, optional image file, optional lipsync=1.
    lipsync=1 runs local Wav2Lip so the mouth moves; otherwise the photo gets
    a slow cinematic zoom while the voice narrates."""
    tmpdir = tempfile.mkdtemp(prefix="voiceforge_vid_")
    try:
        vid = ((request.form.get("voice_id") or "").strip())
        text = ((request.form.get("text") or "").strip())
        speed = request.form.get("speed", "1")
        use_ls = (request.form.get("lipsync") or "") == "1"
        quality = ((request.form.get("quality") or "fast").strip().lower())
        use_hq = quality in ("hq", "high", "1", "true")
        if not vid or not text:
            return fail("'voice_id' and 'text' are both required.")
        if len(text) > MAX_TEXT:
            return fail("Text is too long (5000 characters maximum).")
        row = next((v for v in load_voices() if v["id"] == vid), None)
        if not row:
            return fail("Unknown voice.", 404)

        img = os.path.join(tmpdir, "face.png")
        if request.files.get("image"):
            request.files["image"].save(img)
        elif not use_ls:
            # neutral gradient backdrop if no photo supplied
            run([tool("ffmpeg"), "-y", "-f", "lavfi",
                 "-i", "gradients=s=1280x720:c0=#1a1033:c1=#0f1115:x0=0:y0=0:x1=1280:y1=720",
                 "-frames:v", "1", img])

        caps = capabilities()
        if use_ls and not caps["lipsync"]:
            return fail("Lip-sync is optional and not installed. Run scripts/setup_lipsync.py first.", 503)
        if use_ls and use_hq and not caps["hq"]:
            return fail("HQ restoration is not installed. Re-run optional lip-sync setup.", 503)
        if use_ls and not request.files.get("image"):
            return fail("Lip-sync mode needs a face photo.")

        # 1) narration -> wav -> mp3
        wav = os.path.join(tmpdir, "speech.wav")
        mp3 = os.path.join(tmpdir, "speech.mp3")
        with open(wav, "wb") as f:
            f.write(venice_speech(row["voice_id"], text, float(speed)))
        run([tool("ffmpeg"), "-y", "-i", wav,
             "-codec:a", "libmp3lame", "-q:a", "2", mp3])

        out = os.path.join(tmpdir, "out.mp4")
        if use_ls:
            # 2) Wav2Lip regenerates the mouth region frame-by-frame
            #    (temporal smoothing enabled by omitting --nosmooth)
            run([sys.executable, os.path.join(LS_REPO, "inference.py"),
                 "--checkpoint_path", LS_CKPT,
                 "--face", img, "--audio", wav,
                 "--outfile", out],
                timeout=14400, cwd=LS_REPO)
            # 3) GFPGAN face restoration pass -> sharper, more realistic mouth
            if use_hq and os.path.exists(LS_GFP):
                enhanced = os.path.join(tmpdir, "out_enhanced.mp4")
                env = os.environ.copy()
                env["VOICEFORGE_GFP_WEIGHTS"] = LS_GFP
                r = subprocess.run([sys.executable, LS_ENHANCE, out, enhanced], capture_output=True,
                                   text=True, timeout=14400, cwd=BASE_DIR, shell=False, env=env)
                if r.returncode != 0:
                    raise RuntimeError("HQ face restoration failed; try Fast quality.")
                out = enhanced
        else:
            # 2) measure audio duration -> frame count at 25 fps
            pr = run([tool("ffprobe"), "-v", "error", "-show_entries", "format=duration",
                      "-of", "csv=p=0", mp3])
            dur = max(1.0, float(pr.stdout.strip()))
            frames = int(dur * 25) + 10

            # 3) animate photo (slow zoom-in) + mux narration -> mp4
            vf = ("scale=1600:900:force_original_aspect_ratio=increase,crop=1600:900,"
                  "zoompan=z='min(zoom+0.0006,1.18)':d=%d:s=1280x720:fps=25,"
                  "format=yuv420p" % frames)
            run([tool("ffmpeg"), "-y", "-loop", "1", "-i", img, "-i", mp3,
                 "-vf", vf,
                 "-map", "0:v", "-map", "1:a",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "21",
                 "-c:a", "aac", "-b:a", "192k", "-shortest", out], timeout=600)

        with open(out, "rb") as f:
            buf = io.BytesIO(f.read())
        return send_file(buf, mimetype="video/mp4",
                         download_name="voiceforge_video.mp4")
    except Exception as e:
        return fail(str(e), 500)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    print("VoiceForge running at http://127.0.0.1:8765")
    app.run(host="127.0.0.1", port=8765, debug=False)
