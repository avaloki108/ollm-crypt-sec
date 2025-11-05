"""Pub-sub broker for agent communication with event subscriptions."""

import asyncio
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import json


class EventType(Enum):
    """Event types for pub-sub."""
    VULNERABILITY_FLAGGED = "vulnerability_flagged"
    CONTRACT_ANALYZED = "contract_analyzed"
    STATIC_ANALYSIS_COMPLETE = "static_analysis_complete"
    CONFIDENCE_CALCULATED = "confidence_calculated"
    FINDING_VALIDATED = "finding_validated"
    FINDING_REJECTED = "finding_rejected"
    PHASE_COMPLETE = "phase_complete"
    CUSTOM = "custom"


@dataclass
class Event:
    """Pub-sub event."""
    event_type: EventType
    source_agent: str
    payload: Dict[str, Any]
    timestamp: str
    event_id: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type.value,
            "source_agent": self.source_agent,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "event_id": self.event_id
        }


class PubSubBroker:
    """Lightweight pub-sub broker for agent communication."""
    
    def __init__(self):
        """Initialize pub-sub broker."""
        self.subscribers: Dict[EventType, List[Callable]] = {}
        self.event_history: List[Event] = []
        self._lock = asyncio.Lock()
        self._event_counter = 0
    
    async def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], Any]
    ) -> None:
        """Subscribe to event type.
        
        Args:
            event_type: Type of event to subscribe to
            handler: Async handler function
        """
        async with self._lock:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            self.subscribers[event_type].append(handler)
    
    async def unsubscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], Any]
    ) -> None:
        """Unsubscribe from event type.
        
        Args:
            event_type: Event type
            handler: Handler to remove
        """
        async with self._lock:
            if event_type in self.subscribers:
                if handler in self.subscribers[event_type]:
                    self.subscribers[event_type].remove(handler)
    
    async def publish(
        self,
        event_type: EventType,
        source_agent: str,
        payload: Dict[str, Any]
    ) -> Event:
        """Publish event to subscribers.
        
        Args:
            event_type: Type of event
            source_agent: Agent publishing the event
            payload: Event data
            
        Returns:
            Created event
        """
        async with self._lock:
            self._event_counter += 1
            
            event = Event(
                event_type=event_type,
                source_agent=source_agent,
                payload=payload,
                timestamp=datetime.utcnow().isoformat(),
                event_id=f"evt_{self._event_counter}"
            )
            
            self.event_history.append(event)
            
            # Notify subscribers
            handlers = self.subscribers.get(event_type, [])
            handlers_all = self.subscribers.get(EventType.CUSTOM, [])
            
            # Call handlers asynchronously
            tasks = []
            for handler in handlers + handlers_all:
                if asyncio.iscoroutinefunction(handler):
                    tasks.append(asyncio.create_task(handler(event)))
                else:
                    # Run sync handler in executor
                    tasks.append(asyncio.create_task(
                        asyncio.to_thread(handler, event)
                    ))
            
            # Wait for all handlers (fire-and-forget for async)
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            return event
    
    async def publish_vulnerability(
        self,
        source_agent: str,
        contract_path: str,
        vulnerability: str,
        severity: str,
        confidence: float
    ) -> Event:
        """Publish vulnerability flagged event.
        
        Args:
            source_agent: Agent flagging vulnerability
            contract_path: Contract path
            vulnerability: Vulnerability type
            severity: Severity level
            confidence: Confidence score
            
        Returns:
            Created event
        """
        return await self.publish(
            EventType.VULNERABILITY_FLAGGED,
            source_agent,
            {
                "contract_path": contract_path,
                "vulnerability": vulnerability,
                "severity": severity,
                "confidence": confidence
            }
        )
    
    async def get_event_history(
        self,
        event_type: Optional[EventType] = None,
        source_agent: Optional[str] = None,
        limit: int = 100
    ) -> List[Event]:
        """Get event history with filters.
        
        Args:
            event_type: Filter by event type
            source_agent: Filter by source agent
            limit: Maximum number of events
            
        Returns:
            Filtered event list
        """
        events = self.event_history[-limit:]
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if source_agent:
            events = [e for e in events if e.source_agent == source_agent]
        
        return events
    
    def get_subscriber_count(self, event_type: EventType) -> int:
        """Get number of subscribers for event type.
        
        Args:
            event_type: Event type
            
        Returns:
            Number of subscribers
        """
        return len(self.subscribers.get(event_type, []))


# Global broker instance (singleton pattern)
_global_broker: Optional[PubSubBroker] = None


def get_broker() -> PubSubBroker:
    """Get global pub-sub broker instance.
    
    Returns:
        Global broker instance
    """
    global _global_broker
    if _global_broker is None:
        _global_broker = PubSubBroker()
    return _global_broker

