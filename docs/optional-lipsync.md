# Optional lip-sync

VoiceForge does not bundle Wav2Lip, GFPGAN, PyTorch, or model weights. Wav2Lip's upstream project/model is limited to personal/research/non-commercial use. Review <https://github.com/Rudrabha/Wav2Lip> first.

From the VoiceForge folder after core installation:

```powershell
.venv\Scripts\python scripts\setup_lipsync.py --accept-wav2lip-license
```

For a compatible NVIDIA GPU:

```powershell
.venv\Scripts\python scripts\setup_lipsync.py --accept-wav2lip-license --cuda
```

The installer requires explicit acceptance, checks out a reviewed upstream commit, verifies downloaded model SHA-256 hashes, and stores everything under ignored `.local/lipsync/`. Expect several GB of disk use. Restart VoiceForge afterward.
