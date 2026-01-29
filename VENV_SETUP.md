# Virtual environment setup (short reference)

## Create and use venv

```bash
# From project root
cd /home/adm-admin/projects/aws-orphans

# Create venv
python3 -m venv .venv

# Activate (Linux / WSL / macOS)
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## Run the scanner

```bash
python scripts/scan_orphaned_sgs.py
```

## Deactivate

```bash
deactivate
```

See **README.md** for full options, FastAPI usage, and region list.
