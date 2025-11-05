# Audit Engine Usage Guide

This document explains how to use the new code-level audit engine features that implement the mathematical calculations, parallel execution, and report generation.

## Quick Start

### 1. Build Vulnerability Database

First, build the vulnerability embedding database:

```bash
# Make sure SmartBERT is running at http://localhost:9900
python scripts/build_vuln_db.py

# Or with custom settings
python scripts/build_vuln_db.py --url http://localhost:9900/embed --output ~/.config/ollmcp/vuln_db.json
```

This creates a database of known vulnerability patterns that will be used for similarity matching during audits.

### 2. Configure Audit Options

Edit `config/audit_options.yaml` to enable/disable features:

```yaml
enable_visualisation: true  # Generate t-SNE plots
parallel_static: true       # Run tools in parallel
similarity_threshold: 0.85  # Embedding similarity threshold
```

### 3. Use in Audit Agent

The audit engine is automatically integrated into `Web3AuditAgent`. Just use the agent methods:

```python
# Process scan results with embedding matches
agent.process_scan_results("scan-results.json")

# Run static analysis in parallel
results = await agent.run_static_analysis_parallel(["/path/to/contract1.sol", "/path/to/contract2.sol"])

# Finalize findings with confidence scores
finalized = agent.finalize_findings_with_confidence()

# Generate report with template
report_path = await agent.generate_audit_report(
    repository_path="/path/to/repo",
    output_path="audit_report.md",
    include_viz=True
)
```

## Features Implemented

### ✅ Cosine Similarity Calculation

**Location**: `audit_engine.py::embedding_matches()`

Real vector math using sklearn's cosine similarity:

```python
from mcp_client_for_ollama.agents.audit_engine import AuditEngine

engine = AuditEngine()
matches = engine.embedding_matches(contract_embedding, threshold=0.85)
# Returns: [{"vulnerability": "reentrancy", "similarity": 0.92}, ...]
```

### ✅ Vulnerability Database

**Location**: `audit_engine.py::build_vuln_db()`

Pre-computed embeddings for known bad patterns. Populate once:

```bash
python scripts/build_vuln_db.py
```

Database stored at: `~/.config/ollmcp/vuln_db.json`

### ✅ Confidence Score Calculation

**Location**: `audit_engine.py::compute_confidence()`

Weighted formula:
```
Confidence = AI_Intent * 0.4 + Embedding_Sim * 0.3 + Static * 0.2 + Biz * 0.1
```

Used automatically in `finalize_findings()`.

### ✅ Auto-Approve/Reject Logic

**Location**: `audit_engine.py::finalize_findings()`

Rules:
- `confidence > 0.9` → `status: "validated"` (auto-approve)
- `confidence < 0.7 AND similarity < 0.75` → `status: "rejected"` (auto-reject)
- Else → `status: "needs_review"`

### ✅ Parallel Static Tool Execution

**Location**: `audit_engine.py::run_static_parallel()`

Runs Slither, Mythril, Securify2 simultaneously:

```python
results = engine.run_static_parallel(
    ["contract1.sol", "contract2.sol"],
    tools=["slither", "mythril"],
    max_workers=4
)
```

### ✅ t-SNE Visualization

**Location**: `audit_engine.py::generate_tsne_plot()`

Generates 2D embedding visualization:

```python
plot_path = engine.generate_tsne_plot(embeddings_dict, "tsne.png")
```

### ✅ Jinja2 Report Template

**Location**: `agents/templates/audit_report.md.j2`

Structured markdown report with:
- Executive summary
- AI flags section with scores
- Static corroboration
- Validated risks
- False positives filtered
- Business logic analysis
- Recommendations

## Integration with Existing Workflow

The audit engine integrates seamlessly with the existing AI-first workflow:

### Before (LLM-only)
```
1. LLM reads scan-results.json
2. LLM describes "similarity > 0.85"
3. LLM writes free-form markdown report
```

### After (Code + LLM)
```
1. Code processes scan-results.json
2. Code calculates actual cosine similarities
3. Code computes confidence scores
4. Code auto-approves/rejects findings
5. Jinja2 template generates structured report
6. LLM focuses on deep analysis
```

## Configuration Options

All options in `config/audit_options.yaml`:

| Option | Default | Description |
|-------|--------|-------------|
| `enable_visualisation` | `false` | Generate t-SNE plots |
| `parallel_static` | `true` | Parallel tool execution |
| `similarity_threshold` | `0.85` | Embedding match threshold |
| `confidence_auto_approve` | `0.9` | Auto-approve threshold |
| `confidence_auto_reject` | `0.7` | Auto-reject threshold |

## Example Complete Workflow

```python
# 1. Create audit agent
agent = Web3AuditAgent(name="my-auditor", model="qwen2.5:7b")

# 2. Run comprehensive audit (calls all engine functions)
results = await agent.run_comprehensive_audit(
    repository_path="/path/to/repo",
    config={
        "enable_visualisation": True,
        "parallel_static": True,
        "similarity_threshold": 0.85
    }
)

# 3. Generate final report
report_path = await agent.generate_audit_report(
    repository_path="/path/to/repo",
    output_path="final_audit_report.md"
)
```

## What's Still LLM-Driven vs Code-Driven

### Code-Driven (Implemented)
- ✅ Cosine similarity calculation
- ✅ Confidence score computation
- ✅ Auto-approve/reject decisions
- ✅ Parallel tool execution
- ✅ Report template rendering
- ✅ Visualization generation

### LLM-Driven (Still in Prompts)
- Business logic analysis (deep reasoning)
- Attack vector construction
- Economic modeling
- Invariant identification
- Hypothesis generation

The code handles the **mathematical computations and structure**, while the LLM handles the **reasoning and analysis**.

## Dependencies

Required packages (add to requirements if needed):
```python
scikit-learn  # For cosine similarity and t-SNE
numpy         # For vector operations
jinja2        # For report templating
matplotlib    # For visualization
requests      # For building vuln DB
```

## Troubleshooting

### "No vulnerability embeddings found"
- Run `python scripts/build_vuln_db.py` first
- Ensure SmartBERT is running at configured URL

### "Jinja2 template not found"
- Ensure `agents/templates/audit_report.md.j2` exists
- Check template directory path

### "Visualization failed"
- Ensure matplotlib and sklearn are installed
- Check that embeddings_dict is not empty

### "Parallel execution slow"
- Reduce `max_workers` in config
- Some tools (Mythril) are CPU-intensive

## Next Steps

Future enhancements (from original spec):
- [ ] ML-based false positive filter (train on past audits)
- [ ] Chain watcher agent for on-chain monitoring
- [ ] Policy-as-code logging with provenance
- [ ] Pub-sub broker for agent communication
- [ ] Circuit breakers for flaky MCP servers

