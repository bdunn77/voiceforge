# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.2] - 2026-08-27

### Added
- "Quit VoiceForge" button in Settings and a loopback-only `POST /api/shutdown` endpoint, so users can fully stop the background server (and any active render) from the UI.

## [1.0.1] - 2026-08-26

### Fixed
- Child tools (ffmpeg, ffprobe, yt-dlp, Wav2Lip, GFPGAN) no longer flash terminal windows on Windows; all subprocesses launch with `CREATE_NO_WINDOW` and a hidden startup window.

## [1.0.0] - 2026-08-25

### Added
- Local voice cloning from permitted YouTube links and uploaded media.
- Named local voice library and Venice-powered MP3 generation.
- Cinematic video generation and optional separately installed Wav2Lip/GFPGAN support.
- Real backend video stages, progress display, cancellation, and 30-minute result retention.
- OS credential-vault storage, loopback-only server, same-origin checks, release scanning, CI, CodeQL, and Dependabot.
- Cross-platform launchers and a Windows Desktop shortcut helper.
