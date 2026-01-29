# Hosting AWS Orphans on an Azure VM (HTTP, nginx)

Manual steps to run the app on an Azure Linux VM with nginx as reverse proxy and expose it over the internet via HTTP.

---

## Part 1: Create and prepare the Azure VM

### 1.1 Create a Linux VM

1. In **Azure Portal** → **Virtual machines** → **Create** → **Azure virtual machine**.
2. **Basics:**
   - **Subscription** and **Resource group**: choose or create (e.g. `rg-aws-orphans`).
   - **Virtual machine name**: e.g. `vm-aws-orphans`.
   - **Region**: pick one (e.g. East US).
   - **Image**: **Ubuntu Server 22.04 LTS** (or 24.04).
   - **Size**: e.g. B2s (2 vCPU, 4 GiB) or B1s for light use.
   - **Authentication**: SSH public key (recommended) or password.
   - Create a key pair if needed and paste the public key.
3. **Disks**: default (Premium SSD or Standard SSD).
4. **Networking:**
   - **Virtual network**: create new or use existing.
   - **Subnet**: default.
   - **Public IP**: **Create new** (so the VM gets a public IP).
   - **NIC security group**: **Advanced** → create new or use existing **Network security group (NSG)**.

### 1.2 Open HTTP (port 80) in the NSG

1. Go to the VM → **Networking** (or the NSG attached to the VM’s NIC).
2. **Inbound port rules** → **Add rule**:
   - **Source**: Any (or **Internet**) — `0.0.0.0/0` if you want access from anywhere.
   - **Source port ranges**: `*`
   - **Destination**: Any
   - **Service**: HTTP (or **Custom**)
   - **Destination port ranges**: `80`
   - **Protocol**: TCP
   - **Action**: Allow
   - **Priority**: e.g. 100
3. Save. SSH (port 22) is usually already allowed.

### 1.3 (Optional) Use a static public IP

- By default the VM’s public IP can change on deallocate/restart.
- To keep the same URL: VM → **Networking** → **Public IP** → **Configuration** → set **Assignment** to **Static** and save.

---

## Part 2: On the VM — install dependencies and the app

SSH into the VM (replace with your VM’s public IP and user):

```bash
ssh -i /path/to/your-key.pem azureuser@<VM_PUBLIC_IP>
```

### 2.1 System packages (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx postgresql postgresql-contrib git
```

### 2.2 Postgres: user and database

```bash
sudo -u postgres psql -d postgres << 'EOF'
CREATE USER aws_orphans WITH PASSWORD 'YOUR_SECURE_PASSWORD';
CREATE DATABASE aws_orphans OWNER aws_orphans;
\q
EOF
```

Use a strong password and the same value in `DATABASE_URL` below.

### 2.3 Clone or copy the app

**Option A — from Git (if the repo is in GitHub/Azure Repos):**

```bash
cd /opt
sudo git clone https://github.com/YOUR_ORG/aws-orphans.git
sudo chown -R $USER:$USER /opt/aws-orphans
cd /opt/aws-orphans
```

**Option B — copy from your machine (from your laptop):**

```bash
# On your laptop (from the project folder):
scp -i /path/to/key.pem -r /path/to/aws-orphans azureuser@<VM_PUBLIC_IP>:~/aws-orphans
# Then on the VM:
sudo mv ~/aws-orphans /opt/aws-orphans
sudo chown -R $USER:$USER /opt/aws-orphans
cd /opt/aws-orphans
```

### 2.4 Python venv and dependencies

```bash
cd /opt/aws-orphans
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2.5 Environment: DATABASE_URL

Create a small env file (we’ll load it from the systemd service). Use `127.0.0.1` so Postgres uses password auth:

```bash
echo 'DATABASE_URL="postgresql://aws_orphans:YOUR_SECURE_PASSWORD@127.0.0.1:5432/aws_orphans"' | sudo tee /opt/aws-orphans/.env
sudo chown azureuser:azureuser /opt/aws-orphans/.env
chmod 600 /opt/aws-orphans/.env
```

If you use AWS credentials on this VM for the populate scripts, also set:

```bash
# Optional: for running populate scripts on the VM
echo 'AWS_ACCESS_KEY_ID=...' | sudo tee -a /opt/aws-orphans/.env
echo 'AWS_SECRET_ACCESS_KEY=...' | sudo tee -a /opt/aws-orphans/.env
```

### 2.6 (Optional) Populate the DB once

```bash
cd /opt/aws-orphans
source .venv/bin/activate
set -a && source .env && set +a
python3 scripts/populate_orphaned_sgs_db.py
python3 scripts/populate_orphaned_eips_db.py
python3 scripts/populate_orphaned_ebs_db.py
```

You can run these later via cron or manually when you want fresh data.

---

## Part 3: Run the app with systemd (so it survives reboot)

Create a systemd unit so uvicorn runs in the background and restarts on failure/reboot.

```bash
sudo tee /etc/systemd/system/aws-orphans.service << 'EOF'
[Unit]
Description=AWS Orphans FastAPI app
After=network.target postgresql.service

[Service]
Type=simple
User=azureuser
Group=azureuser
WorkingDirectory=/opt/aws-orphans
EnvironmentFile=/opt/aws-orphans/.env
ExecStart=/opt/aws-orphans/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

Replace `azureuser` with the actual OS user that owns `/opt/aws-orphans` if different.

```bash
sudo systemctl daemon-reload
sudo systemctl enable aws-orphans
sudo systemctl start aws-orphans
sudo systemctl status aws-orphans
```

The app listens on **127.0.0.1:8000** (only localhost). nginx will proxy to it.

---

## Part 4: Configure nginx as reverse proxy

### 4.1 Site config

```bash
sudo tee /etc/nginx/sites-available/aws-orphans << 'EOF'
server {
    listen 80;
    server_name _;
    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

### 4.2 Enable the site and reload nginx

```bash
sudo ln -sf /etc/nginx/sites-available/aws-orphans /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 4.3 (Optional) Disable default site

If the default site is enabled and takes port 80:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

---

## Part 5: Expose over the internet (options)

The app is now reachable only from the VM (nginx on 80, proxying to 127.0.0.1:8000). To make it reachable from the internet you only need to allow traffic to the VM on port 80. Below are the main ways to do that.

### Option A: VM public IP + NSG (simplest)

- You already gave the VM a **public IP** and opened **port 80** in the NSG (Part 1.2).
- From a browser: `http://<VM_PUBLIC_IP>`  
  Example: `http://20.123.45.67`
- No extra Azure resources. Good for a single VM, HTTP-only for now.

### Option B: Static public IP (stable URL)

- In **Part 1.3** you set the VM’s public IP to **Static**.
- Use the same URL: `http://<VM_STATIC_PUBLIC_IP>`.
- The IP (and thus the URL) does not change when you stop/start the VM.

### Option C: DNS name (optional)

- In Azure: **Public IP** → **Configuration** → **DNS name label**: e.g. `aws-orphans-prod`.
- URL becomes: `http://aws-orphans-prod.<region>.cloudapp.azure.com` (e.g. `http://aws-orphans-prod.eastus.cloudapp.azure.com`).
- Still HTTP; no certificate. Good for a stable, readable URL.

### Option D: Azure Load Balancer (optional, for scaling later)

- Use when you want multiple VMs or TLS termination at the load balancer later.
- Create a **Public Load Balancer**, add the VM to a **backend pool**, add a **rule** for port 80 → backend port 80.
- Access via the load balancer’s **public IP** (or its DNS).  
- For a single VM and “HTTP for now”, Option A or B is enough.

---

## Quick checklist

| Step | Done |
|------|------|
| Create Azure VM (Ubuntu, public IP) | ☐ |
| NSG: allow inbound TCP 80 | ☐ |
| (Optional) Static public IP | ☐ |
| On VM: install python3, nginx, postgresql | ☐ |
| Postgres: create user and DB | ☐ |
| Clone/copy app to `/opt/aws-orphans` | ☐ |
| Venv + `pip install -r requirements.txt` | ☐ |
| Create `.env` with `DATABASE_URL` | ☐ |
| (Optional) Run populate scripts | ☐ |
| Create and start `aws-orphans.service` | ☐ |
| Configure nginx and reload | ☐ |
| Open `http://<VM_PUBLIC_IP>` in browser | ☐ |

---

## Troubleshooting

- **502 Bad Gateway**: App not running or not on 8000. Check: `sudo systemctl status aws-orphans` and `curl http://127.0.0.1:8000/`.
- **Connection refused (browser)**: NSG not allowing 80, or nginx not listening: `sudo ss -tlnp | grep -E '80|8000'`.
- **Empty tables**: Run the populate scripts (with `DATABASE_URL` and, if on VM, AWS credentials in `.env`).
- **Postgres auth failed**: Use `127.0.0.1` in `DATABASE_URL` and the same password used in `CREATE USER`.

---

## Adding HTTPS later

When you want HTTPS:

1. Get a domain and point it to the VM (or load balancer) public IP.
2. Install certbot: `sudo apt install certbot python3-certbot-nginx`.
3. Run: `sudo certbot --nginx -d yourdomain.com`.
4. Optionally restrict NSG to only allow 80/443 and SSH from your IP.

For “HTTP for now”, the steps above are enough to host the app on the Azure VM and expose it over the internet.
