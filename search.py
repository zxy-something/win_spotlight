from __future__ import annotations

import os
import threading
import unicodedata
import winreg
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from PySide6.QtCore import QObject, Signal

from logger import log

GROUP_ORDER = ("apps", "files", "folders", "settings")
GROUP_LIMITS = {"apps": 6, "files": 6, "folders": 4, "settings": 5}

APP_EXTENSIONS = {".lnk", ".url", ".exe", ".appref-ms"}
MAX_TOTAL_ENTRIES = 9000
MAX_FILES_PER_ROOT = 2600
MAX_SCAN_DEPTH = 3

SKIP_DIR_NAMES = {
    "appdata",
    "node_modules",
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    ".venv",
    "venv",
    "windows",
    "winnt",
    "$recycle.bin",
    "system volume information",
    ".cache",
    ".npm",
    ".gradle",
    ".cargo",
    ".nuget",
    "temp",
    "tmp",
}

FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_SYSTEM = 0x4

ROOT_KEYWORDS = {
    "desktop": "area de trabalho",
    "documents": "documentos meus documentos",
    "downloads": "baixados downloads",
}

SETTINGS = [
    ("Settings", "ms-settings:", "\ue713", "settings windows config configuracoes definicoes preferencias"),
    ("Wi-Fi", "ms-settings:network-wifi", "\ue701", "wifi wireless internet rede sem fio"),
    ("Bluetooth & devices", "ms-settings:bluetooth", "\ue702", "bluetooth devices dispositivos emparelhar"),
    ("Display", "ms-settings:display", "\ue7f4", "display monitor tela brilho resolucao"),
    ("Sound", "ms-settings:sound", "\ue767", "sound audio som volume alto falante microfone"),
    ("Power & battery", "ms-settings:batterysaver", "\ue850", "power battery energia bateria sleep suspender"),
    ("Installed apps", "ms-settings:appsfeatures", "\ue71d", "installed apps aplicativos programas desinstalar"),
    ("Windows Update", "ms-settings:windowsupdate", "\ue895", "windows update atualizacao atualizar"),
    ("Network & internet", "ms-settings:network", "\ue774", "network internet rede ethernet vpn proxy"),
    ("Privacy & security", "ms-settings:privacy", "\ue72e", "privacy security privacidade seguranca"),
    ("Date & time", "ms-settings:dateandtime", "\ue823", "date time data hora fuso horario"),
    ("Accounts", "ms-settings:yourinfo", "\ue77b", "accounts conta usuario account login"),
    ("Gaming", "ms-settings:gaming-gamebar", "\ue7fc", "gaming games jogos game bar captura"),
    ("Storage", "ms-settings:storagesense", "\ue8b7", "storage armazenamento disco espaco"),
]

BUILTIN_APPS = [
    ("File Explorer", "explorer.exe", "explorer files arquivos pastas"),
    ("Calculator", "calc.exe", "calculator calculadora calc"),
    ("Notepad", "notepad.exe", "notepad bloco notas texto"),
    ("Paint", "mspaint.exe", "paint pintura desenho"),
    ("Command Prompt", "cmd.exe", "command prompt cmd terminal comando"),
    ("PowerShell", "powershell.exe", "powershell terminal shell"),
    ("Task Manager", "taskmgr.exe", "task manager tarefas processos"),
]


@dataclass(slots=True)
class Entry:
    title: str
    subtitle: str
    group: str
    kind: str
    target: str
    glyph: str = ""
    n_title: str = ""
    n_extra: str = ""


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _make_entry(
    title: str,
    subtitle: str,
    group: str,
    kind: str,
    target: str,
    glyph: str = "",
    extra_keywords: str = "",
) -> Entry:
    return Entry(
        title=title,
        subtitle=subtitle,
        group=group,
        kind=kind,
        target=target,
        glyph=glyph,
        n_title=normalize(title),
        n_extra=normalize(f"{subtitle} {extra_keywords}"),
    )


def _known_folder(registry_name: str, fallback_name: str) -> Path:
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, registry_name)
        path = Path(os.path.expandvars(value))
        if path.is_dir():
            return path
    except OSError:
        pass
    return Path.home() / fallback_name


def _display_path(path: Path) -> str:
    try:
        relative = path.relative_to(Path.home())
    except ValueError:
        return str(path)
    text = str(relative)
    return "~" if text == "." else f"~\\{text}"


def _clean_title(stem: str) -> str:
    title = stem
    for suffix in (" - Atalho", " - Shortcut", " (Atalho)", " (Shortcut)"):
        if title.lower().endswith(suffix.lower()):
            title = title[: -len(suffix)]
    return title.strip() or stem


def _iter_files(root: Path, suffixes: set[str], max_depth: int, limit: int):
    queue = deque([(root, 0)])
    count = 0
    while queue and count < limit:
        directory, depth = queue.popleft()
        try:
            children = list(os.scandir(directory))
        except OSError:
            continue
        for child in children:
            try:
                if child.is_dir(follow_symlinks=False):
                    name = child.name.lower()
                    if (
                        depth < max_depth
                        and not name.startswith(".")
                        and name not in SKIP_DIR_NAMES
                    ):
                        queue.append((Path(child.path), depth + 1))
                elif child.is_file(follow_symlinks=False):
                    if Path(child.name).suffix.lower() in suffixes:
                        yield Path(child.path)
                        count += 1
                        if count >= limit:
                            return
            except OSError:
                continue


class SearchIndex(QObject):
    updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._entries: list[Entry] = []
        self._thread = threading.Thread(
            target=self._build, name="SpotlightIndex", daemon=True
        )
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._started = True
            self._thread.start()

    def search(self, query: str, per_group: dict[str, int] | None = None) -> list[tuple[str, list[Entry]]]:
        normalized = normalize(query).strip()
        if not normalized:
            return []

        tokens = [token for token in normalized.split() if token]
        limits = dict(GROUP_LIMITS)
        if per_group:
            limits.update(per_group)

        with self._lock:
            entries = list(self._entries)

        grouped: dict[str, list[tuple[float, Entry]]] = {group: [] for group in GROUP_ORDER}
        for entry in entries:
            title = entry.n_title
            extra = entry.n_extra
            if not all(token in title or token in extra for token in tokens):
                continue

            score = 0.0
            if title == normalized:
                score += 1000
            if title.startswith(normalized):
                score += 420
            position = title.find(normalized)
            if position >= 0:
                score += 220 - min(position, 80)
            elif extra and normalized in extra:
                score += 60

            for token in tokens:
                if title.startswith(token) or f" {token}" in title:
                    score += 45
                elif token in title:
                    score += 22
                else:
                    score += 6

            score -= len(title) * 0.4
            if entry.group == "settings":
                score += 4
            grouped[entry.group].append((score, entry))

        result: list[tuple[str, list[Entry]]] = []
        for group in GROUP_ORDER:
            candidates = sorted(
                grouped[group],
                key=lambda item: (-item[0], len(item[1].title), item[1].title.casefold()),
            )
            selected = [entry for _, entry in candidates[: limits.get(group, 6)]]
            if selected:
                result.append((group, selected))
        return result

    def _add_entries(self, new_entries: list[Entry]) -> None:
        if not new_entries:
            return
        with self._lock:
            remaining = MAX_TOTAL_ENTRIES - len(self._entries)
            if remaining <= 0:
                return
            self._entries.extend(new_entries[:remaining])
        self.updated.emit()

    def _build(self) -> None:
        try:
            settings_entries = [
                _make_entry(
                    title,
                    "Windows Settings",
                    "settings",
                    "setting",
                    uri,
                    glyph,
                    keywords,
                )
                for title, uri, glyph, keywords in SETTINGS
            ]
            self._add_entries(settings_entries)

            app_entries = self._build_apps()
            self._add_entries(app_entries)

            seen_paths: set[str] = set()
            for root in self._user_roots():
                if len(self._entries) >= MAX_TOTAL_ENTRIES:
                    break
                self._add_entries(self._scan_root(root, seen_paths))
        except Exception as exc:  # pragma: no cover - background safety net
            log(f"index build failed: {exc}")

    def _build_apps(self) -> list[Entry]:
        entries: list[Entry] = []
        seen: set[str] = set()

        for title, target, keywords in BUILTIN_APPS:
            key = title.casefold()
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                _make_entry(
                    title,
                    "Windows app",
                    "apps",
                    "app",
                    target,
                    "",
                    keywords,
                )
            )

        roots: list[Path] = []
        for env_name in ("APPDATA", "PROGRAMDATA"):
            base = os.getenv(env_name)
            if base:
                candidate = Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
                if candidate.is_dir():
                    roots.append(candidate)
        desktop = _known_folder("Desktop", "Desktop")
        if desktop.is_dir():
            roots.append(desktop)

        for root in roots:
            for shortcut in _iter_files(root, APP_EXTENSIONS, max_depth=5, limit=520):
                title = _clean_title(shortcut.stem)
                lowered = title.casefold()
                if (
                    lowered in seen
                    or "uninstall" in lowered
                    or "desinstalar" in lowered
                    or lowered.startswith("~$")
                ):
                    continue
                seen.add(lowered)
                entries.append(
                    _make_entry(
                        title,
                        "App",
                        "apps",
                        "app",
                        str(shortcut),
                    )
                )
                if len(entries) >= 320:
                    return entries
        return entries

    def _user_roots(self) -> list[Path]:
        roots = [
            _known_folder("Desktop", "Desktop"),
            _known_folder("Personal", "Documents"),
            _known_folder(
                "{374DE290-123F-4565-9164-39C4925E467B}", "Downloads"
            ),
        ]
        unique: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            key = str(root).casefold()
            if key not in seen and root.is_dir():
                seen.add(key)
                unique.append(root)
        return unique

    def _scan_root(self, root: Path, seen: set[str] | None = None) -> list[Entry]:
        seen = set() if seen is None else seen
        entries: list[Entry] = []
        root_key = str(root).casefold()
        if root_key in seen:
            return entries
        seen.add(root_key)

        entries.append(
            _make_entry(
                root.name,
                _display_path(root.parent),
                "folders",
                "folder",
                str(root),
                "",
                ROOT_KEYWORDS.get(root.name.casefold(), ""),
            )
        )
        count = 1
        queue = deque([(root, 0)])

        while queue and count < MAX_FILES_PER_ROOT:
            directory, depth = queue.popleft()
            try:
                children = list(os.scandir(directory))
            except OSError:
                continue

            for child in children:
                if count >= MAX_FILES_PER_ROOT:
                    break
                try:
                    name = child.name
                    if name.startswith(".") or name.startswith("~$"):
                        continue
                    attributes = child.stat(follow_symlinks=False).st_file_attributes
                    if attributes & (FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM):
                        continue

                    path = Path(child.path)
                    path_key = str(path).casefold()
                    if path_key in seen:
                        continue

                    if child.is_dir(follow_symlinks=False):
                        if name.lower() in SKIP_DIR_NAMES:
                            continue
                        seen.add(path_key)
                        entries.append(
                            _make_entry(
                                name,
                                _display_path(path.parent),
                                "folders",
                                "folder",
                                str(path),
                            )
                        )
                        count += 1
                        if depth < MAX_SCAN_DEPTH:
                            queue.append((path, depth + 1))
                    elif child.is_file(follow_symlinks=False):
                        suffix = path.suffix.lower()
                        if suffix in APP_EXTENSIONS:
                            continue
                        seen.add(path_key)
                        entries.append(
                            _make_entry(
                                name,
                                _display_path(path.parent),
                                "files",
                                "file",
                                str(path),
                            )
                        )
                        count += 1
                except OSError:
                    continue

        return entries


def web_entry(query: str) -> Entry:
    text = query.strip()
    return _make_entry(
        f'Search the web for "{text}"',
        "Open in your default browser",
        "web",
        "web",
        f"https://www.google.com/search?q={quote_plus(text)}",
        "\ue774",
        "internet web search pesquisar buscar google browser",
    )


def open_entry(entry: Entry) -> None:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    try:
        if entry.kind in ("setting", "web"):
            QDesktopServices.openUrl(QUrl(entry.target))
        else:
            os.startfile(entry.target)
    except OSError as exc:
        log(f"open failed for {entry.target}: {exc}")
