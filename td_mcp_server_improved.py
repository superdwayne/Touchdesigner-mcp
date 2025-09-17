"""
TouchDesigner MCP Server - Improved Version
Provides HTTP endpoints for Claude to interact with TouchDesigner
Improvements:
- Better error handling and reporting
- More robust component creation with better auto-connections
- Improved parameter handling with type checking
- Added connection tracking for better auto-wiring
- Enhanced list_parameters functionality
- Better node positioning algorithm
- Support for more component types
- Improved thread safety
"""

import sys
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from collections import defaultdict
import traceback

# Import TouchDesigner-specific modules
try:
    import td
    # Import specific operator types needed for mapping
    from td import (
        textDAT, tableDAT, scriptDAT, opfindDAT, executeDAT, chopexecuteDAT, datexecuteDAT,
        circleTOP, noiseTOP, moviefileinTOP, constantTOP, rampTOP, textTOP, outTOP, renderTOP, 
        switchTOP, compositeTOP, levelTOP, cropTOP, resolutionTOP, nullTOP, cacheTOP,
        constantCHOP, noiseCHOP, lfoCHOP, mathCHOP, selectCHOP, outCHOP, audiodeviceinCHOP,
        mergeCHOP, timerCHOP, speedCHOP, lagCHOP, filterCHOP, analyzeCHOP, audiomovieplayerCHOP,
        sphereSOP, boxSOP, gridSOP, lineSOP, nullSOP, outSOP, tubeSOP, torusSOP,
        mergeSOP, transformSOP, facetSOP, subdivisionSOP, noiseSOP,
        baseCOMP, containerCOMP, geometryCOMP, cameraCOMP, lightCOMP, buttonCOMP, sliderCOMP, windowCOMP,
        phongMAT, pbrMAT, constantMAT, wireframeMAT, depthMAT
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
            self.valid = True
            self.nodeX = 0
            self.nodeY = 0
            self.inputs = []
            self.outputs = []
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
        textDAT = MockCompType(); tableDAT = MockCompType(); scriptDAT = MockCompType()
        # ... (other mock types omitted for brevity)

    class MockProject: name = "mock_project"
    td = MockTd(); project = MockProject()
    def op(path):
        if path == "/invalid_path": return None
        return MockOp(path)
    def run(command, delayFrames=0): print(f"Mock run: {command}")

# Global state for connection tracking
connection_history = defaultdict(list)  # Track connections per parent

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
        node_x = params.get("nodex", None)
        node_y = params.get("nodey", None)
        connect_source = params.get("connect_source", None)
        connect_parameter = params.get("connect_parameter", None)

        if not comp_type_str: raise ValueError("Missing type")

        # Expanded component type mapping
        comp_type_map = {
            # DATs
            "text": textDAT, "table": tableDAT, "script": scriptDAT, 
            "opfind": opfindDAT, "execute": executeDAT, "chopexecute": chopexecuteDAT,
            "datexecute": datexecuteDAT,
            
            # TOPs
            "circle": circleTOP, "noise": noiseTOP, "moviefilein": moviefileinTOP, 
            "constant": constantTOP, "ramp": rampTOP, "texttop": textTOP, "out": outTOP, 
            "render": renderTOP, "switch": switchTOP, "composite": compositeTOP,
            "level": levelTOP, "crop": cropTOP, "resolution": resolutionTOP, 
            "null": nullTOP, "cache": cacheTOP,
            
            # CHOPs
            "constantchop": constantCHOP, "noisechop": noiseCHOP, "lfo": lfoCHOP, 
            "math": mathCHOP, "selectchop": selectCHOP, "outchop": outCHOP, 
            "audiodevicein": audiodeviceinCHOP, "merge": mergeCHOP, "timer": timerCHOP,
            "speed": speedCHOP, "lag": lagCHOP, "filter": filterCHOP, 
            "analyze": analyzeCHOP, "audiomovieplayer": audiomovieplayerCHOP,
            
            # SOPs
            "sphere": sphereSOP, "box": boxSOP, "grid": gridSOP, "line": lineSOP, 
            "nullsop": nullSOP, "outsop": outSOP, "tube": tubeSOP, "torus": torusSOP,
            "mergesop": mergeSOP, "transform": transformSOP, "facet": facetSOP,
            "subdivision": subdivisionSOP, "noisesop": noiseSOP,
            
            # COMPs
            "base": baseCOMP, "container": containerCOMP, "geometrycomp": geometryCOMP, 
            "camera": cameraCOMP, "cam": cameraCOMP, "light": lightCOMP, 
            "button": buttonCOMP, "slider": sliderCOMP, "window": windowCOMP,
            
            # MATs
            "phong": phongMAT, "pbr": pbrMAT, "constantmat": constantMAT,
            "wireframe": wireframeMAT, "depth": depthMAT,
        }
        
        # Normalize the type string
        comp_type_key = comp_type_str.lower().replace(" ", "").replace("comp", "").replace("sop", "").replace("top", "").replace("dat", "").replace("mat", "").replace("chop", "")
        comp_type = comp_type_map.get(comp_type_key)
        
        # Special case for geometry
        if comp_type_key == 'geometry': comp_type = geometryCOMP

        if not comp_type:
            # Try to get the type directly from td module
            try:
                comp_type = getattr(td, comp_type_str, None)
                if not isinstance(comp_type, type) or not issubclass(comp_type, td.OP): 
                    comp_type = None
            except Exception: 
                comp_type = None
            if not comp_type: 
                raise ValueError(f"Unsupported type: {comp_type_str}")

        # Generate name if not provided
        if not name:
            base_name = comp_type_str.lower().replace("comp", "").replace("sop", "").replace("top", "").replace("dat", "").replace("mat", "").replace("chop", "")
            i = 1
            name = f"{base_name}{i}"
            while op(f"{parent_path}/{name}"):
                i += 1
                name = f"{base_name}{i}"

        parent_op = op(parent_path)
        if not parent_op or not parent_op.valid: 
            raise ValueError(f"Invalid parent: {parent_path}")

        new_op = parent_op.create(comp_type, name)
        if not new_op: 
            raise RuntimeError(f"Failed to create {name} in {parent_path}")

        # Set node position
        if node_x is not None and node_y is not None:
            new_op.nodeX = node_x
            new_op.nodeY = node_y
        else:
            # Improved auto-positioning algorithm
            existing_nodes = len(parent_op.children) if hasattr(parent_op, 'children') else 1
            
            # Get operator family for better positioning
            op_family = _get_op_family(new_op)
            
            # Position based on family
            family_offsets = {
                'TOP': (0, 0),
                'CHOP': (0, -300),
                'SOP': (0, -600),
                'MAT': (0, -900),
                'COMP': (0, -1200),
                'DAT': (0, -1500)
            }
            
            base_offset = family_offsets.get(op_family, (0, 0))
            
            # Grid positioning within family
            grid_size = 150
            cols = 6
            family_count = sum(1 for child in parent_op.children 
                             if hasattr(child, 'type') and _get_op_family(child) == op_family)
            
            row = family_count // cols
            col = family_count % cols
            
            new_op.nodeX = base_offset[0] + (col * grid_size)
            new_op.nodeY = base_offset[1] - (row * grid_size)
            
            print(f"Auto-positioned {op_family} node at ({new_op.nodeX}, {new_op.nodeY})")

        # Handle connections
        if connect_source:
            source_op = op(connect_source)
            if source_op and source_op.valid:
                # If a specific parameter is provided, try to connect it
                if connect_parameter:
                    try:
                        param_obj = getattr(new_op.par, connect_parameter, None)
                        if param_obj:
                            param_obj.val = source_op
                            print(f"Connected {source_op.path} to parameter {connect_parameter} of {new_op.path}")
                    except Exception as conn_err:
                        print(f"Parameter connection error: {conn_err}")
                else:
                    # Try input connection
                    if hasattr(new_op, 'inputs') and len(new_op.inputs) > 0:
                        try:
                            new_op.inputs[0] = source_op
                            print(f"Connected {source_op.path} to input 0 of {new_op.path}")
                            # Track connection
                            connection_history[parent_path].append((source_op.path, new_op.path))