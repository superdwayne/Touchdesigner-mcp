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

// Log to stderr (will show in Claude logs)
function log(message) {
  // Use console.error for logging to stderr in Node.js
  console.error(message);
  // Also log to a file for debugging
  try {
    fs.appendFileSync("/tmp/td-mcp-debug.log", message + "\n");
  } catch (err) {
    console.error(`Failed to write to debug log: ${err.message}`);
  }
}

log(`[DEBUG] Process started with PID: ${process.pid}`);
log(`[DEBUG] Working directory: ${process.cwd()}`);
log(`[DEBUG] Node version: ${process.version}`);
log(`[DEBUG] Transport: ${TRANSPORT}`);
log(`[DEBUG] TD_SERVER_URL: ${TD_SERVER_URL}`);
log(`[DEBUG] Command-line args: ${JSON.stringify(process.argv)}`);

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
      version: "1.0.0",
    });
  });

  app.get("/sse", (req, res) => {
    log("[INFO] SSE client connected");

    // Set headers for SSE
    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("Connection", "keep-alive");

    // Send a comment to establish connection
    res.write(":\n\n");

    // Add client to list
    clients.push(res);

    // Handle client disconnect
    req.on("close", () => {
      log("[INFO] SSE client disconnected");
      clients = clients.filter((client) => client !== res);
    });
  });

  app.post("/jsonrpc", express.json(), async (req, res) => {
    try {
      log(
        `[INFO] Received HTTP request: ${req.body.method || "unknown"} (id: ${
          req.body.id
        })`
      );

      // Process request
      await handleRequest(req.body);

      // Don't send a response here, it will be sent via SSE
      res.status(204).end();
    } catch (error) {
      log(`[ERROR] HTTP request error: ${error.message}`);
      res.status(500).json({
        jsonrpc: "2.0",
        id: req.body.id,
        error: {
          code: -32000,
          message: `Server error: ${error.message}`,
        },
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
    log(`[DEBUG] Received raw data: ${data.toString().substring(0, 200)}...`);

    // Add new data to buffer
    buffer += data.toString();

    // Process complete messages (separated by newlines)
    // Use a regex to handle potential multiple messages in one chunk
    let boundary = buffer.indexOf("\n");
    while (boundary !== -1) {
      const line = buffer.substring(0, boundary);
      buffer = buffer.substring(boundary + 1);

      if (line.trim()) {
        try {
          const request = JSON.parse(line);
          log(
            `[INFO] Received request: ${request.method || "unknown"} (id: ${
              request.id
            })`
          );
          log(`[DEBUG] Request content: ${line}`); // Log full request

          // Process request asynchronously
          handleRequest(request).catch((error) => {
            log(`[ERROR] Async request handling error: ${error.message}`);
            sendErrorResponse(
              request.id,
              -32000,
              `Server error: ${error.message}`
            );
          });
        } catch (error) {
          log(
            `[ERROR] Failed to parse message: ${error.message}, Data: ${
              line.substring(0, 100)
            }`
          );
          sendErrorResponse(null, -32700, "Parse error");
        }
      }
      boundary = buffer.indexOf("\n");
    }
  });

  process.stdin.on("end", () => {
    log("[INFO] Stdin stream ended.");
  });

  process.stdin.on("error", (err) => {
    log(`[ERROR] Stdin stream error: ${err.message}`);
  });

  // Make sure we're handling stdin correctly
  process.stdin.resume();
  process.stdin.setEncoding("utf8");
}

// Handle request based on method
async function handleRequest(request) {
  try {
    // Check for valid JSON-RPC 2.0 request
    if (!request.jsonrpc || request.jsonrpc !== "2.0") {
      return sendErrorResponse(
        request.id,
        -32600,
        "Invalid Request - Not JSON-RPC 2.0"
      );
    }

    switch (request.method) {
      case "initialize":
        await handleInitialize(request);
        break;

      case "tools/call": // Updated to handle tools/call
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
        // Just acknowledge this notification
        handleNotification(request);
        break;

      default:
        log(`[WARN] Method not implemented: ${request.method}`);
        sendErrorResponse(
          request.id,
          -32601,
          `Method '${request.method}' not found`
        );
    }
  } catch (error) {
    log(`[ERROR] Request handling error: ${error.message}`);
    sendErrorResponse(request.id, -32000, `Server error: ${error.message}`);
  }
}

// Handle notification (no response needed)
function handleNotification(request) {
  log(`[INFO] Received notification: ${request.method}`);
  // No response needed for notifications
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
          description: "Create a new component or operator in TouchDesigner",
          inputSchema: {
            type: "object",
            properties: {
              type: {
                type: "string",
                description: "The type of component to create (e.g., circle, text, noise, grid)",
              },
              name: {
                type: "string", 
                description: "Optional name for the component",
              },
              parent: {
                type: "string",
                description: "Optional parent path to create the component in",
              },
              properties: {
                type: "object",
                description: "Optional properties to set on the component",
              },
              // Add these new connection parameters
              connect_source: {
                type: "string",
                description: "Optional path to source operator for connection"
              },
              connect_parameter: {
                type: "string",
                description: "Parameter name to connect from source operator"
              },
              // Add these new positioning parameters
              nodex: {
                type: "number",
                description: "Optional X position for the node in the network"
              },
              nodey: {
                type: "number",
                description: "Optional Y position for the node in the network"
              }
            },
            required: ["type"],
          },
          examples: [
            "create a circle connected to noise1",
            "create blur effect connected to movie1 via input",
            "create a text component at position x=500, y=300"
          ]
        },
        {
          name: "list",
          description: "List components in TouchDesigner",
          inputSchema: {
            type: "object",
            properties: {
              path: {
                type: "string",
                description: "Optional path to list components from",
              },
              type: {
                type: "string",
                description: "Optional type of components to filter by",
              },
            },
            required: [], // No required parameters for basic list
          },
          examples: [
            "list all components",
            "list components in /project1",
            "list all SOP components",
            "list all text components",
          ],
        },
        {
          name: "delete",
          description: "Delete a component in TouchDesigner",
          inputSchema: {
            type: "object",
            properties: {
              path: {
                type: "string",
                description: "Path to the component to delete",
              },
            },
            required: ["path"],
          },
          examples: [
            "delete /project1/circle_123456",
            "delete the text component I just created",
          ],
        },
        {
          name: "set",
          description: "Set a parameter value for a component",
          inputSchema: {
            type: "object",
            properties: {
              path: {
                type: "string",
                description: "Path to the component",
              },
              parameter: {
                type: "string",
                description: "Name of the parameter to set",
              },
              value: {
                // Using string for now, as Python backend seems to expect/handle strings
                type: "string",
                description: "Value to set for the parameter",
              },
            },
            required: ["path", "parameter", "value"],
          },
          examples: [
            "set /project1/circle_123456 r 0.5",
            'set /project1/text_123456 text "Hello TouchDesigner"',
            'set /project1/moviefilein_123456 file "/path/to/video.mp4"',
          ],
        },
        {
          name: "get",
          description:
            "Get information about a component or parameter value",
          inputSchema: {
            type: "object",
            properties: {
              path: {
                type: "string",
                description: "Path to the component",
              },
              parameter: {
                type: "string",
                description: "Optional name of the parameter to get",
              },
            },
            required: ["path"],
          },
          examples: [
            "get information about /project1/circle_123456",
            "get the text value of /project1/text_123456",
            "get the resolution of /project1/moviefilein_123456",
          ],
        },
        {
          name: "execute_python",
          description: "Execute a Python script in TouchDesigner",
          inputSchema: {
            type: "object",
            properties: {
              code: {
                type: "string",
                description: "Python code to execute",
              },
              context: {
                type: "string",
                description:
                  "Optional context to execute in (e.g., /project1)",
              },
            },
            required: ["code"],
          },
          examples: [
            // Corrected escaping for the example string (v5)
            'execute_python "op(\'/project1/text1\').text = \'Hello from Python\'"',
            'execute_python "print(td.version)"',
          ],
        },
        // Add the new list_parameters tool here
        {
          name: "list_parameters",
          description: "List all parameters of a TouchDesigner component",
          inputSchema: {
            type: "object",
            properties: {
              path: {
                type: "string",
                description: "Path to the component to list parameters from",
              },
            },
            required: ["path"],
          },
          examples: [
            "list parameters of /project1/circle1",
            "show me all parameters available on /project1/text1",
          ],
        },
      ],
    },
  };

  sendResponse(response);
}

// Handle resources/list method
function handleResourcesList(request) {
  log(`[INFO] Handling resources/list`);

  const response = {
    jsonrpc: "2.0",
    id: request.id,
    result: {
      resources: [], // No resources available
    },
  };

  sendResponse(response);
}

// Handle prompts/list method
function handlePromptsList(request) {
  log(`[INFO] Handling prompts/list`);

  const response = {
    jsonrpc: "2.0",
    id: request.id,
    result: {
      prompts: [], // No predefined prompts available
    },
  };

  sendResponse(response);
}

// Handle initialize method - Mimicking Blender MCP capabilities structure
async function handleInitialize(request) {
  log(`[INFO] Handling initialize request with client version: ${request.params.protocolVersion}`);

  // Test connection to TouchDesigner first
  try {
    await testTouchDesignerConnection();
    initialized = true;
    log(`[DEBUG] Set initialized = true`);
  } catch (error) {
    log(`[WARN] TouchDesigner connection issue: ${error.message}`);
    // Continue anyway - we'll handle the failure in subsequent requests
  }

  // Define the protocol version this server supports
  const supportedProtocolVersion = "2024-11-05"; // Explicitly state the supported version

  // Check if client requested version is compatible (optional but good practice)
  if (request.params.protocolVersion !== supportedProtocolVersion) {
      log(`[WARN] Client requested protocol version ${request.params.protocolVersion}, but server supports ${supportedProtocolVersion}. Proceeding anyway.`);
      // Depending on strictness, you might want to return an error here if versions are incompatible.
  }

  const response = {
    jsonrpc: "2.0",
    id: request.id,
    result: {
      // Match Blender MCP field order
      protocolVersion: supportedProtocolVersion,
      capabilities: {
        // Match Blender MCP detailed structure
        tools: { listChanged: false },
        resources: { subscribe: false, listChanged: false },
        prompts: { listChanged: false },
        context: true, // Keep context for now, but structure might need adjustment
        experimental: {} // Add experimental like Blender MCP
      },
      serverInfo: {
        name: "TouchDesigner",
        version: "1.0.0", // Consider using td.version dynamically if possible
      },
    },
  };

  sendResponse(response);
}

// Handle tools/call method (Updated from handleExecute)
async function handleToolCall(request) {
  log(`[INFO] Handling tools/call request`);

  // Check if initialized
  if (!initialized) {
    log("[ERROR] Server not initialized");
    return sendErrorResponse(request.id, -32002, "Server not initialized");
  }

  try {
    // Extract toolName and args from params based on observed log structure
    const toolName = request.params.name; // Corrected: Use params.name
    const args = request.params.arguments || {}; // Corrected: Use params.arguments

    if (!toolName) {
        log("[ERROR] Missing tool name in tools/call request (expected params.name)");
        return sendErrorResponse(request.id, -32602, "Invalid params: Missing tool name (expected params.name)");
    }

    log(`[INFO] Executing tool: ${toolName} with args: ${JSON.stringify(args)}`);

    // Forward request to TouchDesigner
    try {
      // Send request to the Python backend's /mcp endpoint
      const tdResponse = await axios.post(
        `${TD_SERVER_URL}/mcp`,
        {
          method: toolName, // Send the specific tool name
          params: args, // Send the arguments object as params
        },
        {
          timeout: 30000, // 30 second timeout
        }
      );

      log(
        `[DEBUG] Response from TouchDesigner /mcp: ${JSON.stringify(
          tdResponse.data
        )}`
      );

      // Check if the backend returned an error object
      if (tdResponse.data && tdResponse.data.error) {
          log(`[ERROR] TouchDesigner backend returned error: ${JSON.stringify(tdResponse.data.error)}`);
          return sendErrorResponse(
              request.id,
              tdResponse.data.error.code || -32001,
              tdResponse.data.error.message || "Error from TouchDesigner backend",
              tdResponse.data.error.data // Include extra data if available
          );
      }

      // Handle success
      const result = tdResponse.data.result; // Assuming TD returns { "result": ... }
      sendResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: result,
      });
    } catch (error) {
      log(`[ERROR] TouchDesigner request failed: ${error.message}`);
      const tdErrorData = error.response ? error.response.data : null;
      log(`[DEBUG] TouchDesigner error response data: ${JSON.stringify(tdErrorData)}`);

      // Handle error
      sendErrorResponse(
        request.id,
        -32000,
        `TouchDesigner connection error: ${error.message}`,
        tdErrorData
      );
    }
  } catch (error) {
    log(`[ERROR] Tool call error: ${error.message}`);
    sendErrorResponse(request.id, -32000, `Server error: ${error.message}`);
  }
}

// Handle context method
async function handleGetContext(request) {
  const query = request.params.query || "";
  log(`[INFO] Getting context: "${query}"`);

  try {
    // Forward to TouchDesigner /context endpoint
    const tdResponse = await axios.post(
      `${TD_SERVER_URL}/context`,
      {
        query,
        user: "claude-user", // Example user ID
      },
      {
        timeout: 15000, // 15 second timeout
      }
    );

    log(
      `[DEBUG] Response from TouchDesigner /context: ${JSON.stringify(
        tdResponse.data
      )}`
    );

    // Check if the backend returned an error object
    if (tdResponse.data && tdResponse.data.error) {
        log(`[ERROR] TouchDesigner context backend returned error: ${JSON.stringify(tdResponse.data.error)}`);
        return sendErrorResponse(
            request.id,
            tdResponse.data.error.code || -32001,
            tdResponse.data.error.message || "Error getting context from TouchDesigner backend",
            tdResponse.data.error.data // Include extra data if available
        );
    }

    const response = {
      jsonrpc: "2.0",
      id: request.id,
      result: {
        contextItems: tdResponse.data.contextItems || [],
      },
    };

    sendResponse(response);
  } catch (error) {
    log(`[ERROR] Context error: ${error.message}`);
    const tdErrorData = error.response ? error.response.data : null;
     log(`[DEBUG] TouchDesigner context error response data: ${JSON.stringify(tdErrorData)}`);
    sendErrorResponse(
      request.id,
      -32000,
      `Error getting context: ${error.message}`,
      tdErrorData
    );
  }
}

// Handle shutdown method
async function handleShutdown(request) {
  log(`[INFO] Handling shutdown request`);

  const response = {
    jsonrpc: "2.0",
    id: request.id,
    result: null,
  };

  sendResponse(response);

  // Clean exit after sending response
  setTimeout(() => {
    log("[INFO] Exiting process after shutdown request.");
    process.exit(0);
  }, 500); // Give time for response to be sent
}

// Send a JSON-RPC response
function sendResponse(response) {
  try {
    const responseStr = JSON.stringify(response) + "\n";
    if (TRANSPORT === "stdio") {
      // Write to stdout for stdio transport
      process.stdout.write(responseStr);
      log(`[INFO] Sent response via stdio (id: ${response.id})`);
      log(`[DEBUG] Sent response content: ${responseStr.trim()}`);
    } else if (TRANSPORT === "sse") {
      // Send to all connected SSE clients
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
        // Only include data if it's not null or undefined
        ...(data && { data: data })
    };

    log(`[ERROR] Sending error response (id: ${id}): code=${code}, message=${message}`);

    sendResponse({
        jsonrpc: "2.0",
        id: id,
        error: error
    });
}

// Function to test connection to TouchDesigner
async function testTouchDesignerConnection() {
  try {
    log(`[INFO] Testing connection to TouchDesigner at ${TD_SERVER_URL}`);
    // Use the /api/status endpoint defined in the Python backend
    const response = await axios.get(`${TD_SERVER_URL}/api/status`, { timeout: 5000 });

    // Check if the response contains expected keys
    if (response.data && response.data.status === "running" && response.data.touchdesigner) {
      log(`[INFO] TouchDesigner connected: ${JSON.stringify(response.data)}`);
      return true;
    } else {
      log(`[WARN] TouchDesigner returned unexpected status response: ${JSON.stringify(response.data)}`);
      throw new Error("Unexpected response from TouchDesigner status endpoint");
    }
  } catch (error) {
    log(`[ERROR] Failed to connect to TouchDesigner: ${error.message}`);
    // Re-throw the error so the caller knows the connection failed
    throw new Error(`Failed to connect to TouchDesigner: ${error.message}`);
  }
}

// Keep the process alive (optional, stdio transport usually keeps it alive)
// setInterval(() => {
//   log('[DEBUG] Proxy process heartbeat');
// }, 30000);

// Log startup
log('[INFO] MCP server proxy started and ready');
log('[DEBUG] Waiting for stdin data...');

// Handle process signals for graceful shutdown
const signals = ["SIGINT", "SIGTERM", "SIGQUIT"];
signals.forEach(signal => {
  process.on(signal, () => {
    log(`[INFO] Received ${signal}. Shutting down gracefully.`);
    // Perform any cleanup if needed
    setTimeout(() => {
        process.exit(0);
    }, 500); // Allow time for logs to flush
  });
});

// Handle process errors
process.on("uncaughtException", (error) => {
  log(`[FATAL] Uncaught exception: ${error.message}`);
  log(`[DEBUG] Stack trace: ${error.stack}`);
  process.exit(1); // Exit on unhandled exceptions
});

process.on("unhandledRejection", (reason, promise) => {
  log(`[FATAL] Unhandled promise rejection: ${reason}`);
  // Optionally log more details about the promise
  // log(promise);
  process.exit(1); // Exit on unhandled rejections
});

