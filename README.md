# DHCP Server and Client

A DHCP server and client written from scratch in Python with UDP sockets. The packets are built and parsed byte by byte, with no DHCP library. The client sends DISCOVER, the server replies with an OFFER from its address pool, the client sends a REQUEST, and the server confirms with an ACK. The lease then counts down until it expires.

Built as a Computer Networks mini project.

## Why it's interesting

- **Hand-built packets.** The fixed BOOTP header, the magic cookie and the DHCP options are all encoded and decoded by hand: message type (53), subnet mask (1), router (3), DNS (6), lease time (51), server ID (54), requested IP (50), client ID (61) and hostname (12).
- **Concurrent server.** Each incoming client is handled on its own thread. A separate timer thread expires leases and returns their addresses to the pool.
- **Configurable pool.** `configs.json` sets the pool as an IP range or a subnet, the lease time, fixed MAC-to-IP reservations, and a MAC blacklist.
- **Client retry.** If no reply comes, the client sends DISCOVER again, waiting longer each time (randomized exponential backoff, capped at 120 s).

## Tech stack

Python 3 · `socket` (UDP, broadcast) · `threading` · `struct` / `binascii` · [`netaddr`](https://pypi.org/project/netaddr/)

## How to run

```sh
pip install netaddr

# terminal 1: the server listens on UDP port 67
python3 server.py          # on Linux, run with sudo (port 67 is privileged)

# terminal 2: the client asks for a hostname, then runs the handshake
python3 client.py
```

Run both from the repo root, because the server reads `configs.json` from the current directory.

Sample client output:

```
[Socket] DHCP Discover Sent

[Socket] DHCP Request Sent

Client configuration:
Hostname: laptop1 | MAC: ba:bb:79:02:58:95 | IP: 192.168.1.5 | Lease Time: 30 | DNS : ['1.1.1.1', '8.8.8.8']
```

## Files

| File | Purpose |
|---|---|
| `server.py` | DHCP server: address pool, OFFER/ACK, lease timer |
| `client.py` | DHCP client: DISCOVER/REQUEST, lease countdown, retry backoff |
| `utils.py` | Converts IPs, MACs and lease times to bytes; builds the address pool |
| `configs.json` | Pool range or subnet, lease time, reservations, blacklist |
