#!/usr/bin/env python3
"""
Memory MCP Setup and Diagnostic Script
Helps diagnose and configure the MCP memory server
"""

import json
import os
import requests
import time
from pathlib import Path

def check_memory_mcp_config():
    """Check current MCP memory configuration"""
    config_path = Path("memory.json")
    if not config_path.exists():
        print("❌ memory.json not found")
        return None
    
    with open(config_path) as f:
        config = json.load(f)
    
    print("📋 Current MCP Configuration:")
    if "mcpServers" in config:
        for server_name, server_config in config["mcpServers"].items():
            print(f"  {server_name}:")
            if "url" in server_config:
                print(f"    URL: {server_config['url']}")
            if "command" in server_config:
                print(f"    Command: {server_config['command']}")
            if "healthCheck" in server_config:
                print(f"    Health Check: {server_config['healthCheck']}")
    
    return config

def test_memory_service_connectivity():
    """Test if memory service is accessible"""
    config = check_memory_mcp_config()
    if not config:
        return False
    
    memory_config = config.get("mcpServers", {}).get("my-memory", {})
    base_url = memory_config.get("url", "").replace("/sse", "")
    health_endpoint = memory_config.get("healthCheck", "/health")
    
    if not base_url:
        print("❌ No memory service URL configured")
        return False
    
    print(f"\n🔍 Testing connectivity to {base_url}")
    
    try:
        # Test health endpoint
        health_url = f"{base_url}{health_endpoint}"
        print(f"  Testing: {health_url}")
        
        headers = {}
        if "headers" in memory_config:
            headers.update(memory_config["headers"])
        
        response = requests.get(health_url, headers=headers, timeout=5)
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text[:200]}")
        
        if response.status_code == 200:
            print("✅ Memory service is accessible")
            return True
        else:
            print("❌ Memory service returned error")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection failed: {e}")
        return False

def check_environment_variables():
    """Check if required environment variables are set"""
    print("\n🔧 Environment Variables:")
    
    # Check GitHub token
    github_token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
    if github_token:
        print(f"✅ GITHUB_PERSONAL_ACCESS_TOKEN: {github_token[:10]}...{github_token[-10:]}")
    else:
        print("❌ GITHUB_PERSONAL_ACCESS_TOKEN not set")
    
    # Check for other potential env vars
    for var in ["MCP_MEMORY_URL", "MCP_MEMORY_KEY", "MEMORY_DB_PATH"]:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {value}")
        else:
            print(f"⚠️  {var}: not set")

def test_local_memory_fallback():
    """Test local memory system as fallback"""
    print("\n🧠 Testing Local Memory System:")
    
    try:
        from unified_memory_access import unified_memory
        print("✅ unified_memory_access module loaded")
        
        # Test basic operations
        provider_type = unified_memory.provider_type
        print(f"  Provider: {provider_type}")
        
        # Test search
        results = unified_memory.search("session", limit=3)
        print(f"  Search results: {len(results)} memories found")
        
        # Test add
        test_memory = f"MCP setup test at {time.time()}"
        success = unified_memory.add("mcp_setup_test", test_memory)
        print(f"  Add test: {'✅ Success' if success else '❌ Failed'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Local memory system error: {e}")
        return False

def create_mcp_memory_fallback_config():
    """Create a fallback configuration for MCP memory"""
    fallback_config = {
        "mcpServers": {
            "github": {
                "command": "docker",
                "args": [
                    "run", "-i", "--rm", "--memory=512m", "--cpus=0.5",
                    "--security-opt=no-new-privileges",
                    "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
                    "ghcr.io/github/github-mcp-server"
                ],
                "env": {
                    "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"
                },
                "timeout": 30000,
                "retries": 3
            },
            "local-memory": {
                "command": "python3",
                "args": [
                    "-m", "memory_system.mcp_bridge",
                    "--db-path", "memory-bank/memory.db"
                ],
                "timeout": 10000,
                "retries": 2
            }
        }
    }
    
    print("\n🔧 Creating fallback MCP configuration:")
    with open("memory_mcp_fallback.json", "w") as f:
        json.dump(fallback_config, f, indent=2)
    
    print("✅ Created memory_mcp_fallback.json")
    print("  To use: mv memory_mcp_fallback.json memory.json")

def main():
    print("🧠 Memory MCP Setup and Diagnostics")
    print("=" * 50)
    
    # Check configuration
    config = check_memory_mcp_config()
    
    # Test connectivity
    connectivity_ok = test_memory_service_connectivity()
    
    # Check environment
    check_environment_variables()
    
    # Test local fallback
    local_ok = test_local_memory_fallback()
    
    print("\n📊 Summary:")
    print(f"  MCP Config: {'✅' if config else '❌'}")
    print(f"  Connectivity: {'✅' if connectivity_ok else '❌'}")
    print(f"  Local Memory: {'✅' if local_ok else '❌'}")
    
    if not connectivity_ok and local_ok:
        print("\n💡 Recommendation:")
        print("  External MCP memory service unavailable, but local system works.")
        print("  Consider using local memory system as fallback.")
        create_mcp_memory_fallback_config()
    
    print("\n✅ MCP Memory diagnostic complete!")

if __name__ == "__main__":
    main()
