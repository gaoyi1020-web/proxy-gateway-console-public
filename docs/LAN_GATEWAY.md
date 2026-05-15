# LAN Gateway Mode

LAN gateway mode lets one selected phone or test client use this host as a
manual Wi-Fi router for controlled local testing. It is not a whole-subnet
gateway mode.

## Network Inputs

Use runtime output from `proxy-stack lan-gateway-plan` or your private
deployment wrapper to fill these values:

- host LAN IP: `LAN-IP`
- upstream router: `ROUTER-IP`
- selected client IP: `CLIENT-IP`
- split DNS service: `1053`
- split TCP service: `12345`
- local failover proxy: `18180`

Do not commit real LAN IPs, device MAC addresses, hostnames, or screenshots.

## Check Plan

```bash
~/.local/bin/proxy-stack lan-gateway-plan
```

The plan reports manual Wi-Fi values and the root command required to enable
nftables rules for one selected client.

## Phone Manual Wi-Fi Settings

In the phone Wi-Fi network details, switch IPv4 to manual and keep the phone's
current IP:

- IP address: the `manual_iphone.ip` or equivalent client IP value from the
  plan.
- Subnet mask: the current LAN subnet mask, usually `255.255.255.0`.
- Router: `LAN-IP`.
- DNS: `LAN-IP`.

## Enable

Run only when the plan shows the expected selected client:

```bash
sudo ~/.local/bin/proxy-stack lan-gateway-root-apply --client-ip CLIENT-IP
```

The generated nftables table should match only that client IP. When the
neighbor table exposes the selected device MAC address, the root apply path can
also install a MAC-limited IPv6 forward reject rule for that same client.

## Rollback

```bash
sudo ~/.local/bin/proxy-stack lan-gateway-root-remove
```

Then switch the phone Wi-Fi IPv4 settings back to automatic DHCP.

## Traffic Behavior

- DNS TCP/UDP port `53` is redirected to `1053`.
- TCP traffic is redirected to `12345`.
- Private ranges go direct.
- Foreign routes use the local failover proxy.
- UDP `443` may be rejected to encourage QUIC fallback to TCP.
- Other forwarded traffic is masqueraded on the selected LAN interface.
