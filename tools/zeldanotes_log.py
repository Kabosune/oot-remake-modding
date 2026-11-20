#!/usr/bin/env python3
"""Read the Zelda Notes logs the OoT remake (1.1.1) keeps in option.sav.

  python3 tools/zeldanotes_log.py option.sav [--names names.txt] [--day 2026-11-17] [--timeline] [--positions]

option.sav is in the emulator's save folder for the game (one per user, next to the slot_NN folders).

Event kinds are named from a test round (19 Nov 2026); names marked '?' are guesses. Same list as
mods/adventure-log. More: docs/zelda-notes.md.
Name hashes: actors are CRC32 of the actor name, scenes and events MurmurHash3 (seed 0).
Give --names a text file with one candidate name per line (actor, scene, event names) to resolve them.
"""
import argparse, collections, datetime, struct, zlib

EPOCH = datetime.datetime(2026, 1, 1)          # times are UTC seconds since 1 Jan 2026
HIST_HASH, POS_HASH = 0x5392E233, 0x3C99C416   # option.sav field hashes of the two Binary fields

TYPES = {  # event kind -> what it is (19 Nov 2026 test round; '?' = guess). Same list as mods/adventure-log
    1: 'Link hurt (value2 = quarter hearts)', 2: 'Link defeated', 3: 'enemy defeated', 4: 'Z-target (none = let go)',
    5: 'item readied?', 7: 'item used (value1 = kind)', 11: 'picked up', 14: 'talk line (value1 = message)',
    16: 'event (none = ended)', 17: 'file loaded?', 23: 'lift', 24: 'throw / put down',
    25: 'area change (from, to)', 27: 'equip change (old, new; value1 = slot)', 28: 'attack landed (target, attacker)',
    30: 'learned song', 32: 'came into play?', 33: 'removed', 34: 'room change (values = floor / room)',
    37: 'Link hurt by the world', 38: 'dropped item', 39: 'life / magic (max << 16 | now)',
}

def mm3(s, seed=0):
    key = s.encode(); h = seed; n = len(key)
    c1, c2 = 0xCC9E2D51, 0x1B873593
    rot = lambda x, r: ((x << r) | (x >> (32 - r))) & 0xFFFFFFFF
    for i in range(0, n // 4 * 4, 4):
        k = int.from_bytes(key[i:i + 4], 'little')
        k = rot(k * c1 & 0xFFFFFFFF, 15) * c2 & 0xFFFFFFFF
        h = (rot(h ^ k, 13) * 5 + 0xE6546B64) & 0xFFFFFFFF
    t = key[n // 4 * 4:]
    if t:
        k = int.from_bytes(t, 'little')
        h ^= rot(k * c1 & 0xFFFFFFFF, 15) * c2 & 0xFFFFFFFF
    h ^= n; h ^= h >> 16; h = h * 0x85EBCA6B & 0xFFFFFFFF; h ^= h >> 13
    h = h * 0xC2B2AE35 & 0xFFFFFFFF; h ^= h >> 16
    return h

def binary_fields(data):
    end = struct.unpack_from('<I', data, 8)[0]
    out = {}
    for o in range(0x20, end, 8):
        h, v = struct.unpack_from('<II', data, o)
        if h in (HIST_HASH, POS_HASH):
            size = struct.unpack_from('<I', data, v)[0]
            out[h] = data[v + 4:v + 4 + size]
    return out

def when(t): return EPOCH + datetime.timedelta(seconds=t)

def unpack_pos(code):
    """Whole metres: x and z in -1000..1000 (stored + 1000, 11 bits each), height in -500..500
    (stored + 500, the top 10 bits). Which of the two low fields is x and which z is assumed."""
    return (code & 0x7FF) - 1000, (code >> 22) - 500, ((code >> 11) & 0x7FF) - 1000

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('save'); ap.add_argument('--names'); ap.add_argument('--day')
    ap.add_argument('--timeline', action='store_true'); ap.add_argument('--positions', action='store_true')
    a = ap.parse_args()
    names = {}
    if a.names:
        for line in open(a.names, encoding='utf-8', errors='ignore'):
            n = line.strip()
            if n:
                names.setdefault(zlib.crc32(n.encode()), n); names.setdefault(mm3(n), n)
    nm = lambda h: '-' if h == 0 else names.get(h, '%08x' % h)
    f = binary_fields(open(a.save, 'rb').read())
    hist = f.get(HIST_HASH, b'')
    ev = sorted(e for e in struct.iter_unpack('<IIIIii', hist) if any(e))
    if a.day:
        ev = [e for e in ev if when(e[0]).strftime('%Y-%m-%d') == a.day]
    if ev:
        print(f'{len(ev)} events, {when(ev[0][0])} .. {when(ev[-1][0])} UTC')
    if a.timeline:
        for t, ty, h1, h2, v1, v2 in ev:
            print(when(t).strftime('%m-%d %H:%M:%S'), f'{ty:3d}', TYPES.get(ty, '?'), nm(h1), nm(h2), v1, v2)
    else:
        by = collections.defaultdict(collections.Counter)
        for t, ty, h1, h2, v1, v2 in ev:
            by[ty][(nm(h1), nm(h2))] += 1
        for ty in sorted(by):
            print(f'type {ty:3d} {TYPES.get(ty, "?"):34s} x{sum(by[ty].values()):4d}  ', by[ty].most_common(4))
    if a.positions:
        pos = sorted(p for p in struct.iter_unpack('<IIII', f.get(POS_HASH, b'')) if any(p))
        for t, code, scene, fr in pos:
            print(when(t).strftime('%m-%d %H:%M:%S'), unpack_pos(code), nm(scene), hex(fr))

if __name__ == '__main__':
    main()
