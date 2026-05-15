# Proxy Gateway Desktop for macOS

Native SwiftUI control surface for the local Mac VPN kit at `~/ProxyGatewayMacVPN`.

This app intentionally keeps the visible surface narrow: status, start, stop, refresh, and test. It shells out to the existing `macvpnctl.sh` controller and redacts sensitive command output before rendering it.

## Build

```bash
swift build
```

## Run

```bash
./script/build_and_run.sh --verify
```

## Install for Local Desktop Use

```bash
./script/build_and_run.sh --install
```

The install command copies the app to `~/Applications/Proxy Gateway Desktop.app` and `~/Desktop/Proxy Gateway Desktop.app`.
