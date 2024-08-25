import argparse
import os
import re
import socket
import sqlite3
import subprocess
import time
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
        self.traffic_data = defaultdict(lambda: {'sent': 0, 'received': 0, 'domain_name': None, 'port': None})

        self.local_ip_ranges = [
            re.compile(r'^192\.168\.\d{1,3}\.\d{1,3}$'),
            re.compile(r'^172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}$'),
            re.compile(r'^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$'),
            re.compile(r'^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
        ]

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
                local_ip TEXT,
                remote_ip TEXT,
                port INTEGER,
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

    def _is_local_ip(self, ip):
        if not self._is_valid_ip(ip):
            return False
        return any(pattern.match(ip) for pattern in self.local_ip_ranges)

    @staticmethod
    def _is_valid_ip(ip):
        # Ensure the IP address has four octets
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        # Ensure each octet is a number between 0 and 255
        for part in parts:
            if not part.isdigit() or not 0 <= int(part) <= 255:
                return False
        return True

    @staticmethod
    def _get_service_name(port):
        try:
            return socket.getservbyport(int(port))
        except OSError:
            return None

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

                if not (self._is_valid_ip(src_ip) and self._is_valid_ip(dst_ip)):
                    continue  # Skip invalid IP addresses

                length_match = re.search(r'length (\d+)', line)
                size = int(length_match.group(1)) if length_match else 0

                # Determine if the traffic is outgoing or incoming
                if self._is_local_ip(src_ip):
                    local_ip, remote_ip = src_ip, dst_ip
                    port = dst_port
                    bytes_sent = size
                    bytes_received = 0
                else:
                    local_ip, remote_ip = dst_ip, src_ip
                    port = src_port
                    bytes_sent = 0
                    bytes_received = size

                # Check if the local port is a known service
                service_name = None
                if self._is_local_ip(dst_ip):
                    service_name = self._get_service_name(dst_port)
                    if service_name:
                        port = dst_port

                key = (local_ip, remote_ip)

                if self.traffic_data[key]['port'] is None or service_name:  # Aggregate on service port or first entry
                    self.traffic_data[key]['port'] = port

                self.traffic_data[key]['sent'] += bytes_sent
                self.traffic_data[key]['received'] += bytes_received

                domain_name = self.ip_to_domain.get(remote_ip, None)
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

            local_ip, remote_ip = key
            port = data['port']

            cursor.execute('''
                INSERT OR REPLACE INTO traffic (timestamp, local_ip, remote_ip, port, bytes_sent, bytes_received, domain_name)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), local_ip, remote_ip, int(port), data['sent'], data['received'], data['domain_name']))
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
    parser.add_argument('--db_path', default=os.getenv('DB_PATH', 'data/styx-dpi.db'), help='Path to SQLite3 database (default: data/styx-dpi.db)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--interface', default=os.getenv('INTERFACE', 'wlan0'), help='Network interface to monitor (default: wlan0)')
    parser.add_argument('--log_path', default=os.getenv('LOG_PATH', '/app/log/pihole.log'), help='Path to Pi-hole log (default: /app/log/pihole.log)')
    parser.add_argument('--new-db', action='store_true', help='Create a new database, overwriting any existing one')
    args = parser.parse_args()

    monitor = NetworkMonitor(interface=args.interface, db_path=args.db_path, log_path=args.log_path, new_db=args.new_db, debug=args.debug)
    monitor.start()
