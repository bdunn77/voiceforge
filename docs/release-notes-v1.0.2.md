# VoiceForge 1.0.2

Patch release adding a clean shutdown path.

## Fixed / Added
- **Quit VoiceForge button** in the Settings tab: fully stops the background server from the UI so nothing keeps running after you close the app.
- New loopback-only `POST /api/shutdown` endpoint (protected by the existing same-origin POST policy).

## Notes
No breaking changes. Closing the browser tab alone still leaves the server running by design (so renders survive a refresh); use the Quit button when you want it fully stopped. The app never auto-starts at boot.
