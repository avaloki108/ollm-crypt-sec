"""Specialized agent for Web3 security auditing."""

import json
import pathlib
from typing import Optional, List, Dict, Any
from rich.console import Console
import ollama
from contextlib import AsyncExitStack

from .base import SubAgent
from .audit_engine import AuditEngine
from .report_builder import ReportBuilder


class Web3AuditAgent(SubAgent):
    """Specialized agent for Web3 smart contract security auditing.
    
    This agent is pre-configured with tools and prompts optimized for:
    - Smart contract security analysis
    - Vulnerability detection
    - Code review and best practices
    - Integration with Foundry, Hardhat, Slither, and other audit tools
    """
    
    DEFAULT_SYSTEM_PROMPT = """You are an expert Web3 security auditor specializing in smart contract security analysis.

Your responsibilities include:
1. Analyzing smart contracts for security vulnerabilities
2. Identifying common attack vectors (reentrancy, overflow, access control, etc.)
3. Reviewing code for best practices and optimization opportunities
4. Running automated security tools (Slither, Mythril, Foundry tests)
5. Providing detailed reports with severity classifications
6. Suggesting fixes and improvements

When analyzing contracts:
- Always check for common vulnerabilities first
- Use available tools to verify findings
- Provide clear explanations with code examples
- Prioritize findings by severity (Critical, High, Medium, Low, Info)
- Consider gas optimization opportunities
- Verify against the latest security standards

You have access to tools for:
- Running Foundry tests and fuzzing
- Executing Hardhat scripts and tests
- Running static analysis with Slither
- Checking with Mythril
- File system operations for reading contracts
- Running shell commands for build and test operations
"""
    
    def __init__(
        self,
        name: str = "web3-auditor",
        model: str = "qwen2.5:7b",
        console: Optional[Console] = None,
        ollama_client: Optional[ollama.AsyncClient] = None,
        parent_exit_stack: Optional[AsyncExitStack] = None,
        message_broker = None,
        custom_prompt: Optional[str] = None
    ):
        """Initialize Web3 audit agent.
        
        Args:
            name: Name for this agent instance
            model: Ollama model to use (default: qwen2.5:7b)
            console: Rich console for output
            ollama_client: Ollama client instance
            parent_exit_stack: Parent's exit stack for resource management
            message_broker: Message broker for agent communication
            custom_prompt: Custom system prompt (uses default if None)
        """
        description = "Specialized agent for Web3 smart contract security auditing"
        system_prompt = custom_prompt or self.DEFAULT_SYSTEM_PROMPT
        
        super().__init__(
            name=name,
            description=description,
            model=model,
            system_prompt=system_prompt,
            console=console,
            ollama_client=ollama_client,
            parent_exit_stack=parent_exit_stack,
            message_broker=message_broker
        )
        
        # Audit-specific settings
        self.audit_findings: List[Dict[str, Any]] = []
        self.contracts_analyzed: List[str] = []
        
        # Initialize audit engine and report builder
        self.audit_engine = AuditEngine()
        self.report_builder = ReportBuilder()
        
        # Audit configuration
        self.enable_visualisation = False
        self.parallel_static = True
        self.similarity_threshold = 0.85
    
    async def analyze_contract(self, contract_path: str, analysis_type: str = "full") -> str:
        """Analyze a smart contract file.
        
        Args:
            contract_path: Path to the contract file
            analysis_type: Type of analysis ("quick", "full", "deep")
            
        Returns:
            str: Analysis report
        """
        task = f"""Analyze the smart contract at {contract_path}.
        
Analysis type: {analysis_type}

Please:
1. Read the contract file
2. Identify potential vulnerabilities
3. Run available static analysis tools
4. Provide a comprehensive report with findings
5. Classify findings by severity
6. Suggest fixes for identified issues
"""
        
        result = await self.execute_task(task)
        self.contracts_analyzed.append(contract_path)
        return result
    
    async def run_foundry_tests(self, project_path: str) -> str:
        """Run Foundry tests for a project.
        
        Args:
            project_path: Path to the Foundry project
            
        Returns:
            str: Test results
        """
        task = f"""Run Foundry tests for the project at {project_path}.

Please:
1. Navigate to the project directory
2. Run `forge test -vvv` to execute tests
3. Analyze any test failures
4. Provide a summary of test coverage and results
"""
        
        return await self.execute_task(task)
    
    async def run_slither_analysis(self, contract_or_project_path: str) -> str:
        """Run Slither static analysis.
        
        Args:
            contract_or_project_path: Path to contract file or project
            
        Returns:
            str: Slither analysis results
        """
        task = f"""Run Slither static analysis on {contract_or_project_path}.

Please:
1. Execute `slither {contract_or_project_path}`
2. Parse and categorize the findings
3. Filter out false positives if any
4. Provide a detailed report of vulnerabilities found
"""
        
        return await self.execute_task(task)
    
    async def generate_audit_report(
        self,
        repository_path: str = "",
        output_path: str = "audit_report.md",
        include_viz: bool = None,
        ai_flags: Optional[List[Dict[str, Any]]] = None,
        static_validation: Optional[List[Dict[str, Any]]] = None,
        business_logic: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Generate a comprehensive audit report using Jinja2 template.
        
        Args:
            repository_path: Path to audited repository
            output_path: Output file path for report
            include_viz: Whether to include visualization (overrides config)
            ai_flags: AI detection results (auto-extracted if None)
            static_validation: Static analyzer validation results
            business_logic: Business logic analysis results
            
        Returns:
            Path to generated report file
        """
        # Finalize findings with confidence scores
        finalized_findings = self.finalize_findings_with_confidence()
        
        # Calculate statistics
        summary = self.get_findings_summary()
        stats = {
            "total_contracts": len(self.contracts_analyzed),
            "critical": summary.get("Critical", 0),
            "high": summary.get("High", 0),
            "medium": summary.get("Medium", 0),
            "low": summary.get("Low", 0),
            "info": summary.get("Info", 0),
            "validated": len([f for f in finalized_findings if f.get("status") == "validated"]),
            "rejected": len([f for f in finalized_findings if f.get("status") == "rejected"]),
            "needs_review": len([f for f in finalized_findings if f.get("status") == "needs_review"])
        }
        
        # Extract AI flags from findings if not provided
        if ai_flags is None:
            ai_flags = []
            for finding in finalized_findings:
                if "ai_intent_score" in finding or "max_embedding_similarity" in finding:
                    ai_flags.append({
                        "name": finding.get("title", "Unknown"),
                        "path": finding.get("location", ""),
                        "intent_scores": {"overall": finding.get("ai_intent_score", 0.0)},
                        "max_similarity": finding.get("max_embedding_similarity", 0.0),
                        "embedding_matches": finding.get("embedding_matches", []),
                        "priority": finding.get("severity", "Unknown")
                    })
        
        # Generate visualization if enabled
        viz_path = None
        if include_viz or (include_viz is None and self.enable_visualisation):
            # Try to extract embeddings from findings
            embeddings_dict = {}
            for finding in finalized_findings:
                if "embedding" in finding:
                    name = finding.get("title", "Unknown")
                    embeddings_dict[name] = finding["embedding"]
            
            if embeddings_dict:
                viz_path = self.generate_visualization(embeddings_dict)
        
        # Generate recommendations from findings
        recommendations = []
        for finding in finalized_findings:
            if finding.get("status") == "validated" or finding.get("severity") in ["Critical", "High"]:
                recommendations.append({
                    "title": finding.get("title", "Unknown"),
                    "severity": finding.get("severity", "Unknown"),
                    "location": finding.get("location", ""),
                    "fix": finding.get("recommendation", ""),
                    "priority": "high" if finding.get("severity") in ["Critical", "High"] else "medium"
                })
        
        # Build report
        report_content = self.report_builder.build_report(
            findings=finalized_findings,
            ai_flags=ai_flags,
            stats=stats,
            repository_path=repository_path or "/".join(self.contracts_analyzed[:1]) or "Unknown",
            auditor_name=self.name,
            viz_path=viz_path,
            static_validation=static_validation,
            business_logic=business_logic,
            recommendations=recommendations
        )
        
        # Save report
        report_file = self.report_builder.save_report(report_content, output_path)
        
        self.console.print(f"[green]✓ Generated audit report: {report_file}[/green]")
        return str(report_file)
    
    def add_finding(
        self,
        title: str,
        severity: str,
        description: str,
        location: str,
        recommendation: str
    ) -> None:
        """Add a finding to the audit report.
        
        Args:
            title: Finding title
            severity: Severity level (Critical, High, Medium, Low, Info)
            description: Detailed description
            location: Code location
            recommendation: Recommended fix
        """
        finding = {
            "title": title,
            "severity": severity,
            "description": description,
            "location": location,
            "recommendation": recommendation
        }
        self.audit_findings.append(finding)
    
    def get_findings_summary(self) -> Dict[str, int]:
        """Get summary of findings by severity.
        
        Returns:
            Dict mapping severity to count
        """
        summary = {
            "Critical": 0,
            "High": 0,
            "Medium": 0,
            "Low": 0,
            "Info": 0
        }
        
        for finding in self.audit_findings:
            severity = finding.get("severity", "Info")
            if severity in summary:
                summary[severity] += 1
        
        return summary
    
    def process_scan_results(
        self,
        scan_results_path: str,
        similarity_threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """Process web3-scanner results with embedding similarity matching.
        
        Args:
            scan_results_path: Path to scan results JSON file
            similarity_threshold: Override default threshold
            
        Returns:
            Enhanced scan results with similarity matches
        """
        threshold = similarity_threshold or self.similarity_threshold
        
        try:
            with open(scan_results_path, 'r') as f:
                scan_results = json.load(f)
            
            processed = self.audit_engine.process_scan_results(
                scan_results, threshold
            )
            
            # Store processed results
            processed_path = scan_results_path.replace('.json', '_processed.json')
            with open(processed_path, 'w') as f:
                json.dump(processed, f, indent=2)
            
            self.console.print(f"[green]✓ Processed scan results with embedding matches[/green]")
            return processed
            
        except Exception as e:
            self.console.print(f"[red]Error processing scan results: {e}[/red]")
            return {}
    
    async def run_static_analysis_parallel(
        self,
        contract_paths: List[str],
        tools: Optional[List[str]] = None,
        max_workers: int = 4
    ) -> Dict[str, Dict[str, Any]]:
        """Run static analysis tools in parallel on multiple contracts.
        
        Args:
            contract_paths: List of contract file paths
            tools: List of tool names (default: all available)
            max_workers: Maximum parallel workers
            
        Returns:
            Dictionary mapping contract_path -> {tool_name -> result}
        """
        if not self.parallel_static:
            # Sequential execution
            results = {}
            for path in contract_paths:
                results[path] = {}
                for tool_name in (tools or list(self.audit_engine.static_commands.keys())):
                    results[path][tool_name] = self.audit_engine.run_static_tool(tool_name, path)
            return results
        
        # Parallel execution
        return self.audit_engine.run_static_parallel(contract_paths, tools, max_workers)
    
    def finalize_findings_with_confidence(self) -> List[Dict[str, Any]]:
        """Apply confidence scoring and auto-approve/reject logic.
        
        Returns:
            Finalized findings with confidence scores and status
        """
        finalized = self.audit_engine.finalize_findings(self.audit_findings)
        self.audit_findings = finalized
        return finalized
    
    def generate_visualization(
        self,
        embeddings_dict: Dict[str, Any],
        output_path: str = "embedding_tsne.png"
    ) -> Optional[str]:
        """Generate t-SNE visualization of contract embeddings.
        
        Args:
            embeddings_dict: Dictionary mapping contract names to embeddings
            output_path: Output file path
            
        Returns:
            Path to generated image, or None if unavailable
        """
        if not self.enable_visualisation:
            return None
        
        return self.audit_engine.generate_tsne_plot(embeddings_dict, output_path)
    
    async def run_comprehensive_audit(
        self,
        repository_path: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run comprehensive audit workflow with AI-first approach.
        
        Args:
            repository_path: Path to repository to audit
            config: Optional configuration overrides
            
        Returns:
            Complete audit results
        """
        if config:
            self.enable_visualisation = config.get("enable_visualisation", False)
            self.parallel_static = config.get("parallel_static", True)
            self.similarity_threshold = config.get("similarity_threshold", 0.85)
        
        task = f"""Perform a comprehensive security audit of the repository at {repository_path}.

Follow the AI-first workflow:

1. **AI-Powered Analysis Phase**:
   - Check web3se-lab services status using check_web3se_status
   - Start services if needed using start_web3se_services
   - Run web3_scanner_scan on the repository with intent detection and embeddings enabled
   - Process scan results to find embedding similarity matches
   - Prioritize contracts by intent scores (Critical >0.9, High 0.8-0.9, Medium 0.7-0.8)

2. **Static Analysis Phase** (on AI-flagged contracts):
   - Run Slither, Mythril, and Securify2 in parallel on high-priority contracts
   - For each static finding, re-run SmartIntentNN to validate (bidirectional cross-ref)

3. **False Positive Filtering**:
   - Calculate confidence scores for all findings
   - Auto-approve findings with confidence >0.9
   - Auto-reject findings with confidence <0.7 and similarity <0.75
   - Flag others for manual review

4. **Deep Business Logic Analysis**:
   - Analyze value flows in high-priority contracts
   - Identify invariants and test violations
   - Model economic attack vectors
   - Analyze composability risks

5. **Report Generation**:
   - Generate comprehensive markdown report with all sections
   - Include confidence scores and auto-approval status
   - Add visualization if embeddings are available

Use the audit_engine helper functions:
- process_scan_results() for embedding matches
- run_static_analysis_parallel() for parallel tool execution
- finalize_findings_with_confidence() for confidence scoring
- generate_visualization() if enabled
"""
        
        result = await self.execute_task(task)
        return {
            "audit_result": result,
            "findings": self.audit_findings,
            "summary": self.get_findings_summary(),
            "contracts_analyzed": self.contracts_analyzed
        }
