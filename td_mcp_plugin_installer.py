"""
TouchDesigner MCP Server Plugin Installer
==========================================
Creates a self-contained Base COMP with the MCP server,
ready to save as a reusable .tox plugin.

Usage (in TouchDesigner Textport):

  If your .toe file is inside the cloned repo folder:
    exec(open(project.folder + '/td_mcp_plugin_installer.py').read())

  Otherwise, use the full path:
    exec(open('/path/to/Touchdesigner-mcp/td_mcp_plugin_installer.py').read())

  If auto-detection can't find the server file, set REPO_PATH first:
    REPO_PATH = '/path/to/Touchdesigner-mcp'; exec(open(REPO_PATH + '/td_mcp_plugin_installer.py').read())
"""

import os

# ===================== CONFIGURATION =====================
# Set this if auto-detection fails (point to the repo FOLDER):
try:
    REPO_PATH
except NameError:
    REPO_PATH = ''

COMP_NAME = 'td_mcp_server'
COMP_PARENT = '/project1'
SERVER_FILENAME = 'td_mcp_server_auso_v2.py'
# =========================================================


# --------------- Execute DAT callbacks (lifecycle management) ---------------
CALLBACKS_CODE = '''# MCP Server Plugin — lifecycle callbacks
# This Execute DAT manages start/stop and exposes Start()/Stop()/Reload().

import os
import time as _time

def onStart():
    """Called when the TouchDesigner project opens."""
    comp = parent()
    if comp.par.Autostart.eval():
        run("op('{}').module.Start()".format(me.path), delayFrames=5)

def onCreate():
    pass

def onExit():
    """Called when TouchDesigner closes."""
    Stop()


# ---- Public API: call these from the Textport ----

def Start():
    """Start the MCP server."""
    comp = parent()
    server_dat = comp.op('server_code')
    if not server_dat or not server_dat.text.strip():
        _loadCode()
    if not server_dat.text.strip():
        comp.par.Status = 'Error: no server code'
        print('[MCP Plugin] ERROR: No server code. Set Serverfile parameter.')
        return

    # Stop existing server to free the port
    _stopQuiet()
    _time.sleep(0.3)

    # Apply port from parameter
    port = comp.par.Port.eval()
    os.environ['TD_MCP_PORT'] = str(port)

    try:
        ok = server_dat.module.start_mcp_server(server_dat)
        if ok:
            comp.par.Status = 'Running (port {})'.format(port)
            print('[MCP Plugin] Server started on port {}'.format(port))
        else:
            comp.par.Status = 'Error: start failed'
            print('[MCP Plugin] start_mcp_server returned False')
    except Exception as e:
        comp.par.Status = 'Error'
        print('[MCP Plugin] Start failed: {}'.format(e))

def Stop():
    """Stop the MCP server."""
    _stopQuiet()
    print('[MCP Plugin] Server stopped')

def Reload():
    """Reload server code from disk and restart."""
    _stopQuiet()
    _time.sleep(0.5)
    _loadCode()
    Start()


# ---- Internal helpers ----

def _stopQuiet():
    comp = parent()
    server_dat = comp.op('server_code')
    if server_dat:
        try:
            mod = server_dat.module
            if hasattr(mod, 'stop_mcp_server'):
                mod.stop_mcp_server()
        except Exception:
            pass
    comp.par.Status = 'Stopped'

def _loadCode():
    comp = parent()
    server_file = comp.par.Serverfile.eval()
    if not server_file or not os.path.isfile(server_file):
        server_file = _autoDetect()
    if server_file and os.path.isfile(server_file):
        with open(server_file, 'r', encoding='utf-8') as f:
            code = f.read()
        comp.op('server_code').text = code
        print('[MCP Plugin] Loaded {} bytes from {}'.format(len(code), server_file))
    else:
        print('[MCP Plugin] Could not find server file on disk. Using embedded code.')

def _autoDetect():
    fn = 'td_mcp_server_auso_v2.py'
    try:
        toe = project.folder
        if toe:
            for d in [toe, os.path.dirname(toe)]:
                c = os.path.join(d, fn)
                if os.path.isfile(c):
                    return c
    except Exception:
        pass
    home = os.path.expanduser('~')
    for folder in [
        'Documents/Touchdesigner-mcp',
        'Documents/Playground/Touchdesigner-mcp',
        'Desktop/Touchdesigner-mcp',
        'Projects/Touchdesigner-mcp',
        'dev/Touchdesigner-mcp',
        'src/Touchdesigner-mcp',
        'Touchdesigner-mcp',
        'Downloads/Touchdesigner-mcp',
    ]:
        c = os.path.join(home, folder, fn)
        if os.path.isfile(c):
            return c
    return None
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
                    'Projects/Touchdesigner-mcp',
                    'dev/Touchdesigner-mcp',
                    'src/Touchdesigner-mcp',
                    'Touchdesigner-mcp',
                    'Downloads/Touchdesigner-mcp']:
        candidate = os.path.join(home, folder, SERVER_FILENAME)
        if os.path.isfile(candidate):
            print('[MCP Plugin] Auto-detected: {}'.format(candidate))
            return candidate
    return None


def _kill_existing_server():
    """Stop any running MCP server, regardless of where it was started."""
    import sys, time as _t
    stopped = False
    # Scan all loaded modules for one that looks like the MCP server
    for key, mod in list(sys.modules.items()):
        if hasattr(mod, 'stop_mcp_server') and getattr(mod, 'server_running', False):
            try:
                mod.stop_mcp_server()
                stopped = True
            except Exception:
                pass
    if stopped:
        print('[MCP Plugin] Stopped existing MCP server')
        _t.sleep(0.5)


def install_mcp_plugin():
    print('')
    print('[MCP Plugin] Installing TouchDesigner MCP Server plugin ...')
    print('')

    # ---- 0. Kill any running server to free the port ----
    _kill_existing_server()

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
            cb = existing.op('callbacks')
            if cb and hasattr(cb.module, 'Stop'):
                cb.module.Stop()
        except Exception:
            pass
        try:
            sd = existing.op('server_code')
            if sd and hasattr(sd.module, 'stop_mcp_server'):
                sd.module.stop_mcp_server()
        except Exception:
            pass
        existing.destroy()
        print('[MCP Plugin] Replaced existing COMP')

    # ---- 4. Create Base COMP ----
    comp = parent_op.create(baseCOMP, COMP_NAME)

    # ---- 5. Custom parameters ----
    page = comp.appendCustomPage('MCP Server')

    p = page.appendFile('Serverfile', label='Server File')[0]
    p.default = ''
    p.val = ''

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

    # Server code Text DAT (the full MCP server, embedded)
    server_dat = comp.create(textDAT, 'server_code')
    server_dat.text = server_code
    server_dat.nodeX = 0
    server_dat.nodeY = 0
    server_dat.viewer = False

    # Callbacks Execute DAT (lifecycle: auto-start, shutdown, Start/Stop/Reload)
    cb_dat = comp.create(executeDAT, 'callbacks')
    cb_dat.text = CALLBACKS_CODE
    cb_dat.nodeX = 400
    cb_dat.nodeY = 0
    cb_dat.viewer = False
    # Enable Start and Exit callbacks
    try:
        cb_dat.par.start = True
        cb_dat.par.exit = True
    except Exception:
        print('[MCP Plugin] NOTE: Enable "Start" and "Exit" on the callbacks Execute DAT')

    # ---- 7. Visual polish ----
    try:
        comp.color = (0.18, 0.45, 0.76)
        comp.comment = 'MCP Server — Claude <> TouchDesigner'
    except Exception:
        pass
    comp.nodeX = 0
    comp.nodeY = -200

    # ---- 8. Start the server now ----
    cb_path = cb_dat.path
    run("op('{}').module.Start()".format(cb_path), delayFrames=5)

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
    print("    op('{}/callbacks').module.Start()".format(comp.path))
    print("    op('{}/callbacks').module.Stop()".format(comp.path))
    print("    op('{}/callbacks').module.Reload()".format(comp.path))
    print('')
    return comp


# ---- Run ----
install_mcp_plugin()
