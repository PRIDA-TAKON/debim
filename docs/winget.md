# 🪟 Windows Package Manager (WinGet) Distribution Guide

This document outlines the architecture and automated pipeline for distributing `debim` on Windows via **WinGet** (`winget install debim`).

---

## 🏗️ Architecture

```
GitHub Release (Tag: vX.Y.Z)
       │
       ├──> Job 1: Build Standalone debim.exe (PyInstaller)
       │           ├── Packages: debim-windows-x64.zip
       │           └── Computes SHA256 checksum
       │
       └──> Job 2: Automated WinGet PR (winget-releaser)
                   └── Submits manifest update to microsoft/winget-pkgs
```

---

## 🚀 One-Time Setup: GitHub Secret (`WINGET_PAT`)

To allow the automated CI/CD pipeline (`.github/workflows/winget.yml`) to submit Pull Requests to the [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs) community repository on your behalf:

1. Go to your GitHub account: **Settings** -> **Developer settings** -> **Personal access tokens** -> **Tokens (classic)**.
2. Click **Generate new token (classic)**.
3. Name it `WINGET_RELEASER` and select the **`public_repo`** scope.
4. Copy the generated token.
5. In your `debim` repository, go to:
   **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**.
6. Name: `WINGET_PAT`
   Value: *(Paste your GitHub token)*
7. Click **Add secret**.

---

## 📦 How Users Install `debim` on Windows

Once published to the WinGet repository, any Windows user can install `debim` with a single command without needing Python pre-installed:

```powershell
# Install debim
winget install debim

# Run debim directly anywhere
debim --version
debim --help
```

To upgrade:
```powershell
winget upgrade debim
```

To uninstall:
```powershell
winget uninstall debim
```

---

## 🛠️ Manual Submission / Verification with `wingetcreate`

You can validate or test the manifests located in `distribution/winget/`:

```powershell
# Install WinGet CLI manifest creator
winget install Microsoft.WingetCreate

# Validate manifests
winget validate distribution/winget

# Submit manifests to microsoft/winget-pkgs
wingetcreate submit distribution/winget
```
