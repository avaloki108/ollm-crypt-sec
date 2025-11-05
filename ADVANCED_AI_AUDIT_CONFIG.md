# Advanced AI-Powered Audit Configuration

## Confidence Scoring and Auto-Approval Logic

### Confidence Calculation

Confidence scores combine multiple signals:

```
Confidence = (
  AI_Intent_Score * 0.4 +
  Embedding_Similarity * 0.3 +
  Static_Analyzer_Confirmation * 0.2 +
  Business_Logic_Validation * 0.1
)
```

### Decision Rules

**Auto-Validate (High Confidence >0.9)**:
- AI intent >0.9 AND static analyzer confirms AND exploitability proven
- Embedding similarity >0.85 AND intent >0.8 AND static confirms
- **Action**: Include in report, skip manual review

**Human Review Required (Medium Confidence 0.7-0.9)**:
- AI flags (intent >0.8) OR static flags OR embedding similarity >0.85
- Mixed signals (AI flags but static doesn't, or vice versa)
- **Action**: Escalate to manual review

**Auto-Reject (Low Confidence <0.7)**:
- Only one source flags AND similarity <0.75
- AI intent <0.5 AND static analyzers clean AND embedding similarity <0.75
- **Action**: Auto-approve as safe, unless manual override

## Bidirectional Cross-Referencing

### AI → Static Flow
1. AI flags contract with high intent score (>0.8)
2. Run targeted static analysis on that contract
3. If static confirms → High confidence finding
4. If static doesn't confirm → Medium confidence, requires review

### Static → AI Flow
1. Static analyzer flags vulnerability
2. Re-run SmartIntentNN on that specific contract/function
3. Check embedding similarity to known exploits
4. If AI confirms → High confidence finding
5. If AI doesn't confirm → Medium confidence, still investigate (static may find AI misses)

## Fallback Logic

### Service Failure Handling

**If SmartBERT/web3-sekit services unavailable**:
1. Attempt to start services (3 retries with 5s delay)
2. If still unavailable:
   - Log: "AI services unavailable, proceeding with static-only mode"
   - Continue with: Slither, Mythril, Securify2, Echidna
   - Note in report: "AI-powered analysis skipped due to service unavailability"
   - Flag report section: "Limited to static analysis only"

**If Partial Service Availability**:
- SmartBERT available but web3-sekit down: Use embeddings only
- web3-sekit available but SmartBERT down: Use intent detection only
- Log which services are available

## Parallel Execution Options

### Conditional Flows

**Option 1: AI-First (Current)**:
- AI analysis → Prioritize → Static on flagged contracts → Deep analysis

**Option 2: Parallel Execution**:
- Run AI and static analyzers simultaneously
- Compare results → Prioritize contracts flagged by both
- Deep analysis on high-confidence intersections

**Option 3: Static-First (Fallback)**:
- If AI services unavailable
- Run static analyzers → Flag contracts → Manual deep analysis

## Embedding Similarity Thresholds

### Cosine Similarity Interpretation

- **>0.85**: Strong match to known vulnerability
  - Action: Investigate immediately
  - Confidence: High
  - Reference: Link to similar CVE/exploit

- **0.75-0.85**: Moderate match
  - Action: Review with static analyzers
  - Confidence: Medium
  - Cross-reference: Run Slither/Mythril

- **0.65-0.75**: Weak match
  - Action: Optional review
  - Confidence: Low
  - Filter: Auto-reject if static also clean

- **<0.65**: No significant match
  - Action: Auto-approve if static clean
  - Confidence: Very low
  - Note: May be novel pattern (could be good or bad)

## Intent Score Tiers

### Critical Tier (>0.9)
- **Action**: Immediate halt, investigate before proceeding
- **Examples**: Fee manipulation >0.9, Honeypot any detection
- **Report**: Critical severity, stop audit until resolved

### High Risk Tier (0.8-0.9)
- **Action**: Investigate immediately
- **Examples**: Fee manipulation 0.8-0.9, Mint >0.8
- **Report**: High severity, prioritize in audit

### Medium Risk Tier (0.7-0.8)
- **Action**: Queue for static analysis
- **Examples**: Mint 0.7-0.8, Fee 0.7-0.8
- **Report**: Medium severity, validate with static tools

### Low Risk Tier (0.5-0.7)
- **Action**: Optional review
- **Examples**: Various intents 0.5-0.7
- **Report**: Low severity, review if time permits

### Very Low Tier (<0.5)
- **Action**: Auto-approve if static clean
- **Examples**: Low intent scores across all types
- **Report**: Info severity, likely safe

## Report Generation with Structured Sections

Generate markdown reports with:

1. **Executive Summary** - High-level overview
2. **AI Flags Section** - All AI findings with scores
3. **Static Corroboration** - Tool findings matching/validating AI
4. **Validated Risks** - Only proven vulnerabilities
5. **False Positives Filtered** - What was rejected and why
6. **Business Logic Analysis** - Deep reasoning on high-priority contracts
7. **Recommendations** - Prioritized fixes

Each section should include:
- Clear headings
- Score thresholds and interpretations
- Cross-references between AI and static findings
- Confidence scores
- Exploitability proofs


