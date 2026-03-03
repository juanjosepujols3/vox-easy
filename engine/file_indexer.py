"""
File indexer for @File tagging in Cursor, Windsurf, VSCode, Antigravity y Claude Code.
Indexes the active project's files so dictated file names can be converted
to @path/file references.
"""

import difflib
import os
import subprocess
import threading
import time
from typing import Optional

# ── Bundle ID sets ──────────────────────────────────────────────

# Editors que tienen "proyecto activo" consultable via osascript
EDITOR_BUNDLE_IDS = {
    "com.todesktop.230313mzl4w4u92",  # Cursor
    "com.exafunction.windsurf",        # Windsurf
    "com.microsoft.VSCode",            # VS Code
    "com.google.antigravity",          # Antigravity (fork de VSCode by Google)
}

# Terminales donde corre Claude Code (se usa CWD del proceso activo)
TERMINAL_BUNDLE_IDS = {
    "com.apple.Terminal",              # Terminal.app nativo
    "com.googlecode.iterm2",           # iTerm2
    "dev.warp.Warp-Stable",            # Warp
    "com.mitchellh.ghostty",           # Ghostty
    "net.kovidgoyal.kitty",            # Kitty
}

# Todos los bundle IDs donde el tagging tiene sentido
ALL_SUPPORTED_BUNDLE_IDS = EDITOR_BUNDLE_IDS | TERMINAL_BUNDLE_IDS

# ── File indexing config ─────────────────────────────────────────

INDEXED_EXTENSIONS = {
    '.ts', '.tsx', '.js', '.jsx', '.py', '.rs', '.go',
    '.css', '.scss', '.html', '.json', '.yaml', '.yml',
    '.md', '.env', '.toml', '.swift', '.kt', '.java',
    '.c', '.cpp', '.h', '.vue', '.svelte', '.rb', '.php',
    '.sh', '.bash', '.zsh', '.fish',
}

SKIP_DIRS = {
    'node_modules', '.git', '__pycache__', '.next', 'dist', 'build',
    '.venv', 'venv', 'env', '.cache', 'coverage', '.nyc_output',
    '.turbo', '.svelte-kit', 'target', 'out',
}

# ── Index state ──────────────────────────────────────────────────

_index_lock = threading.Lock()
_file_index = {}          # key_lower → relative_path
_index_project_path = None
_last_index_time = 0.0
INDEX_TTL = 30.0          # segundos antes de re-indexar


# ── Project path detection ───────────────────────────────────────

def _get_editor_project_path(bundle_id: str) -> Optional[str]:
    """Consulta al editor (Cursor/Windsurf/VSCode/Antigravity) por su directorio activo."""
    if "todesktop" in bundle_id or "cursor" in bundle_id.lower():
        app_name = "Cursor"
    elif "windsurf" in bundle_id.lower():
        app_name = "Windsurf"
    elif "antigravity" in bundle_id.lower():
        app_name = "Antigravity"
    elif "vscode" in bundle_id.lower():
        app_name = "Visual Studio Code"
    else:
        return None

    # Intentar obtener el path del proyecto vía AppleScript
    # VSCode-based apps exponen el path del workspace en el título de ventana
    script = f'tell application "{app_name}" to return POSIX path of (path of front window)'
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True, text=True, timeout=3
        )
        path = result.stdout.strip()
        if path and os.path.isdir(path):
            return path
    except Exception:
        pass

    # Fallback: leer el título de la ventana y extraer el path
    try:
        script2 = f'tell application "System Events" to get name of front window of process "{app_name}"'
        result2 = subprocess.run(
            ['osascript', '-e', script2],
            capture_output=True, text=True, timeout=3
        )
        title = result2.stdout.strip()
        # El título suele ser "nombre_archivo — nombre_carpeta" o similar
        # Buscar si algún segmento es un directorio existente
        for part in title.split('—'):
            part = part.strip()
            candidate = os.path.expanduser(f"~/{part}")
            if os.path.isdir(candidate):
                return candidate
    except Exception:
        pass

    return None


def _get_terminal_cwd(bundle_id: str) -> Optional[str]:
    """Obtiene el CWD del proceso en el terminal activo (donde corre Claude Code)."""
    try:
        if "apple.Terminal" in bundle_id:
            # Terminal.app: pedir el directorio del tab activo
            script = (
                'tell application "Terminal" to '
                'return POSIX path of (current settings of front window)'
            )
            # Alternativa más confiable: obtener PID del shell del tab activo
            script = '''
                tell application "Terminal"
                    set frontTab to selected tab of front window
                    set shellPID to id of frontTab
                    return shellPID as string
                end tell
            '''
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True, text=True, timeout=3
            )
            pid_str = result.stdout.strip()
            if pid_str.isdigit():
                cwd = _cwd_from_pid(int(pid_str))
                if cwd:
                    return cwd

        # Fallback universal: encontrar el proceso foreground del terminal
        # Buscar procesos hijos de terminales conocidos
        return _cwd_from_frontmost_terminal()

    except Exception:
        pass
    return None


def _cwd_from_pid(pid: int) -> Optional[str]:
    """Obtiene el CWD de un proceso por su PID usando lsof."""
    try:
        result = subprocess.run(
            ['lsof', '-a', '-p', str(pid), '-d', 'cwd', '-Fn'],
            capture_output=True, text=True, timeout=3
        )
        for line in result.stdout.splitlines():
            if line.startswith('n'):
                path = line[1:].strip()
                if os.path.isdir(path):
                    return path
    except Exception:
        pass
    return None


def _cwd_from_frontmost_terminal() -> Optional[str]:
    """Heurística: buscar el proceso shell más reciente y obtener su CWD."""
    try:
        # Obtener PID del proceso de shell más reciente (bash/zsh/fish)
        result = subprocess.run(
            ['pgrep', '-n', '-x', 'zsh,bash,fish,sh'],
            capture_output=True, text=True, timeout=3
        )
        pid_str = result.stdout.strip()
        if pid_str.isdigit():
            return _cwd_from_pid(int(pid_str))
    except Exception:
        pass
    return None


def get_active_project_path(bundle_id: str) -> Optional[str]:
    """Entry point: detecta si es editor o terminal y obtiene el path de proyecto."""
    if bundle_id in EDITOR_BUNDLE_IDS:
        return _get_editor_project_path(bundle_id)
    elif bundle_id in TERMINAL_BUNDLE_IDS:
        return _get_terminal_cwd(bundle_id)
    return None


# ── File indexing ────────────────────────────────────────────────

def index_project_files(project_path: str) -> dict:
    """Recorre project_path y construye índice filename → relative_path."""
    index = {}
    try:
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
            for fname in files:
                _, ext = os.path.splitext(fname)
                if ext.lower() not in INDEXED_EXTENSIONS:
                    continue
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, project_path)
                fname_lower = fname.lower()
                name_no_ext = os.path.splitext(fname)[0].lower()
                index[fname_lower] = rel
                if name_no_ext not in index:
                    index[name_no_ext] = rel
    except Exception as e:
        print(f"[file_indexer] index error: {e}", flush=True)
    return index


def _ensure_index(bundle_id: str):
    """Refresca el índice si está desactualizado o el proyecto cambió."""
    global _file_index, _index_project_path, _last_index_time
    now = time.monotonic()
    with _index_lock:
        if now - _last_index_time < INDEX_TTL and _file_index:
            return
        project = get_active_project_path(bundle_id)
        if not project:
            return
        _index_project_path = project
        _file_index = index_project_files(project)
        _last_index_time = now
        print(f"[file_indexer] indexed {len(_file_index)} entries from {project}", flush=True)


# ── Public API ───────────────────────────────────────────────────

def find_file_by_name(query: str, bundle_id: str = "", threshold: float = 0.60) -> Optional[str]:
    """Busca un archivo que coincida con query. Devuelve @relative/path o None."""
    _ensure_index(bundle_id)
    if not _file_index:
        return None

    query_lower = query.lower().strip()
    if not query_lower:
        return None

    # Match exacto
    if query_lower in _file_index:
        return f"@{_file_index[query_lower]}"

    # Match fuzzy
    candidates = list(_file_index.keys())
    matches = difflib.get_close_matches(query_lower, candidates, n=1, cutoff=threshold)
    if matches:
        return f"@{_file_index[matches[0]]}"

    return None


def apply_file_tagging(text: str, bundle_id: str) -> str:
    """Escanea el texto y reemplaza menciones de archivos con @path/archivo.

    Detecta patrones como:
    - ES: "el archivo Login", "el componente Header", "el módulo auth"
    - EN: "the Login file", "the Header component", "the auth module"
    - Directo: "helper.swift", "README.md" (nombre con extensión conocida)
    """
    import re

    # Patrón 1: keyword + nombre  → "el componente Header" / "the Login file"
    pattern_kw = re.compile(
        r'\b(?:archivo|fichero|componente|modulo|file|component|module|clase|class)\s+'
        r'([A-Za-z0-9_\-\.]+)',
        re.IGNORECASE
    )

    # Patrón 2: nombre con extensión conocida directamente en el texto
    ext_list = '|'.join(e.lstrip('.') for e in INDEXED_EXTENSIONS)
    pattern_ext = re.compile(
        r'\b([A-Za-z0-9_\-]+\.(?:' + ext_list + r'))\b',
        re.IGNORECASE
    )

    def replace_kw(m):
        candidate = m.group(1)
        tagged = find_file_by_name(candidate, bundle_id)
        return tagged if tagged else m.group(0)

    def replace_ext(m):
        candidate = m.group(1)
        tagged = find_file_by_name(candidate, bundle_id)
        return tagged if tagged else m.group(0)

    text = pattern_kw.sub(replace_kw, text)
    text = pattern_ext.sub(replace_ext, text)
    return text
