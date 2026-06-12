import os

with open('build.bat', 'rb') as f:
    content = f.read()

print("File size:", len(content))
print("First 10 bytes:", content[:10])
print("CRLF count:", content.count(b'\r\n'))
print("LF count (raw):", content.count(b'\n'))
print("Contains BOM:", content.startswith(b'\xef\xbb\xbf'))
