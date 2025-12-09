"""
Retry Manager
Handles retry logic with exponential backoff
"""

import time
import random
from typing import Callable, Any
from loguru import logger

from app.config import config


class RetryManager:
    """
    Manages retry logic for failed operations
    Implements exponential backoff with jitter
    """
    
    @classmethod
    def should_retry(cls, retry_count: int, max_retries: int = None) -> bool:
        """
        Check if should retry based on retry count
        
        Args:
            retry_count: Current retry count
            max_retries: Maximum retries (default from config)
            
        Returns:
            True if should retry
        """
        if max_retries is None:
            max_retries = config.max_retries
        
        return retry_count < max_retries
    
    @classmethod
    def get_retry_delay(cls, retry_count: int, base_delay: int = 30) -> int:
        """
        Calculate retry delay with exponential backoff + jitter
        
        Formula: base_delay * (2 ^ retry_count) + random_jitter
        
        Args:
            retry_count: Current retry count (0-based)
            base_delay: Base delay in seconds
            
        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = base_delay * (2 ** retry_count)
        
        # Add jitter (±20%)
        jitter = delay * 0.2
        delay = delay + random.uniform(-jitter, jitter)
        
        # Cap at 10 minutes
        max_delay = 600
        delay = min(delay, max_delay)
        
        return int(delay)
    
    @classmethod
    def retry_with_backoff(
        cls,
        func: Callable[[], Any],
        max_retries: int = None,
        base_delay: int = 30,
        on_retry: Callable[[int, Exception], None] = None
    ) -> tuple[bool, Any, Exception | None]:
        """
        Execute function with retry and exponential backoff
        
        Args:
            func: Function to execute
            max_retries: Maximum retry attempts
            base_delay: Base delay between retries
            on_retry: Callback when retrying (retry_count, exception)
            
        Returns:
            (success, result, last_exception)
        """
        if max_retries is None:
            max_retries = config.max_retries
        
        retry_count = 0
        last_exception = None
        
        while retry_count <= max_retries:
            try:
                result = func()
                return True, result, None
            except Exception as e:
                last_exception = e
                
                if retry_count >= max_retries:
                    logger.error(f"Max retries ({max_retries}) exceeded: {e}")
                    break
                
                delay = cls.get_retry_delay(retry_count, base_delay)
                logger.warning(f"Retry {retry_count + 1}/{max_retries} in {delay}s: {e}")
                
                if on_retry:
                    on_retry(retry_count, e)
                
                time.sleep(delay)
                retry_count += 1
        
        return False, None, last_exception
    
    @classmethod
    def is_retryable_error(cls, error: Exception) -> bool:
        """
        Check if error is retryable (network issues, rate limits, etc.)
        
        Args:
            error: Exception to check
            
        Returns:
            True if error is retryable
        """
        error_str = str(error).lower()
        
        # Retryable errors
        retryable_patterns = [
            'timeout',
            'connection',
            'network',
            'rate limit',
            'too many requests',
            'quota exceeded',
            '503',
            '504',
            '429',
            'temporarily unavailable'
        ]
        
        for pattern in retryable_patterns:
            if pattern in error_str:
                return True
        
        # Non-retryable errors
        non_retryable_patterns = [
            'invalid',
            'not found',
            'unauthorized',
            '403',
            '404',
            '401',
            'permission denied'
        ]
        
        for pattern in non_retryable_patterns:
            if pattern in error_str:
                return False
        
        # Default to retryable for unknown errors
        return True


# Convenience functions
def should_retry(retry_count: int) -> bool:
    """Check if should retry"""
    return RetryManager.should_retry(retry_count)


def get_retry_delay(retry_count: int) -> int:
    """Get retry delay in seconds"""
    return RetryManager.get_retry_delay(retry_count)
