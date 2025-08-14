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
    
    print("\n" + "-"*60)
    print("Starting server...")
    print("-"*60 + "\n")
    
    # Run server
    if reload:
        # Development mode with auto-reload
        uvicorn.run(
            "src.api.app:app",
            host=host,
            port=port,
            reload=reload,
            log_level=log_level
        )
    else:
        # Production mode with multiple workers
        uvicorn.run(
            "src.api.app:app",
            host=host,
            port=port,
            workers=workers,
            log_level=log_level
        )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Server stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting server: {str(e)}")
        sys.exit(1)
