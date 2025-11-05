"""Chain watcher agent for monitoring on-chain deployments during audits."""

import asyncio
from typing import Optional, Dict, List, Any
from rich.console import Console
import ollama
from contextlib import AsyncExitStack

from .base import SubAgent
from .pubsub import EventType, get_broker


class ChainWatcherAgent(SubAgent):
    """Agent that monitors on-chain activity during audits."""
    
    DEFAULT_SYSTEM_PROMPT = """You are a blockchain monitoring agent specializing in real-time on-chain analysis.

Your responsibilities include:
1. Monitoring on-chain deployments for contracts under audit
2. Detecting live transactions matching flagged vulnerability patterns
3. Alerting on suspicious activity during audit period
4. Tracking contract interactions and state changes
5. Providing real-time threat intelligence

You integrate with:
- Etherscan API for transaction monitoring
- WebSocket connections for real-time events
- On-chain data analysis tools
"""
    
    def __init__(
        self,
        name: str = "chain-watcher",
        model: str = "qwen2.5:7b",
        console: Optional[Console] = None,
        ollama_client: Optional[ollama.AsyncClient] = None,
        parent_exit_stack: Optional[AsyncExitStack] = None,
        message_broker = None,
        custom_prompt: Optional[str] = None,
        etherscan_api_key: Optional[str] = None
    ):
        """Initialize chain watcher agent.
        
        Args:
            name: Agent name
            model: Ollama model
            console: Rich console
            ollama_client: Ollama client
            parent_exit_stack: Parent exit stack
            message_broker: Message broker
            custom_prompt: Custom system prompt
            etherscan_api_key: Etherscan API key (optional)
        """
        description = "On-chain monitoring agent for real-time threat detection"
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
        
        self.etherscan_api_key = etherscan_api_key
        self.monitored_contracts: Dict[str, Dict[str, Any]] = {}
        self.watched_patterns: List[str] = []
        self.pubsub = get_broker()
        self._monitoring_task: Optional[asyncio.Task] = None
    
    async def watch_contract(
        self,
        address: str,
        contract_name: str,
        audit_findings: List[Dict[str, Any]]
    ) -> None:
        """Start monitoring a contract on-chain.
        
        Args:
            address: Contract address
            contract_name: Contract name
            audit_findings: Findings from audit (patterns to watch for)
        """
        self.monitored_contracts[address] = {
            "name": contract_name,
            "address": address,
            "findings": audit_findings,
            "last_check": None,
            "alert_count": 0
        }
        
        # Extract patterns to watch
        for finding in audit_findings:
            if "vulnerability" in finding:
                self.watched_patterns.append(finding["vulnerability"])
        
        self.console.print(
            f"[green]✓ Started monitoring contract: {contract_name} ({address[:10]}...)[/green]"
        )
    
    async def check_transactions(
        self,
        address: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Check recent transactions for a contract.
        
        Args:
            address: Contract address
            limit: Maximum transactions to check
            
        Returns:
            List of transactions
        """
        if not self.etherscan_api_key:
            # Fallback: return empty (would use WebSocket or other method)
            return []
        
        try:
            import requests
            
            url = "https://api.etherscan.io/api"
            params = {
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "sort": "desc",
                "apikey": self.etherscan_api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "1":
                    return data.get("result", [])[:limit]
            
            return []
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not check transactions: {e}[/yellow]")
            return []
    
    async def analyze_transaction_for_patterns(
        self,
        transaction: Dict[str, Any],
        patterns: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Analyze transaction for suspicious patterns.
        
        Args:
            transaction: Transaction data
            patterns: Patterns to match
            
        Returns:
            Alert if pattern matched, None otherwise
        """
        # Simple pattern matching (can be enhanced with ML)
        tx_data = transaction.get("input", "").lower()
        tx_value = int(transaction.get("value", "0"), 16)
        
        alerts = []
        
        for pattern in patterns:
            if pattern.lower() in tx_data:
                alerts.append(pattern)
        
        # Check for large value transfers (potential exploit)
        if tx_value > 1000000000000000000:  # > 1 ETH
            alerts.append("large_value_transfer")
        
        if alerts:
            return {
                "transaction_hash": transaction.get("hash"),
                "from": transaction.get("from"),
                "to": transaction.get("to"),
                "value": transaction.get("value"),
                "patterns_matched": alerts,
                "timestamp": transaction.get("timeStamp")
            }
        
        return None
    
    async def start_monitoring(
        self,
        check_interval: int = 60
    ) -> None:
        """Start continuous monitoring loop.
        
        Args:
            check_interval: Seconds between checks
        """
        if self._monitoring_task and not self._monitoring_task.done():
            return
        
        async def monitor_loop():
            while True:
                try:
                    for address, contract_data in self.monitored_contracts.items():
                        transactions = await self.check_transactions(address)
                        
                        for tx in transactions:
                            alert = await self.analyze_transaction_for_patterns(
                                tx,
                                self.watched_patterns
                            )
                            
                            if alert:
                                # Publish alert
                                await self.pubsub.publish(
                                    EventType.VULNERABILITY_FLAGGED,
                                    self.name,
                                    {
                                        "contract_address": address,
                                        "contract_name": contract_data["name"],
                                        "alert": alert,
                                        "source": "chain_watcher"
                                    }
                                )
                                
                                contract_data["alert_count"] += 1
                                self.console.print(
                                    f"[red]⚠️ Alert: {contract_data['name']} - Pattern detected in transaction[/red]"
                                )
                        
                        contract_data["last_check"] = asyncio.get_event_loop().time()
                    
                    await asyncio.sleep(check_interval)
                except Exception as e:
                    self.console.print(f"[red]Error in monitoring loop: {e}[/red]")
                    await asyncio.sleep(check_interval)
        
        self._monitoring_task = asyncio.create_task(monitor_loop())
        self.console.print("[green]✓ Chain monitoring started[/green]")
    
    async def stop_monitoring(self) -> None:
        """Stop monitoring loop."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
        
        self.console.print("[yellow]Chain monitoring stopped[/yellow]")
    
    async def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "monitored_contracts": len(self.monitored_contracts),
            "total_alerts": sum(c["alert_count"] for c in self.monitored_contracts.values()),
            "watched_patterns": len(self.watched_patterns),
            "contracts": [
                {
                    "name": data["name"],
                    "address": address,
                    "alerts": data["alert_count"]
                }
                for address, data in self.monitored_contracts.items()
            ]
        }

