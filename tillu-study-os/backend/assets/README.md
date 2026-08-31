# Assets

This directory contains static assets used by the Tillu AI Study OS backend.

## Audio

- **`chime.mp3`** — Audio chime played when a reminder fires.
  Place a short chime/notification sound file here named exactly `chime.mp3`.
  The reminder agent (`app/agents/reminder_agent.py`) looks for this file at startup.
  If the file is not present, the audio channel is silently skipped and a warning is logged.

## Supported formats

`pygame.mixer` supports MP3, OGG, and WAV formats. Rename to `chime.mp3` regardless of
original format, or update `_play_chime()` in `reminder_agent.py` if you prefer a different
file name.
