#!/bin/sh
# Copyright (c) 2024 Steve Castellotti
# This file is part of styx-os and is released under the MIT License.
# See LICENSE file in the project root for full license information.

# Exit on any error
set -e

echo "Preparing to install styx-os"

sudo apt update && sudo apt upgrade -y

sudo apt install docker.io containerd docker-compose rsync unzip -y

sudo usermod -aG docker styx
newgrp docker

# Disable graphical and/or automatic login
sudo systemctl set-default multi-user.target
sudo raspi-config nonint do_boot_behaviour B1

# Enable network forwarding
sudo sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf

# styx-os repository URL
REPO_URL="https://github.com/Jigsaw-Studio/styx-os"

# Download the /srv directory
curl -L "${REPO_URL}/archive/refs/heads/main.zip" -o /tmp/styx-os.zip

# Unzip in temporary location
unzip /tmp/styx-os.zip -d /tmp

# Check if /srv exists and create if it doesn't
if [ ! -d "/srv" ]; then
    sudo mkdir /srv
fi

# Move contents from zip to /srv, checking each directory
for dir in /tmp/styx-os-main/srv/*; do
    dir_name=$(basename "$dir")
    # Ensure the target directory exists
    sudo mkdir -p "/srv/$dir_name"
    # Sync contents to existing directory
    sudo rsync -av --ignore-existing "$dir/" "/srv/$dir_name/"
done

# Clean up the downloaded and extracted files
rm -rf /tmp/styx-os.zip /tmp/styx-os-main

# Grant necessary write permissions to docker container for Pi-hole
sudo chown styx:docker -R /srv/styx-pihole/etc/pihole /srv/styx-pihole/etc/dnsmasq.d /srv/styx-pihole/var/log/pihole
sudo chmod ug+w -R /srv/styx-pihole/etc/pihole /srv/styx-pihole/etc/dnsmasq.d /srv/styx-pihole/var/log/pihole

# Configure and start the Pi-hole service
cd /srv/styx-pihole
sudo cp -av etc/systemd/system/docker@styx-pihole.service /etc/systemd/system
sudo systemctl enable docker@styx-pihole.service
sudo systemctl start docker@styx-pihole.service

# Configure and start the AutoWLAN service
cd /srv/styx-autowlan
# Optional: Customize access point name and password
sudo docker build -t styx-autowlan .
sudo cp -av etc/systemd/system/docker@styx-autowlan.service /etc/systemd/system
sudo systemctl enable docker@styx-autowlan.service
sudo systemctl start docker@styx-autowlan.service

# Configure and start the WiFi Power Management service (prevents access point from sleeping)
sudo cp -av etc/systemd/system/wifi-power-management.service /etc/systemd/system
sudo systemctl enable wifi-power-management.service
sudo systemctl start wifi-power-management.service

# Configure and start the Deep Packet Inspection (DPI) service
cd /srv/styx-dpi
sudo docker build -t styx-dpi .
sudo cp -av etc/systemd/system/docker@styx-dpi.service /etc/systemd/system
sudo systemctl enable docker@styx-dpi.service
sudo systemctl start docker@styx-dpi.service

# Configure and start the Application Programming Interface (API) service
cd /srv/styx-api
sudo docker build -t styx-api .
sudo cp -av etc/systemd/system/docker@styx-api.service /etc/systemd/system
sudo systemctl enable docker@styx-api.service
sudo systemctl start docker@styx-api.service
