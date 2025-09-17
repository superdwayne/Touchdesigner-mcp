const fs = require('fs');
const axios = require('axios');

// Read the initialization request
const initRequest = JSON.parse(fs.readFileSync('/tmp/init-request.json', 'utf8'));

// URL to the TouchDesigner server
const TD_SERVER_URL = process.env.TD_SERVER_URL || 'http://localhost:8051';

// Log function
function log(message) {
  console.log(message);
}

// Test connection to TouchDesigner
async function testTouchDesignerConnection() {
  try {
    log(`[INFO] Testing connection to TouchDesigner at ${TD_SERVER_URL}`);
    const response = await axios.get(TD_SERVER_URL, { timeout: 5000 });
    
    log(`[INFO] Response from TouchDesigner: ${JSON.stringify(response.data)}`);
    
    // Check if the response contains expected keys
    if (response.data && response.data.status === 'running' && response.data.touchdesigner) {
      log(`[INFO] TouchDesigner connected: ${JSON.stringify(response.data)}`);
      return true;
    } else {
      log(`[WARN] TouchDesigner returned unexpected response: ${JSON.stringify(response.data)}`);
      return false;
    }
  } catch (error) {
    log(`[ERROR] Failed to connect to TouchDesigner: ${error.message}`);
    return false;
  }
}

// Handle initialization
async function handleInitialize() {
  log(`[INFO] Handling initialization request`);
  
  // Test connection to TouchDesigner
  const connected = await testTouchDesignerConnection();
  
  if (!connected) {
    log(`[ERROR] Failed to connect to TouchDesigner - cannot initialize`);
    return;
  }
  
  log(`[INFO] Successfully connected to TouchDesigner`);
  log(`[INFO] Initialization successful`);
  
  // Return the response that would be sent back to Claude
  const response = {
    jsonrpc: '2.0',
    id: initRequest.id,
    result: {
      serverInfo: {
        name: 'TouchDesigner',
        version: '1.0.0'
      },
      capabilities: {},
      protocolVersion: initRequest.params.protocolVersion
    }
  };
  
  log(`[INFO] Response: ${JSON.stringify(response, null, 2)}`);
}

// Run the test
handleInitialize().catch(error => {
  log(`[ERROR] Test failed: ${error.message}`);
}); 