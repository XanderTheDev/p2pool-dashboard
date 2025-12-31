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

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8080)
parser.add_argument("--data-dir", type=str, default="./p2pool-data")
args = parser.parse_args()

PORT = args.port
DATA_DIR = args.data_dir
LOG_FILE = os.path.join(DATA_DIR, "stats_log.json")
MAX_LOG_AGE = 7 * 24 * 3600

os.makedirs(DATA_DIR, exist_ok=True)

if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w") as f:
        json.dump({
            "timestamps": [],
            "myHash": [],
            "poolHash": [],
            "netHash": [],
            "price": []
        }, f)

# --------------------------------------------------
# Shutdown coordination
# --------------------------------------------------
shutdown_event = threading.Event()

# --------------------------------------------------
# Helper: get last recorded XMR price
# --------------------------------------------------
def get_last_price():
    try:
        with open(LOG_FILE, "r") as f:
            data = json.load(f)
            if data["price"]:
                return float(data["price"][-1])
    except Exception:
        pass
    return 0.0

# --------------------------------------------------
# Helper: multi-API XMR price
# --------------------------------------------------
def get_xmr_price():
    #
    #Return current XMR price in EUR using multiple APIs with fallback:
    #  1. CoinGecko XMR/EUR
    #  2. Kraken XMR/EUR
    #  3. Bitfinex XMR/USD → EUR via Frankfurter API
    #  4. price2sheet XMR/EUR
    #  5. Last logged price
    #Prints which source was used.
    #"""
    # 1. CoinGecko XMR/EUR
    try:
        with urllib.request.urlopen(
            "https://api.coingecko.com/api/v3/simple/price?ids=monero&vs_currencies=eur",
            timeout=5
        ) as r:
            data = json.load(r)
        price = float(data["monero"]["eur"])
        if price > 0:
            print("Price has come from: CoinGecko")
            return price
    except Exception:
        pass

    # 2. Kraken XMR/EUR
    try:
        with urllib.request.urlopen("https://api.kraken.com/0/public/Ticker?pair=XMREUR", timeout=5) as r:
            data = json.load(r)
        price = float(data["result"]["XXMRZEUR"]["c"][0])
        if price > 0:
            print("Price has come from: Kraken")
            return price
    except Exception:
        pass

    # 3. Bitfinex XMR/USD → EUR via Frankfurter
    try:
        # Bitfinex XMR/USD
        with urllib.request.urlopen("https://api-pub.bitfinex.com/v2/ticker/tXMRUSD", timeout=5) as r:
            data = json.load(r)
            bitfinex_usd = float(data[6])

            # USD → EUR using Frankfurter API
            try:
                with urllib.request.urlopen("https://api.frankfurter.app/latest?from=USD&to=EUR", timeout=5) as r2:
                    fx_data = json.load(r2)
                    usd_to_eur = float(fx_data["rates"]["EUR"])
                    price = bitfinex_usd * usd_to_eur
                    if price > 0:
                        print("Price has come from: Bitfinex (converted USD→EUR via Frankfurter)")
                        return price
            except Exception:
                    pass  # USD→EUR conversion failed, skip to next fallback
    except Exception:
        pass  # Bitfinex call failed, skip to next fallback


    # 4. price2sheet
    try:
        with urllib.request.urlopen("https://api.price2sheet.com/json/xmr/eur", timeout=5) as r:
            data = json.load(r)
        price = float(data["price"])
        if price > 0:
            print("Price has come from: price2sheet")
            return price
    except Exception:
        pass

    # 5. Last logged price
    last_price = get_last_price()
    print("Price has come from last recorded value")
    return last_price

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
        with open(LOG_FILE) as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data.encode())


def append_log(myHash, poolHash, netHash, price):
    ts = int(time.time())
    with open(LOG_FILE, "r+") as f:
        data = json.load(f)

        data["timestamps"].append(ts)
        data["myHash"].append(myHash)
        data["poolHash"].append(poolHash)
        data["netHash"].append(netHash)
        data["price"].append(price)

        cutoff = ts - MAX_LOG_AGE
        while data["timestamps"] and data["timestamps"][0] < cutoff:
            for k in data:
                data[k].pop(0)

        f.seek(0)
        json.dump(data, f)
        f.truncate()


def log_loop():
    while not shutdown_event.is_set():
        try:
            xmrig = json.loads(
                urllib.request.urlopen(
                    "http://127.0.0.1:42000/2/summary",
                    timeout=5
                ).read()
            )
            myHash = xmrig["hashrate"]["total"][0]

            pool = json.loads(
                urllib.request.urlopen(
                    f"http://127.0.0.1:{PORT}/pool/stats",
                    timeout=5
                ).read()
            )
            poolHash = pool["pool_statistics"]["hashRate"]

            req = urllib.request.Request(
                "http://127.0.0.1:18081/json_rpc",
                data=json.dumps({
                    "jsonrpc": "2.0",
                    "id": "0",
                    "method": "get_info"
                }).encode(),
                headers={"Content-Type": "application/json"}
            )
            net = json.loads(
                urllib.request.urlopen(req, timeout=5).read()
            )
            netHash = net["result"]["difficulty"] / 120

            # Multi-API price fetch
            price = get_xmr_price()

            append_log(myHash, poolHash, netHash, price)

        except Exception as e:
            if not shutdown_event.is_set():
                print("Log error:", e)

        shutdown_event.wait(10)


# --------------------------------------------------
# Start logger thread
# --------------------------------------------------
threading.Thread(target=log_loop, daemon=True).start()

# --------------------------------------------------
# Start HTTP server
# --------------------------------------------------
socketserver.ThreadingTCPServer.allow_reuse_address = True

print(f"Serving HTTP on 0.0.0.0:{PORT}")

try:
    with socketserver.ThreadingTCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\nCTRL+C received, shutting down cleanly...")
finally:
    shutdown_event.set()
    print("Server stopped cleanly.")
    sys.exit(0)
