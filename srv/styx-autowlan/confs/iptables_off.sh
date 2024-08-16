#/bin/sh
iptables -t nat -C POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null && iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
iptables -C FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null && iptables -D FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -C FORWARD -i wlan0 -o eth0 -j ACCEPT 2>/dev/null && iptables -D FORWARD -i wlan0 -o eth0 -j ACCEPT
