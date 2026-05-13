# Alldesk

Alldesk is a Windows GUI tool for managing and launching RustDesk and TightVNC connections.

This project is fully managed with `uv`, including:

- Python version management
- Virtual environment management
- Dependency installation
- Lockfile management
- Package building
- EXE packaging

## Requirements

- Windows
- `uv`
- Python 3.12

## Setup

```powershell
uv sync --group dev
```

`uv` will create and manage `.venv` automatically.

## Run

```powershell
uv run python Alldesk.py
```

## Dependency Management

Dependencies are managed through:

- [`pyproject.toml`](/e:/py/Alldesk/pyproject.toml)
- [`uv.lock`](/e:/py/Alldesk/uv.lock)

After changing dependencies:

```powershell
uv lock
uv sync --group dev
```

## Build Python Package

```powershell
uv build
```

## Build EXE

One-file build:

```powershell
uv run pyinstaller Alldesk-onefile.spec
```

One-dir build:

```powershell
uv run pyinstaller Alldesk-onedir.spec
```

## Runtime Data

- Main config file: `Alldesk.json`
- Packaging includes the `exe/` directory contents

## Notes

- `requirements.txt` has been removed
- Do not use `pip install -r ...`
- Do not create `.venv` manually
- Use `uv` for all project workflows
