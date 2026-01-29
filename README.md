# AWS Orphans – Orphaned Security Group Scanner

Scans AWS regions for **orphaned** (unassociated) security groups — SGs not attached to any Elastic Network Interface (ENI). Uses the region list from the AWS console screenshot.

The scanner logic lives in the `app` package so it can be reused by a **CLI script** and a **FastAPI web app** later.

---

## Create a virtual environment (venv)

### 1. Create the venv

From the project root:

```bash
cd /home/adm-admin/projects/aws-orphans
python3 -m venv .venv
```

### 2. Activate the venv

**Linux / WSL / macOS:**

```bash
source .venv/bin/activate
```

**Windows (cmd):**

```cmd
.venv\Scripts\activate.bat
```

**Windows (PowerShell):**

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Upgrade pip and install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. (Optional) Install in editable mode for development

If you edit the `app` package and want changes to apply without reinstalling:

```bash
pip install -e .
```

Requires a `pyproject.toml` or `setup.py`; see **Project layout** below.

### 5. Deactivate when done

```bash
deactivate
```

---

## Running the scanner

**Scan all configured regions (default):**

```bash
python scripts/scan_orphaned_sgs.py
```

**Scan specific regions:**

```bash
python scripts/scan_orphaned_sgs.py --regions us-east-1 eu-west-1 ap-southeast-1
```

**Use an AWS profile:**

```bash
python scripts/scan_orphaned_sgs.py --profile my-profile
```

**JSON output (for piping or FastAPI-style responses):**

```bash
python scripts/scan_orphaned_sgs.py --output json
```

**Include the default security group in the orphan list:**

```bash
python scripts/scan_orphaned_sgs.py --include-default-sg
```

---

## Postgres and the web app

The web app reads from a Postgres table. You populate that table by running a script, then start the app.

### Install Postgres locally

**Ubuntu / Debian / WSL (apt):**

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql   # start on boot
```

**Fedora / RHEL (dnf):**

```bash
sudo dnf install postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**macOS (Homebrew):**

```bash
brew install postgresql@16
brew services start postgresql@16
```

### Create a user and database

After Postgres is running, create a dedicated user and database (and set a password you’ll use in `DATABASE_URL`).

**Ubuntu/Debian/WSL:** the install creates an OS user `postgres`. Connect as that user:

```bash
sudo -u postgres psql
```

**Fedora/RHEL:** same:

```bash
sudo -u postgres psql
```

**macOS:** often no `postgres` OS user; connect with your Mac user (who is a superuser):

```bash
psql -d postgres
```

Then in the `psql` prompt:

```sql
CREATE USER aws_orphans WITH PASSWORD 'your_password_here';
CREATE DATABASE aws_orphans OWNER aws_orphans;
\q
```

Use the same password in `DATABASE_URL` below.

### 1. Set DATABASE_URL

Use the user and database you created. Prefer `127.0.0.1` instead of `localhost` so the client uses IPv4 and password auth (on some setups `localhost` uses IPv6/peer and rejects passwords):

```bash
export DATABASE_URL="postgresql://aws_orphans:YOUR_ACTUAL_PASSWORD@127.0.0.1:5432/aws_orphans"
```

### 2. Populate the tables (run ad hoc)

**Security groups:**

```bash
python scripts/populate_orphaned_sgs_db.py
```

**Elastic IPs (unassociated):**

```bash
python scripts/populate_orphaned_eips_db.py
```

**EBS Volumes (unattached):**

```bash
python scripts/populate_orphaned_ebs_db.py
```

Each script scans all regions, creates its table if needed, and replaces its contents. Run whenever you want fresh data.

### 3. Start the app

```bash
uvicorn app.main:app --reload
```

### 4. URLs

Use the top bar on the app to switch between **Security Groups**, **Elastic IPs**, and **EBS Volumes**.

| URL | Description |
|-----|-------------|
| `/orphaned-sgs` | HTML table of orphaned security groups |
| `/orphaned-eips` | HTML table of unassociated Elastic IPs |
| `/orphaned-ebs` | HTML table of unattached EBS volumes |
| `/api/orphaned-sgs` | JSON list of SGs from DB |
| `/api/orphaned-eips` | JSON list of EIPs from DB |
| `/api/orphaned-ebs` | JSON list of EBS volumes from DB |
| `/api/orphaned-sgs/export` | Download SGs as Excel |
| `/api/orphaned-eips/export` | Download EIPs as Excel |
| `/api/orphaned-ebs/export` | Download EBS volumes as Excel |
| `/api/regions` | List of regions |

---

## Hosting on Azure VM (nginx, HTTP)

For manual steps to run the app on an **Azure VM** with **nginx** as reverse proxy and expose it over the internet via **HTTP**, see **[docs/HOSTING_AZURE.md](docs/HOSTING_AZURE.md)**. It covers: VM + NSG (port 80), Postgres on the VM, systemd service for uvicorn, nginx config, and options (VM public IP, static IP, DNS label, load balancer).

---

## Project layout

```
aws-orphans/
├── .venv/
├── app/
│   ├── __init__.py
│   ├── db.py                 # Postgres: table, insert, fetch
│   ├── main.py               # FastAPI app (reads from DB)
│   ├── regions.py
│   ├── scanner.py            # Orphaned security groups
│   ├── scanner_eips.py       # Unassociated Elastic IPs
│   └── scanner_ebs.py        # Unattached EBS volumes
├── templates/                # HTML (Jinja2)
│   ├── _nav.html             # Top bar: SGs | EIPs | EBS
│   ├── orphaned_sgs.html, orphaned_sgs_table.html
│   ├── orphaned_eips.html, orphaned_eips_table.html
│   └── orphaned_ebs.html, orphaned_ebs_table.html
├── scripts/
│   ├── scan_orphaned_sgs.py   # CLI: print or JSON (no DB)
│   ├── populate_orphaned_sgs_db.py   # Ad hoc: scan and fill SGs table
│   ├── populate_orphaned_eips_db.py  # Ad hoc: scan and fill EIPs table
│   └── populate_orphaned_ebs_db.py   # Ad hoc: scan and fill EBS table
├── requirements.txt
├── README.md
└── VENV_SETUP.md
```

---

## Regions scanned

Regions match the AWS console screenshot:

- **United States:** `us-east-1`, `us-east-2`, `us-west-1`, `us-west-2`
- **Asia Pacific:** `ap-southeast-5`, `ap-south-1`, `ap-northeast-3`, `ap-northeast-2`, `ap-southeast-1`, `ap-southeast-2`, `ap-northeast-1`
- **Canada:** `ca-central-1`, `ca-west-1`
- **Europe:** `eu-central-1`, `eu-west-1`, `eu-west-2`, `eu-west-3`, `eu-north-1`
- **Middle East:** `me-south-1`, `me-central-1`
- **South America:** `sa-east-1`

---

## AWS credentials

Use one of:

- Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, optional `AWS_DEFAULT_REGION`
- Shared credentials: `~/.aws/credentials` and `--profile` in the script
- IAM role (e.g. EC2 instance profile)

The script needs `ec2:DescribeSecurityGroups` and `ec2:DescribeNetworkInterfaces` in each region you scan.



In a shell (as a Postgres admin, e.g. sudo -u postgres psql or psql -U postgres):
CREATE USER aws_orphans WITH PASSWORD 'your_secret_password';
CREATE DATABASE aws_orphans OWNER aws_orphans;

export DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"
python3 scripts/populate_orphaned_sgs_db.py


