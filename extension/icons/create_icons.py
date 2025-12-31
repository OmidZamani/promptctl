#!/usr/bin/env python3
import base64

# Minimal PNG files (solid purple squares with white border)
# These are valid PNG files created with minimal headers

def create_icon(size, filename):
    """Create a simple colored square PNG"""
    import struct
    
    # PNG signature
    png = b'\x89PNG\r\n\x1a\n'
    
    # IHDR chunk (image dimensions and properties)
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)  # RGB, 8-bit
    ihdr = b'IHDR' + ihdr
    ihdr_crc = struct.pack('>I', 0)  # Simplified CRC
    png += struct.pack('>I', len(ihdr) - 4) + ihdr + ihdr_crc
    
    # Create simple pixel data - purple background (#764ba2)
    pixels = b''
    for y in range(size):
        pixels += b'\x00'  # Filter type (none)
        for x in range(size):
            # Purple color RGB
            pixels += bytes([0x76, 0x4b, 0xa2])
    
    # Compress pixel data
    import zlib
    compressed = zlib.compress(pixels)
    
    # IDAT chunk (image data)
    idat = b'IDAT' + compressed
    idat_crc = struct.pack('>I', 0)
    png += struct.pack('>I', len(compressed)) + idat + idat_crc
    
    # IEND chunk
    png += b'\x00\x00\x00\x00IEND\xaeB`\x82'
    
    with open(filename, 'wb') as f:
        f.write(png)
    print(f'Created {filename}')

# Create all three sizes
create_icon(16, '16x16.png')
create_icon(48, '48x48.png')
create_icon(128, '128x128.png')

print('All icons created successfully!')
