import os

target = "videos_data.json"
for root, dirs, files in os.walk("."):
    for file in files:
        if file.endswith((".py", ".js", ".html", ".css", ".json")):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if target in content:
                        print(f"Found in {path}")
            except Exception as e:
                pass
