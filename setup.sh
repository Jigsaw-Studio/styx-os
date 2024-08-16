#!/bin/sh
# Copyright (c) 2024 Steve Castellotti
# This file is part of styx-os and is released under the MIT License.
# See LICENSE file in the project root for full license information.

# Exit on any error
set -e

echo "Preparing to install styx-os"

sudo apt update && sudo apt upgrade -y

sudo apt install docker.io containerd docker-compose unzip -y

sudo usermod -aG docker styx
newgrp docker

sudo systemctl set-default multi-user.target
sudo raspi-config nonint do_boot_behaviour B1

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

# Move the contents of the srv directory from the zip to /srv
sudo mv /tmp/styx-os-main/srv/* /srv/

# Clean up the downloaded and extracted files
rm -rf /tmp/styx-os.zip /tmp/styx-os-main

sudo chown styx:docker -R /srv/styx-pihole/etc/pihole /srv/styx-pihole/etc/dnsmasq.d
sudo chmod ug+w -R /srv/styx-pihole/etc/pihole /srv/styx-pihole/etc/dnsmasq.d

# Configure and start the Pihole service
cd /srv/styx-pihole
sudo cp -av etc/systemd/system/docker@styx-pihole.service /etc/systemd/system
sudo systemctl enable docker@styx-pihole.service
sudo systemctl start docker@styx-pihole.service

# Configure and start the AutoWLAN service
cd /srv/styx-autowlan
# Optional: Customize access point name and password
docker build -t styx-autowlan .
sudo cp -av etc/systemd/system/docker@styx-autowlan.service /etc/systemd/system
sudo systemctl enable docker@styx-autowlan.service
sudo systemctl start docker@styx-autowlan.service
