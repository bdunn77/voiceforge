# Privacy and data flow

```text
Browser on this device
        | localhost only
        v
VoiceForge Flask server ---- OS credential vault (Venice API key)
        |
        +---- local data/voices.json (names and Venice handles)
        +---- temporary media directory (deleted after use; completed job expires after 30 min)
        +---- Venice API over HTTPS (reference audio, requested text, voice handle)
        +---- YouTube/yt-dlp when the user supplies a permitted YouTube URL
        +---- optional local Wav2Lip/GFPGAN/ffmpeg processing
```

VoiceForge has no telemetry and binds only to `127.0.0.1`. Do not expose it to a LAN or the internet: it has no multi-user authentication or TLS. The Venice API necessarily receives media/text needed for cloning and synthesis; review Venice's privacy terms before use. YouTube is contacted only for a URL the user submits.

Deleting a voice in VoiceForge removes its **local library record only**. It does not represent or guarantee deletion of data held by Venice. Use Venice account/API controls or contact Venice for upstream deletion and retention requests.
