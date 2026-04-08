# Simple Habbit Tracker

I made this so I can track my stuff. Feel free to use it!

## Linux Deployment Output (Port 80 Background Service)

Here is how to clone this exact repository to a headless Linux box (Raspberry Pi, Ubuntu Home Server, etc) and run it permanently on port 80 without hanging open any console windows. 

### 1. Clone the Code Repository
SSH into your Linux machine, download `git`, and grab the source. 

*(Make sure to change the link to your actual github link!)*
```bash
cd /opt/
sudo git clone https://github.com/destinyfkrr/habit-tracker.git
cd habit-tracker
```

### 2. Setup The Environment
Build a native virtual environment specifically for your Linux architecture so dependencies install properly:

```bash
sudo apt update
sudo apt install python3-venv python3-pip

# Construct the local Python isolated environment sandbox
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Initialize your Database
Running the app manually once triggers the backend configurations and builds your `sqlite3` database exactly where you need it securely.

```bash
flask --app habit_tracker run &
sleep 2; pkill flask
```

### 4. Configure `Systemd` (Always-On Local Web Server)
Because you want native network access exactly on **Port 80**, we will assign this application to your native Linux services manager `Systemd`.

Open a text editor config:
```bash
sudo nano /etc/systemd/system/habit-tracker.service
```

Drop this block directly inside and save the file (`Ctrl+O`, `Enter`, `Ctrl+X`):
```ini
[Unit]
Description=Simple Habbit Tracker Daemon
After=network.target

[Service]
# Note: Since Port 80 requires Root bounds, we run privileged here locally.
User=root
Group=root

WorkingDirectory=/opt/habit-tracker
Environment="PATH=/opt/habit-tracker/.venv/bin"
# Utilize Gunicorn to serve via Port 80 bounds locally.
ExecStart=/opt/habit-tracker/.venv/bin/gunicorn --workers 3 --bind 0.0.0.0:80 app:app

[Install]
WantedBy=multi-user.target
```

### 5. Launch It
Finally, trigger the service scripts. This will enable it to auto-boot indefinitely going forward whenever your linux machine is powered on.

```bash
sudo systemctl daemon-reload
sudo systemctl start habit-tracker
sudo systemctl enable habit-tracker
```

**Done!**
You can now access your app directly via your Linux machine's local assigned network IP (e.g. `http://192.168.1.50`) entirely in the background forever natively!

---
*Project fully made by Antigravity and CodeX :) Under 10 minutes.*
