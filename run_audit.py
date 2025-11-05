#!/usr/bin/env python3
"""Standalone script to run a Web3 security audit."""

import asyncio
import sys
from pathlib import Path
from rich.console import Console

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from mcp_client_for_ollama.agents.web3_audit import Web3AuditAgent
from mcp_client_for_ollama.agents.audit_trail import AuditTrail
from contextlib import AsyncExitStack
import ollama


async def main():
    """Run audit on specified directory."""
    if len(sys.argv) < 2:
        print("Usage: python run_audit.py <repository_path> [model]")
        print("Example: python run_audit.py ~/web3/dexlyn qwen3-coder:30b")
        sys.exit(1)
    
    repo_path = Path(sys.argv[1]).expanduser().resolve()
    model = sys.argv[2] if len(sys.argv) > 2 else "qwen3-coder:30b"
    
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
    
    # Initialize audit trail
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
        
        # Connect to MCP servers if config exists
        server_config = Path.home() / ".config" / "ollmcp" / "mcp-servers" / "web3-audit.json"
        if server_config.exists():
            console.print(f"[cyan]Connecting to MCP servers from {server_config}[/cyan]")
            await agent.connect_to_servers(config_path=str(server_config))
        else:
            console.print("[yellow]No MCP server config found, running without tools[/yellow]")
        
        # Enable visualization and configure
        agent.enable_visualisation = True
        agent.parallel_static = True
        agent.similarity_threshold = 0.85
        
        console.print("[bold]Running comprehensive audit...[/bold]")
        console.print()
        
        # First, let's find and read all Solidity contracts
        contract_files = list(repo_path.rglob("*.sol"))
        # Filter out node_modules
        contract_files = [f for f in contract_files if "node_modules" not in str(f)]
        
        console.print(f"[cyan]Found {len(contract_files)} Solidity contracts[/cyan]")
        
        # Analyze each contract
        for contract_file in contract_files:
            console.print(f"[yellow]Analyzing: {contract_file.name}[/yellow]")
            try:
                result = await agent.analyze_contract(
                    str(contract_file),
                    analysis_type="deep"
                )
                console.print(f"[green]✓ Analyzed {contract_file.name}[/green]")
                
                # Log to audit trail
                audit_trail.log_decision(
                    phase="contract_analysis",
                    action="contract_analyzed",
                    agent_id="dexlyn-auditor",
                    decision={
                        "contract_path": str(contract_file),
                        "contract_name": contract_file.name,
                        "analysis_complete": True
                    }
                )
            except Exception as e:
                console.print(f"[red]Error analyzing {contract_file.name}: {e}[/red]")
        
        console.print()
        
        # Try to run static analysis tools if available
        if contract_files:
            console.print("[bold]Running static analysis tools...[/bold]")
            contract_paths = [str(f) for f in contract_files[:5]]  # Limit to first 5
            
            try:
                static_results = await agent.run_static_analysis_parallel(
                    contract_paths,
                    tools=["slither"],  # Try just slither first
                    max_workers=2
                )
                console.print(f"[green]✓ Static analysis complete on {len(static_results)} contracts[/green]")
            except Exception as e:
                console.print(f"[yellow]Static analysis tools not available: {e}[/yellow]")
        
        # Run comprehensive audit workflow
        console.print()
        console.print("[bold]Running AI-first analysis workflow...[/bold]")
        
        results = await agent.run_comprehensive_audit(
            repository_path=str(repo_path),
            config={
                "enable_visualisation": True,
                "parallel_static": True,
                "similarity_threshold": 0.85
            }
        )
        
        console.print()
        console.print("[bold green]Audit complete![/bold green]")
        console.print()
        
        # Display summary
        summary = results.get("summary", {})
        console.print("[bold]Findings Summary:[/bold]")
        for severity, count in summary.items():
            if count > 0:
                console.print(f"  {severity}: {count}")
        
        # Generate final report
        console.print()
        console.print("[bold]Generating audit report...[/bold]")
        
        report_path = await agent.generate_audit_report(
            repository_path=str(repo_path),
            output_path=str(repo_path / "audit_report.md"),
            include_viz=True
        )
        
        console.print(f"[green]✓ Report generated: {report_path}[/green]")
        
        # Export audit trail
        trail_path = repo_path / "audit_trail.json"
        audit_trail.export_for_compliance(trail_path)
        console.print(f"[green]✓ Audit trail exported: {trail_path}[/green]")
        
        # Verify chain integrity
        integrity = audit_trail.verify_chain_integrity()
        if integrity["tampering_detected"]:
            console.print("[red]⚠️ Warning: Audit trail integrity check detected tampering![/red]")
        else:
            console.print("[green]✓ Audit trail integrity verified[/green]")
        
    except Exception as e:
        console.print(f"[bold red]Error during audit: {e}[/bold red]")
        console.print_exception()
        sys.exit(1)
    finally:
        await exit_stack.aclose()


if __name__ == "__main__":
    asyncio.run(main())

