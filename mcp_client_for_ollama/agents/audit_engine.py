"""Audit engine module for Web3 security audits with AI-powered analysis.

Provides:
- Embedding similarity calculations (cosine similarity with vulnerability DB)
- Confidence score calculation
- Parallel static tool execution
- Auto-approve/reject logic for findings
- Optional visualization (t-SNE)
- UMAP clustering for embedding analysis
- ML-based false positive filtering
"""

import json
import subprocess
import pathlib
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np

try:
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.manifold import TSNE
    import matplotlib.pyplot as plt
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# Default vulnerability database path
VULN_DB_PATH = pathlib.Path.home() / ".config" / "ollmcp" / "vuln_db.json"


class AuditEngine:
    """Core audit engine for processing AI and static analysis results."""
    
    def __init__(self, vuln_db_path: Optional[pathlib.Path] = None):
        """Initialize the audit engine.
        
        Args:
            vuln_db_path: Path to vulnerability embedding database
        """
        self.vuln_db_path = vuln_db_path or VULN_DB_PATH
        self.vuln_embeddings: Dict[str, np.ndarray] = {}
        self._load_vuln_db()
        
        # Static tool commands
        self.static_commands = {
            "slither": lambda p: f"slither {p}",
            "mythril": lambda p: f"mythril analyze {p}",
            "securify2": lambda p: f"securify {p}",
        }
    
    def _load_vuln_db(self) -> None:
        """Load vulnerability embedding database."""
        if self.vuln_db_path.exists():
            try:
                with open(self.vuln_db_path, 'r') as f:
                    data = json.load(f)
                    self.vuln_embeddings = {
                        k: np.array(v, dtype=np.float32)
                        for k, v in data.items()
                    }
            except Exception as e:
                print(f"Warning: Could not load vuln DB: {e}")
                self.vuln_embeddings = {}
        else:
            self.vuln_embeddings = {}
    
    def embedding_matches(
        self,
        contract_emb: np.ndarray,
        threshold: float = 0.85
    ) -> List[Dict[str, Any]]:
        """Find vulnerability matches using cosine similarity.
        
        Args:
            contract_emb: Contract embedding vector (768-dim)
            threshold: Minimum similarity threshold (default 0.85)
            
        Returns:
            List of matches with vulnerability name and similarity score
        """
        if not self.vuln_embeddings or not SKLEARN_AVAILABLE:
            return []
        
        if len(contract_emb.shape) == 1:
            contract_emb = contract_emb.reshape(1, -1)
        
        # Compute cosine similarity with all known vulnerabilities
        vuln_vectors = np.stack(list(self.vuln_embeddings.values()))
        scores = cosine_similarity(contract_emb, vuln_vectors)[0]
        
        matches = []
        for name, score in zip(self.vuln_embeddings.keys(), scores):
            if score >= threshold:
                matches.append({
                    "vulnerability": name,
                    "similarity": float(score),
                    "threshold": "high" if score > 0.85 else "medium"
                })
        
        # Sort by similarity (highest first)
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches
    
    def compute_confidence(
        self,
        ai_intent_score: float,
        embedding_similarity: float,
        static_confirm: bool,
        business_logic_ok: bool
    ) -> float:
        """Calculate confidence score using weighted formula.
        
        Formula: AI_Intent * 0.4 + Embedding_Sim * 0.3 + Static * 0.2 + Biz * 0.1
        
        Args:
            ai_intent_score: AI intent detection score (0-1)
            embedding_similarity: Max embedding similarity (0-1)
            static_confirm: Whether static analyzer confirmed (0 or 1)
            business_logic_ok: Whether business logic validation passed (0 or 1)
            
        Returns:
            Confidence score (0-1)
        """
        static_val = 1.0 if static_confirm else 0.0
        biz_val = 1.0 if business_logic_ok else 0.0
        
        confidence = (
            ai_intent_score * 0.4 +
            embedding_similarity * 0.3 +
            static_val * 0.2 +
            biz_val * 0.1
        )
        
        return round(confidence, 3)
    
    def finalize_findings(
        self,
        findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Apply auto-approve/reject logic to findings.
        
        Rules:
        - confidence > 0.9: validated (auto-approve)
        - confidence < 0.7 AND similarity < 0.75: rejected (auto-reject)
        - else: needs_review
        
        Args:
            findings: List of finding dictionaries
            
        Returns:
            Findings with status and confidence added
        """
        finalized = []
        
        for finding in findings:
            # Extract values with defaults
            ai_score = finding.get("ai_intent_score", 0.0)
            max_sim = finding.get("max_embedding_similarity", 0.0)
            static_confirm = finding.get("static_confirmed", False)
            biz_ok = finding.get("business_logic_validated", False)
            
            # Calculate confidence
            confidence = self.compute_confidence(
                ai_score, max_sim, static_confirm, biz_ok
            )
            
            finding["confidence"] = confidence
            
            # Auto-approve/reject logic
            if confidence > 0.9:
                finding["status"] = "validated"
                finding["requires_review"] = False
            elif confidence < 0.7 and max_sim < 0.75:
                finding["status"] = "rejected"
                finding["requires_review"] = False
            else:
                finding["status"] = "needs_review"
                finding["requires_review"] = True
            
            finalized.append(finding)
        
        return finalized
    
    def run_static_tool(
        self,
        tool_name: str,
        contract_path: str,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """Run a single static analysis tool.
        
        Args:
            tool_name: Name of tool (slither, mythril, securify2)
            contract_path: Path to contract file or directory
            timeout: Execution timeout in seconds
            
        Returns:
            Tool execution result
        """
        if tool_name not in self.static_commands:
            return {
                "tool": tool_name,
                "error": f"Unknown tool: {tool_name}",
                "output": "",
                "success": False
            }
        
        cmd = self.static_commands[tool_name](contract_path)
        
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                "tool": tool_name,
                "command": cmd,
                "output": result.stdout + result.stderr,
                "success": result.returncode == 0,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "tool": tool_name,
                "error": f"Timeout after {timeout}s",
                "output": "",
                "success": False
            }
        except Exception as e:
            return {
                "tool": tool_name,
                "error": str(e),
                "output": "",
                "success": False
            }
    
    def run_static_parallel(
        self,
        contract_paths: List[str],
        tools: Optional[List[str]] = None,
        max_workers: int = 4
    ) -> Dict[str, Dict[str, Any]]:
        """Run static analysis tools in parallel.
        
        Args:
            contract_paths: List of contract file paths
            tools: List of tool names to run (default: all)
            max_workers: Maximum parallel workers
            
        Returns:
            Dictionary mapping contract_path -> {tool_name -> result}
        """
        if tools is None:
            tools = list(self.static_commands.keys())
        
        results = {}
        
        def worker(contract_path: str) -> Tuple[str, Dict[str, Any]]:
            contract_results = {}
            for tool_name in tools:
                contract_results[tool_name] = self.run_static_tool(
                    tool_name, contract_path
                )
            return contract_path, contract_results
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(worker, path): path
                for path in contract_paths
            }
            
            for future in as_completed(future_to_path):
                try:
                    path, result = future.result()
                    results[path] = result
                except Exception as e:
                    path = future_to_path[future]
                    results[path] = {"error": str(e)}
        
        return results
    
    def generate_tsne_plot(
        self,
        embeddings_dict: Dict[str, np.ndarray],
        output_path: str = "embedding_tsne.png"
    ) -> Optional[str]:
        """Generate t-SNE visualization of embeddings.
        
        Args:
            embeddings_dict: Dictionary mapping contract names to embeddings
            output_path: Output file path
            
        Returns:
            Path to generated image, or None if visualization unavailable
        """
        if not SKLEARN_AVAILABLE or not embeddings_dict:
            return None
        
        try:
            names = list(embeddings_dict.keys())
            vecs = np.stack([embeddings_dict[n] for n in names])
            
            # Reduce to 2D using t-SNE
            tsne = TSNE(n_components=2, random_state=42, perplexity=min(30, len(names)-1))
            reduced = tsne.fit_transform(vecs)
            
            # Create plot
            plt.figure(figsize=(12, 8))
            plt.scatter(reduced[:, 0], reduced[:, 1], alpha=0.6, s=100)
            
            # Add labels
            for (x, y), name in zip(reduced, names):
                plt.text(x + 0.02, y, name, fontsize=8, alpha=0.7)
            
            plt.title("SmartBERT Embedding Space (t-SNE)", fontsize=14)
            plt.xlabel("t-SNE Component 1")
            plt.ylabel("t-SNE Component 2")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            return output_path
        except Exception as e:
            print(f"Warning: Could not generate t-SNE plot: {e}")
            return None
    
    def process_scan_results(
        self,
        scan_results: Dict[str, Any],
        similarity_threshold: float = 0.85
    ) -> Dict[str, Any]:
        """Process web3-scanner results and add similarity matches.
        
        Args:
            scan_results: Results from web3_scanner_scan
            similarity_threshold: Threshold for embedding matches
            
        Returns:
            Enhanced scan results with similarity matches
        """
        processed = scan_results.copy()
        
        if "contracts" not in processed:
            processed["contracts"] = []
        
        for contract in processed["contracts"]:
            if "embedding" in contract:
                emb = np.array(contract["embedding"], dtype=np.float32)
                matches = self.embedding_matches(emb, similarity_threshold)
                contract["embedding_matches"] = matches
                
                # Add max similarity for easy filtering
                if matches:
                    contract["max_embedding_similarity"] = matches[0]["similarity"]
                else:
                    contract["max_embedding_similarity"] = 0.0
        
        return processed


def build_vuln_db(
    smartbert_url: str = "http://localhost:9900/embed",
    output_path: Optional[pathlib.Path] = None
) -> bool:
    """Build vulnerability database from known bad patterns.
    
    Args:
        smartbert_url: SmartBERT API endpoint for embeddings
        output_path: Output path for database
        
    Returns:
        True if successful, False otherwise
    """
    if not REQUESTS_AVAILABLE:
        print("Error: requests library required for building vuln DB")
        return False
    
    output_path = output_path or VULN_DB_PATH
    
    # Known vulnerability patterns
    vuln_snippets = {
        "reentrancy": """
        function withdraw() public {
            uint amount = balances[msg.sender];
            (bool success, ) = msg.sender.call{value: amount}("");
            require(success, "Transfer failed");
            balances[msg.sender] = 0;
        }
        """,
        "unchecked_send": """
        function transfer(address to, uint amount) public {
            payable(to).send(amount);
        }
        """,
        "unchecked_call": """
        function transfer(address to, uint amount) public {
            (bool success, ) = to.call{value: amount}("");
            // Missing check on success
        }
        """,
        "integer_overflow": """
        function add(uint a, uint b) public pure returns (uint) {
            return a + b;  // No overflow check
        }
        """,
        "front_running": """
        function swap(uint amount) public {
            uint price = getPrice();
            executeSwap(amount, price);  // No slippage protection
        }
        """,
        "access_control": """
        function adminFunction() public {
            // Missing onlyOwner modifier
            doAdminThing();
        }
        """,
    }
    
    try:
        embeddings = {}
        
        for name, code in vuln_snippets.items():
            try:
                response = requests.post(
                    smartbert_url,
                    json={"code": code.strip()},
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "embedding" in data:
                        embeddings[name] = data["embedding"]
                        print(f"✓ Generated embedding for: {name}")
                    else:
                        print(f"✗ No embedding in response for: {name}")
                else:
                    print(f"✗ HTTP {response.status_code} for: {name}")
            except Exception as e:
                print(f"✗ Error processing {name}: {e}")
        
        if embeddings:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(embeddings, f, indent=2)
            
            print(f"✓ Saved {len(embeddings)} vulnerability embeddings to {output_path}")
            return True
        else:
            print("✗ No embeddings generated")
            return False
            
    except Exception as e:
        print(f"✗ Error building vuln DB: {e}")
        return False


if __name__ == "__main__":
    # CLI for building vulnerability database
    import argparse
    
    parser = argparse.ArgumentParser(description="Build vulnerability embedding database")
    parser.add_argument(
        "--url",
        default="http://localhost:9900/embed",
        help="SmartBERT API URL"
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=VULN_DB_PATH,
        help="Output path for database"
    )
    
    args = parser.parse_args()
    build_vuln_db(args.url, args.output)

