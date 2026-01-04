
#!/usr/bin/env python3
import http.server
import socketserver
import json
import os
import urllib.request
import time
import argparse
import threading
import sys
from collections import deque

# -------------------- CLI --------------------
parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8080)
parser.add_argument("--data-dir", type=str, default="./p2pool-data")
args = parser.parse_args()

PORT = args.port
DATA_DIR = args.data_dir
LOG_FILE = os.path.join(DATA_DIR, "stats_log.json")
STATS_MOD_FILE = os.path.join(DATA_DIR, "stats_mod")
MAX_LOG_AGE = 24 * 3600  # keep 24h of data

os.makedirs(DATA_DIR, exist_ok=True)

# -------------------- In-memory rolling logs --------------------
# Deques for efficient appends/pops from left
log = {
    "timestamps": deque(),
    "myHash": deque(),
    "poolHash": deque(),
    "netHash": deque(),
    "price": deque()
}
log_lock = threading.Lock()  # thread-safe access

# -------------------- Helper functions --------------------
def get_last_price():
    try:
        with open(LOG_FILE, "r") as f:
            data = json.load(f)
            if data["price"]:
                return float(data["price"][-1])
    except Exception:
        pass
    return 0.0

def get_xmr_price():
    """Fetch XMR price from multiple sources with fallback."""
    sources = [
        ("https://api.coingecko.com/api/v3/simple/price?ids=monero&vs_currencies=eur", lambda d: float(d["monero"]["eur"]), "CoinGecko"),
        ("https://api.kraken.com/0/public/Ticker?pair=XMREUR", lambda d: float(d["result"]["XXMRZEUR"]["c"][0]), "Kraken"),
        ("https://api-pub.bitfinex.com/v2/ticker/tXMRUSD", None, "Bitfinex+FX"),
        ("https://api.price2sheet.com/json/xmr/eur", lambda d: float(d["price"]), "price2sheet")
    ]
    for url, parser_func, name in sources:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                data = json.load(r)
            if name == "Bitfinex+FX":
                usd_to_eur = 1.0
                try:
                    with urllib.request.urlopen("https://api.frankfurter.app/latest?from=USD&to=EUR", timeout=5) as r2:
                        fx_data = json.load(r2)
                        usd_to_eur = float(fx_data["rates"]["EUR"])
                except Exception:
                    pass
                price = float(data[6]) * usd_to_eur
            else:
                price = parser_func(data)
            if price > 0:
                print(f"Price has come from: {name}")
                return price
        except Exception:
            continue
    last_price = get_last_price()
    print("Price has come from last recorded value")
    return last_price

def get_min_payment_threshold():
    """Read min payment threshold from stats_mod"""
    try:
        with open(STATS_MOD_FILE) as f:
            data = json.load(f)
        return data["config"]["minPaymentThreshold"] / 1e12
    except Exception:
        return 0.01  # fallback

# -------------------- HTTP Handler --------------------
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DATA_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/monerod_stats":
            self.proxy_monerod()
        elif self.path == "/xmrig_summary":
            self.proxy("http://127.0.0.1:42000/2/summary")
        elif self.path == "/stats_log.json":
            self.serve_log()
        elif self.path == "/min_payment_threshold":
            self.serve_threshold()
        else:
            super().do_GET()

    def proxy(self, url):
        with urllib.request.urlopen(url, timeout=5) as r:
            data = r.read()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def proxy_monerod(self):
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": "0",
            "method": "get_info"
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:18081/json_rpc",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(r.read())

    def serve_log(self):
        """Serve current in-memory rolling log as JSON"""
        with log_lock:
            data = {k: list(v) for k,v in log.items()}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def serve_threshold(self):
        threshold = get_min_payment_threshold()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"minPaymentThreshold": threshold}).encode())

# -------------------- Logging --------------------
def append_log(myHash, poolHash, netHash, price):
    ts = int(time.time())
    cutoff = ts - MAX_LOG_AGE
    with log_lock:
        log["timestamps"].append(ts)
        log["myHash"].append(myHash)
        log["poolHash"].append(poolHash)
        log["netHash"].append(netHash)
        log["price"].append(price)

        # Remove old entries beyond 24h
        while log["timestamps"] and log["timestamps"][0] < cutoff:
            for k in log:
                log[k].popleft()

def save_log_disk():
    """Atomic write to disk"""
    tmp_file = LOG_FILE + ".tmp"
    with log_lock:
        data = {k: list(v) for k,v in log.items()}
    with open(tmp_file, "w") as f:
        json.dump(data, f)
    os.replace(tmp_file, LOG_FILE)

# -------------------- Logger loop --------------------
def log_loop():
    last_save = 0
    while not shutdown_event.is_set():
        try:
            xmrig = json.loads(
                urllib.request.urlopen("http://127.0.0.1:42000/2/summary", timeout=5).read()
            )
            myHash = xmrig["hashrate"]["total"][0]

            pool = json.loads(
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/pool/stats", timeout=5).read()
            )
            poolHash = pool["pool_statistics"]["hashRate"]

            req = urllib.request.Request(
                "http://127.0.0.1:18081/json_rpc",
                data=json.dumps({"jsonrpc": "2.0", "id": "0", "method": "get_info"}).encode(),
                headers={"Content-Type": "application/json"}
            )
            net = json.loads(urllib.request.urlopen(req, timeout=5).read())
            netHash = net["result"]["difficulty"] / 120

            price = get_xmr_price()
            append_log(myHash, poolHash, netHash, price)

            # Save to disk every 10s
            if time.time() - last_save > 10:
                save_log_disk()
                last_save = time.time()

        except Exception as e:
            if not shutdown_event.is_set():
                print("Log error:", e)

        shutdown_event.wait(10)

# -------------------- Shutdown --------------------
shutdown_event = threading.Event()

# -------------------- Start logger thread --------------------
threading.Thread(target=log_loop, daemon=True).start()

# -------------------- Start HTTP server --------------------
socketserver.ThreadingTCPServer.allow_reuse_address = True
print(f"Serving HTTP on 0.0.0.0:{PORT}")

try:
    with socketserver.ThreadingTCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\nCTRL+C received, shutting down cleanly...")
finally:
    shutdown_event.set()
    save_log_disk()
    print("Server stopped cleanly.")
    sys.exit(0)
