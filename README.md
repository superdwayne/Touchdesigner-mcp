# TouchDesigner MCP Server

This is a Model Context Protocol (MCP) server for TouchDesigner, allowing AI tools like Claude to interact with TouchDesigner projects.

With this integration, you can create and manipulate components in TouchDesigner, set parameters, execute Python code, and much more - all through natural language interactions with Claude.

## Overview

This project provides a bridge between Anthropic's Claude and TouchDesigner by implementing the Model Context Protocol (MCP). It consists of two main components:

1. **TouchDesigner Server** (`td_mcp_server_auso_v2.py`): A Python HTTP server running inside TouchDesigner that handles commands and provides an API on port **8053**.
2. **MCP Proxy Server** (`td-mcp-proxy/index.js`): A Node.js application that translates between MCP JSON-RPC and the TouchDesigner HTTP server.

## Key Feature: Result Feedback

Unlike simple fire-and-forget approaches, this server returns **actual results** from TouchDesigner back to Claude. When Claude creates a node, it receives the path, type, position, and connections. When it reads a parameter, it gets the real value. This enables Claude to verify its work and make informed follow-up decisions.

## Features

The TouchDesigner MCP server allows Claude to:

- **Create** operators with smart auto-positioning, auto-wiring, and type resolution (supports natural names like "webcam", "blur", "mic")
- **Delete** operators (with protection for critical paths)
- **Get/Set** parameter values (with case-insensitive lookup and expression support)
- **Set Many** parameters in a single batch operation
- **List** operators and their children (with type filtering)
- **List Parameters** of any operator with current values
- **List Types** available in the current TouchDesigner build
- **Execute Python** code directly in TouchDesigner
- **Connect Nodes** in sequence, parallel, or custom patterns
- **Auto-Connect** two nodes with smart type-based routing
- **Build Workflows** from presets (audio, interactive installation, 3D render scene)
- **Layout** networks into clean grids grouped by family
- **Ensure Inputs** by creating fallback sources for multi-input operators
- **Show Preview** by opening operator viewers

## Prerequisites

- [TouchDesigner](https://derivative.ca/download) 2023 or newer
- [Node.js](https://nodejs.org/) 16.x or newer
- [Anthropic Claude Desktop](https://claude.ai/desktop) or other MCP-compatible client

## Installation

### 1. Clone or download this repository

```bash
git clone https://github.com/yourusername/touchdesigner-mcp.git
cd touchdesigner-mcp
```

### 2. Set up the Node.js MCP proxy

```bash
cd td-mcp-proxy
npm install express axios
```

### 3. Configure TouchDesigner

1. Open TouchDesigner
2. Create a new project
3. Import `td_mcp_server_auso_v2.py` into a Text DAT in your project
4. Run the script to start the server (it listens on port **8053** by default)

## Configuration

### For Claude Desktop

Add the following to your Claude Desktop configuration file:

**Stdio Transport (Recommended)**:

```json
{
  "mcpServers": {
    "TouchDesigner": {
      "command": "node",
      "args": ["/path/to/your/touchdesigner-mcp/td-mcp-proxy/index.js"],
      "env": {
        "TRANSPORT": "stdio",
        "TD_SERVER_URL": "http://localhost:8053"
      }
    }
  }
}
```

**SSE Transport**:

First, start the SSE server:

```bash
cd /path/to/your/touchdesigner-mcp/td-mcp-proxy
TRANSPORT=sse node index.js
```

Then, configure Claude:

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

Save this configuration to:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TD_MCP_PORT` | `8053` | Port the Python server listens on inside TouchDesigner |
| `TD_SERVER_URL` | `http://localhost:8053` | URL the proxy uses to reach the TD server |
| `TRANSPORT` | `stdio` | Proxy transport mode: `stdio` or `sse` |
| `PORT` | `8050` | Port for SSE transport mode |
| `TD_MCP_PROTECTED_PATHS` | (none) | Comma-separated paths to protect from deletion |

## Usage

Once connected, you can use natural language to interact with TouchDesigner through Claude.

### Example Commands

- `create a circle`
- `create a text component with message "Hello World"`
- `list all components`
- `set /project1/circle1 radius 0.5`
- `get the resolution of /project1/moviefilein1`
- `list parameters of /project1/circle1`
- `execute_python "result = [c.name for c in op('/project1').children]"`

### Auto-connecting creation

The `create` tool supports auto-wiring newly created nodes:

- `auto_connect` (boolean, default true): when true and no explicit source is given, the new node's first input is wired to the most recently created compatible sibling.
- `connect_source` (string): explicit operator path to wire from.
- `connect_parameter` (string): either an input name like `input1`/`input2` (wires the corresponding input), or a parameter name on the new node.
- `family` (string): family hint (TOP/CHOP/SOP/DAT/COMP/MAT) to disambiguate types like "null" or "transform".

### High-level workflows

Use the `build_workflow` tool to turn natural requests into working node graphs:

- Presets: `audio_experience`, `interactive_installation`, `render_scene`
- Options: `parent` (default `/project1`), `name_prefix`, `open_preview` (default true)

### Type Resolution

You can use common names - the server resolves them to TD operator types:
- **TOP**: blur, feedback, switch, null, circle, noise, ramp, level, composite, webcam, movie, image
- **CHOP**: mic, lfo, constant, math, filter, lag, timer, keyboard, mouse, osc, midi
- **SOP**: sphere, box, grid, torus, transform, merge, boolean, polyextrude
- **COMP**: geometry/geo, camera/cam, light, container, base, window
- **MAT**: phong, pbr, material
- **DAT**: text, table, script, json, webclient

Add the family suffix if ambiguous (e.g., "transform SOP" vs "transform TOP").

## Troubleshooting

### Connection Issues

- Make sure the TouchDesigner server is running and accessible at http://localhost:8053
- Check if the MCP proxy is running correctly
- Verify that your Claude Desktop configuration is correct
- Restart Claude Desktop after making configuration changes

### TouchDesigner Issues

- Ensure the Python script is running in TouchDesigner
- Check the TextPort in TouchDesigner for any error messages
- Verify that port 8053 is not being used by another application

### Log Files

The MCP proxy creates a log file at `/tmp/td-mcp-debug.log` (auto-truncated at 5MB on startup).

## Advanced Configuration

### Changing the TouchDesigner Server Port

Set the `TD_MCP_PORT` environment variable in TouchDesigner, and update `TD_SERVER_URL` in your Claude configuration to match.

### Changing the MCP Proxy Port (SSE mode)

Set the `PORT` environment variable when starting the proxy, and update the `serverUrl` in your Claude configuration.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
