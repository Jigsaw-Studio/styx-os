import argparse
import os
import subprocess
import sqlite3
import time
import re
from collections import defaultdict
from datetime import datetime
from threading import Thread

class NetworkMonitor:
    def __init__(self, interface='wlan0', db_path='data/styx-dpi.db', log_path='/app/log/pihole.log', new_db=False, debug=False):
        self.interface = interface
        self.db_path = db_path
        self.log_path = log_path
        self.new_db = new_db
        self.debug = debug
        self.ip_to_domain = {}
        self.traffic_data = defaultdict(lambda: {'sent': 0, 'received': 0, 'domain_name': None})

        self._setup_database()

    def _setup_database(self):
        if self.new_db:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
            self._create_database()
        elif not os.path.exists(self.db_path):
            self._create_database()

    def _create_database(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS traffic (
                timestamp TEXT,
                src_ip TEXT,
                src_port INTEGER,
                dst_ip TEXT,
                dst_port INTEGER,
                bytes_sent INTEGER,
                bytes_received INTEGER,
                domain_name TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def update_ip_to_domain(self):
        with open(self.log_path, 'r') as log_file:
            while True:
                line = log_file.readline()
                if not line:
                    time.sleep(1)
                    continue

                match = re.search(r'reply (\S+) is (\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    domain, ip = match.groups()
                    self.ip_to_domain[ip] = domain

    def monitor_network_traffic(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        tcpdump_cmd = f"tcpdump -i {self.interface} -n -l"
        tcpdump_proc = subprocess.Popen(tcpdump_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

        start_time = time.time()

        for line in tcpdump_proc.stdout:
            if 'IP' in line:
                parts = line.split()

                src_ip, src_port = parts[2].rsplit('.', 1)
                dst_ip, dst_port = parts[4].rstrip(':').rsplit('.', 1)

                length_match = re.search(r'length (\d+)', line)
                size = int(length_match.group(1)) if length_match else 0

                domain_name_src = self.ip_to_domain.get(src_ip, None)
                domain_name_dst = self.ip_to_domain.get(dst_ip, None)

                timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                domain_name = domain_name_dst if domain_name_dst else domain_name_src

                key = (timestamp, src_ip, src_port, dst_ip, dst_port)

                self.traffic_data[key]['sent'] += size
                self.traffic_data[key]['received'] += size
                if domain_name:
                    self.traffic_data[key]['domain_name'] = domain_name

                if time.time() - start_time >= 1:
                    self._insert_traffic_data(c)
                    self.traffic_data.clear()
                    start_time = time.time()

        conn.close()

    def _insert_traffic_data(self, cursor):
        for key, data in self.traffic_data.items():
            # Skip entries where both bytes_sent and bytes_received are 0
            if data['sent'] == 0 and data['received'] == 0:
                continue

            timestamp, src_ip, src_port, dst_ip, dst_port = key

            cursor.execute('''
                INSERT OR REPLACE INTO traffic (timestamp, src_ip, src_port, dst_ip, dst_port, bytes_sent, bytes_received, domain_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, src_ip, int(src_port), dst_ip, int(dst_port), data['sent'], data['received'], data['domain_name']))
        cursor.connection.commit()

    def start(self):
        # Create and start the pihole log parsing thread
        pihole_thread = Thread(target=self.update_ip_to_domain)
        pihole_thread.start()

        # Create and start the network monitoring thread
        traffic_thread = Thread(target=self.monitor_network_traffic)
        traffic_thread.start()

        pihole_thread.join()
        traffic_thread.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor network traffic and DNS resolutions.")
    parser.add_argument('--interface', default='wlan0', help='Network interface to monitor (default: wlan0)')
    parser.add_argument('--db_path', default='data/styx-dpi.db', help='Path to SQLite3 database (default: data/styx-dpi.db)')
    parser.add_argument('--log_path', default='/app/log/pihole.log', help='Path to Pi-hole log (default: /app/log/pihole.log)')
    parser.add_argument('--new-db', action='store_true', help='Create a new database, overwriting any existing one')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    if args.debug:
        import pydevd_pycharm
        pydevd_pycharm.settrace('127.0.0.1', port=12345, stdoutToServer=True, stderrToServer=True, suspend=False)

    monitor = NetworkMonitor(interface=args.interface, db_path=args.db_path, log_path=args.log_path, new_db=args.new_db, debug=args.debug)
    monitor.start()
