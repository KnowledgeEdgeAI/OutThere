"""Generate a tintable background mask using only Python's standard library."""
import math
import struct
import zlib
from pathlib import Path

width, height = 520, 340
pixels = bytearray()
for y in range(height):
    pixels.append(0)  # PNG scanline filter
    for x in range(width):
        radius = math.hypot((width - 1 - x) / width, y / height)
        alpha = round(255 * max(0, 1 - radius / 0.9) ** 1.5)
        pixels.extend((255, 255, 255, alpha))

def chunk(kind, data):
    return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))

png = b'\x89PNG\r\n\x1a\n'
png += chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 6, 0, 0, 0))
png += chunk(b'IDAT', zlib.compress(pixels, 9))
png += chunk(b'IEND', b'')
(Path(__file__).resolve().parents[1] / 'assets/page-glow.png').write_bytes(png)
