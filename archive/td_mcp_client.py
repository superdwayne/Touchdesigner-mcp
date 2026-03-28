#!/usr/bin/env python3
"""
TouchDesigner MCP Client
Communicates with TouchDesigner MCP Server
"""

import json
import sys
import requests
from typing import Any, Dict, List, Optional

class TouchDesignerMCPClient:
    def __init__(self, server_url: str = "http://localhost:8001"):
        self.server_url = server_url
        self.base_url = f"{server_url}/mcp"
        
    def _make_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make a request to the TouchDesigner MCP server."""
        try:
            response = requests.post(
                self.base_url,
                json={"method": method, "params": params},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Request failed: {e}"}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON response: {e}"}
    
    def create_component(self, comp_type: str, name: str, parent: str = "/", **kwargs) -> Dict[str, Any]:
        """Create a component in TouchDesigner."""
        params = {
            "type": comp_type,
            "name": name,
            "parent": parent,
            **kwargs
        }
        return self._make_request("create", params)
    
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
    
    def execute_python(self, code: str, context: str = "") -> Dict[str, Any]:
        """Execute Python code in TouchDesigner."""
        return self._make_request("execute_python", {
            "code": code,
            "context": context
        })
    
    def list_components(self, path: str = "/") -> Dict[str, Any]:
        """List components in TouchDesigner."""
        return self._make_request("list", {"path": path})
    
    def get_info(self, path: str) -> Dict[str, Any]:
        """Get information about a component in TouchDesigner."""
        return self._make_request("get", {"path": path})
    
    def list_parameters(self, path: str) -> Dict[str, Any]:
        """List parameters of a component in TouchDesigner."""
        return self._make_request("list_parameters", {"path": path})
    
    def get_status(self) -> Dict[str, Any]:
        """Get server status."""
        try:
            response = requests.get(f"{self.server_url}/status")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Status request failed: {e}"}
    
    def auto_connect_all(self) -> Dict[str, Any]:
        """Automatically connect all components in the project."""
        return self._make_request("auto_connect", {})

def main():
    """Main function for command-line usage."""
    if len(sys.argv) < 2:
        print("Usage: python td_mcp_client.py <method> [params...]")
        print("Methods: create, delete, set, execute_python, list, get, list_parameters, auto_connect, status")
        sys.exit(1)
    
    method = sys.argv[1]
    client = TouchDesignerMCPClient()
    
    if method == "status":
        result = client.get_status()
    elif method == "create" and len(sys.argv) >= 4:
        comp_type = sys.argv[2]
        name = sys.argv[3]
        parent = sys.argv[4] if len(sys.argv) > 4 else "/"
        result = client.create_component(comp_type, name, parent)
    elif method == "delete" and len(sys.argv) >= 3:
        path = sys.argv[2]
        result = client.delete_component(path)
    elif method == "set" and len(sys.argv) >= 5:
        path = sys.argv[2]
        parameter = sys.argv[3]
        value = sys.argv[4]
        result = client.set_parameter(path, parameter, value)
    elif method == "execute_python" and len(sys.argv) >= 3:
        code = sys.argv[2]
        result = client.execute_python(code)
    elif method == "list":
        path = sys.argv[2] if len(sys.argv) > 2 else "/"
        result = client.list_components(path)
    elif method == "get" and len(sys.argv) >= 3:
        path = sys.argv[2]
        result = client.get_info(path)
    elif method == "list_parameters" and len(sys.argv) >= 3:
        path = sys.argv[2]
        result = client.list_parameters(path)
    elif method == "auto_connect":
        result = client.auto_connect_all()
    else:
        print(f"Invalid method or missing parameters: {method}")
        sys.exit(1)
    
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main() 