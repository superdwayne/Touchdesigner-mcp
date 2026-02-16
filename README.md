# TouchDesigner MCP Server

Control TouchDesigner with AI through natural language. This MCP (Model Context Protocol) server lets Claude create operators, set parameters, execute Python, build node graphs, and more — all inside a running TouchDesigner project.

## Quick Start

There are **three things** to set up: the TD server, the Node.js proxy, and your Claude config.

### 1. TouchDesigner Setup (the server)

#### Step 1: Open TouchDesigner

Open TouchDesigner (2023 or newer) and create or open a project. You should see the default `/project1` container in the network editor.

#### Step 2: Create a Text DAT

- Double-click the network background (or press **Tab**) to open the operator menu
- Navigate to **DAT → Text** and place a Text DAT in your network
- It will be named something like `text1` by default

#### Step 3: Paste the server script

- Double-click the Text DAT to open its editor
- Select all and delete any default content
- Open `td_mcp_server_auso_v2.py` from this repo in any text editor
- **Copy the entire file** and paste it into the Text DAT editor
- Close the editor (click outside or press Escape)

#### Step 4: Start the server

Open the **Textport** (menu: **Dialogs → Textport and DATs**) and run:

```python
op('/project1/text1').module.start_mcp_server(op('/project1/text1'))
```

> Replace `text1` with the actual name of your Text DAT if different.

You should see:

```
Starting MCP server on http://127.0.0.1:8053 (DAT: /project1/text1) ...
MCP Server started successfully.
```

#### Step 5: Verify it's running

Visit http://localhost:8053/api/status in a browser. You should get a JSON response confirming the server is active.

#### Stopping the server

To stop the server later, run in the Textport:

```python
op('/project1/text1').module.stop_mcp_server()
```

#### Warnings you can ignore

On startup you may see warnings like:

```
Warning: audioDeviceInCHOP not available in this TouchDesigner version
Warning: lutTOP not available in this TouchDesigner version
```

These are harmless — some operator types aren't available in every TD build and are gracefully skipped.

---

### 2. Node.js Proxy Setup

The proxy translates between the MCP protocol (used by Claude) and the HTTP server running inside TouchDesigner.

```bash
git clone https://github.com/superdwayne/Touchdesigner-mcp.git
cd Touchdesigner-mcp/td-mcp-proxy
npm install
```

You don't need to run the proxy manually if using **stdio** transport (recommended) — Claude Desktop launches it automatically.

---

### 3. Claude Desktop Configuration

Add the following to your Claude Desktop config file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

#### Stdio Transport (Recommended)

```json
{
  "mcpServers": {
    "TouchDesigner": {
      "command": "node",
      "args": ["/path/to/Touchdesigner-mcp/td-mcp-proxy/index.js"],
      "env": {
        "TRANSPORT": "stdio",
        "TD_SERVER_URL": "http://localhost:8053"
      }
    }
  }
}
```

> Replace `/path/to/` with the actual path to your cloned repo.

#### SSE Transport (Alternative)

Start the proxy manually first:

```bash
cd /path/to/Touchdesigner-mcp/td-mcp-proxy
TRANSPORT=sse node index.js
```

Then configure Claude:

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

**Restart Claude Desktop** after saving the config.

---

## Startup Checklist

Every time you want to use this:

1. Open **TouchDesigner** with your project
2. Run in the Textport:
   ```python
   op('/project1/text1').module.start_mcp_server(op('/project1/text1'))
   ```
3. Open **Claude Desktop** (it connects to the proxy automatically)
4. Start talking to Claude about your TouchDesigner project

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
