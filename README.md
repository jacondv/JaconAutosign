# Autosign - Batch PDF Signing

Internal tool: design a signature-position template once (draw a box, like in
Acrobat), then apply that template to sign a batch of PDF files that share
the same layout, entering the certificate password only once. Full spec in
[docs/](docs/00-tong-quan.md) (Vietnamese).

## Requirements

- Windows 10/11
- Python 3.10+ (only needed to run from source; the packaged .exe needs no Python)
- A `.p12`/`.pfx` certificate file and a signature image (PNG, transparent background)

## Run from source (development)

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e .
.\.venv\Scripts\python -m autosign.main
```

`pip install -e .` (editable install) must run first - it registers the
`autosign` package (in `src/autosign/`) with Python so `-m autosign.main` can
find it regardless of your current directory. Skipping this step causes
`ModuleNotFoundError: No module named 'autosign'`.

After the editable install, you can also use the shorter entry point:

```powershell
.\.venv\Scripts\autosign
```

## Build a standalone .exe

```powershell
.\scripts\build.ps1
```

Output goes to `dist\Autosign\Autosign.exe`. Copy the whole `dist\Autosign`
folder to another machine to install/run - no Python required there. Built
in `--onedir` mode (not `--onefile`) for fast startup (< 10 seconds).

## Project layout

```
docs/                       Spec documents (read before the code)
src/autosign/
  models/                   Plain data: Rect, PageRef, Template...
  services/                 TemplateService, PdfInspectService, BatchSignService, SettingsService
  signing/                  CertificateProvider (PKCS#12) + SigningEngine (pyHanko)
  security/                 Windows DPAPI wrapper (optional encrypted password storage)
  ui/                       PySide6 screens: Sign (main), Settings, Template Designer
  main.py                   Application entry point
autosign.spec                PyInstaller packaging config
scripts/build.ps1            One-command build script
```

The UI is a tab-based main window: **Sign** (default tab - open files/folder,
preview, pick a template and scope, sign) and **Settings** (default
certificate, signer name, output folder, template management). The Template
Designer opens as a full-screen overlay when creating/editing a template.

The code is split into 3 layers (UI -> Service -> Signing Engine) per the
design in [docs/03-kien-truc-cong-nghe.md](docs/03-kien-truc-cong-nghe.md) -
`services/` and `signing/` have no Qt dependency, so they're testable
independently of the UI.

## Where app data is stored

Templates and settings are stored under `%APPDATA%\Autosign\` (see
`src/autosign/config.py`), separate from the install folder.

## Security notes

- The certificate password is never stored as plain text. It only lives in
  memory while the app runs, unless you explicitly enable "Remember
  password" in Settings - in that case it is encrypted with **Windows
  DPAPI**, tied to the current Windows user account, so only that account on
  that machine can decrypt it.
- All processing (PDF rendering, signing) happens locally on the machine; no
  network calls are made.
