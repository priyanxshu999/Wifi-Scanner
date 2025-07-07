#!/usr/bin/env python3
"""
Cross‑platform Wi‑Fi scanner (dynamic linear scale)
Windows: pywifi ▸ netsh │ Linux: pywifi ▸ nmcli ▸ iwlist
"""

import platform, subprocess, sys, time, json, re, shutil

# ───── Colour helper (works on Win via colorama) ──────────
try:
    from colorama import init, Fore, Style
    init()
except ImportError:
    class _N:              # no‑colour fallback
        def __getattr__(self, _): return ""
    Fore = Style = _N()    # type: ignore

BAR_STEPS = ["▂", "▂█", "▂█▆", "▂█▆▅", "▂█▆▅▇"]

# ───── Dynamic linear scale builder ───────────────────────
def build_scale(values):
    mn, mx = min(values), max(values)
    if mx == mn:
        cuts = [mx] * 4          # all identical → always 5 bars
    else:
        step = (mx - mn) / 5
        cuts = [mn + step * i for i in range(1, 5)]  # 4 cuts

    palette = [Fore.RED + Style.DIM,
               Fore.RED,
               Fore.YELLOW,
               Fore.GREEN,
               Fore.GREEN + Style.BRIGHT]

    def bars(v):
        idx = sum(v >= c for c in cuts)      # 0‑4
        return BAR_STEPS[idx]

    def paint(v, s):
        idx = sum(v >= c for c in cuts)
        return f"{palette[idx]}{s}{Style.RESET_ALL}"

    return bars, paint

# ───── pywifi deep scan (preferred) ───────────────────────
def scan_pywifi():
    from pywifi import PyWiFi
    iface = PyWiFi().interfaces()[0]
    cells, seen = [], set()
    for _ in range(3):
        iface.scan(); time.sleep(2)
        for c in iface.scan_results():
            key = (c.ssid, c.bssid)
            if key not in seen:
                cells.append((c.ssid or "<hidden>", c.bssid, c.signal))
                seen.add(key)
    return cells

# ───── Linux fallbacks ────────────────────────────────────
def scan_linux():
    if shutil.which("nmcli"):
        raw = subprocess.check_output(
            ["nmcli", "-t", "-f", "SSID,SIGNAL,BSSID", "dev", "wifi", "list"],
            text=True, stderr=subprocess.DEVNULL)
        return [(p[0] or "<hidden>", p[2], int(p[1]))
                for p in (l.split(":") for l in raw.splitlines())
                if len(p) >= 3]
    iface = subprocess.check_output(["iw", "dev"], text=True)\
                      .split("Interface")[-1].split()[0]
    raw = subprocess.check_output(["iwlist", iface, "scan"],
                                  text=True, stderr=subprocess.DEVNULL)
    rx = re.compile(r'Cell \d+ - Address: ([\dA-F:]+).*?ESSID:"(.*?)".*?Signal level=(-?\d+)', re.S)
    return [(m[1] or "<hidden>", m[0], int(m[2])) for m in rx.findall(raw)]

# ───── Windows fallback ───────────────────────────────────
def scan_windows():
    raw = subprocess.check_output(
        ["netsh", "wlan", "show", "networks", "mode=bssid"],
        text=True, stderr=subprocess.DEVNULL, encoding="utf-8", errors="ignore")
    ssid, cells = None, []
    for ln in raw.splitlines():
        ln = ln.strip()
        if ln.startswith("SSID"):
            ssid = ln.split(":", 1)[1].strip() or "<hidden>"
        elif ln.startswith("BSSID"):
            bssid = ln.split(":", 1)[1].strip()
        elif ln.startswith("Signal"):
            pct = int(ln.split(":")[1].strip().rstrip("%"))
            cells.append((ssid, bssid, pct))          # 0‑100 %
    return cells

# ───── Dispatch ───────────────────────────────────────────
def scan():
    try:
        return scan_pywifi()
    except Exception:
        return scan_windows() if platform.system() == "Windows" else scan_linux()

# ───── Main ───────────────────────────────────────────────
def main():
    cells = scan()
    values = [v for *_, v in cells]
    bar, paint = build_scale(values)

    hdr = f"{'SSID':<20} {'BSSID':<20} {'Val':>6}  Bars"
    print(hdr + "\n" + "-" * len(hdr))
    for ssid, bssid, val in sorted(cells, key=lambda x: x[2], reverse=True):
        print(f"{ssid[:18]:<20} {bssid:<20} {paint(val, f'{val:>6}')}  {bar(val)}")

    with open("wifi_scan.json", "w", encoding="utf-8") as fp:
        json.dump([{"ssid": s, "bssid": b, "value": v} for s, b, v in cells],
                  fp, indent=2)
    print("\n[+] Results dumped to wifi_scan.json")

if __name__ == "__main__":
    main()
