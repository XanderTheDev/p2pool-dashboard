#!/usr/bin/env python3
import http.server
import socketserver
import json
import os
import urllib.request
import time
import argparse
import threading

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
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                data = r.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(502, str(e))

    def proxy_monerod(self):
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": "0",
            "method": "get_info"
        }).encode()
        try:
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
        except Exception as e:
            self.send_error(502, str(e))

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
    while True:
        try:
            xmrig = json.loads(
                urllib.request.urlopen("http://127.0.0.1:42000/2/summary").read()
            )
            myHash = xmrig["hashrate"]["total"][0]

            pool = json.loads(
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/pool/stats").read()
            )
            poolHash = pool["pool_statistics"]["hashRate"]

            req = urllib.request.Request(
                "http://127.0.0.1:18081/json_rpc",
                data=json.dumps({"jsonrpc":"2.0","id":"0","method":"get_info"}).encode(),
                headers={"Content-Type":"application/json"}
            )
            net = json.loads(urllib.request.urlopen(req).read())
            netHash = net["result"]["difficulty"] / 120

            try:
                price = float(json.loads(
                    urllib.request.urlopen(
                        "https://api.price2sheet.com/json/xmr/eur"
                    ).read()
                )["price"])
            except:
                price = 0

            append_log(myHash, poolHash, netHash, price)

        except Exception as e:
            print("Log error:", e)

        time.sleep(10)

threading.Thread(target=log_loop, daemon=True).start()

with socketserver.ThreadingTCPServer(("", PORT), Handler) as httpd:
    print(f"Serving HTTP on 0.0.0.0:{PORT}")
    httpd.serve_forever()
