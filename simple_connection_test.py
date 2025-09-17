#!/usr/bin/env python3
"""
Simple connection test for TouchDesigner MCP
"""

import json
import urllib.request

def make_request(method, params):
    """Make a request to the TouchDesigner MCP server."""
    try:
        data = json.dumps({"method": method, "params": params}).encode('utf-8')
        req = urllib.request.Request(
            "http://localhost:8053/mcp",
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
    except Exception as e:
        return {"error": f"Request failed: {e}"}

def test_simple_connection():
    """Test simple connection between two nodes."""
    print("=== Testing Simple Connection ===")
    
    # Step 1: Create a circle TOP
    print("1. Creating circle TOP...")
    result1 = make_request("create", {
        "type": "circle",
        "name": "DebugCircle",
        "parent": "/project1",
        "auto_connect": False
    })
    print(f"Circle creation result: {result1}")
    
    # Step 2: Create a text TOP with connection
    print("\n2. Creating text TOP with connection...")
    result2 = make_request("create", {
        "type": "text",
        "name": "DebugText",
        "parent": "/project1",
        "auto_connect": True,
        "connect_source": "/project1/DebugCircle",
        "connect_parameter": "input1"
    })
    print(f"Text creation result: {result2}")
    
    # Step 3: List components to see what was created
    print("\n3. Listing components...")
    result3 = make_request("list", {"path": "/project1"})
    print(f"List result: {result3}")
    
    # Step 4: Get info about the text node
    print("\n4. Getting info about DebugText...")
    result4 = make_request("get", {"path": "/project1/DebugText"})
    print(f"DebugText info: {result4}")
    
    return {"step1": result1, "step2": result2, "step3": result3, "step4": result4}

def test_manual_connection():
    """Test manual connection using set parameter."""
    print("\n=== Testing Manual Connection ===")
    
    # Step 1: Create nodes
    print("1. Creating nodes...")
    make_request("create", {"type": "circle", "name": "ManualCircle", "parent": "/project1", "auto_connect": False})
    make_request("create", {"type": "text", "name": "ManualText", "parent": "/project1", "auto_connect": False})
    
    # Step 2: Manually set the connection
    print("2. Manually setting connection...")
    result = make_request("set", {
        "path": "/project1/ManualText",
        "parameter": "input1",
        "value": "op('/project1/ManualCircle')"
    })
    print(f"Manual connection result: {result}")
    
    return result

if __name__ == "__main__":
    print("Starting connection tests...")
    
    # Test 1: Simple auto-connection
    test_simple_connection()
    
    # Test 2: Manual connection
    test_manual_connection()
    
    print("\nTests completed. Check TouchDesigner Textport for detailed logs.") 