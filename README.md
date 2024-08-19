# styx-os

## Features
- Wireless Access Point (via `hostapd`)
- Ad blocking for all connected devices (via `Pi-hole`/`dnsmasqd`)

## Requirements
- Raspberry Pi 3, 4, or 5
- Ethernet network connection
- Base Raspberry Pi OS installation
  - 64 bit version
  - "Lite" image preferred

## Instructions

- Log into console directly or via SSH

- Automated installation:
  - Install dependencies
  - Build software
  - Deploy containers
  - Start services
```shell
curl -sL setup.styx.jigsaw.studio | sudo sh
```
