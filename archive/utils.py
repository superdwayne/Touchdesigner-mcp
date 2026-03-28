"""Utility functions for the TouchDesigner MCP server."""
from typing import Any, Dict, List, Optional


class DummyMemory:
    """
    A dummy class to stand in for the Memory class from the original example.
    This allows the server to run without needing the actual Mem0 client library.
    """
    
    def __init__(self):
        pass
    
    def add(self, messages: List[Dict[str, Any]], user_id: str) -> None:
        """Dummy implementation of adding memories."""
        print(f"Would add memory for user {user_id}: {messages}")
    
    def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        """Dummy implementation of retrieving all memories."""
        return [{"memory": "This is a dummy memory implementation."}]
    
    def search(self, query: str, user_id: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Dummy implementation of searching memories."""
        return [{"memory": f"This is a dummy search result for query: {query}"}]


def get_mem0_client() -> DummyMemory:
    """
    Returns a dummy Mem0 client.
    This is used as a placeholder for the original example's Memory client.
    
    Returns:
        A dummy memory client instance
    """
    return DummyMemory() 