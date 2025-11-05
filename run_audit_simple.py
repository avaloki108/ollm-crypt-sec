#!/usr/bin/env python3
"""Simplified audit script that works with filesystem tools only."""

import asyncio
import sys
from pathlib import Path
from rich.console import Console

sys.path.insert(0, str(Path(__file__).parent))

from mcp_client_for_ollama.agents.web3_audit import Web3AuditAgent
from mcp_client_for_ollama.agents.audit_trail import AuditTrail
from contextlib import AsyncExitStack
import ollama


async def main():
    """Run audit on specified directory."""
    if len(sys.argv) < 2:
        print("Usage: python run_audit_simple.py <repository_path> [model]")
        sys.exit(1)
    
    repo_path = Path(sys.argv[1]).expanduser().resolve()
    model = sys.argv[2] if len(sys.argv) > 2 else "gpt-oss:20b"
    
    if not repo_path.exists():
        print(f"Error: Repository path does not exist: {repo_path}")
        sys.exit(1)
    
    console = Console()
    console.print(f"[bold green]Starting audit of {repo_path}[/bold green]")
    console.print(f"[cyan]Using model: {model}[/cyan]")
    console.print()
    
    # Initialize components
    exit_stack = AsyncExitStack()
    ollama_client = ollama.AsyncClient()
    audit_trail = AuditTrail()
    
    try:
        # Create audit agent
        agent = Web3AuditAgent(
            name="dexlyn-auditor",
            model=model,
            console=console,
            ollama_client=ollama_client,
            parent_exit_stack=exit_stack
        )
        
        # Try to connect only to filesystem server
        server_config = Path.home() / ".config" / "ollmcp" / "mcp-servers" / "web3-audit.json"
        if server_config.exists():
            try:
                # Read config and connect only to filesystem
                import json
                with open(server_config) as f:
                    config = json.load(f)
                    if "mcpServers" in config and "mcp-filesystem" in config["mcpServers"]:
                        # Create minimal config with just filesystem
                        minimal_config = {
                            "mcpServers": {
                                "mcp-filesystem": config["mcpServers"]["mcp-filesystem"]
                            }
                        }
                        import tempfile
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
                            json.dump(minimal_config, tmp)
                            tmp_path = tmp.name
                        await agent.connect_to_servers(config_path=tmp_path)
                        console.print("[green]✓ Connected to filesystem server[/green]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not connect to MCP servers: {e}[/yellow]")
                console.print("[yellow]Continuing without MCP tools...[/yellow]")
        
        # PHASE 1: AI-Powered Analysis (if tools available)
        console.print("[bold cyan]Phase 1: AI-Powered Analysis[/bold cyan]")
        console.print()
        
        # Try to run web3-scanner if available
        scan_results_path = None
        try:
            console.print("[yellow]Attempting AI-powered scan with SmartBERT/SmartIntentNN...[/yellow]")
            # Check if web3-scanner tools are available
            available_tools = agent.tool_manager.get_enabled_tool_objects()
            has_web3_scanner = any('web3_scanner' in tool.name for tool in available_tools)
            
            if has_web3_scanner:
                console.print("[green]Web3-scanner tools available, running AI-powered scan...[/green]")
                scan_task = f"""Use the web3_scanner_scan tool to scan the repository at {repo_path}.

Run with:
- with_intent: true (enable SmartIntentNN intent detection)
- with_embed: true (enable SmartBERT embeddings)
- output_file: "scan-results.json"

This will generate:
1. SmartBERT embeddings (768-dim vectors) for each contract
2. SmartIntentNN intent scores (fee manipulation, honeypots, etc.)
3. Code tree structure

After scanning, analyze the results to prioritize contracts by:
- High intent scores (>0.8 = high risk)
- Embedding similarity matches (>0.85 = strong match)
"""
                
                scan_result = await agent.execute_task(scan_task)
                scan_results_path = repo_path / "scan-results.json"
                
                if scan_results_path.exists():
                    console.print(f"[green]✓ AI scan complete: {scan_results_path}[/green]")
                    
                    # Process scan results with embedding matching
                    processed = agent.process_scan_results(str(scan_results_path))
                    
                    # Extract prioritized contracts from scan results
                    if processed and "contracts" in processed:
                        prioritized = []
                        for contract in processed.get("contracts", []):
                            # Check intent scores
                            max_intent = 0.0
                            if "intent" in contract:
                                max_intent = max(contract["intent"].values()) if isinstance(contract["intent"], dict) else 0.0
                            
                            # Check embedding similarity
                            max_sim = contract.get("max_embedding_similarity", 0.0)
                            
                            # Prioritize if high intent or high similarity
                            if max_intent > 0.7 or max_sim > 0.75:
                                prioritized.append({
                                    "path": contract.get("path", ""),
                                    "intent_score": max_intent,
                                    "similarity": max_sim,
                                    "priority": "HIGH" if max_intent > 0.8 or max_sim > 0.85 else "MEDIUM"
                                })
                        
                        # Sort by priority
                        prioritized.sort(key=lambda x: (x["intent_score"], x["similarity"]), reverse=True)
                        console.print(f"[cyan]Found {len(prioritized)} high-priority contracts from AI analysis[/cyan]")
                        
                        for p in prioritized[:10]:  # Top 10
                            console.print(f"  - {p['path']}: intent={p['intent_score']:.2f}, similarity={p['similarity']:.2f}")
                        console.print()
                else:
                    console.print("[yellow]Scan completed but results file not found[/yellow]")
            else:
                console.print("[yellow]Web3-scanner tools not available, skipping AI-powered scan[/yellow]")
                console.print("[yellow]Will proceed with traditional analysis[/yellow]")
        except Exception as e:
            console.print(f"[yellow]AI-powered scan not available: {e}[/yellow]")
            console.print("[yellow]Proceeding with traditional contract-by-contract analysis[/yellow]")
        
        console.print()
        
        # PHASE 2: Find contracts for analysis
        contract_files = [f for f in repo_path.rglob("*.sol") 
                         if f.is_file() 
                         and "node_modules" not in str(f) 
                         and "artifacts" not in str(f)
                         and "hardhat" not in str(f).lower()
                         and "test" not in str(f)]
        
        console.print(f"[cyan]Found {len(contract_files)} Solidity contracts[/cyan]")
        console.print()
        
        # PHASE 3: Deep Analysis on Prioritized Contracts
        console.print("[bold cyan]Phase 2: Deep Contract Analysis[/bold cyan]")
        console.print()
        
        # Use comprehensive audit workflow if we have scan results, otherwise analyze individually
        if scan_results_path and scan_results_path.exists():
            console.print("[green]Using AI-first comprehensive audit workflow...[/green]")
            
            # Run the full comprehensive audit
            results = await agent.run_comprehensive_audit(
                repository_path=str(repo_path),
                config={
                    "enable_visualisation": False,
                    "parallel_static": True,
                    "similarity_threshold": 0.85
                }
            )
            
            console.print(f"[green]✓ Comprehensive audit complete[/green]")
            analyzed_contracts = agent.contracts_analyzed
        else:
            # Fallback: Analyze contracts individually (prioritize core contracts)
            console.print("[yellow]Analyzing contracts individually (AI scan not available)[/yellow]")
            
            # Prioritize core contracts
            core_keywords = ["PanopticPool", "PanopticFactory", "CollateralTracker", "SemiFungible"]
            core_contracts = [f for f in contract_files if any(kw in f.name for kw in core_keywords)]
            other_contracts = [f for f in contract_files if f not in core_contracts]
            
            contract_files_sorted = core_contracts + other_contracts[:15]  # Core first, then up to 15 others
            
            analyzed_contracts = []
            for contract_file in contract_files_sorted:
                console.print(f"[bold yellow]Analyzing: {contract_file.relative_to(repo_path)}[/bold yellow]")
                try:
                    # Read contract content
                    with open(contract_file, 'r') as f:
                        contract_code = f.read()
                    
                    # Create analysis task with context awareness
                    analysis_task = f"""Analyze this smart contract for security vulnerabilities in the context of the Panoptic protocol:

Contract path: {contract_file}
Contract name: {contract_file.name}

Contract code:
```solidity
{contract_code[:8000]}
```

Please provide a detailed security analysis considering:
1. Protocol-level risks (how this contract fits into Panoptic's architecture)
2. Integration risks (interactions with other contracts)
3. Common attack vectors (reentrancy, overflow, access control, etc.)
4. Business logic issues specific to DeFi/perpetual swaps
5. Economic attack vectors (funding rate manipulation, liquidation risks, etc.)

For each vulnerability found, provide:
- Title
- Severity (Critical/High/Medium/Low/Info)
- Description
- Location (file and line if possible)
- Attack vector/exploit scenario
- Recommendation
"""
                    
                    # Use execute_task which supports tools
                    result = await agent.execute_task(analysis_task)
                    console.print(f"[green]✓ Analysis complete[/green]")
                    
                    # Log to audit trail
                    audit_trail.log_decision(
                        phase="contract_analysis",
                        action="contract_analyzed",
                        agent_id=agent.name,
                        decision={
                            "contract_path": str(contract_file),
                            "contract_name": contract_file.name,
                            "analysis_complete": True
                        }
                    )
                    
                    analyzed_contracts.append(str(contract_file))
                    agent.contracts_analyzed.append(str(contract_file))
                    
                    console.print()
                    
                except Exception as e:
                    console.print(f"[red]Error analyzing {contract_file.name}: {e}[/red]")
                    console.print_exception()
        
        console.print(f"[bold green]✓ Analyzed {len(analyzed_contracts)} contracts[/bold green]")
        console.print()
        
        # PHASE 4: Finalize findings with confidence scores
        console.print("[bold cyan]Phase 3: Finalizing Findings[/bold cyan]")
        
        if agent.audit_findings:
            console.print(f"[cyan]Finalizing {len(agent.audit_findings)} findings with confidence scores...[/cyan]")
            finalized = agent.finalize_findings_with_confidence()
            console.print(f"[green]✓ Finalized {len(finalized)} findings[/green]")
            
            # Show confidence distribution
            validated = len([f for f in finalized if f.get("status") == "validated"])
            rejected = len([f for f in finalized if f.get("status") == "rejected"])
            needs_review = len([f for f in finalized if f.get("status") == "needs_review"])
            console.print(f"  - Validated (auto-approve): {validated}")
            console.print(f"  - Rejected (auto-reject): {rejected}")
            console.print(f"  - Needs review: {needs_review}")
        else:
            console.print("[yellow]No findings recorded (may need tool access to add findings)[/yellow]")
        
        console.print()
        
        # PHASE 5: Generate comprehensive report
        console.print("[bold cyan]Phase 4: Report Generation[/bold cyan]")
        console.print("[bold]Generating audit report...[/bold]")
        
        # Prepare AI flags if we have scan results
        ai_flags = None
        if scan_results_path and scan_results_path.exists():
            try:
                import json
                with open(scan_results_path) as f:
                    scan_data = json.load(f)
                    if "contracts" in scan_data:
                        ai_flags = []
                        for contract in scan_data["contracts"]:
                            ai_flags.append({
                                "name": contract.get("name", ""),
                                "path": contract.get("path", ""),
                                "intent_scores": contract.get("intent", {}),
                                "max_similarity": contract.get("max_embedding_similarity", 0.0),
                                "embedding_matches": contract.get("embedding_matches", []),
                                "priority": "HIGH" if max(contract.get("intent", {}).values()) > 0.8 else "MEDIUM"
                            })
            except Exception as e:
                console.print(f"[yellow]Could not load AI flags: {e}[/yellow]")
        
        report_path = await agent.generate_audit_report(
            repository_path=str(repo_path),
            output_path=str(repo_path / "audit_report.md"),
            include_viz=False,
            ai_flags=ai_flags
        )
        
        console.print(f"[green]✓ Report generated: {report_path}[/green]")
        
        # Export audit trail
        trail_path = repo_path / "audit_trail.json"
        audit_trail.export_for_compliance(trail_path)
        console.print(f"[green]✓ Audit trail exported: {trail_path}[/green]")
        
        # Show summary
        summary = agent.get_findings_summary()
        console.print()
        console.print("[bold]Findings Summary:[/bold]")
        for severity, count in summary.items():
            if count > 0:
                console.print(f"  {severity}: {count}")
        
        if sum(summary.values()) == 0:
            console.print("[yellow]  No findings recorded (agent may need tool access to add findings)[/yellow]")
        
        # Verify chain integrity
        integrity = audit_trail.verify_chain_integrity()
        if integrity["tampering_detected"]:
            console.print("[red]⚠️ Warning: Audit trail integrity check detected tampering![/red]")
        else:
            console.print(f"[green]✓ Audit trail verified ({integrity['total_entries']} entries)[/green]")
        
    except Exception as e:
        console.print(f"[bold red]Error during audit: {e}[/bold red]")
        console.print_exception()
        sys.exit(1)
    finally:
        await exit_stack.aclose()


if __name__ == "__main__":
    asyncio.run(main())

