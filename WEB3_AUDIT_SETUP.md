# Quick Start Guide: Web3 Audit Setup

## ✅ What's Already Configured

1. **MCP Server Configuration** created at:
   `~/.config/ollmcp/mcp-servers/web3-audit.json`
   
   This includes:
   - `mcp-filesystem` - File operations (read, write, list, search)
   - `analyze-solidity` - Solidity contract analysis

2. **Agent Configuration** created at:
   `config/agents/web3_auditor_local.yaml`

## 🚀 How to Use

### Step 1: Start ollmcp with the MCP servers

```bash
cd /home/dok/tools/ollm-crypt-sec
ollmcp --servers-json ~/.config/ollmcp/mcp-servers/web3-audit.json
```

### Step 2: Create a Web3 Audit Agent

Once in the ollmcp interface:
```
> agent
> 1 (Create a new agent)
> web3_audit
> my-web3-auditor
> qwen2.5:7b (or your preferred model)
> yes (connect to MCP servers)
> 1 (use same servers as main client)
```

OR load from config:
```
> agent
> 4 (Load agent from config file)
> config/agents/web3_auditor_local.yaml
```

### Step 3: Audit a Web3 Repository

```
> agent
> 3 (Execute task with agent)
> my-web3-auditor
> [Enter your audit task, for example:]
```

Example tasks:
```
Perform a comprehensive security audit of the Solidity project at /path/to/web3-repo. 
Check all contracts in src/, analyze each contract for vulnerabilities (reentrancy, 
overflow, access control), and generate a detailed report with findings classified by severity.
```

```
Analyze the smart contract at /path/to/Contract.sol. Identify potential vulnerabilities, 
check for common attack vectors, and suggest fixes.
```

```
Audit all contracts in /path/to/project/src. Run Slither analysis if available, 
check test coverage, and provide a comprehensive security assessment.
```

## 📋 Available Tools

The agent will have access to:
- **Filesystem operations**: Read files, list directories, search files
- **Solidity analysis**: Function context analysis, contract structure

## ⚠️ Note About Command Execution

The current setup doesn't include a bash/command execution MCP server. To run tools like:
- `slither`
- `forge test`
- `mythril`

You would need to either:
1. Add a bash MCP server (like `mcp-server-bash` from the MCP servers collection)
2. Or manually run these commands and have the agent analyze the output files

## 🔧 Customizing the Setup

### To add more directories to filesystem access:

Edit `~/.config/ollmcp/mcp-servers/web3-audit.json` and add more paths:
```json
"args": [
  "--directory",
  "/home/dok/MCP/mcp-filesystem",
  "run",
  "run_server.py",
  "/home/dok",
  "/path/to/your/projects",
  "/another/path"
]
```

### To test the setup:

1. Clone a test repo:
```bash
git clone https://github.com/example/web3-project.git /tmp/test-audit
```

2. Run audit:
```
> agent
> 3
> my-web3-auditor
> Analyze the contracts in /tmp/test-audit/src for security vulnerabilities
```

## 🎯 Next Steps

1. Test with a small project first
2. Verify the agent can read files
3. Test Solidity analysis
4. Consider adding a bash MCP server for command execution
5. Fine-tune the agent's system prompt for your specific needs
