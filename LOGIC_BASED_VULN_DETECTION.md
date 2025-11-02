# Logic-Based Vulnerability Detection Guide

## The Real Work: Finding Vulnerabilities Tools Miss

Automated tools like Slither, Mythril, and Securify2 find **pattern-based vulnerabilities**. They're great at finding:
- Reentrancy (sometimes)
- Access control issues
- Common bugs

But they **miss** vulnerabilities that require:
- **Economic modeling**
- **Multi-transaction reasoning**
- **Cross-protocol composability analysis**
- **Business logic understanding**

## The Complete Workflow

### Step 1: Run Tools (Starting Point)
```bash
# Run all tools
slither .
mythril analyze Contract.sol
securify2 Contract.sol
echidna-test Contract.sol
forge test -vvv
```

### Step 2: Filter False Positives (CRITICAL)
Most tool findings are false positives. For each finding, ask:

1. **Can this actually be exploited?**
   - What's the attack path?
   - What are the preconditions?
   - Can an attacker meet these conditions?

2. **Is it profitable?**
   - What are the gas costs?
   - What's the expected return?
   - Is there economic incentive?

3. **Is it realistic?**
   - Does it require unrealistic assumptions?
   - Can this happen in practice?
   - Are there mitigations?

**Example**:
```
Tool Finding: "Potential reentrancy in withdraw()"
Analysis:
- Can this be exploited? NO
- Why? Requires attacker to control the token contract
- Is that realistic? NO, token is standard ERC-20
- Decision: FALSE POSITIVE - REJECT
```

### Step 3: Deep Logic Analysis

This is where real vulnerabilities are found. Analyze:

#### 3.1 Value Flow Analysis
Map where value enters and exits:
- Deposits
- Withdrawals
- Fees
- Rewards
- Transfers

**Ask**: Can value be extracted unexpectedly?

#### 3.2 Invariant Analysis
What should always be true?
- Total supply = sum of balances
- Total deposits = total shares
- Collateral >= debt

**Ask**: Can invariants be violated?

#### 3.3 Economic Modeling
Model economic incentives:
- Flash loan attacks
- Oracle manipulation
- Price manipulation
- MEV extraction

**Ask**: What's profitable for an attacker?

#### 3.4 Composability Analysis
How does this interact with other protocols?
- External calls
- State changes
- Cross-protocol exploits

**Ask**: Can composability be exploited?

### Step 4: Hypothesis Generation

Generate hypotheses about potential vulnerabilities:

**Example Hypotheses**:
1. "Flash loan could manipulate oracle price in single transaction"
2. "Vault share price could be inflated by donating assets"
3. "Governance vote could be manipulated via flash borrowing"
4. "Cross-protocol interaction could drain protocol"

### Step 5: Hypothesis Testing

For each hypothesis:
1. **Construct attack scenario**: Detailed step-by-step
2. **Test assumptions**: Can preconditions be met?
3. **Calculate profitability**: Is attack profitable?
4. **Look for counter-evidence**: What prevents it?
5. **Validate or reject**: Only report if exploitation is proven

## Vulnerability Categories Requiring Logic

### 1. Flash Loan-Driven Oracle Manipulation
**Why tools miss**: Can't model economic incentives or single-tx price swings

**How to find**:
- Find all oracle price sources
- Check if prices can be manipulated in single tx
- Model flash loan attack sequence
- Calculate profitability

**Example**: Mango Markets $100M exploit

### 2. Governance Vote Manipulation
**Why tools miss**: Can't simulate transient token balances

**How to find**:
- Check voting power calculation
- Test if tokens can be flash borrowed
- Analyze snapshot timing
- Model vote manipulation attack

**Example**: Beanstalk Farms $182M attack

### 3. Vault Share Inflation
**Why tools miss**: Don't reason about PPS dilution

**How to find**:
- Check share price calculation
- Test if assets can be donated
- Model PPS manipulation
- Calculate share inflation impact

**Example**: Yearn Finance clones

### 4. Cross-Protocol Composability
**Why tools miss**: Can't model cross-protocol state changes

**How to find**:
- Map all external calls
- Model state changes across protocols
- Test interaction sequences
- Find exploit chains

**Example**: Ronin Bridge $625M hack

### 5. MEV and Timing Attacks
**Why tools miss**: Can't simulate tx ordering

**How to find**:
- Identify timing dependencies
- Analyze MEV extraction opportunities
- Check for front-running vulnerabilities
- Test block timestamp dependencies

## Example Deep Analysis Task

```
Task: Analyze Vault.sol for logic-based vulnerabilities:

1. Tool Execution:
   - Run Slither, Mythril, Securify2
   - Run Echidna fuzzing
   - Run Foundry tests

2. False Positive Filtering:
   - Review all tool findings
   - Filter false positives
   - Keep only exploitable findings

3. Value Flow Analysis:
   - Map all deposit/withdrawal paths
   - Identify fee calculations
   - Find value transfer points
   - Check for value leakage

4. Invariant Analysis:
   - Identify invariants (totalSupply = sum of balances)
   - Test if invariants can be violated
   - Find attack scenarios

5. Economic Modeling:
   - Model flash loan attacks
   - Analyze oracle manipulation
   - Calculate attack profitability

6. Composability Analysis:
   - Map external protocol calls
   - Model cross-protocol interactions
   - Find composability exploits

7. Hypothesis Generation:
   - Generate 5 hypotheses
   - Test each hypothesis
   - Validate or reject

8. Report:
   - Compile validated findings
   - Include business logic analysis
   - Provide recommendations
```

## Key Principles

1. **Tools are starting point, not endpoint**
2. **Filter false positives aggressively**
3. **Think like an attacker**
4. **Model economic incentives**
5. **Validate everything**
6. **Only report exploitability-proven vulnerabilities**

## The Real Work

The real work happens **after** running tools:
- False positive filtering
- Deep business logic analysis
- Economic modeling
- Hypothesis generation and testing
- Finding vulnerabilities that require logic

Remember: **User fund loss is the only way to define real vulnerabilities**. If it can't cause user fund loss, it's not a real vulnerability.
