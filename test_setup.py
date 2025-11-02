#!/usr/bin/env python3
"""
Quick test script to verify MCP servers are configured correctly
"""
import asyncio
import json
from pathlib import Path

def test_config():
    """Test that the configuration file is valid."""
    config_path = Path.home() / ".config/ollmcp/mcp-servers/web3-audit.json"
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return False
    
    try:
        with open(config_path) as f:
            config = json.load(f)
        
        servers = config.get("mcpServers", {})
        
        print("✅ Configuration file is valid JSON")
        print(f"✅ Found {len(servers)} MCP servers:")
        
        for name, server_config in servers.items():
            command = server_config.get("command", "unknown")
            print(f"   - {name}: {command}")
        
        # Check for required servers
        required = ["mcp-filesystem", "bash-server"]
        missing = [s for s in required if s not in servers]
        
        if missing:
            print(f"⚠️  Missing servers: {', '.join(missing)}")
        else:
            print("✅ All required servers configured")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_tools_dir():
    """Test that ~/tools exists."""
    tools_dir = Path.home() / "tools"
    
    if tools_dir.exists():
        print(f"✅ Tools directory exists: {tools_dir}")
        
        # List some tools
        tools = [d.name for d in tools_dir.iterdir() if d.is_dir()][:5]
        if tools:
            print(f"✅ Found tools: {', '.join(tools)}")
        
        return True
    else:
        print(f"⚠️  Tools directory not found: {tools_dir}")
        return False

def test_bash_server():
    """Test that bash server file exists and is executable."""
    bash_server = Path("/home/dok/tools/ollm-crypt-sec/mcp_bash_server.py")
    
    if bash_server.exists():
        print(f"✅ Bash server exists: {bash_server}")
        
        if os.access(bash_server, os.X_OK):
            print("✅ Bash server is executable")
        else:
            print("⚠️  Bash server is not executable (run: chmod +x)")
        
        return True
    else:
        print(f"❌ Bash server not found: {bash_server}")
        return False

if __name__ == "__main__":
    import os
    
    print("🧪 Testing Web3 Audit Setup\n")
    print("=" * 50)
    
    results = []
    results.append(("Config File", test_config()))
    results.append(("Tools Directory", test_tools_dir()))
    results.append(("Bash Server", test_bash_server()))
    
    print("\n" + "=" * 50)
    print("\n📊 Summary:")
    
    all_ok = all(r[1] for r in results)
    
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    
    if all_ok:
        print("\n🎉 Setup looks good! You can start using ollmcp now.")
        print("\nNext steps:")
        print("1. Start ollmcp: ollmcp --servers-json ~/.config/ollmcp/mcp-servers/web3-audit.json")
        print("2. Create agent: agent > 1 > web3_audit")
        print("3. Start auditing!")
    else:
        print("\n⚠️  Some checks failed. Please review the errors above.")
