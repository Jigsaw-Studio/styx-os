#!/bin/sh

mkdir -p /run/dhcp/

NOCOLOR='\033[0m'
RED='\033[0;31m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'

sigterm_handler () {
  printf "%s[*] Caught SIGTERM/SIGINT!%s\n" "$CYAN" "$NOCOLOR"
  pkill hostapd
  cleanup
  exit 0
}
cleanup () {
  printf "%s[*] Deleting iptables rules...%s\n" "$CYAN" "$NOCOLOR"
  sh /iptables_off.sh || printf "%s[-] Error deleting iptables rules%s\n" "$RED" "$NOCOLOR"
  printf "%s[*] Restarting network interface...%s\n" "$CYAN" "$NOCOLOR"
  ifdown wlan0
  ifup wlan0
  printf "%s[+] Successfully exited, byebye! %s\n" "$GREEN" "$NOCOLOR"
}

trap 'sigterm_handler' TERM INT
printf "%s[*] Creating iptables rules%s\n" "$CYAN" "$NOCOLOR"
sh /iptables.sh || printf "%s[-] Error creating iptables rules%s\n" "$RED" "$NOCOLOR"

printf "%s[*] Setting wlan0 settings%s\n" "$CYAN" "$NOCOLOR"
ifdown wlan0
ifup wlan0

printf "%s[+] Configuration successful! Services will start now%s\n" "$CYAN" "$NOCOLOR"
dhcpd -4 -f -d wlan0 &
hostapd /etc/hostapd/hostapd.conf &
pid=$!
wait $pid

cleanup
