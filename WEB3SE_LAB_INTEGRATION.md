# Web3se-Lab Integration Complete! 🎉

## What's New

### ✅ web3se-lab Tools Added

The bash server now includes integration with `~/tools/web3se-lab`:

1. **`bash-server.web3_scanner_scan`**
   - Scan Web3 repositories for malicious intents and generate embeddings
   - Uses SmartBERT and SmartIntentNN models
   - Example: `web3_scanner_scan({"repository_path": "./my-contracts", "with_intent": true, "with_embed": true})`

2. **`bash-server.check_web3se_status`**
   - Check if SmartBERT API (port 9900) and web3-sekit API (port 8081) are running
   - Verify web3-scanner CLI availability

3. **`bash-server.start_web3se_services`**
   - Instructions for starting web3se-lab services
   - Services run on:
     - SmartBERT API: http://localhost:9900
     - web3-sekit API: http://localhost:8081

### ✅ Updated Configuration

- **MCP Server Config** (`~/.config/ollmcp/mcp-servers/web3-audit.json`):
  - Added `web3se-lab` to PATH
  - Set `SMARTBERT_API` and `WEB3_SEKIT_API` environment variables

- **Agent Config** (`config/agents/web3_auditor_local.yaml`):
  - Added all web3se-lab tools to enabled tools list

## Usage Examples

### Check Service Status

```yaml
Task: Check if web3se-lab services are running
```

### Scan a Repository

```yaml
Task: Scan the repository at /path/to/repo using web3se-lab scanner:
1. Check service status first
2. If services not running, start them
3. Run full scan with intent detection and embeddings
4. Save results to scan-results.json
```

### Complete Audit Workflow

```yaml
Task: Perform comprehensive security audit using all available tools:
1. Use web3-scanner to scan repository for malicious intents
2. Run Slither analysis
3. Run Foundry tests
4. Generate combined audit report
```

## Getting Started

### 1. Start web3se-lab Services

Before using the scanner, start the services:

```bash
cd ~/tools/web3se-lab
./web3-scanner start
```

Or via the agent:
```
> agent
> 3 (Execute task)
> my-auditor
> Start web3se-lab services and check status
```

### 2. Scan a Repository

Use the agent to scan:
```
> agent
> 3 (Execute task)
> my-auditor
> Scan the repository at /path/to/repo using web3se-lab scanner with intent detection and embeddings
```

### 3. Check Status

```
> agent
> 3 (Execute task)
> my-auditor
> Check if web3se-lab services are running
```

## What web3se-lab Provides

- **SmartBERT**: Generates 768-dimensional embeddings for smart contracts
- **SmartIntentNN**: Detects malicious intents:
  - Fee manipulation
  - Trading restrictions
  - User blacklisting
  - Honeypot scams
  - Unauthorized minting
  - And more...

- **Code Tree Extraction**: Parses Solidity contract structure
- **Vulnerability Detection**: (with LLM API configured)

## Integration Benefits

Now your audit agent can:
1. ✅ Use traditional tools (Slither, Mythril, Foundry)
2. ✅ Use AI-powered intent detection (SmartBERT + SmartIntentNN)
3. ✅ Generate embeddings for similarity analysis
4. ✅ Combine results from multiple analysis methods
5. ✅ Generate comprehensive audit reports

## Next Steps

1. **Test the integration**:
   ```bash
   ollmcp --servers-json ~/.config/ollmcp/mcp-servers/web3-audit.json
   ```

2. **Create/load agent**:
   ```
   > agent
   > 4 (Load from config)
   > config/agents/web3_auditor_local.yaml
   ```

3. **Try scanning**:
   ```
   > agent
   > 3 (Execute task)
   > [agent name]
   > Check web3se-lab status
   ```

Happy auditing! 🐛💰
