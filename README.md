# P2Pool Dashboard

A lightweight, real-time dashboard for monitoring your P2Pool mining stats, XMRig hashrate, network stats, and XMR price, all in one place.  
Mostly vibe-coded because I just wanted something that worked. No hand-holding here, but it’s pretty straightforward.

---

## How it looks

<img width="2485" height="1286" alt="Dashboard Screenshot" src="https://github.com/user-attachments/assets/7ce0cbb0-43ee-4df7-8563-dbd6e50b3b9d" />



---

## Features

- Tracks your **mining hashrate**, **pool hashrate**, and **network hashrate**.
- Estimates your **earnings in XMR and EUR** with selectable time periods (hour/day/week/etc.).
- Shows pretty (as good as it is going to get) **accurate payout interval**
- Shows your **recent payments in XMR and EUR** and shows your **total earned XMR/EUR on p2pool**
- Shows **XMR price trends** over time.
- Shows current **luck** in the PPLNS window
- Shows current **accumulated XMR** in the PPLNS window (expectations, not reality)
- Shows estimated **true luck** since you started mining with your current daily hashrate
- Shows how many **shares and uncles** you have gotten
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

You need a P2Pool instance running. P2Pool has its own data directory (where it stores pool stats), but it isn't setup in the most handy location and can vary per linux distro.

#### Run P2Pool with a specified data directory
When running p2pool, you need to add the ```--data-dir``` flag so there is a place p2pool-dashboard can retrieve statistics from.

For example:
```bash
p2pool --data-dir /home/user/p2pool-data   # user is your username
# or if you want it directly in the repository and you have it in your home directory
p2pool --data-dir /home/user/p2pool-dashboard/p2pool-data
```

#### Then link it to the dashboard p2pool-data directory:

If your P2Pool data is somewhere else than in the repository, create a symlink
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
python3 server.py --port 8080 --data-dir ./p2pool-data --wallet YOUR_WALLET_ADDRESS --nano-p2pool/--mini-p2pool/--normal-p2pool
```
- ```--port``` is the HTTP port for the dashboard (default: 8080)
- ```--data-dir``` points to the P2Pool data directory linked earlier. So the one that is in the p2pool-dashboard repository with all the website files
- ```--wallet``` is your wallet address you are using for p2pool
- ```--nano-p2pool``` you should use this option if you are using p2pool nano
- ```--mini-p2pool``` you should use this option if you are using p2pool mini
- ```--normal-p2pool``` you should use this option if you are using the normal/default p2pool

#### Open your browser:
Open your browser and visit [Your Dashboard](http://127.0.0.1:8080/dashboard.html) to see your stats in real-time.

You should see your hashrate, pool stats, XMR price, and estimated earnings updating in real-time.

### 6. Notes

- Data updates every 5 seconds.
- Logs are stored in stats_log.json automatically.
- Tooltip icons (ⓘ) give extra info like moving averages and payout intervals.
- The dashboard uses a dark theme and is mobile-friendly.

---

## Credits

Made by XanderTheDev. No support guaranteed, but hey, it works!
Here is some stuff I used for the HTML
- [Chart.js](https://www.chartjs.org/) for rendering charts (MIT License)
- [Luxon](https://moment.github.io/luxon/) for date/time handling (MIT License)
- [chartjs-adapter-luxon](https://github.com/chartjs/chartjs-adapter-luxon) (MIT License)

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

⚠️ Disclaimer: This project is not affiliated with or endorsed by the Monero Project. The Monero logo used as the favicon is a trademark of the Monero Project and is used for informational purposes only.
