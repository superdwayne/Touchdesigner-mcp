# TouchDesigner MCP Server

Control TouchDesigner with AI through natural language. This MCP (Model Context Protocol) server lets Claude create operators, set parameters, execute Python, build node graphs, and more — all inside a running TouchDesigner project.

## One-Click Install

Download the latest `.mcpb` bundle and double-click to install in Claude Desktop:

[**touchdesigner-mcp-1.0.0.mcpb**](https://github.com/superdwayne/Touchdesigner-mcp/releases/latest/download/touchdesigner-mcp-1.0.0.mcpb) (1.3 MB)

> Double-click to install. No terminal commands, no configuration files. You still need to set up the TouchDesigner side — see [TouchDesigner Setup](#1-touchdesigner-setup-the-server) below.

---

## Quick Start

There are **three things** to set up: the TD server, the Node.js proxy, and your Claude config. If you used the one-click install above, skip to step 1 (TouchDesigner Setup) — the proxy is already configured.

### 1. TouchDesigner Setup (the server)

This is the most important part. You need to run a small Python server **inside** TouchDesigner that listens for commands from Claude.

#### Step 1: Open TouchDesigner

Open TouchDesigner (2023 or newer) and create or open a project. You should see the default `/project1` container in the network editor.

#### Step 2: Set up the server (choose one method)

**Option A: Plugin Installer (Recommended)** — creates a self-contained COMP you can save as a `.tox` and reuse in any project.

1. Clone the repo:
   ```bash
   git clone https://github.com/superdwayne/Touchdesigner-mcp.git
   ```

2. Open the **Textport** (**Dialogs → Textport and DATs**) and run **one** of these:

   If your `.toe` file is saved **inside** the repo folder (easiest):
   ```python
   exec(open(project.folder + '/td_mcp_plugin_installer.py').read())
   ```

   Otherwise, use the full path to where you cloned the repo:
   ```python
   exec(open('/Users/yourname/Touchdesigner-mcp/td_mcp_plugin_installer.py').read())
   ```

3. A `td_mcp_server` Base COMP appears in `/project1` with custom parameters:
   - **Port** — server port (default 8053)
   - **Auto Start** — starts the server on project open (default ON)
   - **Start / Stop / Reload** — pulse buttons for manual control

4. **Save as reusable plugin:** Right-click the COMP → **Save Component .tox**
   Next time, just drag the `.tox` into any project — no installer needed, no repo required.

5. **Save your `.toe` file** to keep the plugin in this project.

> **Tip:** The server code is **embedded** inside the COMP. The `.tox` is fully self-contained — you can share it with others and it works without the repo.

---

**Option B: Auto-Bootstrap** — a lighter approach. The server loads and starts automatically every time you open your project.

1. In TouchDesigner, **Tab** → **DAT** → **Execute** to create an Execute DAT
2. Open the file **`td_mcp_bootstrap.py`** from this repo and **copy its entire contents**
3. Double-click the Execute DAT and **paste** it in
4. Set `REPO_PATH` to where you cloned this repo on your machine, e.g.:
   - macOS: `'/Users/yourname/Documents/Touchdesigner-mcp'`
   - Windows: `r'C:\Users\yourname\Documents\Touchdesigner-mcp'`

   > **Tip:** If you save your `.toe` file inside the repo folder, you can leave `REPO_PATH` empty — it auto-detects!
5. In the Execute DAT parameters (right panel), toggle **Start** → `On` and **Exit** → `On`
6. **Save your `.toe` file**

That's it! Every time you open the project, the server starts automatically. No Textport commands needed.

To start it right now without reopening:
```python
op('/project1/mcp_bootstrap').module.onStart()
```

---

**Option C: Manual Setup** — paste the server code directly and start via the Textport.

1. **Tab** → **DAT** → **Text** to create a Text DAT (e.g., `text1`)
2. Open **`td_mcp_server_auso_v2.py`** from this repo, copy the entire contents, and paste into the Text DAT
3. Open the **Textport** (**Dialogs → Textport and DATs**) and run:

```python
op('/project1/text1').module.start_mcp_server(op('/project1/text1'))
```

> Replace `text1` with the actual name of your Text DAT if different.

You should see:
```
Starting MCP server on http://127.0.0.1:8053 (DAT: /project1/text1) ...
MCP Server started successfully.
```

#### Step 3: Verify it's running

Open a browser and visit: http://localhost:8053/api/status

You should get a JSON response confirming the server is active.

#### Stopping the server

The server stops automatically when you close TouchDesigner.

To stop manually, run in the Textport:

```python
# Option A (Plugin):
op('/project1/td_mcp_server').Stop()

# Option B (Bootstrap):
op('/project1/mcp_server').module.stop_mcp_server()

# Option C (Manual):
op('/project1/text1').module.stop_mcp_server()
```

#### Restarting after an error

If you get `Address already in use`, stop the server first then start it again:

```python
# Option A (Plugin) — handles it automatically, or:
op('/project1/td_mcp_server').Stop()
op('/project1/td_mcp_server').Start()
```

For Options B/C, **save your project and restart TouchDesigner**.

#### Warnings you can safely ignore

On startup you may see warnings like:

```
Warning: audioDeviceInCHOP not available in this TouchDesigner version
Warning: lutTOP not available in this TouchDesigner version
```

These are normal — some operator types don't exist in every TD build. The server skips them gracefully and works fine without them.

---

### 2. Node.js Proxy Setup

The proxy sits between Claude and TouchDesigner, translating MCP messages into HTTP calls.

#### Step 1: Clone and install

```bash
git clone https://github.com/superdwayne/Touchdesigner-mcp.git
cd Touchdesigner-mcp/td-mcp-proxy
npm install
```

#### Step 2: Find your absolute path to `index.js`

You'll need the **full path** to `td-mcp-proxy/index.js` on your computer. Run this to get it:

```bash
cd Touchdesigner-mcp/td-mcp-proxy
pwd
```

This will print something like:

- **macOS**: `/Users/yourname/Projects/Touchdesigner-mcp/td-mcp-proxy`
- **Windows**: `C:\Users\yourname\Projects\Touchdesigner-mcp\td-mcp-proxy`

Your full path to index.js is that output + `/index.js`. For example:
`/Users/yourname/Projects/Touchdesigner-mcp/td-mcp-proxy/index.js`

**Copy this path** — you'll paste it into the Claude config in the next step.

> You don't need to run the proxy manually — Claude Desktop launches it automatically.

---

### 3. Claude Desktop Configuration

#### Step 1: Open the config file

Open your Claude Desktop configuration file in a text editor:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

If the file doesn't exist, create it.

#### Step 2: Add the TouchDesigner MCP server

Paste this into the config file, **replacing the path** with the one you copied in step 2 above:

```json
{
  "mcpServers": {
    "TouchDesigner": {
      "command": "node",
      "args": ["/YOUR/ACTUAL/PATH/TO/Touchdesigner-mcp/td-mcp-proxy/index.js"],
      "env": {
        "TRANSPORT": "stdio",
        "TD_SERVER_URL": "http://localhost:8053"
      }
    }
  }
}
```

**Example (macOS):**
```json
{
  "mcpServers": {
    "TouchDesigner": {
      "command": "node",
      "args": ["/Users/dwayne/Projects/Touchdesigner-mcp/td-mcp-proxy/index.js"],
      "env": {
        "TRANSPORT": "stdio",
        "TD_SERVER_URL": "http://localhost:8053"
      }
    }
  }
}
```

**Example (Windows):**
```json
{
  "mcpServers": {
    "TouchDesigner": {
      "command": "node",
      "args": ["C:\\Users\\dwayne\\Projects\\Touchdesigner-mcp\\td-mcp-proxy\\index.js"],
      "env": {
        "TRANSPORT": "stdio",
        "TD_SERVER_URL": "http://localhost:8053"
      }
    }
  }
}
```

> **Do not use `/path/to/` literally.** You must replace it with the real path on your computer.

#### Step 3: Restart Claude Desktop

**Quit and reopen Claude Desktop** for the config to take effect.

#### Alternative: SSE Transport

If you prefer SSE transport, start the proxy manually:

```bash
cd /path/to/Touchdesigner-mcp/td-mcp-proxy
TRANSPORT=sse node index.js
```

Then use this config instead:

```json
{
  "mcpServers": {
    "TouchDesigner": {
      "transport": "sse",
      "serverUrl": "http://localhost:8050/sse"
    }
  }
}
```

---

## Startup Checklist

Every time you want to use this:

1. **Open TouchDesigner** with your project
2. **If using the Plugin (Option A):** the server starts automatically — check the Textport for `MCP Server started successfully.`
3. **If using Manual Setup (Option C):** open the Textport and run:
   ```python
   op('/project1/text1').module.start_mcp_server(op('/project1/text1'))
   ```
4. **Open Claude Desktop** — it connects to the proxy automatically
5. **Start talking** to Claude about your TouchDesigner project

---

## Features

- **Create** operators with smart auto-positioning, auto-wiring, and natural name resolution (`"webcam"`, `"blur"`, `"mic"`)
- **Delete** operators (with protection for critical paths)
- **Get/Set** parameter values (case-insensitive lookup, expression support)
- **Set Many** parameters in a single batch
- **List** operators, children, parameters, and available types
- **Execute Python** code directly inside TouchDesigner
- **Connect Nodes** in sequence, parallel, or custom patterns
- **Auto-Connect** two nodes with smart type-based routing
- **Build Workflows** from presets (audio, interactive installation, 3D render scene)
- **Layout** networks into clean grids grouped by family
- **Show Preview** by opening operator viewers
- **Timeline** control (play, pause, set frame/FPS/range)
- **CHOP Export** bindings for audio-reactive and data-driven visuals
- **Custom Parameters** on COMPs for user-facing controls
- **Node Styling** with colors, comments, and tags

## Example Commands

Once connected, just talk naturally to Claude:

```
create a circle
create a text TOP with message "Hello World"
list all components in /project1
set /project1/circle1 radius 0.5
list parameters of /project1/noise1
create a webcam input and connect it to a blur
build me an audio experience
execute python: result = [c.name for c in op('/project1').children]
```

### Auto-connect

- `auto_connect` (default true) — wires new nodes to the most recent same-family sibling
- `connect_source` — explicit source operator path
- `connect_parameter` — input name (`input1`) or parameter name for connection
- `family` — hint (TOP/CHOP/SOP/DAT/COMP/MAT) to disambiguate ambiguous types

### Workflow Presets

Use `build_workflow` for instant node graphs:

- `audio_experience` — Audio Device In → Out CHOP with viewer
- `interactive_installation` — Movie File In → Out TOP with viewer
- `render_scene` — Geometry + SOP, Phong MAT, Camera, Light, Render TOP

### Natural Type Names

Use common names — the server resolves them:

| Family | Aliases |
|---|---|
| **TOP** | blur, feedback, switch, null, circle, noise, ramp, level, composite, webcam, movie, image |
| **CHOP** | mic, lfo, constant, math, filter, lag, timer, keyboard, mouse, osc, midi |
| **SOP** | sphere, box, grid, torus, transform, merge, boolean, polyextrude |
| **COMP** | geometry/geo, camera/cam, light, container, base, window |
| **MAT** | phong, pbr, material |
| **DAT** | text, table, script, json, webclient |

Add the family suffix if ambiguous (e.g., `"transform SOP"` vs `"transform TOP"`).

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TD_MCP_PORT` | `8053` | Port the Python server listens on inside TouchDesigner |
| `TD_SERVER_URL` | `http://localhost:8053` | URL the proxy uses to reach the TD server |
| `TRANSPORT` | `stdio` | Proxy transport mode: `stdio` or `sse` |
| `PORT` | `8050` | Port for SSE transport mode |
| `TD_MCP_PROTECTED_PATHS` | _(none)_ | Comma-separated operator paths to protect from deletion |

## Troubleshooting

### Server won't start in TouchDesigner

- Make sure you pasted the **entire** contents of `td_mcp_server_auso_v2.py` into the Text DAT
- Make sure you're calling `start_mcp_server()` with the DAT reference — just running the script (`op('text1').run()`) only loads the code, it doesn't start the server
- Check the Textport for error messages
- Verify port 8053 isn't already in use

### Claude can't connect

- Confirm the TD server is running: visit http://localhost:8053/api/status in a browser
- Check your `claude_desktop_config.json` has the correct path to `index.js`
- Restart Claude Desktop after config changes
- Check the proxy log at `/tmp/td-mcp-debug.log`

### Port conflicts

Change the TD server port with the `TD_MCP_PORT` environment variable and update `TD_SERVER_URL` in your Claude config to match.

## Architecture

```
Claude Desktop  ←→  MCP Proxy (Node.js, stdio/SSE)  ←→  TD HTTP Server (Python, port 8053)  ←→  TouchDesigner
```

The proxy translates MCP JSON-RPC messages into HTTP calls to the Python server running inside TouchDesigner. The Python server uses `run()` to dispatch all TD API calls on the main thread and returns structured results back through the chain.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
