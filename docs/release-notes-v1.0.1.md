# VoiceForge 1.0.1

## Fixed
- **No more flashing terminal windows on Windows.** Every background tool call (ffmpeg, ffprobe, yt-dlp, Wav2Lip, GFPGAN) now launches with `CREATE_NO_WINDOW` and a hidden startup window, so cloning, generation, and video rendering run completely silently in the background.

No other changes; fully backward compatible with v1.0.0.
