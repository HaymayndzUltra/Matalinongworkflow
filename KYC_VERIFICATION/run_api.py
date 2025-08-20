#!/usr/bin/env python3
"""
FastAPI Server Launcher
Starts the KYC Verification API server
"""

import os
import sys
import uvicorn
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    """Launch FastAPI server"""
    print("\n" + "="*60)
    print("🚀 STARTING KYC VERIFICATION API SERVER")
    print("="*60 + "\n")
    
    # Configuration
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"
    workers = int(os.getenv("API_WORKERS", "1"))
    log_level = os.getenv("API_LOG_LEVEL", "info")
    
    print(f"📍 Configuration:")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Reload: {reload}")
    print(f"   Workers: {workers}")
    print(f"   Log Level: {log_level}")
    
    print(f"\n📚 API Documentation will be available at:")
    print(f"   Swagger UI: http://localhost:{port}/docs")
    print(f"   ReDoc: http://localhost:{port}/redoc")
    print(f"   OpenAPI JSON: http://localhost:{port}/openapi.json")
    
    print(f"\n🔌 API Endpoints:")
    print(f"   Health Check: http://localhost:{port}/health")
    print(f"   Metrics: http://localhost:{port}/metrics")
    print(f"   Validate: POST http://localhost:{port}/validate")
    print(f"   Extract: POST http://localhost:{port}/extract")
    print(f"   Score: POST http://localhost:{port}/score")
    print(f"   Decide: POST http://localhost:{port}/decide")
    print(f"   Complete: POST http://localhost:{port}/complete")
    print(f"   Mobile KYC Page: http://localhost:{port}/web/mobile_kyc.html")
    
    print("\n" + "-"*60)
    print("Starting server...")
    print("-"*60 + "\n")
    
    # TLS support for mobile getUserMedia (HTTPS required on non-localhost)
    certfile = os.getenv("SSL_CERTFILE")
    keyfile = os.getenv("SSL_KEYFILE")
    if certfile and keyfile:
        print(f"\n🔒 TLS enabled")
        print(f"   Cert: {certfile}")
        print(f"   Key : {keyfile}")

    # Run server
    run_kwargs = {
        "app": "src.api.app:app",
        "host": host,
        "port": port,
        "log_level": log_level,
    }
    if certfile and keyfile:
        run_kwargs.update({"ssl_certfile": certfile, "ssl_keyfile": keyfile})
    if reload:
        run_kwargs.update({"reload": reload})
    else:
        run_kwargs.update({"workers": workers})

    uvicorn.run(**run_kwargs)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Server stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting server: {str(e)}")
        sys.exit(1)
