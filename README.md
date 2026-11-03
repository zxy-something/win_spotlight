# Spotlight

A fast, native search overlay for Windows 10 and 11 — built with Python and PySide6.

**[Download the latest release →](../../releases/latest)**

## Features

- **One hotkey** — press `Win + Space` anywhere to open or close the overlay.
- **Fuzzy search** across apps, files, folders and Windows settings.
- **Apps** from the Start Menu plus common built-ins (Explorer, Calculator, Notepad, Paint, Terminal, Task Manager).
- **Files and folders** from Desktop, Documents and Downloads (scanned up to 3 levels deep), with accents ignored.
- **Windows settings** shortcuts — Wi-Fi, Bluetooth, Display, Sound, Power, Windows Update and more.
- **Keyboard-first** — `↑` `↓` to navigate, `Enter` to open, `Esc` to close.
- **Web fallback** — when nothing matches, search the query on Google in your default browser.
- **Glass-like panel** over a snapshot of your desktop, with a smooth fade animation.
- **Light and dark themes** that follow the Windows system setting automatically.
- **Lives in the tray** — single instance, optional start with Windows, no taskbar clutter.

## Install

Two options are attached to every release:

| File | Description |
| --- | --- |
| `SpotlightSetup.exe` | Installer (recommended). Start Menu shortcut, optional desktop shortcut, optional startup entry and a built-in uninstaller. |
| `Spotlight.exe` | Portable single file. Just run it — nothing is installed. |

> Spotlight is not code-signed, so Windows SmartScreen may show a warning. Click **More info → Run anyway**.

## Usage

| Shortcut | Action |
| --- | --- |
| `Win + Space` | Open / close Spotlight |
| `↑` `↓` | Move through results |
| `Enter` | Open the selected result |
| `Esc` | Close the overlay |
| Left click on tray icon | Open Spotlight |
| Right click on tray icon | Menu with Open and Quit |

If `Win + Space` is already taken by another app, Spotlight falls back to a low-level keyboard hook and keeps working. If neither method is available, it shows a tray notification and you can still open it from the tray icon.

## Run from source

Requirements: Windows 10/11, Python 3.10+ and [PySide6](https://pypi.org/project/PySide6/).

```bat
python -m pip install -r requirements.txt
python main.py
```

## Build

Build the portable executable:

```bat
build.bat
```

Or run PyInstaller directly:

```bat
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Spotlight --icon icon.ico main.py
```

The result is `dist\Spotlight.exe`.

To build the installer, install [Inno Setup 6](https://jrsoftware.org/isinfo.php) and compile `installer.iss` after the executable exists:

```bat
iscc installer.iss
```

The installer is written to `installer\SpotlightSetup.exe`.

## Project layout

| File | Purpose |
| --- | --- |
| `main.py` | Application entry point, single-instance server and tray icon |
| `overlay.py` | Overlay window, results list, theme and animations |
| `search.py` | Background index for apps, files, folders and settings |
| `hotkey.py` | `Win + Space` registration with keyboard-hook fallback |
| `visuals.py` | Icons, fonts and system accent/theme helpers |
| `logger.py` | Minimal file logger |
| `installer.iss` | Inno Setup script for the installer |
| `Spotlight.spec` | PyInstaller build spec |
