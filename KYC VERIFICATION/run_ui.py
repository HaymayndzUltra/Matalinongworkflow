#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import uvicorn

sys.path.insert(0, str(Path(__file__).parent))


def main():
    host = os.getenv("UI_HOST", "0.0.0.0")
    port = int(os.getenv("UI_PORT", "8080"))
    reload = os.getenv("UI_RELOAD", "true").lower() == "true"

    print("\n============================================")
    print("🖥️  STARTING KYC UI SERVER")
    print("============================================\n")
    print(f"Host: {host}\nPort: {port}\nReload: {reload}")
    print(f"Open UI: http://localhost:{port}/")

    uvicorn.run("src.ui.app:app", host=host, port=port, reload=reload, log_level="info")


if __name__ == "__main__":
    main()