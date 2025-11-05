"""Report builder using Jinja2 templates for audit reports."""

import pathlib
from datetime import datetime
from typing import Dict, List, Any, Optional

try:
    from jinja2 import Environment, FileSystemLoader, TemplateNotFound
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False


class ReportBuilder:
    """Build audit reports from Jinja2 templates."""
    
    def __init__(self, template_dir: Optional[pathlib.Path] = None):
        """Initialize report builder.
        
        Args:
            template_dir: Directory containing Jinja2 templates
        """
        if not JINJA2_AVAILABLE:
            raise ImportError("Jinja2 is required for report generation")
        
        if template_dir is None:
            # Default to templates directory relative to this file
            template_dir = pathlib.Path(__file__).parent / "templates"
        
        self.template_dir = pathlib.Path(template_dir)
        self.template_dir.mkdir(parents=True, exist_ok=True)
        
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def build_report(
        self,
        findings: List[Dict[str, Any]],
        ai_flags: List[Dict[str, Any]],
        stats: Dict[str, int],
        repository_path: str,
        auditor_name: str = "ollm-crypt-sec",
        template_name: str = "audit_report.md.j2",
        viz_path: Optional[str] = None,
        static_validation: Optional[List[Dict[str, Any]]] = None,
        business_logic: Optional[List[Dict[str, Any]]] = None,
        recommendations: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Build audit report from template.
        
        Args:
            findings: List of finalized findings
            ai_flags: AI detection results
            stats: Statistics dictionary
            repository_path: Path to audited repository
            auditor_name: Name of auditor/system
            template_name: Template file name
            viz_path: Path to visualization image (optional)
            static_validation: Static analyzer validation results
            business_logic: Business logic analysis results
            recommendations: Recommendation list
            
        Returns:
            Generated markdown report as string
        """
        try:
            template = self.env.get_template(template_name)
        except TemplateNotFound:
            # Fallback to simple text report
            return self._build_simple_report(findings, stats, repository_path)
        
        # Calculate additional statistics
        ai_stats = self._calculate_ai_stats(ai_flags)
        
        # Prepare context
        context = {
            "title": pathlib.Path(repository_path).name,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "repository_path": repository_path,
            "auditor_name": auditor_name,
            "stats": stats,
            "ai_stats": ai_stats,
            "findings": findings,
            "ai_flags": ai_flags,
            "static_ai_validation": static_validation or [],
            "static_findings": [],
            "business_logic": business_logic or [],
            "recommendations": recommendations or [],
            "viz_path": viz_path,
            "engine_version": "1.0.0"
        }
        
        return template.render(**context)
    
    def _calculate_ai_stats(self, ai_flags: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calculate AI statistics from flags.
        
        Args:
            ai_flags: AI detection results
            
        Returns:
            Statistics dictionary
        """
        high_confidence = 0
        medium_confidence = 0
        low_confidence = 0
        
        for flag in ai_flags:
            max_intent = max(flag.get("intent_scores", {}).values()) if flag.get("intent_scores") else 0
            max_sim = flag.get("max_similarity", 0) or 0
            
            # Simple confidence approximation
            if max_intent > 0.9 or (max_intent > 0.8 and max_sim > 0.85):
                high_confidence += 1
            elif max_intent > 0.7 or max_sim > 0.75:
                medium_confidence += 1
            else:
                low_confidence += 1
        
        return {
            "high_confidence": high_confidence,
            "medium_confidence": medium_confidence,
            "low_confidence": low_confidence
        }
    
    def _build_simple_report(
        self,
        findings: List[Dict[str, Any]],
        stats: Dict[str, int],
        repository_path: str
    ) -> str:
        """Build simple text report if template not available.
        
        Args:
            findings: List of findings
            stats: Statistics
            repository_path: Repository path
            
        Returns:
            Simple markdown report
        """
        lines = [
            f"# Security Audit Report - {pathlib.Path(repository_path).name}",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
            f"- Total Findings: {len(findings)}",
            f"- Critical: {stats.get('Critical', 0)}",
            f"- High: {stats.get('High', 0)}",
            f"- Medium: {stats.get('Medium', 0)}",
            f"- Low: {stats.get('Low', 0)}",
            "",
            "## Findings",
            ""
        ]
        
        for finding in findings:
            lines.extend([
                f"### {finding.get('title', 'Unknown')}",
                f"- Severity: {finding.get('severity', 'Unknown')}",
                f"- Confidence: {finding.get('confidence', 'N/A')}",
                f"- Status: {finding.get('status', 'Unknown')}",
                f"- Description: {finding.get('description', 'No description')}",
                ""
            ])
        
        return "\n".join(lines)
    
    def save_report(
        self,
        report_content: str,
        output_path: str
    ) -> pathlib.Path:
        """Save report to file.
        
        Args:
            report_content: Generated report content
            output_path: Output file path
            
        Returns:
            Path to saved file
        """
        output = pathlib.Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        return output

