"""
TouchDesigner MCP Server - Fixed version 8
Provides HTTP endpoints for Claude to interact with TouchDesigner
Fixes:
- Expanded component type mapping in _tool_create_component
- Added robustness to _tool_list_components
- Uses run() to execute ALL TD API calls (including list, get) in the main thread.
- Returns structured result object { "content": [{ "type": "text", "text": "Command queued..." }] } for ALL commands.
  NOTE: Results for list/get are NOT returned to Claude, only printed in TD Textport.
"""

import sys
import json
import threading
import time
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Import TouchDesigner-specific modules
try:
    import td
    # Import specific operator types needed for mapping
    from td import (
        textDAT, tableDAT, scriptDAT, opfindDAT, executeDAT,
        circleTOP, noiseTOP, moviefileinTOP, constantTOP, rampTOP, textTOP, outTOP, renderTOP, 
        constantCHOP, noiseCHOP, lfoCHOP, mathCHOP, selectCHOP, outCHOP, audiodeviceinCHOP,
        sphereSOP, boxSOP, gridSOP, lineSOP, nullSOP, outSOP,
        baseCOMP, containerCOMP, geometryCOMP, cameraCOMP, lightCOMP, buttonCOMP, sliderCOMP, windowCOMP,
        phongMAT, pbrMAT, constantMAT
    )
    TDF = True
except ImportError:
    TDF = False
    print("Not running inside TouchDesigner. Mock functions will be used.")
    # Mock td and op for testing outside TouchDesigner
    class MockOp:
        def __init__(self, path):
            self.path = path
            self.name = path.split("/")[-1] if path else "mock_op"
            self.type = "mockType"
            self.children = []
            self.pars = lambda: []
            self.text = "mock text"
            self.valid = True # Mock validity
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
        # Add mock component types
        class MockCompType: pass
        textDAT = MockCompType(); tableDAT = MockCompType(); scriptDAT = MockCompType(); opfindDAT = MockCompType(); executeDAT = MockCompType()
        circleTOP = MockCompType(); noiseTOP = MockCompType(); moviefileinTOP = MockCompType(); constantTOP = MockCompType(); rampTOP = MockCompType(); textTOP = MockCompType(); outTOP = MockCompType()
        constantCHOP = MockCompType(); noiseCHOP = MockCompType(); lfoCHOP = MockCompType(); mathCHOP = MockCompType(); selectCHOP = MockCompType(); outCHOP = MockCompType(); audiodeviceinCHOP = MockCompType()
        sphereSOP = MockCompType(); boxSOP = MockCompType(); gridSOP = MockCompType(); lineSOP = MockCompType(); nullSOP = MockCompType(); outSOP = MockCompType()
        baseCOMP = MockCompType(); containerCOMP = MockCompType(); geometryCOMP = MockCompType(); cameraCOMP = MockCompType(); lightCOMP = MockCompType(); buttonCOMP = MockCompType(); sliderCOMP = MockCompType()
        phongMAT = MockCompType(); pbrMAT = MockCompType(); constantMAT = MockCompType()

    class MockProject: name = "mock_project"
    td = MockTd(); project = MockProject()
    def op(path):
        if path == "/invalid_path": return None
        return MockOp(path)
    def run(command, delayFrames=0): print(f"Mock run: {command}")
    # Define mock component types if needed for create
    textDAT = td.textDAT; tableDAT = td.tableDAT; scriptDAT = td.scriptDAT; opfindDAT = td.opfindDAT; executeDAT = td.executeDAT
    circleTOP = td.circleTOP; noiseTOP = td.noiseTOP; moviefileinTOP = td.moviefileinTOP; constantTOP = td.constantTOP; rampTOP = td.rampTOP; textTOP = td.textTOP; outTOP = td.outTOP
    constantCHOP = td.constantCHOP; noiseCHOP = td.noiseCHOP; lfoCHOP = td.lfoCHOP; mathCHOP = td.mathCHOP; selectCHOP = td.selectCHOP; outCHOP = td.outCHOP; audiodeviceinCHOP = td.audiodeviceinCHOP
    sphereSOP = td.sphereSOP; boxSOP = td.boxSOP; gridSOP = td.gridSOP; lineSOP = td.lineSOP; nullSOP = td.nullSOP; outSOP = td.outSOP
    baseCOMP = td.baseCOMP; containerCOMP = td.containerCOMP; geometryCOMP = td.geometryCOMP; cameraCOMP = td.cameraCOMP; lightCOMP = td.lightCOMP; buttonCOMP = td.buttonCOMP; sliderCOMP = td.sliderCOMP
    phongMAT = td.phongMAT; pbrMAT = td.pbrMAT; constantMAT = td.constantMAT

# --- Helper Functions for run() ---
# These functions run in the main TD thread

def _run_create(params_json):
    """Creates a component in the main thread."""
    try:
        params = json.loads(params_json)
        comp_type_str = params.get("type")
        name = params.get("name")
        parent_path = params.get("parent", "/")
        properties = params.get("properties", {})
        # Add position parameters with defaults if not provided
        node_x = params.get("nodex", None)
        node_y = params.get("nodey", None)
        # Add connection parameters
        connect_to_path = params.get("connect_to", None)
        connect_input = params.get("connect_input", 0)

        if not comp_type_str: raise ValueError("Missing type")

        comp_type_map = {
            "text": textDAT, "table": tableDAT, "script": scriptDAT, "opfind": opfindDAT, "execute": executeDAT,
            "circle": circleTOP, "noise": noiseTOP, "moviefilein": moviefileinTOP, "constant": constantTOP, 
            "ramp": rampTOP, "texttop": textTOP, "out": outTOP, "render": renderTOP,
            "constantchop": constantCHOP, "noisechop": noiseCHOP, "lfo": lfoCHOP, "math": mathCHOP, 
            "selectchop": selectCHOP, "outchop": outCHOP, "audiodevicein": audiodeviceinCHOP,
            "sphere": sphereSOP, "box": boxSOP, "grid": gridSOP, "line": lineSOP, "geometry": geometryCOMP, 
            "nullsop": nullSOP, "outsop": outSOP,
            "base": baseCOMP, "container": containerCOMP, "geometrycomp": geometryCOMP, 
            "camera": cameraCOMP, "cam": cameraCOMP, "light": lightCOMP, 
            "button": buttonCOMP, "slider": sliderCOMP, "window": windowCOMP,
            "phong": phongMAT, "pbr": pbrMAT, "constantmat": constantMAT,
        }
        comp_type_key = comp_type_str.lower().replace(" ", "").replace("comp", "").replace("sop", "").replace("top", "").replace("dat", "").replace("mat", "")
        comp_type = comp_type_map.get(comp_type_key)
        if comp_type_key == 'geometry': comp_type = geometryCOMP # Special case

        if not comp_type:
            try:
                comp_type = getattr(td, comp_type_str, None)
                if not isinstance(comp_type, type) or not issubclass(comp_type, td.OP): comp_type = None
            except Exception: comp_type = None
            if not comp_type: raise ValueError(f"Unsupported type: {comp_type_str}")

        if not name:
            base_name = comp_type_str.lower().replace("comp", "").replace("sop", "").replace("top", "").replace("dat", "").replace("mat", "")
            i = 1; name = f"{base_name}{i}";
            while op(f"{parent_path}/{name}"):
                i += 1
                name = f"{base_name}{i}"

        parent_op = op(parent_path)
        if not parent_op or not parent_op.valid: raise ValueError(f"Invalid parent: {parent_path}")

        new_op = parent_op.create(comp_type, name)
        if not new_op: raise RuntimeError(f"Failed to create {name} in {parent_path}")

        # Set node position if provided or use auto-positioning
        if node_x is not None and node_y is not None:
            new_op.nodeX = node_x
            new_op.nodeY = node_y
        else:
            # Auto-position: Get count of existing nodes and use it for spacing
            existing_nodes = len(parent_op.children) if hasattr(parent_op, 'children') else 1
            # Space nodes in a grid pattern (adjust multipliers as needed)
            grid_size = 300  # Increase this value for more spacing
            cols = 4  # Number of columns in the grid
            row = (existing_nodes - 1) // cols
            col = (existing_nodes - 1) % cols
            new_op.nodeX = col * grid_size
            new_op.nodeY = row * grid_size
            print(f"Auto-positioned node at ({new_op.nodeX}, {new_op.nodeY})")

        # Handle automatic connections
        if connect_to_path:
            source_op = op(connect_to_path)
            if source_op and source_op.valid:
                try:
                    # Check if both operators are of compatible types
                    if hasattr(new_op, 'inputs') and len(new_op.inputs) > connect_input:
                        new_op.inputs[connect_input] = source_op
                        print(f"Connected {source_op.path} to input {connect_input} of {new_op.path}")
                except Exception as conn_err:
                    print(f"Connection error: {conn_err}")
        
        # Auto-connect to previous node of same family if no explicit connection
        elif not connect_to_path:
            # Get the operator type family (TOP, CHOP, SOP, etc.)
            op_family = None
            if hasattr(new_op, 'type'):
                op_type = new_op.type
                if op_type.endswith('TOP'): op_family = 'TOP'
                elif op_type.endswith('CHOP'): op_family = 'CHOP'
                elif op_type.endswith('SOP'): op_family = 'SOP'
                elif op_type.endswith('MAT'): op_family = 'MAT'
                elif op_type.endswith('COMP'): op_family = 'COMP'
            
            if op_family and hasattr(new_op, 'inputs') and len(new_op.inputs) > 0:
                # Find the most recently created operator of the same family
                siblings = []
                if hasattr(parent_op, 'children'):
                    for child in parent_op.children:
                        if child and child.valid and child.path != new_op.path:
                            if hasattr(child, 'type') and child.type.endswith(op_family):
                                siblings.append(child)
                
                # Sort by creation time or node position as a proxy for creation order
                if siblings:
                    # Use X position as a proxy for creation order
                    siblings.sort(key=lambda x: getattr(x, 'nodeX', 0))
                    latest_sibling = siblings[-1]
                    try:
                        new_op.inputs[0] = latest_sibling
                        print(f"Auto-connected {latest_sibling.path} to {new_op.path}")
                    except Exception as auto_conn_err:
                        print(f"Auto-connection error: {auto_conn_err}")

        if properties:
            for key, value in properties.items():
                try:
                    param_obj = getattr(new_op.par, key, None)
                    if param_obj:
                        current_val = param_obj.val; target_type = type(current_val)
                        try:
                            if target_type == bool: value_conv = str(value).lower() in ["true", "1", "on"]
                            elif target_type == int: value_conv = int(value)
                            elif target_type == float: value_conv = float(value)
                            else: value_conv = str(value)
                        except ValueError: value_conv = str(value)
                        param_obj.val = value_conv
                    # else: print(f"MCP Run Warning: Param 			'{key}' not found on {new_op.path}") # Optional warning
                except Exception as e: print(f"MCP Run Warning: Failed to set {key} on {new_op.path}: {e}")

        print(f"MCP Run: Created component at {new_op.path}")
    except Exception as e:
        print(f"MCP Run Error (_run_create): {e}")

def _run_delete(params_json):
    """Deletes a component in the main thread."""
    try:
        params = json.loads(params_json)
        path = params.get("path")
        if not path: raise ValueError("Missing path")
        component = op(path)
        if not component or not component.valid: raise ValueError(f"Invalid component: {path}")
        parent = component.parent(); name = component.name
        component.destroy()
        parent_path = parent.path if parent and parent.valid else "(invalid)"
        print(f"MCP Run: Deleted {name} from {parent_path}")
    except Exception as e:
        print(f"MCP Run Error (_run_delete): {e}")

def _run_set(params_json):
    """Sets a parameter in the main thread."""
    try:
        params = json.loads(params_json)
        path = params.get("path"); parameter = params.get("parameter"); value_str = params.get("value")
        if not path or not parameter or value_str is None: raise ValueError("Missing params")
        component = op(path)
        if not component or not component.valid: raise ValueError(f"Invalid component: {path}")
        param_obj = getattr(component.par, parameter, None)
        if param_obj:
            current_val = param_obj.val; target_type = type(current_val)
            try:
                if target_type == bool: value = str(value_str).lower() in ["true", "1", "on"]
                elif target_type == int: value = int(value_str)
                elif target_type == float: value = float(value_str)
                else: value = str(value_str)
            except ValueError: value = str(value_str)
            param_obj.val = value
            print(f"MCP Run: Set {parameter}={value} on {path}")
        else: raise ValueError(f"Parameter not found: {parameter}")
    except Exception as e:
        print(f"MCP Run Error (_run_set): {e}")

def _run_execute(params_json):
    """Executes Python code in the main thread."""
    try:
        params = json.loads(params_json)
        code = params.get("code"); context_path = params.get("context")
        if not code: raise ValueError("Missing code")
        exec_globals = globals().copy(); exec_locals = {}
        if TDF:
            exec_globals["td"] = td; exec_globals["op"] = op; exec_globals["project"] = project
            context_op = op(context_path) if context_path else op("/")
            # Check if context_op exists and is valid before setting it as 'me'
            if context_op and context_op.valid: 
                exec_globals["me"] = context_op
            else: 
                exec_globals["me"] = op("/")
                
        # Add a try-except block around the exec to catch and report specific errors
        try:
            exec(code, exec_globals, exec_locals)
            result_val = exec_locals.get("result", "Python code executed via run().")
            
            # Fix for td.Parameter not existing
            is_td_object = False
            if TDF:
                # Check for TouchDesigner-specific types without directly referencing td.Parameter
                if hasattr(td, 'OP') and isinstance(result_val, td.OP):
                    is_td_object = True
                # Check for Parameter type by name rather than direct reference
                elif hasattr(result_val, '__class__') and result_val.__class__.__name__ in ['Parameter', 'ParGroup']:
                    is_td_object = True
            
            if is_td_object:
                result_str = str(result_val)
            else:
                try: json.dumps(result_val); result_str = result_val
                except TypeError: result_str = str(result_val)
            print(f"MCP Run: Executed Python. Result: {result_str}")
        except IndexError as idx_error:
            print(f"MCP Run Python Execution Error (IndexError): {idx_error}")
            print(f"Tip: This may be caused by trying to access a list element that doesn't exist.")
            print(f"Tip: Always check list length before accessing elements: 'if index < len(my_list): ...'")
            raise idx_error
        except AttributeError as attr_error:
            error_msg = str(attr_error)
            if "has no attribute 'clear'" in error_msg:
                print(f"MCP Run Python Execution Error: {attr_error}")
                print(f"Tip: The clear() method is not available on all component types. It's typically used with text DATs and table DATs.")
                print(f"Tip: Check component type with 'print(op(\"/path\").type)' and verify method availability with 'hasattr(op(\"/path\"), \"clear\")'")
            elif "has no attribute 'borderless'" in error_msg or "ParCollection" in error_msg:
                print(f"MCP Run Python Execution Error: {attr_error}")
                print(f"Tip: Parameter not found on this component type.")
                print(f"Tip: Check available parameters with 'print([p.name for p in op(\"/path\").pars()])'")
            elif "has no attribute 'Parameter'" in error_msg:
                print(f"MCP Run Python Execution Error: {attr_error}")
                print(f"Tip: The TouchDesigner module structure may have changed or the Parameter class is accessed differently.")
                print(f"Tip: Try using type checking with isinstance() or check the class name with __class__.__name__ instead.")
                print(f"Tip: You can print available attributes with 'print(dir(td))' to see what's available.")
            else:
                print(f"MCP Run Python Execution Error (AttributeError): {attr_error}")
                print(f"Tip: Check if the attribute exists before accessing it with 'hasattr(obj, \"attribute_name\")'")
            raise attr_error
        except Exception as exec_error:
            print(f"MCP Run Python Execution Error: {exec_error}")
            raise exec_error  # Re-raise to be caught by the outer try-except
    except Exception as e:
        print(f"MCP Run Error (_run_execute): {e}")

def _run_list(params_json):
    """Lists components in the main thread."""
    try:
        params = json.loads(params_json)
        path = params.get("path", "/"); type_filter = params.get("type")
        target_op = op(path)
        if not target_op or not target_op.valid: print(f"MCP Run List Warning: Path invalid {path}"); return
        components = []
        if hasattr(target_op, 'children'):
            for child in target_op.children:
                if child and child.valid:
                    child_type = getattr(child, 'type', 'N/A'); child_name = getattr(child, 'name', 'N/A'); child_path = getattr(child, 'path', 'N/A')
                    if not type_filter or child_type == type_filter: components.append({"path": child_path, "type": child_type, "name": child_name})
        print(f"MCP Run List Result ({path}): {json.dumps(components)}")
    except Exception as e:
        print(f"MCP Run Error (_run_list): {e}")

def _run_get(params_json):
    """Gets component/parameter info in the main thread."""
    try:
        params = json.loads(params_json)
        path = params.get("path"); parameter = params.get("parameter")
        if not path: raise ValueError("Missing path")
        op_obj = op(path)
        if not op_obj or not op_obj.valid:
            result = {"path": path, "exists": False, "error": "Component not found or invalid"}
        elif parameter:
            param_obj = getattr(op_obj.par, parameter, None)
            if param_obj is not None:
                 val = param_obj.eval(); val_str = str(val) if isinstance(val, (td.OP, td.Parameter, td.ParGroup)) else val
                 result = {"path": path, "exists": True, "parameter": parameter, "value": val_str, "type": type(val).__name__}
            else: result = {"path": path, "exists": True, "parameter": parameter, "error": "Parameter not found"}
        else:
            param_list = [p.name for p in op_obj.pars()] if hasattr(op_obj, "pars") else []
            result = {"path": path, "exists": True, "type": op_obj.type if hasattr(op_obj, "type") else "N/A", "name": op_obj.name if hasattr(op_obj, "name") else "N/A", "parameters": param_list}
        print(f"MCP Run Get Result ({path}): {json.dumps(result)}")
    except Exception as e:
        print(f"MCP Run Error (_run_get): {e}")

def _run_list_parameters(params_json):
    """Lists all parameters of a component in the main thread."""
    try:
        params = json.loads(params_json)
        path = params.get("path", "/")
        target_op = op(path)
        if not target_op or not target_op.valid:
            print(f"MCP Run List Parameters Warning: Path invalid {path}")
            return
            
        # Get component type
        comp_type = getattr(target_op, 'type', 'N/A')
        
        # Get all parameters
        parameters = []
        if hasattr(target_op, 'pars'):
            parameters = [p.name for p in target_op.pars()]
            
        print(f"MCP Run: Component {path} is of type {comp_type}")
        print(f"MCP Run: Available parameters: {parameters}")
    except Exception as e:
        print(f"MCP Run Error (_run_list_parameters): {e}")

def _run_auto_connect(params_json):
    """Auto-connects components based on smart rules in the main thread."""
    try:
        params = json.loads(params_json)
        source_path = params.get("source")
        target_path = params.get("target")
        connection_type = params.get("connection_type", "auto")  # auto, input, output, both
        
        if not source_path or not target_path:
            raise ValueError("Missing source or target path")
            
        source_op = op(source_path)
        target_op = op(target_path)
        
        if not source_op or not source_op.valid:
            raise ValueError(f"Invalid source component: {source_path}")
        if not target_op or not target_op.valid:
            raise ValueError(f"Invalid target component: {target_path}")
            
        connections_made = []
        
        # Smart connection logic based on component types
        source_type = getattr(source_op, 'type', '')
        target_type = getattr(target_op, 'type', '')
        
        # Determine connection direction based on component types
        if connection_type == "auto":
            # TOP to TOP connections (visual pipeline)
            if source_type.endswith('TOP') and target_type.endswith('TOP'):
                if hasattr(target_op, 'inputs') and len(target_op.inputs) > 0:
                    target_op.inputs[0] = source_op
                    connections_made.append(f"TOP output -> TOP input")
                    
            # CHOP to CHOP connections (audio pipeline)
            elif source_type.endswith('CHOP') and target_type.endswith('CHOP'):
                if hasattr(target_op, 'inputs') and len(target_op.inputs) > 0:
                    target_op.inputs[0] = source_op
                    connections_made.append(f"CHOP output -> CHOP input")
                    
            # SOP to SOP connections (geometry pipeline)
            elif source_type.endswith('SOP') and target_type.endswith('SOP'):
                if hasattr(target_op, 'inputs') and len(target_op.inputs) > 0:
                    target_op.inputs[0] = source_op
                    connections_made.append(f"SOP output -> SOP input")
                    
            # DAT to DAT connections (data pipeline)
            elif source_type.endswith('DAT') and target_type.endswith('DAT'):
                if hasattr(target_op, 'inputs') and len(target_op.inputs) > 0:
                    target_op.inputs[0] = source_op
                    connections_made.append(f"DAT output -> DAT input")
                    
            # Cross-family connections (common patterns)
            elif source_type.endswith('TOP') and target_type.endswith('COMP'):
                # TOP to COMP (visual to container)
                if hasattr(target_op, 'inputs') and len(target_op.inputs) > 0:
                    target_op.inputs[0] = source_op
                    connections_made.append(f"TOP -> COMP (visual input)")
                    
            elif source_type.endswith('CHOP') and target_type.endswith('COMP'):
                # CHOP to COMP (audio to container)
                if hasattr(target_op, 'inputs') and len(target_op.inputs) > 0:
                    target_op.inputs[0] = source_op
                    connections_made.append(f"CHOP -> COMP (audio input)")
                    
            elif source_type.endswith('SOP') and target_type.endswith('COMP'):
                # SOP to COMP (geometry to container)
                if hasattr(target_op, 'inputs') and len(target_op.inputs) > 0:
                    target_op.inputs[0] = source_op
                    connections_made.append(f"SOP -> COMP (geometry input)")
                    
        elif connection_type == "input":
            # Force input connection
            if hasattr(target_op, 'inputs') and len(target_op.inputs) > 0:
                target_op.inputs[0] = source_op
                connections_made.append(f"forced input connection")
                
        elif connection_type == "output":
            # Force output connection
            if hasattr(source_op, 'outputs') and len(source_op.outputs) > 0:
                source_op.outputs[0] = target_op
                connections_made.append(f"forced output connection")
                
        elif connection_type == "both":
            # Bidirectional connection
            if hasattr(target_op, 'inputs') and len(target_op.inputs) > 0:
                target_op.inputs[0] = source_op
                connections_made.append(f"input connection")
            if hasattr(source_op, 'outputs') and len(source_op.outputs) > 0:
                source_op.outputs[0] = target_op
                connections_made.append(f"output connection")
        
        # Record connection in history
        if connections_made:
            connection_info = {
                "source": source_path,
                "target": target_path,
                "source_type": source_type,
                "target_type": target_type,
                "connections": connections_made,
                "timestamp": time.time()
            }
            connection_history.append(connection_info)
            
            print(f"MCP Run: Auto-connected {source_path} -> {target_path}")
            print(f"MCP Run: Connection types: {', '.join(connections_made)}")
            print(f"MCP Run: Total connections made: {len(connection_history)}")
        else:
            print(f"MCP Run: No valid connections found between {source_path} and {target_path}")
            
    except Exception as e:
        print(f"MCP Run Error (_run_auto_connect): {e}")

def _run_connect_nodes(params_json):
    """Connects multiple nodes in sequence or parallel in the main thread."""
    try:
        params = json.loads(params_json)
        nodes = params.get("nodes", [])  # List of node paths
        connection_mode = params.get("mode", "sequence")  # sequence, parallel, custom
        custom_connections = params.get("custom_connections", [])  # List of [source, target] pairs
        
        if not nodes and not custom_connections:
            raise ValueError("No nodes or custom connections specified")
            
        connections_made = []
        
        if connection_mode == "sequence":
            # Connect nodes in sequence: node1 -> node2 -> node3 -> ...
            for i in range(len(nodes) - 1):
                source_path = nodes[i]
                target_path = nodes[i + 1]
                
                source_op = op(source_path)
                target_op = op(target_path)
                
                if source_op and source_op.valid and target_op and target_op.valid:
                    if hasattr(target_op, 'inputs') and len(target_op.inputs) > 0:
                        target_op.inputs[0] = source_op
                        connections_made.append(f"{source_path} -> {target_path}")
                        
        elif connection_mode == "parallel":
            # Connect all nodes to a central hub (first node as hub)
            if len(nodes) > 1:
                hub_path = nodes[0]
                hub_op = op(hub_path)
                
                if hub_op and hub_op.valid:
                    for i in range(1, len(nodes)):
                        node_path = nodes[i]
                        node_op = op(node_path)
                        
                        if node_op and node_op.valid:
                            if hasattr(hub_op, 'inputs') and len(hub_op.inputs) > i - 1:
                                hub_op.inputs[i - 1] = node_op
                                connections_made.append(f"{node_path} -> {hub_path} (input {i-1})")
                                
        elif connection_mode == "custom":
            # Use custom connection pairs
            for connection in custom_connections:
                if len(connection) == 2:
                    source_path = connection[0]
                    target_path = connection[1]
                    
                    source_op = op(source_path)
                    target_op = op(target_path)
                    
                    if source_op and source_op.valid and target_op and target_op.valid:
                        if hasattr(target_op, 'inputs') and len(target_op.inputs) > 0:
                            target_op.inputs[0] = source_op
                            connections_made.append(f"{source_path} -> {target_path}")
        
        if connections_made:
            print(f"MCP Run: Connected {len(connections_made)} node pairs")
            for conn in connections_made:
                print(f"MCP Run: {conn}")
        else:
            print(f"MCP Run: No connections made")
            
    except Exception as e:
        print(f"MCP Run Error (_run_connect_nodes): {e}")

def _run_get_connection_history(params_json):
    """Gets the connection history in the main thread."""
    try:
        params = json.loads(params_json)
        limit = params.get("limit", 10)  # Number of recent connections to return
        
        recent_connections = connection_history[-limit:] if connection_history else []
        
        print(f"MCP Run: Connection history (last {len(recent_connections)} connections):")
        for i, conn in enumerate(recent_connections):
            print(f"MCP Run: {i+1}. {conn['source']} -> {conn['target']} ({', '.join(conn['connections'])})")
            
    except Exception as e:
        print(f"MCP Run Error (_run_get_connection_history): {e}")

# --- MCP Server Implementation (Port 8052) ---

# Global server state
server_thread = None
server_instance = None
server_running = False
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8052

# Auto-connector state
connection_history = []
auto_connect_enabled = True

class ThreadingHTTPServer(HTTPServer):
    """Allow storing DAT path."""
    def __init__(self, server_address, RequestHandlerClass, dat_path, bind_and_activate=True):
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)
        self.dat_path = dat_path # Store the path of the DAT running the server

class TouchDesignerMCPHandler(BaseHTTPRequestHandler):
    """Handler for TouchDesigner MCP requests"""

    def log_message(self, format, *args): return # Suppress logs

    def _send_json(self, data, status=200):
        try:
            self.send_response(status)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        except Exception as e: print(f"Error sending JSON response: {e}")

    def _handle_error(self, message, status_code=400):
        print(f"MCP Server Error: {message} (Status: {status_code})")
        self._send_json({"error": {"message": message, "code": -32000}}, status=status_code)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        try:
            parsed_path = urlparse(self.path); path = parsed_path.path
            if path == "/api/status" or path == "/":
                self._send_json({
                    "status": "running", 
                    "touchdesigner": True, 
                    "version": "2.0.0",
                    "features": [
                        "create", "delete", "list", "get", "set", 
                        "execute_python", "list_parameters",
                        "auto_connect", "connect_nodes", "get_connection_history",
                        "smart_positioning", "connection_history"
                    ]
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
        
        print(f"\n=== MCP Request: {method} ===")
        print(f"Params: {json.dumps(params, indent=2)}")
        
        try:
            result = None
            if method == "create": 
                result = self._tool_create_component(params)
            elif method == "list": 
                result = self._tool_list_components(params)
            elif method == "delete": 
                result = self._tool_delete_component(params)
            elif method == "set": 
                result = self._tool_set_parameter(params)
            elif method == "get": 
                result = self._tool_get_info(params)
            elif method == "execute_python": 
                result = self._tool_execute_python(params)
            elif method == "list_parameters": 
                result = self._tool_list_parameters(params)
            else: 
                return self._handle_error(f"Unknown MCP method: {method}", 404)
            
            self._send_json({"result": result})
            
        except Exception as e:
            error_message = f"Error executing MCP method '{method}': {str(e)}"
            print(error_message)
            traceback.print_exc()
            self._send_json({"error": {"message": error_message, "code": -32001}}, status=500)

    def _handle_context_request(self, data):
        query = data.get("query", "")
        print(f"Received context query: {query}")
        
        try:
            context_items = self._get_context(query)
            self._send_json({"contextItems": context_items})
        except Exception as e:
            error_message = f"Error getting context: {str(e)}"
            print(error_message)
            self._handle_error(error_message, 500)

    # --- Tool Implementation Functions --- (ALL use run())

    def _tool_create_component(self, params):
        """Queues component creation in the main thread."""
        try:
            if not params.get("type"): 
                raise ValueError("Missing type param")
            
            params_json = json.dumps(params)
            run(f"mod('{self.server.dat_path}')._run_create({repr(params_json)})", delayFrames=1)
            
            # Return structured response for Claude Desktop
            return {
                "content": [{
                    "type": "text", 
                    "text": f"Command queued: create {params.get('type')} component"
                }]
            }
        except Exception as e: 
            raise RuntimeError(f"Error queuing create command: {e}")

    def _tool_delete_component(self, params):
        """Queues component deletion in the main thread."""
        try:
            if not params.get("path"): 
                raise ValueError("Missing path param")
            
            params_json = json.dumps(params)
            run(f"mod('{self.server.dat_path}')._run_delete({repr(params_json)})", delayFrames=1)
            
            return {
                "content": [{
                    "type": "text", 
                    "text": f"Command queued: delete component at {params.get('path')}"
                }]
            }
        except Exception as e: 
            raise RuntimeError(f"Error queuing delete command: {e}")

    def _tool_set_parameter(self, params):
        """Queues parameter setting in the main thread."""
        try:
            if not params.get("path") or not params.get("parameter") or params.get("value") is None:
                raise ValueError("Missing params for set")
            
            params_json = json.dumps(params)
            run(f"mod('{self.server.dat_path}')._run_set({repr(params_json)})", delayFrames=1)
            
            return {
                "content": [{
                    "type": "text", 
                    "text": f"Command queued: set {params.get('parameter')}={params.get('value')} on {params.get('path')}"
                }]
            }
        except Exception as e: 
            raise RuntimeError(f"Error queuing set command: {e}")

    def _tool_execute_python(self, params):
        """Queues Python execution in the main thread."""
        try:
            if not params.get("code"): 
                raise ValueError("Missing code param")
            
            params_json = json.dumps(params)
            run(f"mod('{self.server.dat_path}')._run_execute({repr(params_json)})", delayFrames=1)
            
            return {
                "content": [{
                    "type": "text", 
                    "text": "Command queued: execute python code"
                }]
            }
        except Exception as e: 
            raise RuntimeError(f"Error queuing execute command: {e}")

    def _tool_list_components(self, params):
        """Queues component listing in the main thread."""
        try:
            params_json = json.dumps(params)
            run(f"mod('{self.server.dat_path}')._run_list({repr(params_json)})", delayFrames=1)
            
            return {
                "content": [{
                    "type": "text", 
                    "text": f"Command queued: list components in {params.get('path', '/')}"
                }]
            }
        except Exception as e: 
            raise RuntimeError(f"Error queuing list command: {e}")

    def _tool_get_info(self, params):
        """Queues component/parameter info retrieval in the main thread."""
        try:
            if not params.get("path"): 
                raise ValueError("Missing path param")
            
            params_json = json.dumps(params)
            run(f"mod('{self.server.dat_path}')._run_get({repr(params_json)})", delayFrames=1)
            
            param = params.get("parameter")
            if param:
                text = f"Command queued: get {param} from {params.get('path')}"
            else:
                text = f"Command queued: get info for {params.get('path')}"
            
            return {
                "content": [{
                    "type": "text", 
                    "text": text
                }]
            }
        except Exception as e: 
            raise RuntimeError(f"Error queuing get command: {e}")

    def _tool_list_parameters(self, params):
        """Queues parameter listing in the main thread."""
        try:
            params_json = json.dumps(params)
            run(f"mod('{self.server.dat_path}')._run_list_parameters({repr(params_json)})", delayFrames=1)
            
            return {
                "content": [{
                    "type": "text", 
                    "text": f"Command queued: list parameters for {params.get('path', '/')}"
                }]
            }
        except Exception as e: 
            raise RuntimeError(f"Error queuing list_parameters command: {e}")

    def _tool_auto_connect(self, params):
        """Queues auto-connection in the main thread."""
        try:
            if not params.get("source") or not params.get("target"):
                raise ValueError("Missing source or target param")
            
            params_json = json.dumps(params)
            run(f"mod('{self.server.dat_path}')._run_auto_connect({repr(params_json)})", delayFrames=1)
            
            return {
                "content": [{
                    "type": "text", 
                    "text": f"Command queued: auto-connect {params.get('source')} -> {params.get('target')}"
                }]
            }
        except Exception as e: 
            raise RuntimeError(f"Error queuing auto_connect command: {e}")

    def _tool_connect_nodes(self, params):
        """Queues node connection in the main thread."""
        try:
            if not params.get("nodes") and not params.get("custom_connections"):
                raise ValueError("Missing nodes or custom_connections param")
            
            params_json = json.dumps(params)
            run(f"mod('{self.server.dat_path}')._run_connect_nodes({repr(params_json)})", delayFrames=1)
            
            return {
                "content": [{
                    "type": "text", 
                    "text": f"Command queued: connect nodes with mode {params.get('mode', 'sequence')}"
                }]
            }
        except Exception as e: 
            raise RuntimeError(f"Error queuing connect_nodes command: {e}")

    def _tool_get_connection_history(self, params):
        """Queues connection history retrieval in the main thread."""
        try:
            params_json = json.dumps(params)
            run(f"mod('{self.server.dat_path}')._run_get_connection_history({repr(params_json)})", delayFrames=1)
            
            return {
                "content": [{
                    "type": "text", 
                    "text": f"Command queued: get connection history (limit: {params.get('limit', 10)})"
                }]
            }
        except Exception as e: 
            raise RuntimeError(f"Error queuing get_connection_history command: {e}")

    def _get_context(self, query):
        """Get context information - runs directly in request thread."""
        # This is safe as it only reads data and doesn't modify TD state
        try:
            context_items = []
            
            if TDF:
                # Search for operators
                matches = op("/").findChildren(name=f"*{query}*", maxDepth=5)
                
                for match in matches[:20]:  # Limit results
                    if match and match.valid:
                        context_items.append({
                            "uri": match.path,
                            "content": f"Op: {match.name} ({match.type})",
                            "metadata": {
                                "type": "operator",
                                "name": match.name,
                                "op_type": match.type
                            }
                        })
                
                # Add common TouchDesigner functions/classes to context
                if "td" in query.lower() or "touch" in query.lower():
                    context_items.extend([
                        {
                            "uri": "td:module",
                            "content": "TouchDesigner module with classes and functions",
                            "metadata": {"type": "module"}
                        },
                        {
                            "uri": "op:function",
                            "content": "op(path) - Get operator by path",
                            "metadata": {"type": "function"}
                        },
                        {
                            "uri": "run:function",
                            "content": "run(command, delayFrames) - Execute in main thread",
                            "metadata": {"type": "function"}
                        }
                    ])
            
            if not context_items:
                return [{
                    "uri": "info:none",
                    "content": "No relevant context found."
                }]
            
            return context_items
            
        except Exception as e:
            print(f"Context Error: {e}")
            return [{
                "uri": "info:error",
                "content": f"Error retrieving context: {str(e)}"
            }]

# --- Server Control Functions ---

def start_mcp_server(dat_op=None):
    """Starts the MCP HTTP server in a separate thread."""
    global server_thread, server_instance, server_running
    
    if server_running:
        print("MCP Server already running.")
        return True
    
    if not TDF:
        print("Cannot start server outside TouchDesigner.")
        return False
    
    if not dat_op or not isinstance(dat_op, td.OP):
        print("Error: DAT operator reference not provided or invalid.")
        return False
    
    dat_path = dat_op.path

    try:
        server_instance = ThreadingHTTPServer(
            (SERVER_HOST, SERVER_PORT), 
            TouchDesignerMCPHandler, 
            dat_path
        )
        
        print(f"Starting MCP server on port {SERVER_PORT} (DAT: {dat_path})...")
        
        server_thread = threading.Thread(target=server_instance.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        server_running = True
        
        print(f"MCP Server started successfully on http://{SERVER_HOST}:{SERVER_PORT}")
        print("Features: create, delete, list, get, set, execute_python, list_parameters")
        print("Auto-connection and smart positioning enabled")
        
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
        # Clear connection history
        connection_history.clear()

def get_server_status():
    """Get the current server status."""
    global server_running
    return {
        "running": server_running,
        "host": SERVER_HOST,
        "port": SERVER_PORT,
        "version": "2.0.0"
    }

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0: return self._handle_error("Empty request body", 400)
            post_data = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(post_data)
            parsed_path = urlparse(self.path); path = parsed_path.path
            if path == "/mcp": self._handle_mcp_request(data)
            elif path == "/context": self._handle_context_request(data)
            else: self._handle_error(f"Unknown POST endpoint: {path}", 404)
        except json.JSONDecodeError: self._handle_error("Invalid JSON", 400)
        except Exception as e: self._handle_error(f"Error handling POST: {str(e)}", 500)

    def _handle_mcp_request(self, data):
        method = data.get("method"); params = data.get("params", {})
        if not method: return self._handle_error("Missing 'method'", 400)
        print(f"Received MCP method: {method} with params: {params}")
        try:
            result = None
            if method == "create": result = self._tool_create_component(params)
            elif method == "list": result = self._tool_list_components(params)
            elif method == "delete": result = self._tool_delete_component(params)
            elif method == "set": result = self._tool_set_parameter(params)
            elif method == "get": result = self._tool_get_info(params)
            elif method == "execute_python": result = self._tool_execute_python(params)
            elif method == "list_parameters": result = self._tool_list_parameters(params)
            elif method == "auto_connect": result = self._tool_auto_connect(params)
            elif method == "connect_nodes": result = self._tool_connect_nodes(params)
            elif method == "get_connection_history": result = self._tool_get_connection_history(params)
            else: return self._handle_error(f"Unknown MCP method: {method}", 404)
            self._send_json({"result": result})
        except Exception as e:
            error_message = f"Error executing MCP method '{method}': {str(e)}"
            print(error_message)
            self._send_json({"error": {"message": error_message, "code": -32001}}, status=500)

    def _handle_context_request(self, data):
         query = data.get("query", ""); print(f"Received context query: {query}")
         try:
             context_items = self._get_context(query)
             self._send_json({"contextItems": context_items})
         except Exception as e:
             error_message = f"Error getting context: {str(e)}"; print(error_message)
             self._handle_error(error_message, 500)

    # --- Tool Implementation Functions --- (ALL use run())

    def _tool_create_component(self, params):
        """Queues component creation in the main thread."""
        try:
            if not params.get("type"): raise ValueError("Missing type param")
            params_json = json.dumps(params)
            run(f"mod('{self.server.dat_path}')._run_create({repr(params_json)})", delayFrames=1)
            # Return structured response for Claude Desktop
            return {"content": [{"type": "text", "text": "Command queued: create component"}]}
        except Exception as e: raise RuntimeError(f"Error queuing create command: {e}")

    def _tool_delete_component(self, params):
        """Queues component deletion in the main thread."""
        try:
            if not params.get("path"): raise ValueError("Missing path param")
            params_json = json.dumps(params)
            run(f"mod('{self.server.dat_path}')._run_delete({repr(params_json)})", delayFrames=1)
            # Return structured response for Claude Desktop
            return {"content": [{"type": "text", "text": "Command queued: delete component"}]}
        except Exception as e: raise RuntimeError(f"Error queuing delete command: {e}")

    def _tool_set_parameter(self, params):
        """Queues parameter setting in the main thread."""
        try:
            if not params.get("path") or not params.get("parameter") or params.get("value") is None:
                 raise ValueError("Missing params for set")
            params_json = json.dumps(params)
            run(f"mod('{self.server.dat_path}')._run_set({repr(params_json)})", delayFrames=1)
            # Return structured response for Claude Desktop
            return {"content": [{"type": "text", "text": "Command queued: set parameter"}]}
        except Exception as e: raise RuntimeError(f"Error queuing set command: {e}")

    def _tool_execute_python(self, params):
        """Queues Python execution in the main thread."""
        try:
            if not params.get("code"): raise ValueError("Missing code param")
            params_json = json.dumps(params)
            run(f"mod('{self.server.dat_path}')._run_execute({repr(params_json)})", delayFrames=1)
            # Return structured response for Claude Desktop
            return {"content": [{"type": "text", "text": "Command queued: execute python"}]}
        except Exception as e: raise RuntimeError(f"Error queuing execute command: {e}")

    def _tool_list_components(self, params):
        """Queues component listing in the main thread."""
        try:
            params_json = json.dumps(params)
            run(f"mod('{self.server.dat_path}')._run_list({repr(params_json)})", delayFrames=1)
            # Return structured response for Claude Desktop
            return {"content": [{"type": "text", "text": "Command queued: list components"}]}
        except Exception as e: raise RuntimeError(f"Error queuing list command: {e}")

    def _tool_get_info(self, params):
        """Queues component/parameter info retrieval in the main thread."""
        try:
            if not params.get("path"): raise ValueError("Missing path param")
            params_json = json.dumps(params)
            run(f"mod('{self.server.dat_path}')._run_get({repr(params_json)})", delayFrames=1)
            # Return structured response for Claude Desktop
            return {"content": [{"type": "text", "text": "Command queued: get info"}]}
        except Exception as e: raise RuntimeError(f"Error queuing get command: {e}")

    def _get_context(self, query):
        """Placeholder for context retrieval logic (direct call - potentially unsafe if TD API used)."""
        # NOTE: This context function might still cause threading issues if it uses TD API calls.
        # For safety, it should ideally also use run() or only access non-TD data.
        try:
            matches = op("/").findChildren(name=f"*{query}*") if TDF else []
            context_items = []
            for match in matches:
                if match and match.valid:
                    context_items.append({"uri": match.path, "content": f"Op: {match.name} ({match.type})", "metadata": {"type": "operator", "name": match.name}})
            if not context_items: return [{"uri": "info:none", "content": "No relevant context found."}]
            return context_items
        except Exception as e: print(f"Context Error: {e}"); return [{"uri": "info:error", "content": "Error retrieving context."}]


# --- Server Control Functions ---

def start_mcp_server(dat_op=None): # Expects the DAT operator itself
    """Starts the MCP HTTP server in a separate thread."""
    global server_thread, server_instance, server_running
    if server_running: print("MCP Server already running."); return True
    if not TDF: print("Cannot start server outside TouchDesigner."); return False
    if not dat_op or not isinstance(dat_op, td.OP):
        print("Error: DAT operator reference not provided or invalid.")
        return False
    dat_path = dat_op.path

    try:
        server_instance = ThreadingHTTPServer((SERVER_HOST, SERVER_PORT), TouchDesignerMCPHandler, dat_path)
        print(f"Starting MCP server on port {SERVER_PORT} (DAT: {dat_path})...")
        server_thread = threading.Thread(target=server_instance.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        server_running = True
        print(f"MCP Server started successfully on http://{SERVER_HOST}:{SERVER_PORT}")
        return True
    except Exception as e:
        print(f"Failed to start MCP server: {e}"); server_instance = None; server_thread = None; server_running = False; return False

def stop_mcp_server():
    """Stops the MCP HTTP server."""
    global server_thread, server_instance, server_running
    if not server_running or not server_instance: print("MCP Server is not running."); return
    print("Shutting down MCP server...")
    try:
        server_instance.shutdown(); server_instance.server_close()
        server_thread.join(timeout=5)
        print("MCP Server stopped.")
    except Exception as e: print(f"Error stopping MCP server: {e}")
    finally: server_instance = None; server_thread = None; server_running = False

