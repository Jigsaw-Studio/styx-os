# Copyright (c) 2024 Steve Castellotti
# This file is part of styx-os and is released under the MIT License.
# See LICENSE file in the project root for full license information.

import argparse
import requests
import socket
import threading

BUFFER_SIZE = 1024


class UDPRelayService:
    def __init__(self, udp_port):
        self.udp_port = udp_port
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.bind(("0.0.0.0", udp_port))
        print(f"UDP relay service started on 0.0.0.0:{udp_port}")

    def handle_request(self, data, client_address):
        print("Received:", client_address, data)
        try:
            # Decode the incoming data
            json_data = data.decode('utf-8')
            json_obj = eval(json_data)
            http_method = json_obj.get("GET", None)

            if not http_method:
                print("Invalid JSON data received.")
                return

            # Make HTTP GET request to local server
            url = f"http://styx-web{http_method}"
            response = requests.get(url)

            # Prepare the response for UDP transmission
            udp_response = response.text.encode('utf-8')
            max_udp_packet_size = BUFFER_SIZE - 32  # smaller than BUFFER_SIZE
            total_fragments = (len(udp_response) + max_udp_packet_size - 1) // max_udp_packet_size

            # Split and send fragments
            for fragment_num in range(total_fragments):
                start = fragment_num * max_udp_packet_size
                end = start + max_udp_packet_size
                fragment_body = udp_response[start:end]

                # Create the fragment with header (format: "fragment_num/total_fragments:fragment_body")
                fragment = f"{fragment_num + 1}/{total_fragments}:".encode('utf-8') + fragment_body
                self.udp_sock.sendto(fragment, client_address)

        except Exception as e:
            print(f"Error handling request: {e}")

    def start(self):
        # Listen for incoming UDP packets
        while True:
            try:
                udp_data, address = self.udp_sock.recvfrom(BUFFER_SIZE)
                threading.Thread(target=self.handle_request, args=(udp_data, address)).start()
            except KeyboardInterrupt:
                print("Shutting down UDP relay service.")
                break
            except Exception as exception:
                print(f"Error: {exception}")

        self.udp_sock.close()


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="UDP to HTTP relay service.")
    parser.add_argument('--port', type=int, default=8192, help="UDP port to bind to (default: 8192)")
    args = parser.parse_args()

    # Create and start the UDPRelayService
    relay_service = UDPRelayService(udp_port=args.port)
    relay_service.start()
