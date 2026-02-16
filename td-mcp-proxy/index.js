const net = require("net");
const axios = require("axios");
const process = require("process");
const fs = require("fs");
const express = require("express");

// Transport type - "stdio" or "sse"
const TRANSPORT = process.env.TRANSPORT || "stdio";
// TouchDesigner server URL - Ensure this matches the TD server port
const TD_SERVER_URL = process.env.TD_SERVER_URL || "http://localhost:8053";
// Port to use for SSE server (if using SSE transport)
const PORT = process.env.PORT || 8050;

const LOG_FILE = "/tmp/td-mcp-debug.log";
const LOG_MAX_BYTES = 5 * 1024 * 1024; // 5MB

// Truncate log file on startup if over limit
try {
  const stats = fs.statSync(LOG_FILE);
  if (stats.size > LOG_MAX_BYTES) {
    fs.writeFileSync(LOG_FILE, `[INFO] Log truncated at startup (was ${stats.size} bytes)\n`);
  }
} catch (err) {
  // File doesn't exist yet, that's fine
}

// Log to stderr (will show in Claude logs)
function log(message) {
  console.error(message);
  try {
    fs.appendFileSync(LOG_FILE, message + "\n");
  } catch (err) {
    console.error(`Failed to write to debug log: ${err.message}`);
  }
}

// Per-tool timeout configuration (ms)
const TOOL_TIMEOUTS = {
  get: 10000,
  list: 10000,
  list_types: 10000,
  list_parameters: 10000,
  show_preview: 10000,
  timeline: 10000,
  create: 15000,
  delete: 15000,
  set: 15000,
  set_many: 15000,
  connect_nodes: 15000,
  auto_connect: 15000,
  ensure_inputs: 15000,
  layout: 15000,
  disconnect: 15000,
  rename: 15000,
  set_text: 15000,
  chop_export: 15000,
  custom_par: 15000,
  node_style: 15000,
  build_workflow: 30000,
  execute_python: 30000,
};

log(`[DEBUG] Process started with PID: ${process.pid}`);
log(`[DEBUG] Working directory: ${process.cwd()}`);
log(`[DEBUG] Node version: ${process.version}`);
log(`[DEBUG] Transport: ${TRANSPORT}`);
log(`[DEBUG] TD_SERVER_URL: ${TD_SERVER_URL}`);
log(`[INFO] TouchDesigner MCP server proxy starting...`);

let buffer = "";
let initialized = false;
let clients = []; // For SSE transport

// Set up express for SSE transport
if (TRANSPORT === "sse") {
  const app = express();

  app.get("/", (req, res) => {
    res.json({
      status: "running",
      touchdesigner: true,
      version: "2.0.0",
    });
  });

  app.get("/sse", (req, res) => {
    log("[INFO] SSE client connected");
    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("Connection", "keep-alive");
    res.write(":\n\n");
    clients.push(res);
    req.on("close", () => {
      log("[INFO] SSE client disconnected");
      clients = clients.filter((client) => client !== res);
    });
  });

  app.post("/jsonrpc", express.json(), async (req, res) => {
    try {
      log(`[INFO] Received HTTP request: ${req.body.method || "unknown"} (id: ${req.body.id})`);
      await handleRequest(req.body);
      res.status(204).end();
    } catch (error) {
      log(`[ERROR] HTTP request error: ${error.message}`);
      res.status(500).json({
        jsonrpc: "2.0",
        id: req.body.id,
        error: { code: -32000, message: `Server error: ${error.message}` },
      });
    }
  });

  app.listen(PORT, () => {
    log(`[INFO] SSE server listening on port ${PORT}`);
  });
}

// Handle incoming data from Claude via stdio
if (TRANSPORT === "stdio") {
  process.stdin.on("data", (data) => {
    buffer += data.toString();
    let boundary = buffer.indexOf("\n");
    while (boundary !== -1) {
      const line = buffer.substring(0, boundary);
      buffer = buffer.substring(boundary + 1);
      if (line.trim()) {
        try {
          const request = JSON.parse(line);
          log(`[INFO] Received request: ${request.method || "unknown"} (id: ${request.id})`);
          handleRequest(request).catch((error) => {
            log(`[ERROR] Async request handling error: ${error.message}`);
            sendErrorResponse(request.id, -32000, `Server error: ${error.message}`);
          });
        } catch (error) {
          log(`[ERROR] Failed to parse message: ${error.message}`);
          sendErrorResponse(null, -32700, "Parse error");
        }
      }
      boundary = buffer.indexOf("\n");
    }
  });

  process.stdin.on("end", () => { log("[INFO] Stdin stream ended."); });
  process.stdin.on("error", (err) => { log(`[ERROR] Stdin stream error: ${err.message}`); });
  process.stdin.resume();
  process.stdin.setEncoding("utf8");
}

// Handle request based on method
async function handleRequest(request) {
  try {
    if (!request.jsonrpc || request.jsonrpc !== "2.0") {
      return sendErrorResponse(request.id, -32600, "Invalid Request - Not JSON-RPC 2.0");
    }

    switch (request.method) {
      case "initialize":
        await handleInitialize(request);
        break;
      case "tools/call":
        await handleToolCall(request);
        break;
      case "getContext":
        await handleGetContext(request);
        break;
      case "shutdown":
        await handleShutdown(request);
        break;
      case "tools/list":
        handleToolsList(request);
        break;
      case "resources/list":
        handleResourcesList(request);
        break;
      case "prompts/list":
        handlePromptsList(request);
        break;
      case "notifications/initialized":
        log(`[INFO] Received notification: ${request.method}`);
        break;
      default:
        log(`[WARN] Method not implemented: ${request.method}`);
        sendErrorResponse(request.id, -32601, `Method '${request.method}' not found`);
    }
  } catch (error) {
    log(`[ERROR] Request handling error: ${error.message}`);
    sendErrorResponse(request.id, -32000, `Server error: ${error.message}`);
  }
}

// Handle tools/list method
function handleToolsList(request) {
  log(`[INFO] Handling tools/list request`);

  const response = {
    jsonrpc: "2.0",
    id: request.id,
    result: {
      tools: [
        {
          name: "create",
          description: "Create a new operator in TouchDesigner. Returns the created node's path, type, position, and connections.",
          inputSchema: {
            type: "object",
            properties: {
              type: { type: "string", description: "Operator type (e.g., circle, noise, blur, sphere, text, moviefilein, webcam, mic, phong)" },
              name: { type: "string", description: "Optional name for the operator" },
              parent: { type: "string", description: "Parent container path (default /project1)" },
              family: { type: "string", description: "Family hint: TOP, CHOP, SOP, DAT, COMP, or MAT. Helps resolve ambiguous types." },
              properties: { type: "object", description: "Initial parameter values to set (e.g., {\"resolutionw\": 1920})" },
              auto_connect: { type: "boolean", description: "Auto-wire to most recent same-family sibling (default true)" },
              connect_source: { type: "string", description: "Explicit source operator path to connect from" },
              connect_parameter: { type: "string", description: "Input name (e.g., input1) or parameter name for connection" },
              open_preview: { type: "boolean", description: "Open viewer for the created node" },
              nodex: { type: "number", description: "X position in network" },
              nodey: { type: "number", description: "Y position in network" }
            },
            required: ["type"],
          },
        },
        {
          name: "delete",
          description: "Delete an operator. Returns the deleted node name and parent path.",
          inputSchema: {
            type: "object",
            properties: {
              path: { type: "string", description: "Path to the operator to delete" },
            },
            required: ["path"],
          },
        },
        {
          name: "set",
          description: "Set a parameter value on an operator. Returns the path, parameter name, new value, and previous value.",
          inputSchema: {
            type: "object",
            properties: {
              path: { type: "string", description: "Operator path" },
              parameter: { type: "string", description: "Parameter name" },
              value: { type: "string", description: "Value to set" },
              expression: { type: "boolean", description: "If true, set as expression instead of constant value" }
            },
            required: ["path", "parameter", "value"],
          },
        },
        {
          name: "set_many",
          description: "Batch set multiple parameters at once. Returns count of updated parameters and details.",
          inputSchema: {
            type: "object",
            properties: {
              items: {
                type: "array",
                description: "Array of parameter updates",
                items: {
                  type: "object",
                  properties: {
                    path: { type: "string" },
                    parameter: { type: "string" },
                    value: { type: "string" },
                    expression: { type: "boolean" }
                  },
                  required: ["path", "parameter", "value"]
                }
              }
            },
            required: ["items"],
          },
        },
        {
          name: "get",
          description: "Get operator info or a specific parameter value. Returns existence, type, name, and parameter values.",
          inputSchema: {
            type: "object",
            properties: {
              path: { type: "string", description: "Operator path" },
              parameter: { type: "string", description: "Optional parameter name to read" },
            },
            required: ["path"],
          },
        },
        {
          name: "list",
          description: "List child operators under a path. Returns array of children with path, type, and name.",
          inputSchema: {
            type: "object",
            properties: {
              path: { type: "string", description: "Parent path to list (default /)" },
              type_filter: { type: "string", description: "Filter children by type (e.g., TOP, CHOP, SOP)" },
            },
            required: [],
          },
        },
        {
          name: "list_parameters",
          description: "List all parameters of an operator with their current values and types.",
          inputSchema: {
            type: "object",
            properties: {
              path: { type: "string", description: "Operator path" },
            },
            required: ["path"],
          },
        },
        {
          name: "list_types",
          description: "List available TouchDesigner operator types, optionally filtered by family or search term.",
          inputSchema: {
            type: "object",
            properties: {
              family: { type: "string", description: "Filter by family: TOP, CHOP, SOP, DAT, COMP, MAT" },
              search: { type: "string", description: "Substring search filter" },
            },
            required: [],
          },
        },
        {
          name: "execute_python",
          description: "Execute Python code inside TouchDesigner. Set 'result' variable to return data to Claude.",
          inputSchema: {
            type: "object",
            properties: {
              code: { type: "string", description: "Python code to execute" },
              context: { type: "string", description: "Operator path for 'me' context (default /)" },
            },
            required: ["code"],
          },
        },
        {
          name: "connect_nodes",
          description: "Connect multiple nodes in sequence, parallel (fan-in), or custom pairs. Returns list of connections made.",
          inputSchema: {
            type: "object",
            properties: {
              nodes: { type: "array", description: "Ordered list of operator paths", items: { type: "string" } },
              mode: { type: "string", enum: ["sequence", "parallel", "custom"], description: "Connection mode (default sequence)" },
              custom_connections: { type: "array", description: "Pairs of [source, target] for custom mode", items: { type: "array", items: { type: "string" } } }
            },
            required: [],
          },
        },
        {
          name: "auto_connect",
          description: "Smart connect two nodes based on their types. Returns connections made.",
          inputSchema: {
            type: "object",
            properties: {
              source: { type: "string", description: "Source operator path" },
              target: { type: "string", description: "Target operator path" },
              connection_type: { type: "string", enum: ["auto", "input"], description: "Connection strategy (default auto)" }
            },
            required: ["source", "target"],
          },
        },
        {
          name: "ensure_inputs",
          description: "Ensure an operator has minimum required inputs, creating fallback sources if needed.",
          inputSchema: {
            type: "object",
            properties: {
              path: { type: "string", description: "Operator path" },
              min_inputs: { type: "number", description: "Minimum inputs needed (default 2)" }
            },
            required: ["path"],
          },
        },
        {
          name: "build_workflow",
          description: "Create a complete workflow preset (audio_experience, interactive_installation, render_scene). Returns list of created nodes.",
          inputSchema: {
            type: "object",
            properties: {
              preset: { type: "string", description: "Preset name: audio_experience, interactive_installation, render_scene" },
              parent: { type: "string", description: "Parent path (default /project1)" },
              name_prefix: { type: "string", description: "Prefix for created node names" },
              open_preview: { type: "boolean", description: "Open viewer on final node (default true)" }
            },
            required: ["preset"],
          },
        },
        {
          name: "layout",
          description: "Reposition all nodes under a parent into a clean grid grouped by family. Returns count repositioned.",
          inputSchema: {
            type: "object",
            properties: {
              parent: { type: "string", description: "Parent path (default /project1)" },
              spacing_x: { type: "number", description: "Horizontal spacing (default 220)" },
              spacing_y: { type: "number", description: "Vertical spacing (default 160)" },
              cols: { type: "number", description: "Columns per row (default 6)" }
            },
            required: [],
          },
        },
        {
          name: "show_preview",
          description: "Open the viewer for an operator.",
          inputSchema: {
            type: "object",
            properties: {
              path: { type: "string", description: "Operator path" }
            },
            required: ["path"],
          },
        },
        {
          name: "disconnect",
          description: "Disconnect inputs from a node. Can clear a specific input by index or all inputs at once.",
          inputSchema: {
            type: "object",
            properties: {
              path: { type: "string", description: "Operator path" },
              input_index: { type: "number", description: "Specific input index to disconnect (omit to clear all)" }
            },
            required: ["path"],
          },
        },
        {
          name: "rename",
          description: "Rename an operator. Returns old name, new name, and updated path.",
          inputSchema: {
            type: "object",
            properties: {
              path: { type: "string", description: "Operator path" },
              new_name: { type: "string", description: "New name for the operator" }
            },
            required: ["path", "new_name"],
          },
        },
        {
          name: "set_text",
          description: "Set the text content of a DAT operator (text DAT, script DAT, etc.). Can replace or append.",
          inputSchema: {
            type: "object",
            properties: {
              path: { type: "string", description: "DAT operator path" },
              text: { type: "string", description: "Text content to set" },
              append: { type: "boolean", description: "Append to existing text instead of replacing (default false)" }
            },
            required: ["path", "text"],
          },
        },
        {
          name: "timeline",
          description: "Control the TouchDesigner timeline: play, pause, set frame, set FPS, get current state.",
          inputSchema: {
            type: "object",
            properties: {
              action: { type: "string", enum: ["play", "pause", "stop", "get", "set_frame", "set_fps", "set_range"], description: "Timeline action (default: get)" },
              frame: { type: "number", description: "Frame number for set_frame" },
              fps: { type: "number", description: "Frames per second for set_fps" },
              start: { type: "number", description: "Start frame for set_range" },
              end: { type: "number", description: "End frame for set_range" }
            },
            required: [],
          },
        },
        {
          name: "chop_export",
          description: "Create a CHOP export binding: drive a parameter with a CHOP channel value. Essential for audio-reactive and data-driven visuals.",
          inputSchema: {
            type: "object",
            properties: {
              chop_path: { type: "string", description: "Path to the CHOP operator" },
              channel: { type: "string", description: "Channel name (e.g., 'chan1', 'tx'). Omit for first channel." },
              target_path: { type: "string", description: "Path to the target operator" },
              parameter: { type: "string", description: "Parameter name to drive (e.g., 'tx', 'scale', 'opacity')" },
              enable: { type: "boolean", description: "Enable or disable the export (default true)" }
            },
            required: ["chop_path", "target_path", "parameter"],
          },
        },
        {
          name: "custom_par",
          description: "Add or remove custom parameters on a COMP. Useful for creating user-facing controls.",
          inputSchema: {
            type: "object",
            properties: {
              path: { type: "string", description: "COMP operator path" },
              action: { type: "string", enum: ["add", "remove"], description: "Add or remove parameter (default add)" },
              name: { type: "string", description: "Parameter name (lowercase, no spaces)" },
              par_type: { type: "string", enum: ["float", "int", "string", "bool", "menu", "pulse"], description: "Parameter type (default float)" },
              label: { type: "string", description: "Display label (default: same as name)" },
              default: { type: "number", description: "Default value" },
              min: { type: "number", description: "Minimum value (clamps)" },
              max: { type: "number", description: "Maximum value (clamps)" },
              page: { type: "string", description: "Custom parameter page name (default 'Custom')" }
            },
            required: ["path", "name"],
          },
        },
        {
          name: "node_style",
          description: "Set visual style on a node: color, comment text, and tags for organization.",
          inputSchema: {
            type: "object",
            properties: {
              path: { type: "string", description: "Operator path" },
              color: { type: "array", items: { type: "number" }, description: "RGB color as [r, g, b] with values 0.0-1.0" },
              comment: { type: "string", description: "Comment text shown on the node" },
              tags: { type: "array", items: { type: "string" }, description: "Tags for the node" }
            },
            required: ["path"],
          },
        },
      ],
    },
  };

  sendResponse(response);
}

// Handle resources/list method
function handleResourcesList(request) {
  log(`[INFO] Handling resources/list`);
  sendResponse({ jsonrpc: "2.0", id: request.id, result: { resources: [] } });
}

// Handle prompts/list method
function handlePromptsList(request) {
  log(`[INFO] Handling prompts/list`);
  sendResponse({ jsonrpc: "2.0", id: request.id, result: { prompts: [] } });
}

// Handle initialize method
async function handleInitialize(request) {
  log(`[INFO] Handling initialize request`);

  try {
    await testTouchDesignerConnection();
    initialized = true;
  } catch (error) {
    log(`[WARN] TouchDesigner connection issue: ${error.message}`);
    // Continue anyway - TD may start later
    initialized = true;
  }

  const supportedProtocolVersion = "2024-11-05";

  sendResponse({
    jsonrpc: "2.0",
    id: request.id,
    result: {
      protocolVersion: supportedProtocolVersion,
      capabilities: {
        tools: { listChanged: false },
        resources: { subscribe: false, listChanged: false },
        prompts: { listChanged: false },
        experimental: {}
      },
      serverInfo: {
        name: "TouchDesigner",
        version: "2.0.0",
      },
    },
  });
}

// Handle tools/call method
async function handleToolCall(request) {
  log(`[INFO] Handling tools/call request`);

  if (!initialized) {
    log("[ERROR] Server not initialized");
    return sendErrorResponse(request.id, -32002, "Server not initialized");
  }

  try {
    const toolName = request.params.name;
    const args = request.params.arguments || {};

    if (!toolName) {
      return sendErrorResponse(request.id, -32602, "Invalid params: Missing tool name");
    }

    log(`[INFO] Executing tool: ${toolName}`);

    const timeout = TOOL_TIMEOUTS[toolName] || 15000;

    try {
      const tdResponse = await axios.post(
        `${TD_SERVER_URL}/mcp`,
        { method: toolName, params: args },
        { timeout }
      );

      log(`[DEBUG] Response from TD: ${JSON.stringify(tdResponse.data).substring(0, 500)}`);

      if (tdResponse.data && tdResponse.data.error) {
        log(`[ERROR] TD backend error: ${JSON.stringify(tdResponse.data.error)}`);
        return sendErrorResponse(
          request.id,
          tdResponse.data.error.code || -32001,
          tdResponse.data.error.message || "Error from TouchDesigner backend",
          tdResponse.data.error.data
        );
      }

      // Handle success - ensure proper MCP content format
      let result = tdResponse.data.result;

      // If result already has content array, use it directly
      // Otherwise wrap raw data in MCP content format
      if (result && !result.content) {
        result = {
          content: [{ type: "text", text: JSON.stringify(result) }]
        };
      }

      sendResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: result,
      });
    } catch (error) {
      log(`[ERROR] TD request failed: ${error.message}`);
      sendErrorResponse(
        request.id,
        -32000,
        `TouchDesigner connection error: ${error.message}`
      );
    }
  } catch (error) {
    log(`[ERROR] Tool call error: ${error.message}`);
    sendErrorResponse(request.id, -32000, `Server error: ${error.message}`);
  }
}

// Handle context method
async function handleGetContext(request) {
  const query = (request.params && request.params.query) || "";
  log(`[INFO] Getting context: "${query}"`);

  try {
    const tdResponse = await axios.post(
      `${TD_SERVER_URL}/context`,
      { query, user: "claude-user" },
      { timeout: 15000 }
    );

    if (tdResponse.data && tdResponse.data.error) {
      return sendErrorResponse(
        request.id,
        tdResponse.data.error.code || -32001,
        tdResponse.data.error.message || "Error getting context"
      );
    }

    sendResponse({
      jsonrpc: "2.0",
      id: request.id,
      result: { contextItems: tdResponse.data.contextItems || [] },
    });
  } catch (error) {
    log(`[ERROR] Context error: ${error.message}`);
    sendErrorResponse(request.id, -32000, `Error getting context: ${error.message}`);
  }
}

// Handle shutdown method
async function handleShutdown(request) {
  log(`[INFO] Handling shutdown request`);
  sendResponse({ jsonrpc: "2.0", id: request.id, result: null });
  setTimeout(() => { process.exit(0); }, 500);
}

// Send a JSON-RPC response
function sendResponse(response) {
  try {
    const responseStr = JSON.stringify(response) + "\n";
    if (TRANSPORT === "stdio") {
      process.stdout.write(responseStr);
      log(`[INFO] Sent response (id: ${response.id})`);
    } else if (TRANSPORT === "sse") {
      const eventData = `event: message\ndata: ${JSON.stringify(response)}\n\n`;
      clients.forEach(client => client.write(eventData));
      log(`[INFO] Sent response via SSE to ${clients.length} clients (id: ${response.id})`);
    }
  } catch (error) {
    log(`[ERROR] Failed to send response: ${error.message}`);
  }
}

// Send a JSON-RPC error response
function sendErrorResponse(id, code, message, data = null) {
  const error = {
    code: code,
    message: message,
    ...(data && { data: data })
  };
  log(`[ERROR] Sending error response (id: ${id}): code=${code}, message=${message}`);
  sendResponse({ jsonrpc: "2.0", id: id, error: error });
}

// Function to test connection to TouchDesigner
async function testTouchDesignerConnection() {
  try {
    log(`[INFO] Testing connection to TouchDesigner at ${TD_SERVER_URL}`);
    const response = await axios.get(`${TD_SERVER_URL}/api/status`, { timeout: 5000 });
    if (response.data && response.data.status === "running" && response.data.touchdesigner) {
      log(`[INFO] TouchDesigner connected: v${response.data.version}`);
      return true;
    }
    throw new Error("Unexpected response from TouchDesigner status endpoint");
  } catch (error) {
    throw new Error(`Failed to connect to TouchDesigner: ${error.message}`);
  }
}

// Log startup
log('[INFO] MCP server proxy started and ready');

// Handle process signals for graceful shutdown
["SIGINT", "SIGTERM", "SIGQUIT"].forEach(signal => {
  process.on(signal, () => {
    log(`[INFO] Received ${signal}. Shutting down gracefully.`);
    setTimeout(() => { process.exit(0); }, 500);
  });
});

process.on("uncaughtException", (error) => {
  log(`[FATAL] Uncaught exception: ${error.message}\n${error.stack}`);
  process.exit(1);
});

process.on("unhandledRejection", (reason) => {
  log(`[FATAL] Unhandled promise rejection: ${reason}`);
  process.exit(1);
});
