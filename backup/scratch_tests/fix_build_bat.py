import os
import stat

file_path = 'build.bat'

# Check if read-only and remove it
if os.path.exists(file_path):
    mode = os.stat(file_path).st_mode
    print("Original mode:", oct(mode))
    # Remove read-only attribute if set
    if not (mode & stat.S_IWRITE):
        print("File is read-only, removing read-only attribute...")
        os.chmod(file_path, stat.S_IWRITE)
        print("New mode:", oct(os.stat(file_path).st_mode))

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # Replace Unix LF with Windows CRLF
    crlf_text = text.replace('\r\n', '\n').replace('\n', '\r\n')

    with open(file_path, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(crlf_text)
    print("build.bat line endings fixed to CRLF!")
except Exception as e:
    print("Error during write:", e)
