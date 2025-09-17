"""
TouchDesigner MCP Server - Standalone Version
Can run outside TouchDesigner for testing purposes
"""

import sys
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Mock TouchDesigner environment for standalone testing
TDF = False
print("Running TouchDesigner MCP Server in standalone mode (outside TouchDesigner)")

# Mock TouchDesigner classes and functions
class MockOp:
    def __init__(self, path):
        self.path = path
        self.name = path.split("/")[-1] if path else "mock_op"
        self.type = "mockType"
        self.children = []
        self.valid = True
        
    def destroy(self):
        print(f"Mock destroy: {self.path}")
        
    def parent(self):
        return MockOp("/mock_parent")
        
    def create(self, comp_type, name):
        print(f"Mock create: {comp_type} named {name} in {self.path}")
        return MockOp(f"{self.path}/{name}")
        
    def clear(self):
        print(f"Mock clear: {self.path}")
        return self
        
    @property
    def par(self):
        class MockPar:
            def __getattr__(self, name):
                class MockParam:
                    val = "mock_val"
                    def eval(self): return self.val
                return MockParam()
        return MockPar()

class MockTd:
    version = "mock.version"
    OP = MockOp
    
    # Mock component types
    class MockCompType: pass
    
    # DAT types
    textDAT = MockCompType()
    tableDAT = MockCompType()
    scriptDAT = MockCompType()
    opfindDAT = MockCompType()
    executeDAT = MockCompType()
    
    # TOP types
    circleTOP = MockCompType()
    noiseTOP = MockCompType()
    moviefileinTOP = MockCompType()
    constantTOP = MockCompType()
    rampTOP = MockCompType()
    textTOP = MockCompType()
    outTOP = MockCompType()
    renderTOP = MockCompType()
    
    # CHOP types
    constantCHOP = MockCompType()
    noiseCHOP = MockCompType()
    lfoCHOP = MockCompType()
    mathCHOP = MockCompType()
    selectCHOP = MockCompType()
    outCHOP = MockCompType()
    audiodeviceinCHOP = MockCompType()
    
    # SOP types
    sphereSOP = MockCompType()
    boxSOP = MockCompType()
    gridSOP = MockCompType()
    lineSOP = MockCompType()
    nullSOP = MockCompType()
    outSOP = MockCompType()
    
    # COMP types
    baseCOMP = MockCompType()
    containerCOMP = MockCompType()
    geometryCOMP = MockCompType()
    cameraCOMP = MockCompType()
    lightCOMP = MockCompType()
    buttonCOMP = MockCompType()
    sliderCOMP = MockCompType()
    windowCOMP = MockCompType()
    
    # MAT types
    phongMAT = MockCompType()
    pbrMAT = MockCompType()
    constantMAT = MockCompType()

class MockProject:
    name = "mock_project"

# Global mock objects
td = MockTd()
project = MockProject()

def op(path):
    if path == "/invalid_path": 
        return None
    return MockOp(path)

def run(command, delayFrames=0): 
    print(f"Mock run: {command}")

# Server configuration
SERVER_HOST = "localhost"
SERVER_PORT = 8001
server_running = False
server_instance = None
server_thread = None
connection_history = []

class ThreadingHTTPServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, dat_path, bind_and_activate=True):
        self.dat_path = dat_path
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)

class TouchDesignerMCPHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _handle_error(self, message, status_code=400):
        self._send_json({"error": message}, status_code)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            
            if path == "/status":
                self._send_json({
                    "status": "running", 
                    "touchdesigner": TDF, 
                    "version": "1.0.0",
                    "mode": "standalone"
                })
            else:
                self._handle_error("Endpoint not found", 404)
        except Exception as e:
            self._handle_error(f"Error handling GET: {str(e)}", 500)

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                return self._handle_error("Empty request body", 400)
            
            post_data = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(post_data)
            
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            
            if path == "/mcp":
                self._handle_mcp_request(data)
            elif path == "/context":
                self._handle_context_request(data)
            else:
                self._handle_error(f"Unknown POST endpoint: {path}", 404)
        except json.JSONDecodeError:
            self._handle_error("Invalid JSON", 400)
        except Exception as e:
            self._handle_error(f"Error handling POST: {str(e)}", 500)

    def _handle_mcp_request(self, data):
        method = data.get("method")
        params = data.get("params", {})
        
        if not method:
            return self._handle_error("Missing 'method'", 400)
        
        print(f"Received MCP method: {method} with params: {params}")
        
        try:
            if method == "create":
                result = self._tool_create_component(params)
            elif method == "delete":
                result = self._tool_delete_component(params)
            elif method == "set":
                result = self._tool_set_parameter(params)
            elif method == "execute_python":
                result = self._tool_execute_python(params)
            elif method == "list":
                result = self._tool_list_components(params)
            elif method == "get":
                result = self._tool_get_info(params)
            elif method == "list_parameters":
                result = self._tool_list_parameters(params)
            else:
                return self._handle_error(f"Unknown method: {method}", 400)
            
            self._send_json({"result": result})
            
        except Exception as e:
            self._handle_error(f"Error executing {method}: {str(e)}", 500)

    def _handle_context_request(self, data):
        query = data.get("query", "")
        context = self._get_context(query)
        self._send_json({"context": context})

    def _tool_create_component(self, params):
        """Create a component in TouchDesigner."""
        comp_type = params.get("type")
        name = params.get("name", "new_component")
        parent = params.get("parent", "/")
        
        print(f"Mock creating {comp_type} named {name} in {parent}")
        
        return {
            "content": [{"type": "text", "text": f"Mock created {comp_type} named {name} in {parent}"}],
            "success": True
        }

    def _tool_delete_component(self, params):
        """Delete a component in TouchDesigner."""
        path = params.get("path")
        
        print(f"Mock deleting component at {path}")
        
        return {
            "content": [{"type": "text", "text": f"Mock deleted component at {path}"}],
            "success": True
        }

    def _tool_set_parameter(self, params):
        """Set a parameter value in TouchDesigner."""
        path = params.get("path")
        parameter = params.get("parameter")
        value = params.get("value")
        
        print(f"Mock setting {parameter} = {value} on {path}")
        
        return {
            "content": [{"type": "text", "text": f"Mock set {parameter} = {value} on {path}"}],
            "success": True
        }

    def _tool_execute_python(self, params):
        """Execute Python code in TouchDesigner."""
        code = params.get("code", "")
        context = params.get("context", "")
        
        print(f"Mock executing Python code: {code[:100]}...")
        
        return {
            "content": [{"type": "text", "text": f"Mock executed Python code in TouchDesigner"}],
            "success": True
        }

    def _tool_list_components(self, params):
        """List components in TouchDesigner."""
        path = params.get("path", "/")
        
        print(f"Mock listing components at {path}")
        
        # Return mock component list
        mock_components = [
            {"name": "project1", "type": "baseCOMP", "path": "/project1"},
            {"name": "null1", "type": "nullSOP", "path": "/project1/null1"},
            {"name": "constant1", "type": "constantTOP", "path": "/project1/constant1"}
        ]
        
        return {
            "content": [{"type": "text", "text": f"Mock found {len(mock_components)} components at {path}"}],
            "components": mock_components,
            "success": True
        }

    def _tool_get_info(self, params):
        """Get information about a component in TouchDesigner."""
        path = params.get("path", "/")
        
        print(f"Mock getting info for {path}")
        
        return {
            "content": [{"type": "text", "text": f"Mock info for {path}"}],
            "info": {
                "name": path.split("/")[-1] if path else "root",
                "type": "mockType",
                "path": path,
                "valid": True
            },
            "success": True
        }

    def _tool_list_parameters(self, params):
        """List parameters of a component in TouchDesigner."""
        path = params.get("path", "/")
        
        print(f"Mock listing parameters for {path}")
        
        # Return mock parameters
        mock_parameters = [
            {"name": "par1", "value": "value1", "type": "string"},
            {"name": "par2", "value": 42, "type": "int"},
            {"name": "par3", "value": 3.14, "type": "float"}
        ]
        
        return {
            "content": [{"type": "text", "text": f"Mock found {len(mock_parameters)} parameters for {path}"}],
            "parameters": mock_parameters,
            "success": True
        }

    def _get_context(self, query):
        """Get context information for TouchDesigner."""
        return {
            "project": "mock_project",
            "version": "mock.version",
            "mode": "standalone",
            "query": query
        }

def start_mcp_server(dat_op=None):
    """Starts the MCP HTTP server in a separate thread."""
    global server_thread, server_instance, server_running
    
    if server_running:
        print("MCP Server already running.")
        return True
    
    print("Starting TouchDesigner MCP Server in standalone mode...")
    
    try:
        server_instance = ThreadingHTTPServer(
            (SERVER_HOST, SERVER_PORT), 
            TouchDesignerMCPHandler, 
            "/mock_dat"
        )
        
        print(f"Starting MCP server on port {SERVER_PORT}...")
        
        server_thread = threading.Thread(target=server_instance.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        server_running = True
        
        print(f"MCP Server started successfully on http://{SERVER_HOST}:{SERVER_PORT}")
        print("Features: create, delete, list, get, set, execute_python, list_parameters")
        print("Running in standalone mode (mock TouchDesigner environment)")
        
        return True
        
    except Exception as e:
        print(f"Failed to start MCP server: {e}")
        server_instance = None
        server_thread = None
        server_running = False
        return False

def stop_mcp_server():
    """Stops the MCP HTTP server."""
    global server_thread, server_instance, server_running
    
    if not server_running or not server_instance:
        print("MCP Server is not running.")
        return
    
    print("Shutting down MCP server...")
    
    try:
        server_instance.shutdown()
        server_instance.server_close()
        server_thread.join(timeout=5)
        print("MCP Server stopped.")
    except Exception as e:
        print(f"Error stopping MCP server: {e}")
    finally:
        server_instance = None
        server_thread = None
        server_running = False
        connection_history.clear()

def get_server_status():
    """Get the current server status."""
    global server_running
    return {
        "running": server_running,
        "host": SERVER_HOST,
        "port": SERVER_PORT,
        "version": "2.0.0",
        "mode": "standalone"
    }

if __name__ == "__main__":
    print("TouchDesigner MCP Server - Standalone Mode")
    print("This server runs outside TouchDesigner for testing purposes")
    print("All operations are mocked and will not affect a real TouchDesigner instance")
    print()
    
    if start_mcp_server():
        print("Server is running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            stop_mcp_server()
    else:
        print("Failed to start server.") 