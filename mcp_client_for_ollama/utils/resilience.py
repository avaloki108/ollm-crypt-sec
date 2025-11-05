"""Resilience patterns: circuit breakers, exponential backoff, retry logic."""

import asyncio
import time
from enum import Enum
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import functools


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5  # Open circuit after N failures
    success_threshold: int = 2  # Close circuit after N successes (half-open)
    timeout: int = 60  # Seconds to wait before trying half-open
    expected_exception: type = Exception


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""
    failures: int = 0
    successes: int = 0
    last_failure_time: Optional[datetime] = None
    state: CircuitState = CircuitState.CLOSED
    total_calls: int = 0
    total_failures: int = 0


class CircuitBreaker:
    """Circuit breaker pattern for resilient service calls."""
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        """Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name (for logging)
            config: Configuration (uses defaults if None)
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection.
        
        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception if circuit is open or function fails
        """
        async with self._lock:
            # Check circuit state
            if self.stats.state == CircuitState.OPEN:
                # Check if timeout expired (try half-open)
                if self.stats.last_failure_time:
                    elapsed = (datetime.now() - self.stats.last_failure_time).seconds
                    if elapsed >= self.config.timeout:
                        self.stats.state = CircuitState.HALF_OPEN
                        self.stats.successes = 0
                    else:
                        raise Exception(
                            f"Circuit breaker {self.name} is OPEN. "
                            f"Wait {self.config.timeout - elapsed}s"
                        )
            
            # Try to execute
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Success
                await self._record_success()
                return result
                
            except self.config.expected_exception as e:
                await self._record_failure()
                raise e
    
    async def _record_success(self) -> None:
        """Record successful call."""
        self.stats.total_calls += 1
        self.stats.successes += 1
        self.stats.failures = 0
        
        if self.stats.state == CircuitState.HALF_OPEN:
            if self.stats.successes >= self.config.success_threshold:
                self.stats.state = CircuitState.CLOSED
                self.stats.successes = 0
    
    async def _record_failure(self) -> None:
        """Record failed call."""
        self.stats.total_calls += 1
        self.stats.total_failures += 1
        self.stats.failures += 1
        self.stats.last_failure_time = datetime.now()
        self.stats.successes = 0
        
        if self.stats.failures >= self.config.failure_threshold:
            self.stats.state = CircuitState.OPEN


class ExponentialBackoff:
    """Exponential backoff retry logic."""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        """Initialize exponential backoff.
        
        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential calculation
            jitter: Add random jitter to avoid thundering herd
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    async def retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Retry function with exponential backoff.
        
        Args:
            func: Function to retry
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception after all retries exhausted
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    delay = min(
                        self.initial_delay * (self.exponential_base ** attempt),
                        self.max_delay
                    )
                    
                    if self.jitter:
                        import random
                        delay *= (0.5 + random.random())
                    
                    await asyncio.sleep(delay)
                else:
                    raise last_exception
        
        raise last_exception


def with_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff: Optional[ExponentialBackoff] = None
):
    """Decorator for retry logic.
    
    Args:
        max_retries: Maximum retries
        initial_delay: Initial delay
        backoff: Custom backoff instance
    """
    def decorator(func: Callable) -> Callable:
        backoff_instance = backoff or ExponentialBackoff(
            max_retries=max_retries,
            initial_delay=initial_delay
        )
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await backoff_instance.retry(func, *args, **kwargs)
        
        return wrapper
    return decorator


class IdempotentTask:
    """Idempotent task wrapper to prevent duplicate work."""
    
    def __init__(self):
        """Initialize idempotent task manager."""
        self.completed_tasks: Dict[str, Any] = {}
        self.in_progress_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
    
    async def execute(
        self,
        task_id: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute task idempotently.
        
        Args:
            task_id: Unique task identifier
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Task result (cached if already completed)
        """
        async with self._lock:
            # Check if already completed
            if task_id in self.completed_tasks:
                return self.completed_tasks[task_id]
            
            # Check if in progress
            if task_id in self.in_progress_tasks:
                # Wait for existing task
                return await self.in_progress_tasks[task_id]
            
            # Start new task
            async def task_wrapper():
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                    self.completed_tasks[task_id] = result
                    return result
                finally:
                    if task_id in self.in_progress_tasks:
                        del self.in_progress_tasks[task_id]
            
            task = asyncio.create_task(task_wrapper())
            self.in_progress_tasks[task_id] = task
            
            return await task


def make_idempotent(task_manager: IdempotentTask):
    """Decorator to make function idempotent.
    
    Args:
        task_manager: IdempotentTask instance
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate task ID from function name and arguments
            import hashlib
            task_id = hashlib.md5(
                f"{func.__name__}:{str(args)}:{str(kwargs)}".encode()
            ).hexdigest()
            
            return await task_manager.execute(task_id, func, *args, **kwargs)
        
        return wrapper
    return decorator

