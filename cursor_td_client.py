#!/usr/bin/env python3
"""
TouchDesigner MCP Client for Cursor
Simple interface to interact with TouchDesigner MCP server
Uses only built-in Python libraries
"""

import json
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional

class TouchDesignerClient:
    def __init__(self, server_url: str = "http://localhost:8053"):
        self.server_url = server_url
        self.base_url = f"{server_url}/mcp"
    
    def _make_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make a request to the TouchDesigner MCP server."""
        try:
            data = json.dumps({"method": method, "params": params}).encode('utf-8')
            req = urllib.request.Request(
                self.base_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result
        except Exception as e:
            return {"error": f"Request failed: {e}"}
    
    def create_component(self, comp_type: str, name: str, parent: str = "/project1", auto_connect: bool = True, connect_source: str = None, connect_parameter: str = None, connect_type: str = "auto", nodex: int = None, nodey: int = None, **kwargs) -> Dict[str, Any]:
        """Create a component in TouchDesigner with optional auto-connection and positioning."""
        params = {
            "type": comp_type,
            "name": name,
            "parent": parent,
            "auto_connect": auto_connect,
            **kwargs
        }
        
        # Add positioning parameters if provided
        if nodex is not None:
            params["nodex"] = nodex
        if nodey is not None:
            params["nodey"] = nodey
        
        # Add connection parameters if provided
        if connect_source:
            params["connect_source"] = connect_source
        if connect_parameter:
            params["connect_parameter"] = connect_parameter
        if connect_type:
            params["connect_type"] = connect_type
            
        return self._make_request("create", params)
    
    def list_components(self, path: str = "/") -> Dict[str, Any]:
        """List components in TouchDesigner."""
        return self._make_request("list", {"path": path})
    
    def delete_component(self, path: str) -> Dict[str, Any]:
        """Delete a component in TouchDesigner."""
        return self._make_request("delete", {"path": path})
    
    def set_parameter(self, path: str, parameter: str, value: Any) -> Dict[str, Any]:
        """Set a parameter value in TouchDesigner."""
        return self._make_request("set", {
            "path": path,
            "parameter": parameter,
            "value": value
        })
    
    def get_info(self, path: str, parameter: Optional[str] = None) -> Dict[str, Any]:
        """Get information about a component or parameter."""
        params = {"path": path}
        if parameter:
            params["parameter"] = parameter
        return self._make_request("get", params)
    
    def execute_python(self, code: str, context: str = "/") -> Dict[str, Any]:
        """Execute Python code in TouchDesigner."""
        return self._make_request("execute_python", {
            "code": code,
            "context": context
        })
    
    def get_status(self) -> Dict[str, Any]:
        """Get server status."""
        try:
            with urllib.request.urlopen(f"{self.server_url}/api/status", timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            return {"error": f"Status request failed: {e}"}

# Example usage functions
def create_circle(name: str = "TestCircle", auto_connect: bool = True) -> Dict[str, Any]:
    """Create a circle TOP with auto-connection."""
    client = TouchDesignerClient()
    return client.create_component("circle", name, auto_connect=auto_connect)

def create_text(name: str = "TestText", text: str = "Hello from Cursor!", auto_connect: bool = True) -> Dict[str, Any]:
    """Create a text TOP with custom text and auto-connection."""
    client = TouchDesignerClient()
    return client.create_component("text", name, auto_connect=auto_connect, properties={"text": text})

def create_sphere(name: str = "TestSphere", auto_connect: bool = True) -> Dict[str, Any]:
    """Create a sphere SOP with auto-connection."""
    client = TouchDesignerClient()
    return client.create_component("sphere", name, auto_connect=auto_connect)

def create_connected_chain(components: list) -> Dict[str, Any]:
    """Create a chain of connected components with proper positioning."""
    client = TouchDesignerClient()
    results = []
    
    for i, comp in enumerate(components):
        comp_type = comp.get("type")
        name = comp.get("name", f"{comp_type}{i+1}")
        properties = comp.get("properties", {})
        
        # Calculate position for this component
        nodex = i * 200  # Space nodes horizontally
        nodey = 0  # Keep them at same Y level for a clean chain
        
        # Connect to previous component if not the first one
        connect_source = None
        if i > 0:
            prev_name = components[i-1].get("name", f"{components[i-1]['type']}{i}")
            connect_source = f"/project1/{prev_name}"
        
        result = client.create_component(
            comp_type, 
            name, 
            auto_connect=True,
            connect_source=connect_source,
            connect_parameter="input1",
            nodex=nodex,
            nodey=nodey,
            properties=properties
        )
        results.append(result)
    
    return {"results": results}

def list_all_components() -> Dict[str, Any]:
    """List all components in the project."""
    client = TouchDesignerClient()
    return client.list_components("/project1")

def execute_td_python(code: str) -> Dict[str, Any]:
    """Execute Python code in TouchDesigner."""
    client = TouchDesignerClient()
    return client.execute_python(code)

def test_connection_debug():
    """Test connection debugging by creating a simple chain."""
    client = TouchDesignerClient()
    
    # Create a simple test chain
    print("Creating test chain...")
    
    # Create first node
    result1 = client.create_component("circle", "TestCircle1", auto_connect=False)
    print(f"Created TestCircle1: {result1}")
    
    # Wait a moment for the first node to be created
    import time
    time.sleep(1)
    
    # Create second node with connection
    result2 = client.create_component(
        "text", 
        "TestText1", 
        auto_connect=True,
        connect_source="/TestCircle1",
        connect_parameter="input1"
    )
    print(f"Created TestText1: {result2}")
    
    # Wait and then list components to see what was created
    time.sleep(1)
    list_result = client.list_components()
    print(f"Current components: {list_result}")
    
    return {"test1": result1, "test2": result2, "list": list_result}

def debug_network_state():
    """Debug the current network state in TouchDesigner."""
    client = TouchDesignerClient()
    
    # Execute Python code to inspect the network
    debug_code = """
# Debug network state
print("=== NETWORK DEBUG ===")
print(f"Current project: {project.name}")

# List all operators in the project
root = op("/")
if root and root.valid:
    print(f"Root path: {root.path}")
    if hasattr(root, 'children'):
        print(f"Number of children: {len(root.children)}")
        for i, child in enumerate(root.children):
            if child and child.valid:
                print(f"Child {i}: {child.name} ({child.type}) at {child.path}")
                # Try to get input parameters
                try:
                    if hasattr(child, 'pars'):
                        inputs = [par.name for par in child.pars() if 'input' in par.name.lower()]
                        if inputs:
                            print(f"  Input parameters: {inputs}")
                except Exception as e:
                    print(f"  Error getting parameters: {e}")
    else:
        print("No children found")

# Check for specific test nodes
test_circle = op("/TestCircle1")
if test_circle and test_circle.valid:
    print(f"TestCircle1 found at {test_circle.path}")
    print(f"TestCircle1 type: {test_circle.type}")
else:
    print("TestCircle1 not found")

test_text = op("/TestText1")
if test_text and test_text.valid:
    print(f"TestText1 found at {test_text.path}")
    print(f"TestText1 type: {test_text.type}")
    # Check input parameters
    try:
        if hasattr(test_text, 'pars'):
            for par in test_text.pars():
                if 'input' in par.name.lower():
                    print(f"  Input parameter '{par.name}': {par.expr}")
    except Exception as e:
        print(f"  Error checking parameters: {e}")
else:
    print("TestText1 not found")

print("=== END DEBUG ===")
"""
    
    result = client.execute_python(debug_code)
    print(f"Debug result: {result}")
    return result

# Quick test function
def test_connection():
    """Test the connection to TouchDesigner."""
    client = TouchDesignerClient()
    status = client.get_status()
    print(f"TouchDesigner MCP Server Status: {status}")
    return status

if __name__ == "__main__":
    # Test the connection
    test_connection()
    
    # Example: Create a circle with auto-connection
    result = create_circle("MyCircle", auto_connect=True)
    print(f"Create circle result: {result}")
    
    # Example: Create text with auto-connection
    result = create_text("MyText", "Hello TouchDesigner!", auto_connect=True)
    print(f"Create text result: {result}")
    
    # Example: Create a connected chain
    chain = create_connected_chain([
        {"type": "circle", "name": "Circle1"},
        {"type": "text", "name": "Text1", "properties": {"text": "Connected!"}},
        {"type": "out", "name": "Output1"}
    ])
    print(f"Connected chain result: {chain}") 