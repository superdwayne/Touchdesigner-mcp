"""
TouchDesigner MCP Server Plugin Installer
==========================================
Creates a self-contained Base COMP with the MCP server,
ready to save as a reusable .tox plugin.

Usage (in TouchDesigner Textport):
    exec(open('/path/to/Touchdesigner-mcp/td_mcp_plugin_installer.py').read())

If auto-detection fails, set REPO_PATH first:
    REPO_PATH = '/path/to/Touchdesigner-mcp'; exec(open(REPO_PATH + '/td_mcp_plugin_installer.py').read())
"""

import os

# ===================== CONFIGURATION =====================
# Set this if auto-detection fails (point to the repo FOLDER):
if 'REPO_PATH' not in dir() or not REPO_PATH:
    REPO_PATH = ''

COMP_NAME = 'td_mcp_server'
COMP_PARENT = '/project1'
SERVER_FILENAME = 'td_mcp_server_auso_v2.py'
# =========================================================


# --------------- Extension class (embedded in Text DAT) ---------------
EXTENSION_CODE = '''import os
import time as _time


class MCPServerExt:
    """
    TouchDesigner MCP Server Extension.

    Controls the lifecycle of the MCP HTTP server that lets
    Claude interact with TouchDesigner.

    Usage (Textport or any script):
        op('/project1/td_mcp_server').Start()
        op('/project1/td_mcp_server').Stop()
        op('/project1/td_mcp_server').Reload()
    """

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        # Auto-start after TD finishes initialising
        if self.ownerComp.par.Autostart.eval():
            run("args[0].Start()", self, delayFrames=5)

    # ---- public API (promoted on the COMP) ----

    def Start(self):
        """Start the MCP server (stops any existing instance first)."""
        server_dat = self.ownerComp.op('server_code')

        # Load from disk if the Text DAT is empty
        if not server_dat.text.strip():
            self._loadCode()
        if not server_dat.text.strip():
            self.ownerComp.par.Status = 'Error: no server code'
            print('[MCP Plugin] ERROR: No server code. Set the Serverfile parameter.')
            return

        # Free the port
        self._stopQuiet()
        _time.sleep(0.3)

        # Apply port setting
        port = self.ownerComp.par.Port.eval()
        os.environ['TD_MCP_PORT'] = str(port)

        try:
            ok = server_dat.module.start_mcp_server(server_dat)
            if ok:
                self.ownerComp.par.Status = 'Running (port {})'.format(port)
                print('[MCP Plugin] Server started on port {}'.format(port))
            else:
                self.ownerComp.par.Status = 'Error: start returned False'
                print('[MCP Plugin] start_mcp_server returned False — check Textport for details')
        except Exception as e:
            self.ownerComp.par.Status = 'Error'
            print('[MCP Plugin] Start failed: {}'.format(e))

    def Stop(self):
        """Stop the MCP server."""
        self._stopQuiet()
        print('[MCP Plugin] Server stopped')

    def Reload(self):
        """Reload server code from Serverfile and restart."""
        self._stopQuiet()
        _time.sleep(0.5)
        self._loadCode()
        self.Start()

    # ---- internals ----

    def _stopQuiet(self):
        server_dat = self.ownerComp.op('server_code')
        if server_dat:
            try:
                mod = server_dat.module
                if hasattr(mod, 'stop_mcp_server'):
                    mod.stop_mcp_server()
            except Exception:
                pass
        self.ownerComp.par.Status = 'Stopped'

    def _loadCode(self):
        server_file = self.ownerComp.par.Serverfile.eval()
        if not server_file:
            server_file = self._autoDetect()
        if server_file and os.path.isfile(server_file):
            with open(server_file, 'r', encoding='utf-8') as f:
                code = f.read()
            self.ownerComp.op('server_code').text = code
            print('[MCP Plugin] Loaded {} bytes from {}'.format(len(code), server_file))
        elif server_file:
            print('[MCP Plugin] File not found: {}'.format(server_file))

    def _autoDetect(self):
        fn = 'td_mcp_server_auso_v2.py'
        # Relative to .toe
        try:
            toe = project.folder
            if toe:
                for d in [toe, os.path.dirname(toe)]:
                    c = os.path.join(d, fn)
                    if os.path.isfile(c):
                        return c
        except Exception:
            pass
        # Common locations
        home = os.path.expanduser('~')
        for folder in ['Documents/Touchdesigner-mcp',
                        'Documents/Playground/Touchdesigner-mcp',
                        'Desktop/Touchdesigner-mcp']:
            c = os.path.join(home, folder, fn)
            if os.path.isfile(c):
                return c
        return None

    def Destroy(self):
        """Called when the extension is destroyed — clean shutdown."""
        self._stopQuiet()
'''


# --------------- Parameter Execute callbacks ---------------
PAR_EXEC_CODE = '''# Pulse-button routing for the MCP Server plugin.
# This DAT watches the parent COMP's custom parameters.

def onValueChange(par, prev):
    return

def onPulse(par):
    try:
        ext = parent().ext.MCPServerExt
    except Exception:
        return
    name = par.name
    if name == 'Start':
        ext.Start()
    elif name == 'Stop':
        ext.Stop()
    elif name == 'Reload':
        ext.Reload()

def onExpressionChange(par, val, prev):
    return

def onExportChange(par, val, prev):
    return

def onEnableChange(par, val, prev):
    return

def onModeChange(par, val, prev):
    return
'''


# ======================== Installer logic ========================

def _find_server_file():
    repo = REPO_PATH
    if repo:
        if os.path.isfile(repo):
            repo = os.path.dirname(repo)
        candidate = os.path.join(repo, SERVER_FILENAME)
        if os.path.isfile(candidate):
            return candidate
        print('[MCP Plugin] WARNING: Not at REPO_PATH: {}'.format(candidate))

    try:
        toe_path = project.folder
        if toe_path:
            for d in [toe_path, os.path.dirname(toe_path)]:
                candidate = os.path.join(d, SERVER_FILENAME)
                if os.path.isfile(candidate):
                    return candidate
    except Exception:
        pass

    home = os.path.expanduser('~')
    for folder in ['Documents/Touchdesigner-mcp',
                    'Documents/Playground/Touchdesigner-mcp',
                    'Desktop/Touchdesigner-mcp',
                    'Touchdesigner-mcp',
                    'Downloads/Touchdesigner-mcp']:
        candidate = os.path.join(home, folder, SERVER_FILENAME)
        if os.path.isfile(candidate):
            print('[MCP Plugin] Auto-detected: {}'.format(candidate))
            return candidate
    return None


def install_mcp_plugin():
    print('')
    print('[MCP Plugin] Installing TouchDesigner MCP Server plugin ...')
    print('')

    # ---- 1. Locate & read server code ----
    server_file = _find_server_file()
    if not server_file:
        print('[MCP Plugin] ERROR: Could not find ' + SERVER_FILENAME)
        print('[MCP Plugin] Set REPO_PATH before running the installer:')
        print('  REPO_PATH = "/Users/yourname/Documents/Touchdesigner-mcp"')
        print('  exec(open(REPO_PATH + "/td_mcp_plugin_installer.py").read())')
        return None

    with open(server_file, 'r', encoding='utf-8') as f:
        server_code = f.read()
    print('[MCP Plugin] Server code: {} ({:,} bytes)'.format(server_file, len(server_code)))

    # ---- 2. Parent check ----
    parent_op = op(COMP_PARENT)
    if not parent_op:
        print('[MCP Plugin] ERROR: Parent "{}" not found.'.format(COMP_PARENT))
        return None

    # ---- 3. Replace existing COMP if present ----
    existing = parent_op.op(COMP_NAME)
    if existing:
        try:
            if hasattr(existing, 'ext') and hasattr(existing.ext, 'MCPServerExt'):
                existing.ext.MCPServerExt.Stop()
        except Exception:
            pass
        existing.destroy()
        print('[MCP Plugin] Replaced existing COMP')

    # ---- 4. Create Base COMP ----
    comp = parent_op.create(baseCOMP, COMP_NAME)

    # ---- 5. Custom parameters ----
    page = comp.appendCustomPage('MCP Server')

    p = page.appendFile('Serverfile', label='Server File')[0]
    p.default = server_file
    p.val = server_file

    p = page.appendInt('Port', label='Port')[0]
    p.default = 8053
    p.val = 8053
    p.min = 1024
    p.max = 65535
    p.clampMin = True
    p.clampMax = True

    p = page.appendToggle('Autostart', label='Auto Start')[0]
    p.default = True
    p.val = True

    p = page.appendStr('Status', label='Status')[0]
    p.default = 'Stopped'
    p.val = 'Stopped'
    p.readOnly = True

    page.appendPulse('Start', label='Start Server')
    page.appendPulse('Stop', label='Stop Server')
    page.appendPulse('Reload', label='Reload Code')

    # ---- 6. Child operators ----

    # Server code Text DAT
    server_dat = comp.create(textDAT, 'server_code')
    server_dat.text = server_code
    server_dat.nodeX = 0
    server_dat.nodeY = 0
    server_dat.viewer = False

    # Extension Text DAT
    ext_dat = comp.create(textDAT, 'MCPServerExt')
    ext_dat.text = EXTENSION_CODE
    ext_dat.nodeX = 400
    ext_dat.nodeY = 0
    ext_dat.viewer = False

    # Parameter Execute DAT (routes pulse buttons to extension)
    try:
        par_exec = comp.create(parameterexecuteDAT, 'par_callbacks')
        par_exec.text = PAR_EXEC_CODE
        par_exec.nodeX = 800
        par_exec.nodeY = 0
        par_exec.viewer = False
        # Point it at the parent COMP
        _linked = False
        for attr in ('op', 'ops', 'operator'):
            try:
                setattr(par_exec.par, attr, '..')
                _linked = True
                break
            except Exception:
                continue
        if not _linked:
            print('[MCP Plugin] NOTE: Open par_callbacks and set Operator to ".."')
    except Exception:
        print('[MCP Plugin] NOTE: parameterexecuteDAT unavailable — use Textport for Start/Stop')

    # ---- 7. Wire up the extension ----
    try:
        comp.par.extension1 = 'MCPServerExt'
        comp.par.promoteExtension1 = True
    except Exception as e:
        print('[MCP Plugin] NOTE: Set Extension 1 = "MCPServerExt" manually ({})'.format(e))

    # ---- 8. Visual polish ----
    try:
        comp.color = (0.18, 0.45, 0.76)
        comp.comment = 'MCP Server — Claude <> TouchDesigner'
    except Exception:
        pass
    comp.nodeX = 0
    comp.nodeY = -200

    # ---- Done ----
    print('')
    print('=' * 60)
    print('  MCP SERVER PLUGIN INSTALLED')
    print('=' * 60)
    print('')
    print('  COMP:       {}'.format(comp.path))
    print('  Server:     {:,} bytes embedded'.format(len(server_code)))
    print('  Port:       8053  (change in custom parameters)')
    print('  Auto-start: ON    (server starts on project open)')
    print('')
    print('  SAVE AS REUSABLE PLUGIN:')
    print('    Right-click {} > Save Component .tox'.format(comp.path))
    print('')
    print('  MANUAL CONTROL (Textport):')
    print("    op('{}').Start()".format(comp.path))
    print("    op('{}').Stop()".format(comp.path))
    print("    op('{}').Reload()".format(comp.path))
    print('')
    return comp


# ---- Run ----
install_mcp_plugin()
