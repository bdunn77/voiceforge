# Troubleshooting

- **ffmpeg missing:** ensure `ffmpeg` and `ffprobe` work in a new terminal.
- **YouTube 403:** update yt-dlp or upload a file you have permission to use.
- **Linux keyring error:** configure a Secret Service-compatible keyring.
- **Lip-sync unavailable:** follow `docs/optional-lipsync.md`, then restart.
- **CUDA unavailable:** update the NVIDIA driver or use CPU mode.
- **Port 8765 busy:** close the prior VoiceForge process.
- **Damaged voice library:** back up `data/voices.json`, then repair or remove it.
