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
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Import TouchDesigner-specific modules
try:
    import td
    # Check if we're actually in TouchDesigner by testing if 'op' function exists
    if 'op' in globals():
        TDF = True
        print("Running inside TouchDesigner - MCP server will start.")
        
        # Import specific operator types needed for mapping - handle missing types gracefully
        def safe_import_td_type(module, type_name, default=None):
            try:
                return getattr(module, type_name)
            except AttributeError:
                print(f"Warning: {type_name} not available in this TouchDesigner version")
                return default
        
        # Import basic types that should always be available
        textDAT = safe_import_td_type(td, 'textDAT')
        tableDAT = safe_import_td_type(td, 'tableDAT')
        scriptDAT = safe_import_td_type(td, 'scriptDAT')
        circleTOP = safe_import_td_type(td, 'circleTOP')
        noiseTOP = safe_import_td_type(td, 'noiseTOP')
        constantTOP = safe_import_td_type(td, 'constantTOP')
        rampTOP = safe_import_td_type(td, 'rampTOP')
        textTOP = safe_import_td_type(td, 'textTOP')
        outTOP = safe_import_td_type(td, 'outTOP')
        constantCHOP = safe_import_td_type(td, 'constantCHOP')
        noiseCHOP = safe_import_td_type(td, 'noiseCHOP')
        lfoCHOP = safe_import_td_type(td, 'lfoCHOP')
        mathCHOP = safe_import_td_type(td, 'mathCHOP')
        selectCHOP = safe_import_td_type(td, 'selectCHOP')
        outCHOP = safe_import_td_type(td, 'outCHOP')
        sphereSOP = safe_import_td_type(td, 'sphereSOP')
        boxSOP = safe_import_td_type(td, 'boxSOP')
        gridSOP = safe_import_td_type(td, 'gridSOP')
        lineSOP = safe_import_td_type(td, 'lineSOP')
        nullSOP = safe_import_td_type(td, 'nullSOP')
        outSOP = safe_import_td_type(td, 'outSOP')
        baseCOMP = safe_import_td_type(td, 'baseCOMP')
        containerCOMP = safe_import_td_type(td, 'containerCOMP')
        geometryCOMP = safe_import_td_type(td, 'geometryCOMP')
        cameraCOMP = safe_import_td_type(td, 'cameraCOMP')
        lightCOMP = safe_import_td_type(td, 'lightCOMP')
        buttonCOMP = safe_import_td_type(td, 'buttonCOMP')
        sliderCOMP = safe_import_td_type(td, 'sliderCOMP')
        phongMAT = safe_import_td_type(td, 'phongMAT')
        pbrMAT = safe_import_td_type(td, 'pbrMAT')
        constantMAT = safe_import_td_type(td, 'constantMAT')
        
        # Import additional types that might not be available in all versions
        opfindDAT = safe_import_td_type(td, 'opfindDAT')
        executeDAT = safe_import_td_type(td, 'executeDAT')
        moviefileinTOP = safe_import_td_type(td, 'moviefileinTOP')
        audioDeviceInCHOP = safe_import_td_type(td, 'audioDeviceInCHOP')
        
        # Import additional TOP types
        blurTOP = safe_import_td_type(td, 'blurTOP')
        levelTOP = safe_import_td_type(td, 'levelTOP')
        compositeTOP = safe_import_td_type(td, 'compositeTOP')
        displaceTOP = safe_import_td_type(td, 'displaceTOP')
        feedbackTOP = safe_import_td_type(td, 'feedbackTOP')
        lutTOP = safe_import_td_type(td, 'lutTOP')
        
        # Import additional CHOP types
        filterCHOP = safe_import_td_type(td, 'filterCHOP')
        lagCHOP = safe_import_td_type(td, 'lagCHOP')
        chopexecuteCHOP = safe_import_td_type(td, 'chopexecuteCHOP')
        mergeCHOP = safe_import_td_type(td, 'mergeCHOP')
        waveCHOP = safe_import_td_type(td, 'waveCHOP')
        
        # Import additional SOP types
        tubeSOP = safe_import_td_type(td, 'tubeSOP')
        mergeSOP = safe_import_td_type(td, 'mergeSOP')
        transformSOP = safe_import_td_type(td, 'transformSOP')
        copySOP = safe_import_td_type(td, 'copySOP')
        groupSOP = safe_import_td_type(td, 'groupSOP')
        
        # Import additional COMP types
        panelCOMP = safe_import_td_type(td, 'panelCOMP')
        webCOMP = safe_import_td_type(td, 'webCOMP')
        switchCOMP = safe_import_td_type(td, 'switchCOMP')
        renderCOMP = safe_import_td_type(td, 'renderCOMP')
        audioCOMP = safe_import_td_type(td, 'audioCOMP')
        
        # Import additional MAT types
        glslMAT = safe_import_td_type(td, 'glslMAT')
        textureMAT = safe_import_td_type(td, 'textureMAT')
        videoMAT = safe_import_td_type(td, 'videoMAT')
        
        # Set defaults for missing types
        if opfindDAT is None: opfindDAT = textDAT
        if executeDAT is None: executeDAT = textDAT
        if moviefileinTOP is None: moviefileinTOP = constantTOP
        if audioDeviceInCHOP is None: audioDeviceInCHOP = constantCHOP
        if blurTOP is None: blurTOP = constantTOP
        if levelTOP is None: levelTOP = constantTOP
        if compositeTOP is None: compositeTOP = constantTOP
        if displaceTOP is None: displaceTOP = constantTOP
        if feedbackTOP is None: feedbackTOP = constantTOP
        if lutTOP is None: lutTOP = constantTOP
        if filterCHOP is None: filterCHOP = constantCHOP
        if lagCHOP is None: lagCHOP = constantCHOP
        if chopexecuteCHOP is None: chopexecuteCHOP = constantCHOP
        if mergeCHOP is None: mergeCHOP = constantCHOP
        if waveCHOP is None: waveCHOP = constantCHOP
        if tubeSOP is None: tubeSOP = sphereSOP
        if mergeSOP is None: mergeSOP = nullSOP
        if transformSOP is None: transformSOP = nullSOP
        if copySOP is None: copySOP = nullSOP
        if groupSOP is None: groupSOP = nullSOP
        if panelCOMP is None: panelCOMP = baseCOMP
        if webCOMP is None: webCOMP = baseCOMP
        if switchCOMP is None: switchCOMP = baseCOMP
        if renderCOMP is None: renderCOMP = baseCOMP
        if audioCOMP is None: audioCOMP = baseCOMP
        if glslMAT is None: glslMAT = phongMAT
        if textureMAT is None: textureMAT = phongMAT
        if videoMAT is None: videoMAT = phongMAT
        
    else:
        TDF = False
        print("Not running inside TouchDesigner. Mock functions will be used.")
except ImportError:
    TDF = False
    print("Not running inside TouchDesigner. Mock functions will be used.")

# Mock functions for when not running in TouchDesigner
if not TDF:
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
        # Update mock component types with new additions
        textDAT = MockCompType(); tableDAT = MockCompType(); scriptDAT = MockCompType(); opfindDAT = MockCompType(); executeDAT = MockCompType()
        circleTOP = MockCompType(); noiseTOP = MockCompType(); moviefileinTOP = MockCompType(); constantTOP = MockCompType(); rampTOP = MockCompType(); textTOP = MockCompType(); outTOP = MockCompType()
        blurTOP = MockCompType(); levelTOP = MockCompType(); compositeTOP = MockCompType(); displaceTOP = MockCompType(); feedbackTOP = MockCompType(); lutTOP = MockCompType()
        constantCHOP = MockCompType(); noiseCHOP = MockCompType(); lfoCHOP = MockCompType(); mathCHOP = MockCompType(); selectCHOP = MockCompType(); outCHOP = MockCompType()
        filterCHOP = MockCompType(); lagCHOP = MockCompType(); chopexecuteCHOP = MockCompType(); mergeCHOP = MockCompType(); waveCHOP = MockCompType()
        sphereSOP = MockCompType(); boxSOP = MockCompType(); gridSOP = MockCompType(); lineSOP = MockCompType(); nullSOP = MockCompType(); outSOP = MockCompType()
        tubeSOP = MockCompType(); mergeSOP = MockCompType(); transformSOP = MockCompType(); copySOP = MockCompType(); groupSOP = MockCompType()
        baseCOMP = MockCompType(); containerCOMP = MockCompType(); geometryCOMP = MockCompType(); cameraCOMP = MockCompType(); lightCOMP = MockCompType(); buttonCOMP = MockCompType(); sliderCOMP = MockCompType()
        panelCOMP = MockCompType(); webCOMP = MockCompType(); switchCOMP = MockCompType(); renderCOMP = MockCompType(); audioCOMP = MockCompType()
        phongMAT = MockCompType(); pbrMAT = MockCompType(); constantMAT = MockCompType(); glslMAT = MockCompType(); textureMAT = MockCompType(); videoMAT = MockCompType()

    class MockProject: name = "mock_project"
    td = MockTd(); project = MockProject()
    def op(path):
        if path == "/invalid_path": return None
        return MockOp(path)
    def run(command, delayFrames=0): print(f"Mock run: {command}")
    # Define all mock component types for create operations
    textDAT = td.textDAT; tableDAT = td.tableDAT; scriptDAT = td.scriptDAT; opfindDAT = td.opfindDAT; executeDAT = td.executeDAT
    circleTOP = td.circleTOP; noiseTOP = td.noiseTOP; moviefileinTOP = td.moviefileinTOP; constantTOP = td.constantTOP; rampTOP = td.rampTOP; textTOP = td.textTOP; outTOP = td.outTOP
    blurTOP = td.blurTOP; levelTOP = td.levelTOP; compositeTOP = td.compositeTOP; displaceTOP = td.displaceTOP; feedbackTOP = td.feedbackTOP; lutTOP = td.lutTOP
    constantCHOP = td.constantCHOP; noiseCHOP = td.noiseCHOP; lfoCHOP = td.lfoCHOP; mathCHOP = td.mathCHOP; selectCHOP = td.selectCHOP; outCHOP = td.outCHOP
    filterCHOP = td.filterCHOP; lagCHOP = td.lagCHOP; chopexecuteCHOP = td.chopexecuteCHOP; mergeCHOP = td.mergeCHOP; waveCHOP = td.waveCHOP
    sphereSOP = td.sphereSOP; boxSOP = td.boxSOP; gridSOP = td.gridSOP; lineSOP = td.lineSOP; nullSOP = td.nullSOP; outSOP = td.outSOP
    tubeSOP = td.tubeSOP; mergeSOP = td.mergeSOP; transformSOP = td.transformSOP; copySOP = td.copySOP; groupSOP = td.groupSOP
    baseCOMP = td.baseCOMP; containerCOMP = td.containerCOMP; geometryCOMP = td.geometryCOMP; cameraCOMP = td.cameraCOMP; lightCOMP = td.lightCOMP; buttonCOMP = td.buttonCOMP; sliderCOMP = td.sliderCOMP
    panelCOMP = td.panelCOMP; webCOMP = td.webCOMP; switchCOMP = td.switchCOMP; renderCOMP = td.renderCOMP; audioCOMP = td.audioCOMP
    phongMAT = td.phongMAT; pbrMAT = td.pbrMAT; constantMAT = td.constantMAT; glslMAT = td.glslMAT; textureMAT = td.textureMAT; videoMAT = td.videoMAT

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
        # New connection parameters
        connect_source = params.get("connect_source")
        connect_parameter = params.get("connect_parameter")

        if not comp_type_str: raise ValueError("Missing type")

        comp_type_map = {
            # DATs
            "text": textDAT, "table": tableDAT, "script": scriptDAT, 
            "opfind": opfindDAT, "execute": executeDAT, "dat": textDAT,
            
            # TOPs
            "circle": circleTOP, "noise": noiseTOP, "moviefilein": moviefileinTOP,
            "constant": constantTOP, "ramp": rampTOP, "texttop": textTOP, 
            "out": outTOP, "blur": blurTOP, "level": levelTOP, "composite": compositeTOP,
            "displace": displaceTOP, "feedback": feedbackTOP, "lut": lutTOP,
            
            # CHOPs
            "constantchop": constantCHOP, "noisechop": noiseCHOP, "lfo": lfoCHOP,
            "math": mathCHOP, "selectchop": selectCHOP, "outchop": outCHOP,
            "filter": filterCHOP, "lag": lagCHOP, "chopexecute": chopexecuteCHOP,
            "merge": mergeCHOP, "wave": waveCHOP,
            
            # SOPs
            "sphere": sphereSOP, "box": boxSOP, "grid": gridSOP, "line": lineSOP,
            "nullsop": nullSOP, "outsop": outSOP, "tube": tubeSOP, "merge": mergeSOP,
            "transform": transformSOP, "copy": copySOP, "group": groupSOP,
            
            # COMPs
            "base": baseCOMP, "container": containerCOMP, "geometrycomp": geometryCOMP,
            "cameracomp": cameraCOMP, "lightcomp": lightCOMP, "buttoncomp": buttonCOMP,
            "slidercomp": sliderCOMP, "panel": panelCOMP, "web": webCOMP,
            "switch": switchCOMP, "render": renderCOMP, "audio": audioCOMP,
            
            # MATs
            "phong": phongMAT, "pbr": pbrMAT, "constantmat": constantMAT,
            "glsl": glslMAT, "texture": textureMAT, "video": videoMAT,
            
            # Common aliases
            "render": outTOP, "cam": cameraCOMP, "camera": cameraCOMP,
            "mov": moviefileinTOP, "movie": moviefileinTOP, "geo": geometryCOMP,
            "material": phongMAT, "light": lightCOMP, "null": nullSOP
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

        # Handle the create method call properly
        try:
            new_op = parent_op.create(comp_type, name)
        except TypeError as e:
            # If the create method expects different arguments, try alternative approach
            if "Invalid number or type of arguments" in str(e):
                # Try creating with just the type and let TouchDesigner auto-name
                new_op = parent_op.create(comp_type)
                if new_op and new_op.valid:
                    # Rename the created operator
                    new_op.name = name
            else:
                raise e
        
        if not new_op or not new_op.valid: 
            raise RuntimeError(f"Failed to create {name} in {parent_path}")

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

        # Update connection handling in _run_create
        if connect_source and connect_parameter:
            try:
                source_op = op(connect_source)
                if source_op and source_op.valid:
                    target_par = new_op.par[connect_parameter]
                    if target_par:
                        # Handle different connection types
                        if connect_type == 'bind':
                            target_par.bind(source_op)
                        elif connect_type == 'chop':
                            target_par.expr = f"op('{connect_source}')"
                        elif connect_type == 'top':
                            target_par.expr = f"op('{connect_source}').output"
                        elif connect_type == 'pulse':
                            source_op.par.pulse.pulse(target_par)
                        
                        print(f"Connected {new_op.path}.{connect_parameter} to {connect_source} ({connect_type})")
                    else:
                        print(f"Connection failed: Target parameter {connect_parameter} not found")
                else:
                    print(f"Connection failed: Source operator {connect_source} not found")
            except Exception as e:
                print(f"Connection error: {str(e)}")

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
            if context_op and context_op.valid: exec_globals["me"] = context_op
            else: exec_globals["me"] = op("/")

            # --- Add this section to explicitly include imported TD types ---
            td_types_to_include = [
                textDAT, tableDAT, scriptDAT, opfindDAT, executeDAT,
                circleTOP, noiseTOP, moviefileinTOP, constantTOP, rampTOP, textTOP, outTOP,
                constantCHOP, noiseCHOP, lfoCHOP, mathCHOP, selectCHOP, outCHOP, audioDeviceInCHOP,
                sphereSOP, boxSOP, gridSOP, lineSOP, nullSOP, outSOP,
                baseCOMP, containerCOMP, geometryCOMP, cameraCOMP, lightCOMP, buttonCOMP, sliderCOMP,
                phongMAT, pbrMAT, constantMAT
                # Add any other specific types you import and want accessible directly by name
            ]
            for td_type in td_types_to_include:
                if hasattr(td_type, '__name__'): # Ensure it's a valid type/class
                     exec_globals[td_type.__name__] = td_type
            # --- End of added section ---

        exec(code, exec_globals, exec_locals)
        result_val = exec_locals.get("result", "Python code executed via run().")
        if isinstance(result_val, (td.OP, td.Parameter, td.ParGroup)): result_str = str(result_val)
        else:
            try: json.dumps(result_val); result_str = result_val
            except TypeError: result_str = str(result_val)
        print(f"MCP Run: Executed Python. Result: {result_str}")
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


# --- MCP Server Implementation (Port 8052) ---

# Global server state
server_thread = None
server_instance = None
server_running = False
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8053  # Changed to 8053 to avoid conflict

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
                self._send_json({"status": "running", "touchdesigner": True, "version": "1.0.0"})
            else: self._handle_error("Endpoint not found", 404)
        except Exception as e: self._handle_error(f"Error handling GET: {str(e)}", 500)

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

def start_mcp_server(dat_op):
    """Starts the MCP HTTP server in a separate thread."""
    global server_thread, server_instance, server_running, TDF # Ensure TDF is accessible

    print(f"DEBUG: Inside start_mcp_server, TDF = {TDF}") # <-- ADD THIS LINE

    # Stop any existing server first
    if server_running:
        print("Stopping existing MCP server...")
        stop_mcp_server()

    if not TDF:
        print("Running in mock mode - server will start with limited functionality.")
        # Create a mock DAT operator for testing
        class MockDatOp:
            def __init__(self):
                self.path = "/mock/text1"
        dat_op = MockDatOp()
        dat_path = dat_op.path
    else:
        if not dat_op or not isinstance(dat_op, td.OP):
            print("Error: DAT operator reference not provided or invalid.")
            return False
        dat_path = dat_op.path

    try:
        print(f"Creating server instance on {SERVER_HOST}:{SERVER_PORT}...")
        server_instance = ThreadingHTTPServer((SERVER_HOST, SERVER_PORT), TouchDesignerMCPHandler, dat_path)
        print(f"Starting MCP server on port {SERVER_PORT} (DAT: {dat_path})...")
        server_thread = threading.Thread(target=server_instance.serve_forever)
        server_thread.daemon = True
        print("Starting server thread...")
        server_thread.start()
        server_running = True
        print(f"MCP Server started successfully on http://{SERVER_HOST}:{SERVER_PORT}")
        return True
    except Exception as e:
        print(f"Failed to start MCP server: {e}")
        import traceback
        traceback.print_exc()
        server_instance = None; server_thread = None; server_running = False; return False

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