# Copyright (c) 2024 Steve Castellotti
# This file is part of styx-os and is released under the MIT License.
# See LICENSE file in the project root for full license information.

import requests
import socket
import threading

UDP_ADDRESS = "0.0.0.0"
UDP_PORT = 8192
BUFFER_SIZE = 1024

# Function to handle UDP request and relay it over HTTP
def handle_request(data, client_address):
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
            udp_sock.sendto(fragment, client_address)

    except Exception as e:
        print(f"Error handling request: {e}")

# Create a UDP socket
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_sock.bind((UDP_ADDRESS, UDP_PORT))

print(f"UDP relay service started on {UDP_ADDRESS}:{UDP_PORT}")

# Listen for incoming UDP packets
while True:
    try:
        udp_data, address = udp_sock.recvfrom(BUFFER_SIZE)
        threading.Thread(target=handle_request, args=(udp_data, address)).start()
    except KeyboardInterrupt:
        print("Shutting down UDP relay service.")
        break
    except Exception as exception:
        print(f"Error: {exception}")

udp_sock.close()
