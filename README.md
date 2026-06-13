# Alce Project Manager

A desktop GUI tool for managing local copies of the [AlceEngine-Project](https://github.com/Ekrol34/AlceEngine-Project) repository. Built with Python and Tkinter.

> **Author:** [Ekrol34](https://github.com/Ekrol34)

---

## What it does

Every copy created by this tool is **fully detached** from the original repository. The `.git` folder is stripped automatically after cloning, so each project is a clean slate — ready for `git init` and a brand-new history, with no connection to the upstream repo whatsoever.

---

## Requirements

| Dependency | Version | Notes |
|---|---|---|
| Python | 3.10 + | Must be in PATH |
| [gitpython](https://gitpython.readthedocs.io/) | any | `pip install gitpython` |
| Tkinter | bundled | Included with standard Python on Windows and macOS |
| Git | any | Must be installed and in PATH |

No other dependencies. Pillow is **not** required.

---

## Installation

```bash
# 1. Clone or download this repository
git clone https://github.com/Ekrol34/AlceEngine-Project

# 2. Install the only Python dependency
pip install gitpython

# 3. Place these three files in the same folder:
#    alce_project_manager.py
#    icon.ico          ← window/taskbar icon
#    Ekrol34.ico       ← author logo (used as window icon on Windows)
```

---

## Running

```bash
python alce_project_manager.py
# or
python3 alce_project_manager.py
```

On Windows you can also double-click the `.py` file if Python is associated with it, or create a shortcut pointing to `pythonw.exe alce_project_manager.py` to suppress the console window.

---

## Actions

### NEW — Clone a project
Creates a new detached local copy of AlceEngine-Project.

1. Click **NEW** and enter a name.
2. The repo is cloned into your configured workspace folder.
3. The `.git` directory is deleted — the copy has **no remote, no history, no link** to the original.
4. You can run `git init` inside it and start a completely new repository.

### OPEN — Open in editor
Opens the selected project in your preferred code editor.

- **Single-click** a project card to select it, then press **OPEN**.
- **Double-click** a project card to select and open it immediately.
- On first use, the app scans your PATH for known editors and asks you to confirm. Your choice is saved automatically.

### DELETE — Remove a project
Permanently deletes the project folder from disk and removes the entry from the list.

> ⚠️ This cannot be undone. All files inside the folder are deleted.

If the folder is locked (e.g. a file is open in another program), the app will offer to remove just the list entry without touching the folder.

### UPDATE — Create a remote branch
Creates a new branch on the **AlceEngine-Project remote repository**.

1. Click **UPDATE** and enter a branch name.
2. The app clones the repo to a temporary folder, creates the branch, pushes it, and cleans up.
3. `main` and `master` are **permanently protected** — this operation will never touch either of them.

This does not affect any of your local project copies.

---

## Sidebar settings

### Workspace
The folder where all new projects are cloned into. Click the path to change it. Saved between sessions.

### Editor
The executable used by the OPEN action. Click to open the editor picker, which shows all supported editors and marks which ones are found on your system. You can also browse for any other executable.

**Supported editors (auto-detected):**
VS Code · Visual Studio · Cursor · Sublime Text · Notepad++ · PyCharm · Neovim · Vim · Atom

---

## Project icons

Each project card can show a custom icon. The app walks the project folder recursively looking for a file named `icon.ico`:

| Situation | Result |
|---|---|
| Exactly one `icon.ico` found anywhere inside the project | That icon is shown on the card |
| No `icon.ico` found | Default Alce icon is used |
| Two or more `icon.ico` files found | Default Alce icon is used |

---

## Theme

Click the **DARK / LIGHT** pill button in the top-right corner to toggle between dark and light themes. On first launch the app detects your operating system's theme preference automatically.

| OS | Detection method |
|---|---|
| Windows | Registry key `AppsUseLightTheme` |
| macOS | `defaults read -g AppleInterfaceStyle` |
| Linux | `gsettings` color-scheme |

The preference is saved in `~/.alce_manager.json`.

---

## Configuration file

All settings are stored in a single JSON file:

```
~/.alce_manager.json
```

```json
{
  "workspace": "C:/Users/you/AlceProjects",
  "editor": "C:/Users/you/AppData/Local/Programs/Microsoft VS Code/bin/code",
  "theme": "dark",
  "projects": [
    { "nombre": "MyGame", "ruta": "C:/Users/you/AlceProjects/MyGame" }
  ]
}
```

You can edit this file manually if needed (e.g. to fix a stale path). Delete it to reset all settings to defaults.

---

## File structure

```
AlceProjectManager/
├── alce_project_manager.py   ← main script (single file, no packages)
├── icon.ico                  ← Alce icon — used for project card thumbnails
├── Ekrol34.ico               ← Author icon — used as the window/taskbar icon
└── README.md
```

---

## Known limitations

- The UPDATE action (remote branch creation) requires write access to the AlceEngine-Project repository. If you do not have push permission, the operation will fail with a Git authentication error.
- ICO files that do not contain an embedded PNG frame (e.g. pure BMP ICO files) will not display as project thumbnails — the default icon is used instead.
- On Linux, Tkinter must be installed separately if not bundled with your Python distribution (`sudo apt install python3-tk` on Debian/Ubuntu).

---

## License

This tool is provided as-is for use with the AlceEngine-Project. See the upstream repository for licensing information.
