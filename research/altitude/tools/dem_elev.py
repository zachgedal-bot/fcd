#!/usr/bin/env python3
"""Elevation lookup from public SRTM/skadi 1-arc-second terrain tiles (AWS Terrain Tiles, elevation-tiles-prod).
Usage: python3 dem_elev.py LAT LON   (decimal degrees; south/west negative)
Prints: elevation_m at nearest cell, bilinear estimate, and min/max within ~150 m radius.
Tiles are cached in ../data/dem/. Source: https://registry.opendata.aws/terrain-tiles/ (skadi format = SRTM HGT, 3601x3601 big-endian int16, void = -32768).
"""
import sys, os, math, gzip, urllib.request
import numpy as np
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'dem')
os.makedirs(CACHE, exist_ok=True)

def tile_name(lat, lon):
    la = math.floor(lat); lo = math.floor(lon)
    return f"{'N' if la>=0 else 'S'}{abs(la):02d}{'E' if lo>=0 else 'W'}{abs(lo):03d}"

def load_tile(lat, lon):
    name = tile_name(lat, lon)
    path = os.path.join(CACHE, name + '.hgt')
    if not os.path.exists(path):
        url = f"https://s3.amazonaws.com/elevation-tiles-prod/skadi/{name[:3]}/{name}.hgt.gz"
        gz = f"{path}.{os.getpid()}.gz"; tmp = f"{path}.{os.getpid()}.tmp"
        urllib.request.urlretrieve(url, gz)
        with gzip.open(gz, 'rb') as f, open(tmp, 'wb') as o:
            o.write(f.read())
        os.replace(tmp, path)  # atomic: safe when several agents fetch the same tile
        try: os.remove(gz)
        except OSError: pass
    n = os.path.getsize(path); side = int(round((n/2) ** 0.5))
    a = np.fromfile(path, dtype='>i2').reshape(side, side).astype(float)
    a[a == -32768] = np.nan
    return a, side

def elevation(lat, lon):
    a, side = load_tile(lat, lon)
    la0 = math.floor(lat); lo0 = math.floor(lon)
    # row 0 = northern edge (lat la0+1), col 0 = western edge (lon lo0)
    fr = (la0 + 1 - lat) * (side - 1); fc = (lon - lo0) * (side - 1)
    r = int(round(fr)); c = int(round(fc))
    nearest = a[r, c]
    r0, c0 = int(math.floor(fr)), int(math.floor(fc)); dr, dc = fr - r0, fc - c0
    r1, c1 = min(r0 + 1, side - 1), min(c0 + 1, side - 1)
    bil = (a[r0, c0] * (1-dr) * (1-dc) + a[r0, c1] * (1-dr) * dc + a[r1, c0] * dr * (1-dc) + a[r1, c1] * dr * dc)
    w = 5  # ~150 m window
    win = a[max(r-w,0):r+w+1, max(c-w,0):c+w+1]
    return nearest, bil, np.nanmin(win), np.nanmax(win)

if __name__ == '__main__':
    lat = float(sys.argv[1]); lon = float(sys.argv[2])
    n, b, mn, mx = elevation(lat, lon)
    print(f"lat={lat} lon={lon} tile={tile_name(lat,lon)} elevation_nearest_m={n:.0f} bilinear_m={b:.0f} window150m_min={mn:.0f} window150m_max={mx:.0f}")
