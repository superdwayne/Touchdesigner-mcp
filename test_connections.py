#!/usr/bin/env python3
"""
Test script to verify TouchDesigner MCP connections
"""

from cursor_td_client import TouchDesignerClient, create_connected_chain

def test_basic_connections():
    """Test basic node creation and connections."""
    print("=== Testing Basic Connections ===")
    
    client = TouchDesignerClient()
    
    # Create a simple chain: Circle -> Text -> Out
    print("Creating connected chain...")
    result = create_connected_chain([
        {"type": "circle", "name": "MyCircle"},
        {"type": "text", "name": "MyText", "properties": {"text": "Connected!"}},
        {"type": "out", "name": "MyOutput"}
    ])
    
    print(f"Chain creation result: {result}")
    
    # List all components to see what was created
    print("\nListing components...")
    list_result = client.list_components("/project1")
    print(f"Components in /project1: {list_result}")
    
    return result

def test_individual_connections():
    """Test individual node creation with auto-connection."""
    print("\n=== Testing Individual Connections ===")
    
    client = TouchDesignerClient()
    
    # Create first node
    print("Creating first node...")
    result1 = client.create_component("sphere", "TestSphere", auto_connect=False)
    print(f"Sphere result: {result1}")
    
    # Create second node with auto-connection
    print("Creating second node with auto-connection...")
    result2 = client.create_component("box", "TestBox", auto_connect=True)
    print(f"Box result: {result2}")
    
    return {"sphere": result1, "box": result2}

if __name__ == "__main__":
    print("Starting connection tests...")
    
    # Test 1: Connected chain
    test_basic_connections()
    
    # Test 2: Individual connections
    test_individual_connections()
    
    print("\nTests completed. Check TouchDesigner to see if nodes are connected!") 