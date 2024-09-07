#!/bin/sh
# Copyright (c) 2024 Steve Castellotti
# This file is part of styx-os and is released under the MIT License.
# See LICENSE file in the project root for full license information.

# Exit on any error
set -e

echo "Preparing to install styx-os"

# Defaults
USERNAME="styx"
BRANCH="main"
SSID="Styx"
WPA_PASSPHRASE="myvoiceismypassport"
WEB_PASSWORD="ShutYourPi-hole!"

# Parse command-line arguments
while [ "$#" -gt 0 ]; do
    case "$1" in
        --user|--username)
            USERNAME="$2"
            shift 2
            ;;
        --branch)
            BRANCH="$2"
            shift 2
            ;;
        --ssid)
            SSID="$2"
            shift 2
            ;;
        --wpa|--wpa-passphrase|--passphrase)
            WPA_PASSPHRASE="$2"
            shift 2
            ;;
        --web|--web-password|--password)
            WEB_PASSWORD="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument passed: $1"
            exit 1
            ;;
    esac
done

# Install and upgrade system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install docker.io containerd docker-compose rsync unzip -y

# Check if /srv exists and create if it doesn't
if [ ! -d "/srv" ]; then
    sudo mkdir /srv
fi

# Create the user for services ("styx" by default) if it doesn't already exist
if ! id "$USERNAME" >/dev/null 2>&1; then
    sudo useradd -r -s /usr/sbin/nologin -d /srv "$USERNAME"
    echo "User $USERNAME created."
else
    echo "User $USERNAME already exists."
fi

sudo usermod -aG docker "$USERNAME"

# Enable containers to communicate
sudo docker network create styx-net

# Disable graphical and/or automatic login
sudo systemctl set-default multi-user.target
sudo raspi-config nonint do_boot_behaviour B1

# Enable network forwarding
sudo sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf

# styx-os repository URL
REPO_URL="https://github.com/Jigsaw-Studio/styx-os"

# Download the /srv directory for the specified branch
curl -L "${REPO_URL}/archive/refs/heads/${BRANCH}.zip" -o /tmp/styx-os.zip

# Unzip in temporary location
unzip /tmp/styx-os.zip -d /tmp

# Adjust path based on the branch (removing the 'v' prefix if present)
UNZIP_DIR="/tmp/styx-os-$(echo "$BRANCH" | sed 's/^v//')"

# Move contents from zip to /srv, checking each directory
for dir in "$UNZIP_DIR"/srv/*; do
    dir_name=$(basename "$dir")
    # Ensure the target directory exists
    sudo mkdir -p "/srv/$dir_name"
    # Sync contents to existing directory
    sudo rsync -av --ignore-existing "$dir/" "/srv/$dir_name/"
done

# Clean up the downloaded and extracted files
rm -rf /tmp/styx-os.zip "$UNZIP_DIR"

# Grant necessary write permissions to docker container for Pi-hole
sudo chown "$USERNAME":docker -R /srv/styx-pihole/etc/pihole /srv/styx-pihole/etc/dnsmasq.d /srv/styx-pihole/var/log/pihole
sudo chmod ug+w -R /srv/styx-pihole/etc/pihole /srv/styx-pihole/etc/dnsmasq.d /srv/styx-pihole/var/log/pihole

# Update the user in the docker@styx-pihole.service file
sudo sed -i "s|^User=.*|User=$USERNAME|" /srv/styx-pihole/etc/systemd/system/docker@styx-pihole.service

# Update the .env file with the new Pi-hole administrator web password and system timezone
TIMEZONE=$(cat /etc/timezone)  # Get the system's timezone
sudo sed -i "s|^WEBPASSWORD=.*|WEBPASSWORD=$WEB_PASSWORD|" /srv/styx-pihole/docker/.env
sudo sed -i "s|^TIMEZONE=.*|TIMEZONE=$TIMEZONE|" /srv/styx-pihole/docker/.env

# Configure and start the Pi-hole service
cd /srv/styx-pihole
sudo cp -av etc/systemd/system/docker@styx-pihole.service /etc/systemd/system
sudo systemctl enable docker@styx-pihole.service
sudo systemctl start docker@styx-pihole.service

# Configure the AutoWLAN service
hostapd_config="/srv/styx-autowlan/confs/hostapd_confs/wpa2.conf"
wpa_supplicant_config="/etc/wpa_supplicant/wpa_supplicant.conf"

# Update the hostapd configuration SSID
sudo sed -i "s|^ssid=.*|ssid=$SSID|" "$hostapd_config"

# Update the hostapd configuration WPA passphrase
sudo sed -i "s|^wpa_passphrase=.*|wpa_passphrase=$WPA_PASSPHRASE|" "$hostapd_config"

# Extract the country code from the wpa_supplicant configuration (if it exists)
country_code=$(sudo grep '^country=' "$wpa_supplicant_config" | cut -d= -f2)

# Update the hostapd configuration with the extracted country code
if [ -n "$country_code" ]; then
    sudo sed -i "s|^country_code=.*|country_code=$country_code|" "$hostapd_config"
else
    echo "No country code found in wpa_supplicant.conf. No changes made to country_code in hostapd."
fi

# Check if wlan0 is currently managed by NetworkManager and is a wifi device
if nmcli device show wlan0 | grep -q 'GENERAL.TYPE:.*wifi' && nmcli device status | grep -q 'wlan0.*connected'; then
    echo "wlan0 is set up as a WiFi client. Proceeding with updates..."

    # Disable NetworkManager from managing wlan0
    nmcli device set wlan0 managed no

    # Optionally, restart NetworkManager and hostapd to apply changes
    sudo systemctl restart NetworkManager
    echo "Updates applied. wlan0 is now configured for hostapd."
else
    echo "wlan0 is not set up as a WiFi client or is not connected. No changes made."
fi

# Build and install styx-autowlan Docker image and service
cd /srv/styx-autowlan
sudo docker build -t styx-autowlan .
sudo cp -av etc/systemd/system/docker@styx-autowlan.service /etc/systemd/system
sudo systemctl enable docker@styx-autowlan.service
sudo systemctl start docker@styx-autowlan.service

# Configure and start the WiFi Power Management service (prevents access point from sleeping)
sudo cp -av etc/systemd/system/wifi-power-management.service /etc/systemd/system
sudo systemctl enable wifi-power-management.service
sudo systemctl start wifi-power-management.service

# Update the user in the docker@styx-dpi.service file
sudo sed -i "s|^User=.*|User=$USERNAME|" /srv/styx-dpi/etc/systemd/system/docker@styx-dpi.service

# Configure and start the Deep Packet Inspection (DPI) service
cd /srv/styx-dpi
sudo docker build -t styx-dpi .
sudo cp -av etc/systemd/system/docker@styx-dpi.service /etc/systemd/system
sudo systemctl enable docker@styx-dpi.service
sudo systemctl start docker@styx-dpi.service

# Update the user in the docker@styx-api.service file
sudo sed -i "s|^User=.*|User=$USERNAME|" /srv/styx-api/etc/systemd/system/docker@styx-api.service

# Configure and start the Application Programming Interface (API) service
cd /srv/styx-api
sudo docker build -t styx-api .
sudo cp -av etc/systemd/system/docker@styx-api.service /etc/systemd/system
sudo systemctl enable docker@styx-api.service
sudo systemctl start docker@styx-api.service

# Configure and start the web service
cd /srv/styx-web
sudo docker build -t styx-web .
sudo cp -av etc/systemd/system/docker@styx-web.service /etc/systemd/system
sudo systemctl enable docker@styx-web.service
sudo systemctl start docker@styx-web.service

# Configure and start the UDP relay service
cd /srv/styx-relay
sudo docker build -t styx-relay .
sudo cp -av etc/systemd/system/docker@styx-relay.service /etc/systemd/system
sudo systemctl enable docker@styx-relay.service
sudo systemctl start docker@styx-relay.service
