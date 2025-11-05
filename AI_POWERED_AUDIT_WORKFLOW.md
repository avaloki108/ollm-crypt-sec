# AI-Powered Audit Workflow (SmartBERT + SmartIntentNN)

## Why Start with AI-Powered Analysis?

SmartBERT and SmartIntentNN are **uniquely powerful** for finding vulnerabilities because they:
- **Detect malicious intents** that static analyzers miss (fee manipulation, honeypots, etc.)
- **Find similar vulnerable patterns** using semantic embeddings
- **Prioritize contracts** that need deep manual review
- **Identify economic attack vectors** through intent detection

## Complete AI-First Workflow

### Step 1: Start AI Services (REQUIRED FIRST STEP)

```bash
# Check if services are running
check_web3se_status

# If not running, start them
start_web3se_services (background=true)
```

Services needed:
- **SmartBERT API**: Port 9900 (generates embeddings)
- **web3-sekit API**: Port 8081 (intent detection + orchestration)

### Step 2: Run web3-scanner (AI-Powered Analysis)

```bash
web3_scanner_scan({
  "repository_path": "/path/to/repo",
  "with_intent": true,      # Enable SmartIntentNN
  "with_embed": true,       # Enable SmartBERT embeddings
  "output_file": "scan-results.json"
})
```

**What this generates**:
- **SmartBERT embeddings** (768-dim vectors) for each contract
  - Use to find similar vulnerable patterns
  - Compare against known exploit patterns
  - Identify outliers and unusual structures
  
- **SmartIntentNN intent scores** for each contract:
  - `fee`: Arbitrary fee changes (score >0.8 = suspicious)
  - `honeypot`: Honeypot scams (any detection = investigate)
  - `mint`: Unauthorized minting (score >0.7 = suspicious)
  - `disableTrading`: Trading restrictions
  - `blacklist`: User blacklisting
  - `reflect`: Tax redistribution
  - And more...

- **Code tree structure** showing contract organization

### Step 3: Analyze AI Findings

#### 3.1 Prioritize by Intent Scores

**High Risk (Score >0.8)** - Investigate immediately:
- Fee manipulation >0.8: Check for arbitrary fee changes
- Honeypot any detection: Look for fund trapping
- Mint >0.7: Check for unauthorized minting

**Medium Risk (0.5-0.8)** - Review with business logic:
- Cross-reference with static analyzers
- Apply deep reasoning analysis
- Model economic attack vectors

**Low Risk (<0.5)** - May be false positives:
- Verify manually
- Check against known patterns

#### 3.2 Use Embeddings for Pattern Matching

- **Compare embeddings** with known vulnerable contracts
- **Find similar code structures** that may have similar vulnerabilities
- **Identify outliers** - contracts with unusual patterns
- **Cross-reference** with intent detection scores

#### 3.3 Create Prioritized Review List

Based on AI findings:
1. Contracts with high intent scores (>0.8)
2. Contracts with unusual embeddings (outliers)
3. Contracts matching known vulnerable patterns
4. Contracts flagged by both AI and static analyzers

### Step 4: Deep Analysis on AI-Flagged Contracts

For each high-priority contract:

1. **Read the contract code**
2. **Verify intent detection**: Why did SmartIntentNN flag this?
3. **Check embedding similarities**: What vulnerable patterns match?
4. **Apply business logic analysis**: Model economic attack vectors
5. **Cross-reference with static analyzers**: Do Slither/Mythril agree?
6. **Generate hypotheses**: What could go wrong?
7. **Test hypotheses**: Construct attack scenarios

### Step 5: Combine with Static Analysis

Run static analyzers on AI-flagged contracts:
- Slither on high-intent-score contracts
- Mythril on unusual embedding matches
- Securify2 on contracts matching vulnerable patterns

**Cross-reference findings**:
- AI says "high fee manipulation intent" → Slither finds fee manipulation code?
- Embeddings match known exploit → Static analyzer confirms vulnerability?
- Both AI and tools agree → High confidence finding

## Example Complete Workflow

```
Task: Audit repository at /path/to/repo

1. AI-Powered Analysis (START HERE):
   - Check web3se-lab services status
   - Start services if needed
   - Run web3-scanner with intent and embeddings
   - Analyze intent scores and embeddings
   - Create prioritized review list

2. Deep Analysis on AI-Flagged Contracts:
   - Read contracts with high intent scores (>0.8)
   - Verify AI findings with code review
   - Check embedding similarities
   - Apply business logic analysis

3. Static Analysis on Priority Contracts:
   - Run Slither on high-intent contracts
   - Run Mythril on unusual embedding matches
   - Cross-reference AI and tool findings

4. False Positive Filtering:
   - Filter AI findings (verify exploitability)
   - Filter tool findings (verify exploitability)
   - Combine validated findings

5. Report Generation:
   - Include AI findings with scores
   - Include embedding similarities
   - Include validated tool findings
   - Provide comprehensive audit report
```

## Key Points

1. **AI Analysis is FIRST**, not optional
2. **Intent scores prioritize** what to review
3. **Embeddings find patterns** humans might miss
4. **Cross-reference AI and tools** for validation
5. **Deep reasoning validates** AI findings

Remember: SmartBERT and SmartIntentNN are powerful tools, but they require human reasoning to validate and exploit their findings.
