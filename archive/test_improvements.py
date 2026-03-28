#!/usr/bin/env python3
"""
Test script to verify the improvements to bu.py
"""

from cursor_td_client import TouchDesignerClient

def test_improved_positioning():
    """Test improved positioning logic."""
    print("=== Testing Improved Positioning ===")
    
    client = TouchDesignerClient()
    
    # Create multiple nodes to test spacing
    print("Creating multiple nodes to test spacing...")
    
    nodes = [
        ("circle", "PosTest1"),
        ("text", "PosTest2"),
        ("sphere", "PosTest3"),
        ("box", "PosTest4"),
        ("noise", "PosTest5")
    ]
    
    results = []
    for node_type, node_name in nodes:
        result = client.create_component(node_type, node_name, auto_connect=True)
        results.append(result)
        print(f"Created {node_type} '{node_name}': {result}")
    
    return results

def test_debug_info():
    """Test that debug information is being logged."""
    print("\n=== Testing Debug Information ===")
    
    client = TouchDesignerClient()
    
    # Create a node that might not have standard input parameters
    print("Creating a node to test debug info...")
    result = client.create_component("out", "DebugTest", auto_connect=True)
    print(f"Debug test result: {result}")
    
    return result

if __name__ == "__main__":
    print("Testing improvements to bu.py...")
    
    # Test 1: Improved positioning
    test_improved_positioning()
    
    # Test 2: Debug information
    test_debug_info()
    
    print("\nImprovement tests completed!")
    print("Check TouchDesigner Textport for debug information and verify node spacing.") 