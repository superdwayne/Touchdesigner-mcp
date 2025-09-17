# TouchDesigner MCP Server

This is a Model Context Protocol (MCP) server for TouchDesigner, allowing AI tools like Claude to interact with TouchDesigner projects.

With this integration, you can create and manipulate components in TouchDesigner, set parameters, execute Python code, and much more - all through natural language interactions with Claude.

## Overview

This project provides a bridge between Anthropic's Claude and TouchDesigner by implementing the Model Context Protocol (MCP). It consists of two main components:

1. **TouchDesigner Server**: A Python HTTP server running in TouchDesigner that handles commands and provides an API.
2. **MCP Proxy Server**: A Node.js application that translates between the MCP format and the TouchDesigner server.

## Features

The TouchDesigner MCP server allows Claude to:

- Create various TouchDesigner components (circles, text, noise generators, etc.)
- List components in a project
- Delete components
- Get and set parameter values
- Execute Python code directly in TouchDesigner
- Query component information

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
3. Import the `td_mcp_server.py` script into a Text DAT in your project
4. Run the script to start the server (it will listen on port 8051 by default)

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
        "TD_SERVER_URL": "http://localhost:8051"
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

### For Other MCP Clients

For other MCP-compatible clients, refer to their specific documentation for configuring external MCP servers.

## Usage

Once connected, you can use natural language to interact with TouchDesigner through Claude.

### Example Commands

- `create a circle`
- `create a text component with message "Hello World"`
- `list all components`
- `set /project1/text1 text "Updated text"`
- `get the resolution of /project1/moviefilein1`
- `execute_python "op('/project1/text1').text = 'Hello from Python'"`

## Troubleshooting

### Connection Issues

- Make sure the TouchDesigner server is running and accessible at http://localhost:8051
- Check if the MCP proxy is running correctly
- Verify that your Claude Desktop configuration is correct and in the right location
- Restart Claude Desktop after making configuration changes

### TouchDesigner Issues

- Ensure the Python script is running in TouchDesigner
- Check the TextPort in TouchDesigner for any error messages
- Verify that port 8051 is not being used by another application

### Log Files

The MCP proxy creates a log file at `/tmp/td-mcp-debug.log` which can be helpful for diagnosing issues.

## Advanced Configuration

### Changing the TouchDesigner Server Port

If you need to change the default port (8051) that TouchDesigner listens on:

1. Modify the port in the `td_mcp_server.py` script
2. Update the `TD_SERVER_URL` environment variable in your Claude configuration

### Changing the MCP Proxy Port (SSE mode)

If you need to change the default port (8050) that the MCP proxy listens on in SSE mode:

1. Set the `PORT` environment variable when starting the proxy
2. Update the `serverUrl` in your Claude configuration

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 