# Deep Security Audit Workflow Guide

## Overview

This guide describes the complete workflow for deep security auditing that goes beyond tool execution to find logic-based vulnerabilities.

## The Complete Workflow

### Phase 1: Tool Execution and Initial Analysis

**Objective**: Run automated tools and collect initial findings

**Steps**:
1. Execute all available static analyzers:
   - Slither: `run_security_tool({"tool_name": "slither", "arguments": "."})`
   - Mythril: `run_security_tool({"tool_name": "mythril", "arguments": "analyze Contract.sol"})`
   - Securify2: `run_security_tool({"tool_name": "securify2", "arguments": "Contract.sol"})`

2. Run fuzzing tools:
   - Echidna: `run_security_tool({"tool_name": "echidna", "arguments": "test Contract.sol"})`
   - Medusa: `run_security_tool({"tool_name": "medusa", "arguments": "..."})`

3. Run Foundry tests:
   - `execute_command({"command": "forge test -vvv"})`

4. Run AI-powered analysis:
   - web3-scanner for intent detection and embeddings

**Output**: Raw findings from all tools

### Phase 2: False Positive Filtering ⚠️ CRITICAL

**Objective**: Filter out findings that cannot be exploited in practice

**Process**:
For each tool finding, ask:

1. **Can this be exploited?**
   - Is there a realistic attack path?
   - What are the preconditions?
   - Can an attacker meet these conditions?

2. **Economic Feasibility**
   - Is the attack profitable?
   - What are the gas costs?
   - What's the expected return?

3. **Practical Constraints**
   - Does this require unrealistic assumptions?
   - Can this happen in a single transaction?
   - Are there mitigations already in place?

4. **Impact Assessment**
   - What's the maximum damage?
   - How many users are affected?
   - Is this a real vulnerability or just a warning?

**Decision**: Accept only findings with proven exploitability and significant impact.

**Example Task**:
```
Review all Slither findings for Contract.sol:
1. For each finding, determine if it can be exploited
2. Model the attack scenario
3. Calculate potential impact
4. Filter out false positives
5. Provide filtered list with reasoning
```

### Phase 3: Deep Business Logic Analysis 🔍

**Objective**: Find vulnerabilities that require logic reasoning, not pattern matching

**Key Areas**:

#### 3.1 Value Flow Analysis
- Map where value enters the protocol
- Track where value exits
- Identify all value transformation points
- Find potential value leakage points

**Example Task**:
```
Analyze value flows in Vault.sol:
1. Map all deposit/withdrawal paths
2. Identify all fee calculations
3. Find all value transfer points
4. Check for value leakage or manipulation
```

#### 3.2 Invariant Analysis
- Identify protocol invariants
- Check if invariants can be violated
- Test invariant preservation across operations
- Find edge cases where invariants break

**Example Task**:
```
Identify and verify invariants in LendingProtocol.sol:
1. List all invariants that should hold
2. Test if they can be violated
3. Find attack scenarios that break invariants
4. Verify invariant preservation in edge cases
```

#### 3.3 Economic Modeling
- Model economic incentives
- Calculate profit margins for attacks
- Analyze flash loan attack vectors
- Consider MEV extraction opportunities

**Example Task**:
```
Model economic attack vectors for Oracle.sol:
1. Calculate flash loan attack profitability
2. Model oracle manipulation scenarios
3. Analyze economic incentives for attacks
4. Find profitable attack paths
```

#### 3.4 Composability Analysis
- Identify cross-protocol interactions
- Analyze state changes across protocols
- Find composability exploits
- Check for unintended interactions

**Example Task**:
```
Analyze composability risks for ProtocolA.sol:
1. Identify all external protocol calls
2. Model cross-protocol state changes
3. Find composability exploit vectors
4. Test interaction with Uniswap, Aave, etc.
```

#### 3.5 Timing and MEV Analysis
- Identify timing dependencies
- Analyze MEV extraction opportunities
- Check for front-running vulnerabilities
- Test block timestamp dependencies

**Example Task**:
```
Analyze timing and MEV risks in Auction.sol:
1. Identify timing dependencies
2. Analyze MEV extraction opportunities
3. Check for front-running vulnerabilities
4. Test block timestamp manipulation
```

### Phase 4: Hypothesis Generation and Testing 💡

**Objective**: Generate hypotheses about potential vulnerabilities and test them

**Process**:

1. **Generate Hypotheses**:
   - What could go wrong economically?
   - Where are value flows vulnerable?
   - What invariants could be violated?
   - How could composability be exploited?

2. **Construct Attack Scenarios**:
   - Detailed step-by-step attack
   - Transaction sequence
   - State changes
   - Expected outcomes

3. **Test Hypotheses**:
   - Can preconditions be met?
   - Is the attack path realistic?
   - Calculate profitability
   - Look for counter-evidence

4. **Validate or Reject**:
   - Only report if exploitation is proven
   - Provide proof of concept
   - Calculate impact

**Example Task**:
```
Generate and test hypotheses for SwapProtocol.sol:
1. Generate 5 hypotheses about potential vulnerabilities
2. For each hypothesis, construct a detailed attack scenario
3. Test if each attack is feasible
4. Calculate impact for feasible attacks
5. Report only proven vulnerabilities
```

### Phase 5: Comprehensive Report Generation 📊

**Objective**: Create a professional audit report with only validated findings

**Report Structure**:

1. **Executive Summary**
   - Scope of review
   - Summary of findings
   - Risk assessment

2. **Methodology**
   - Tools used
   - Analysis approach
   - False positive filtering process

3. **Findings** (Only validated vulnerabilities)
   - Organized by severity
   - Each finding includes:
     - Title
     - Severity
     - Description
     - Attack Vector
     - Proof of Concept
     - Impact
     - Recommendation

4. **Business Logic Analysis**
   - Value flow analysis
   - Invariant violations
   - Economic attack vectors
   - Composability risks

5. **Recommendations**
   - Prioritized fixes
   - Code examples
   - Best practices

**Example Task**:
```
Generate comprehensive audit report:
1. Filter all findings (remove false positives)
2. Organize by severity
3. Include business logic analysis
4. Provide detailed recommendations
5. Format as professional markdown report
```

## Example Complete Audit Workflow

```yaml
Task: Perform deep security audit of /path/to/protocol:

Phase 1: Tool Execution
1. Run Slither analysis
2. Run Mythril analysis
3. Run Securify2 analysis
4. Run Echidna fuzzing
5. Run Foundry tests
6. Run web3-scanner for intent detection

Phase 2: False Positive Filtering
1. Review all tool findings
2. For each finding, determine exploitability
3. Model attack scenarios
4. Calculate impact
5. Filter out false positives
6. Document filtering decisions

Phase 3: Deep Business Logic Analysis
1. Map value flows in all contracts
2. Identify and verify invariants
3. Model economic attack vectors
4. Analyze cross-protocol composability
5. Check timing and MEV risks

Phase 4: Hypothesis Testing
1. Generate hypotheses about potential vulnerabilities
2. Construct detailed attack scenarios
3. Test each hypothesis
4. Validate or reject hypotheses
5. Calculate impact for validated vulnerabilities

Phase 5: Report Generation
1. Compile all validated findings
2. Organize by severity
3. Include business logic analysis
4. Provide detailed recommendations
5. Generate professional audit report
```

## Key Principles

1. **Tools are assistants, not authorities**: Always verify tool findings
2. **Exploitability is required**: Only report vulnerabilities that can be exploited
3. **Impact matters**: Focus on findings with significant impact
4. **Think like an attacker**: Model economic incentives and attack vectors
5. **Deep reasoning**: Use logic to find vulnerabilities tools miss
6. **Validate everything**: Test hypotheses before reporting

## Advanced Analysis Techniques

### Flash Loan Attack Modeling
- Identify all price-dependent operations
- Check if prices can be manipulated
- Model flash loan attack sequences
- Calculate profitability

### Governance Attack Modeling
- Analyze voting mechanisms
- Check for flash loan vote manipulation
- Test delegate timing attacks
- Model bribe economics

### Oracle Manipulation Analysis
- Check oracle sources
- Analyze TWAP vulnerabilities
- Test price manipulation vectors
- Verify oracle fallback mechanisms

### Composability Exploit Finding
- Map all external calls
- Model cross-protocol state changes
- Test interaction sequences
- Find exploit chains

Remember: The goal is to find vulnerabilities that require deep logic reasoning, not just pattern matching. Automated tools are your starting point, but your reasoning is what finds real vulnerabilities.
