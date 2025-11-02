# Complete Web3 Audit Setup Guide

## ✅ What's Configured

### 1. MCP Servers Configuration (`~/.config/ollmcp/mcp-servers/web3-audit.json`)

**Filesystem Server** (`mcp-filesystem`):
- ✅ Read files
- ✅ Write files  
- ✅ Edit files (`edit_file`, `edit_file_at_line`)
- ✅ List directories
- ✅ Search files
- ✅ Multiple file operations
- **Accessible directories**: `/home/dok`, `/home/dok/tools`

**Solidity Analysis Server** (`analyze-solidity`):
- ✅ Analyze Solidity function contexts
- ✅ Extract contract structure

**Bash Command Server** (`bash-server`):
- ✅ Execute shell commands
- ✅ Run tools from `~/tools` (slither, mythril, echidna, foundry, etc.)
- ✅ Check tool availability
- ✅ Automatic PATH setup with `~/tools` included

### 2. Agent Configuration (`config/agents/web3_auditor_local.yaml`)

Pre-configured Web3 audit agent ready to use with all tools enabled.

## 🚀 Quick Start

### Step 1: Start ollmcp

```bash
cd /home/dok/tools/ollm-crypt-sec
ollmcp --servers-json ~/.config/ollmcp/mcp-servers/web3-audit.json
```

### Step 2: Create Audit Agent

In the ollmcp interface:
```
> agent
> 1 (Create a new agent)
> web3_audit
> my-auditor
> qwen2.5:7b
> yes (connect to servers)
> 1 (use same servers)
```

OR load from config:
```
> agent
> 4 (Load agent from config file)
> config/agents/web3_auditor_local.yaml
```

### Step 3: Audit a Repository

```
> agent
> 3 (Execute task with agent)
> my-auditor
```

**Example audit tasks:**

```
Perform a comprehensive security audit of the Solidity project at /path/to/repo:
1. Read all contracts in src/
2. Run Slither analysis: slither .
3. Run Foundry tests: forge test -vvv
4. Check for common vulnerabilities (reentrancy, overflow, access control)
5. Generate a detailed report with findings classified by severity (Critical, High, Medium, Low)
```

```
Analyze the contract at /path/to/Contract.sol:
- Read the contract file
- Run slither analysis
- Check for specific vulnerabilities
- Suggest fixes
```

```
Audit all contracts in /path/to/project/src:
1. List all .sol files
2. Analyze each contract
3. Run forge test if available
4. Run slither on the entire project
5. Generate comprehensive audit report
```

## 📋 Available Tools

### Filesystem Operations
- `mcp-filesystem.read_file` - Read file contents
- `mcp-filesystem.read_multiple_files` - Read multiple files at once
- `mcp-filesystem.write_file` - Write/create files
- `mcp-filesystem.edit_file` - Edit files (search/replace)
- `mcp-filesystem.edit_file_at_line` - Edit specific lines
- `mcp-filesystem.list_directory` - List directory contents
- `mcp-filesystem.search_files` - Search for files

### Command Execution
- `bash-server.execute_command` - Execute shell commands
  - Examples:
    - `slither .` - Run Slither static analysis
    - `forge test -vvv` - Run Foundry tests
    - `mythril analyze Contract.sol` - Run Mythril
    - `cd ~/tools/slither && python3 -m slither .` - Run tools from ~/tools
- `bash-server.check_tool_available` - Check if a tool exists

### Solidity Analysis
- `analyze-solidity.analyze_function_context` - Analyze Solidity functions

## 🛠️ Running Tools from ~/tools

The bash server automatically adds `~/tools` to PATH, so you can run tools directly:

**Examples:**
```
slither .
forge test
mythril analyze Contract.sol
```

**If tools are in subdirectories:**
```
cd ~/tools/slither && python3 -m slither .
cd ~/tools/mythril2.0 && myth analyze Contract.sol
```

The agent will automatically discover and use tools from `~/tools`.

## 💡 Usage Examples

### Example 1: Quick Vulnerability Scan

**Task:**
```
Scan the contract at /path/to/Contract.sol for common vulnerabilities:
- Reentrancy attacks
- Integer overflow/underflow
- Access control issues
- Unsafe external calls
```

### Example 2: Full Project Audit

**Task:**
```
Perform a comprehensive security audit of the project at /path/to/project:
1. Read all contracts in src/
2. Run Slither: slither .
3. Run Foundry tests: forge test -vvv
4. Check test coverage: forge coverage
5. Identify vulnerabilities by severity
6. Generate detailed audit report
```

### Example 3: Fix Suggestions

**Task:**
```
Review the contract at /path/to/Contract.sol:
1. Analyze for vulnerabilities
2. For each vulnerability found, suggest a fix
3. Show code examples of the fixes
```

## 🔧 Customization

### Add More Directories to Filesystem Access

Edit `~/.config/ollmcp/mcp-servers/web3-audit.json`:

```json
"args": [
  "--directory",
  "/home/dok/MCP/mcp-filesystem",
  "run",
  "run_server.py",
  "/home/dok",
  "/home/dok/tools",
  "/path/to/your/projects",
  "/another/directory"
]
```

### Change Agent Model

Edit `config/agents/web3_auditor_local.yaml`:

```yaml
model: qwen2.5:7b  # Change to your preferred model
# Options: qwen2.5:7b, llama3.2:3b, deepseek-r1:32b, etc.
```

### Customize System Prompt

Edit `config/agents/web3_auditor_local.yaml`:

```yaml
system_prompt: |
  Your custom system prompt here...
  Focus on specific vulnerability types or analysis approaches
```

## ⚠️ Security Notes

1. **Command Execution**: The bash server can execute ANY command. Use Human-in-the-Loop (HIL) mode to review commands before execution.

2. **File Access**: Filesystem server only allows access to specified directories (`/home/dok`, `/home/dok/tools`).

3. **Tool Execution**: Tools from `~/tools` are automatically available via PATH.

## 🎯 Next Steps

1. **Test the Setup**:
   ```bash
   # Clone a test repo
   git clone https://github.com/example/web3-project.git /tmp/test-audit
   
   # Start ollmcp
   ollmcp --servers-json ~/.config/ollmcp/mcp-servers/web3-audit.json
   
   # Create agent and audit
   ```

2. **Enable HIL for Safety**:
   ```
   > human-in-loop
   > hil
   ```
   This will prompt you before executing commands.

3. **Fine-tune Agent Prompts**: Customize the system prompt for your specific audit needs.

## 📚 Additional Resources

- [Web3 Audit Quickstart](docs/WEB3_AUDIT_QUICKSTART.md)
- [Multi-Agent System Guide](docs/MULTI_AGENT_SYSTEM.md)
- [Agent Configuration](config/agents/README.md)

## 🐛 Troubleshooting

### Issue: Commands not executing
- Check that the bash server is running
- Verify PATH includes `~/tools`
- Check command syntax

### Issue: Files not readable
- Verify directory is in allowed list
- Check file permissions
- Ensure absolute paths are used

### Issue: Tools not found
- Run `bash-server.check_tool_available` tool to check
- Verify tools are in `~/tools` with correct permissions
- Check PATH configuration
