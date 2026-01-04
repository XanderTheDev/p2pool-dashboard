# P2Pool Dashboard

A lightweight, real-time dashboard for monitoring your P2Pool mining stats, XMRig hashrate, network stats, and XMR price — all in one place.  
Mostly vibe-coded because I just wanted something that worked. No hand-holding here, but it’s pretty straightforward.

---

## How it looks

<img width="1917" height="650" alt="Dashboard screenshot" src="https://github.com/user-attachments/assets/c17abf8c-9bf3-46e9-9f69-b33fd388c3fd" />

---

## Features

- Tracks your **mining hashrate**, **pool hashrate**, and **network hashrate**.
- Estimates your **earnings in XMR and EUR** with selectable time periods (hour/day/week/etc.).
- Shows **XMR price trends** over time.
- Rolling **24-hour log** saved to disk automatically.
- Lightweight Python server serving live charts and stats.

---

## Requirements

- Python 3.8+
- `monerod` (full node or pruned node)
- XMRig miner
- P2Pool node

---

## Setup Tutorial

Follow these steps to get the dashboard running:

### 1. Clone this repository
```bash
git clone https://github.com/XanderTheDev/p2pool-dashboard.git
cd p2pool-dashboard
```

### 2. Set up P2Pool

You need a P2Pool instance running. P2Pool has its own data directory (where it stores pool stats). For example:

#### Run P2Pool with a specified data directory
When running p2pool, you need to add the ```--data-dir``` flag so there is a place p2pool-dashboard can retrieve statistics from.

For example:
```bash
p2pool --data-dir /home/user/p2pool-data   # user is your username 
```

Then link it to the dashboard p2pool-data directory:

#### If your P2Pool data is somewhere else, create a symlink
```bash
cd p2pool-dashboard     # if not already
ln -s /home/user/p2pool-data ./p2pool-data  # Or a different data directory if you setup a different one.
#            ^
#            |
#  Again user is your username
```

Now the dashboard will read pool stats from your P2Pool node.

### 3. Start monerod with RPC enabled

The dashboard fetches network stats from monerod, so you need to run it with (you can keep any other flags):

```bash
monerod --rpc-bind-port 18081
```
- Default RPC port: 18081 (matches the dashboard)
- Make sure monerod is fully synced for accurate network stats.

### 4. Start XMRig with HTTP API

The dashboard fetches your miner hashrate from XMRig. Make sure the HTTP API is enabled:

```bash
xmrig --api-worker-id=worker1 --http-port=42000
```
- ```--api-worker-id``` can be any name; used to identify your miner in the dashboard. Actually not sure if this is needed. Just do it to be sure
- ```--http-port``` must match the port in server.py (42000 by default).

### 5. Run the dashboard server
```bash
python3 server.py --port 8080 --data-dir ./p2pool-data
```
- ```--port``` is the HTTP port for the dashboard (default: 8080)
- ```--data-dir``` points to the P2Pool data directory linked earlier. So the one that is in the p2pool-dashboard repository with all the website files

#### Open your browser:
Open your browser and visit [Your Dashboard](http://127.0.0.1:8080/dashboard.html) to see your stats in real-time.

You should see your hashrate, pool stats, XMR price, and estimated earnings updating in real-time.

### 6. Notes

- Data updates every 5 seconds.
- Logs are stored in stats_log.json automatically.
- Tooltip icons (ⓘ) give extra info like moving averages and payout intervals.
- The dashboard uses a dark theme and is mobile-friendly.

Made by XanderTheDev. No support guaranteed, but hey, it works!
