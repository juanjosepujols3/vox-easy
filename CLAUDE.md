# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Vox Easy** is a universal AI dictation application for macOS. It consists of:
1. **Desktop app** (main.py): Native macOS app using pywebview for UI, with global hotkey support
2. **API server** (api.py): FastAPI backend for transcription, user auth, and usage tracking
3. **Intelligent text processing pipeline**: Client-side text transformations (filler removal, punctuation, code mode, etc.)

The app uses the Groq API (whisper-large-v3-turbo) for fast speech-to-text transcription.

## Architecture

### Desktop App (main.py)
- **ApiBridge**: JavaScript-Python bridge for webview communication. All JS->Python calls go through methods exposed via `@expose` decorator
- **AudioRecorder** (engine/audio.py): Records audio using sounddevice, includes silence detection and visualizer
- **KeyboardController** (engine/keyboard.py): Global hotkey detection using macOS CGEventTap, supports fn key
- **Transcriber** (engine/transcriber.py): Groq API client for speech-to-text
- **Text Processing Pipeline** (engine/text_processing.py): Pure functions for filler removal, punctuation, self-correction, list formatting, and code mode transformations
- **Storage** (engine/storage.py): Local config persistence in ~/.voxeasy/config.json

### API Server (api.py)
- **Auth**: JWT-based authentication using python-jose
- **Database**: PostgreSQL with SQLAlchemy async (models.py defines User, WeeklyUsage, UserConfig)
- **Usage Tracking**: Free tier gets 3000 words/week, Pro unlimited
- **Config Sync**: Server-side config storage for multi-device support
- **Style Transform**: Claude Haiku integration for formality rewrites (casual/formal/email)

### Text Processing Pipeline
All processing runs client-side in main.py after transcription. The pipeline is pure, stateless, and modular:
1. `remove_fillers()` - Remove muletillas (es) or filler words (en)
2. `dictate_punctuation()` - Convert "punto", "coma" → punctuation marks
3. `detect_self_correction()` - Handle "mejor dicho", "I mean" corrections
4. `format_list()` - Detect ordinals ("primero", "segundo") → numbered lists
5. **Code Mode** (when enabled):
   - `apply_code_casing()` - "camel case my variable" → "myVariable"
   - `apply_code_punctuation()` - "doble igual" → "==", "flecha" → "=>"
   - `apply_file_tagging()` - Uses file_indexer to tag filenames in transcription
   - Dev terms added to Whisper prompt for better recognition

### Key Concepts
- **Hotkey parsing**: Stored as `"<fn>"`, `"<cmd>+<shift>+r"`, etc. See engine/keyboard.py for modifier mapping
- **Language auto-detection**: Groq auto-detects by default, can force with `language="es"` or `"en"`
- **Dev mode**: Enables code-specific transformations and boosts Whisper with tech terms
- **Low volume mode**: Lower silence threshold + 2x gain for quiet environments

## Common Commands

### Development
```bash
# Run API server
uvicorn api:app --reload

# Run desktop app (development)
python main.py
```

### Building macOS App
```bash
# Build both Intel and arm64 DMGs
./build.sh

# Build only arm64 (Apple Silicon)
.venv/bin/pyinstaller vox-arm64.spec --clean --noconfirm

# Build only Intel (requires .venv-intel on arm64 Macs)
# On arm64 Mac, first create Intel venv:
arch -x86_64 ~/.pyenv/versions/3.9.6/bin/python3 -m venv .venv-intel
arch -x86_64 .venv-intel/bin/pip install -r requirements-app.txt pyinstaller
# Then build:
arch -x86_64 .venv-intel/bin/pyinstaller vox-intel.spec --clean --noconfirm --distpath dist-intel
```

### Docker Deployment
```bash
# Build and run API server
docker build -t voxeasy .
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql+asyncpg://... \
  -e GROQ_API_KEY=... \
  -e ANTHROPIC_API_KEY=... \
  voxeasy
```

## Dependencies

- **Desktop app** (requirements-app.txt): pywebview, sounddevice, scipy, numpy, httpx, requests, pyinstaller
- **API server** (requirements.txt): FastAPI, uvicorn, SQLAlchemy, asyncpg, python-jose, passlib, httpx
- **Frontend**: Tailwind CSS, DaisyUI (web/ directory)

## Environment Variables

### API Server
- `DATABASE_URL`: PostgreSQL connection string (auto-converted to asyncpg format)
- `GROQ_API_KEY`: Required for transcription
- `ANTHROPIC_API_KEY`: Required for style transformations
- `JWT_SECRET`: Secret for JWT token signing
- `PORT`: Server port (default: 8000)

### Desktop App
- `VOX_API_URL`: API endpoint (default: https://unicords-voxeasy-app.ujamzy.easypanel.host)
- `GROQ_API_KEY`: Groq API key for transcription

## File Structure Notes

- **engine/**: Core modules (audio, keyboard, transcriber, text_processing, file_indexer, dev_terms, storage)
- **web/**: HTML/CSS for pywebview UI (app.html is main desktop UI, index.html/login.html are landing pages)
- **assets/**: Icons, images, DMG backgrounds
- **vox-{arm64,intel}.spec**: PyInstaller specs for macOS builds
- **build.sh**: Automated build script that creates DMGs for both architectures

## Code Patterns

### Adding a new text transformation
1. Add pure function to engine/text_processing.py
2. Wire it into ApiBridge.process_text() in main.py
3. Add UI toggle in web/app.html if needed
4. Update config save/load if it's a persistent setting

### Adding a new API endpoint
1. Define Pydantic schema at top of api.py
2. Add route with `@app.{method}("/path")`
3. Use `Depends(get_current_user)` for authenticated endpoints
4. Update usage tracking if it consumes resources

### Modifying keyboard hotkeys
1. Hotkey format: `"<modifier>+<key>"` or just `"<modifier>"` for modifier-only
2. Parse in KeyboardController using _CONFIG_TO_FLAG mapping
3. Display using hotkey_to_display() for UI
4. Save to config via save_hotkey_config()

## macOS Permissions

The app requires:
- **Microphone**: For audio recording (NSMicrophoneUsageDescription)
- **Accessibility**: For typing transcribed text (NSAppleEventsUsageDescription)
- Both are declared in vox-{arm64,intel}.spec info_plist

## Notes

- The app stores config locally in `~/.voxeasy/config.json` (hotkey, language, token)
- Server config sync is separate - stored in UserConfig table
- PyInstaller excludes unused ML frameworks (torch, onnxruntime, faster_whisper) to reduce bundle size
- Whisper hallucination filtering is done via _WHISPER_HALLUCINATIONS set in main.py
- Code signing: `codesign --deep --force --sign - "dist/Vox Easy.app"` (ad-hoc signing for development)
