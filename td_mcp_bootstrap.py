# TouchDesigner MCP Bootstrap - Paste this into an Execute DAT
#
# Setup:
# 1. Clone/download the repo: https://github.com/superdwayne/Touchdesigner-mcp
# 2. In TouchDesigner, create an Execute DAT (e.g., /project1/mcp_bootstrap)
# 3. Paste this entire script into it
# 4. In the Execute DAT parameters, enable "Start" and "Exit"
# 5. Set REPO_PATH below to where you cloned the repo on YOUR machine
# 6. Save your .toe file — the server auto-starts on every project open
#
# That's it! No Textport commands needed.

import os

# ===================== CONFIGURE THIS =====================
# Set this to the folder where you cloned/downloaded the repo.
# Examples:
#   macOS:   '/Users/yourname/Documents/Touchdesigner-mcp'
#   Windows: r'C:\Users\yourname\Documents\Touchdesigner-mcp'
#   Linux:   '/home/yourname/Touchdesigner-mcp'
REPO_PATH = ''

# Where to create the server Text DAT inside TouchDesigner
SERVER_DAT_NAME = 'mcp_server'        # Name of the Text DAT
SERVER_DAT_PARENT = '/project1'       # Parent COMP for the Text DAT

# Server filename (you shouldn't need to change this)
SERVER_FILENAME = 'td_mcp_server_auso_v2.py'
# ==========================================================


def _find_server_file():
	"""Find the server .py file, trying REPO_PATH first, then auto-detection."""
	# 1. If user set REPO_PATH, use it directly
	if REPO_PATH:
		repo = REPO_PATH
		# Guard: if user pointed REPO_PATH at the file itself, use its parent dir
		if os.path.isfile(repo):
			repo = os.path.dirname(repo)
		candidate = os.path.join(repo, SERVER_FILENAME)
		if os.path.isfile(candidate):
			return candidate
		print(f'[MCP Bootstrap] WARNING: Not found at REPO_PATH: {candidate}')

	# 2. Try to find it relative to the .toe project file
	try:
		toe_path = project.folder
		if toe_path:
			# Check if server file is in same folder as the .toe
			candidate = os.path.join(toe_path, SERVER_FILENAME)
			if os.path.isfile(candidate):
				return candidate
			# Check parent folder (if .toe is inside the repo)
			candidate = os.path.join(os.path.dirname(toe_path), SERVER_FILENAME)
			if os.path.isfile(candidate):
				return candidate
	except Exception:
		pass

	# 3. Try common locations
	home = os.path.expanduser('~')
	common_paths = [
		os.path.join(home, 'Documents', 'Touchdesigner-mcp'),
		os.path.join(home, 'Desktop', 'Touchdesigner-mcp'),
		os.path.join(home, 'Touchdesigner-mcp'),
		os.path.join(home, 'Downloads', 'Touchdesigner-mcp'),
	]
	for folder in common_paths:
		candidate = os.path.join(folder, SERVER_FILENAME)
		if os.path.isfile(candidate):
			print(f'[MCP Bootstrap] Auto-detected server at: {candidate}')
			return candidate

	return None


def onStart():
	"""Called when TouchDesigner project opens."""
	_load_and_start()


def onCreate():
	"""Called when this Execute DAT is created."""
	pass


def onExit():
	"""Called when TouchDesigner closes - clean shutdown."""
	try:
		parent_op = op(SERVER_DAT_PARENT)
		if parent_op:
			server_dat = parent_op.op(SERVER_DAT_NAME)
			if server_dat:
				mod = server_dat.module
				if hasattr(mod, 'stop_mcp_server'):
					mod.stop_mcp_server()
					print('[MCP Bootstrap] Server stopped on exit.')
	except Exception as e:
		print(f'[MCP Bootstrap] Error during shutdown: {e}')


def _load_and_start():
	"""Load the server file into a Text DAT and start the MCP server."""
	server_file = _find_server_file()

	if not server_file:
		print('[MCP Bootstrap] ERROR: Could not find ' + SERVER_FILENAME)
		print('[MCP Bootstrap] Please set REPO_PATH in this Execute DAT to your repo folder.')
		print('[MCP Bootstrap] Example: REPO_PATH = r"/Users/yourname/Documents/Touchdesigner-mcp"')
		return

	# Read the server code from disk
	with open(server_file, 'r', encoding='utf-8') as f:
		server_code = f.read()

	# Get or create the Text DAT
	parent_op = op(SERVER_DAT_PARENT)
	if not parent_op:
		print(f'[MCP Bootstrap] ERROR: Parent "{SERVER_DAT_PARENT}" not found.')
		return

	server_dat = parent_op.op(SERVER_DAT_NAME)
	if not server_dat:
		server_dat = parent_op.create(textDAT, SERVER_DAT_NAME)
		print(f'[MCP Bootstrap] Created {server_dat.path}')

	# Load the code
	server_dat.text = server_code
	print(f'[MCP Bootstrap] Loaded from: {server_file} ({len(server_code)} bytes)')

	# Auto-start the server (no Textport needed!)
	run(f"op('{server_dat.path}').module.start_mcp_server(op('{server_dat.path}'))", delayFrames=2)
	print(f'[MCP Bootstrap] Server start scheduled on {server_dat.path}')
