// File: rtmp_server/server.js

import NodeMediaServer from 'node-media-server';
import dotenv from 'dotenv';

dotenv.config();

// Configuration for Node Media Server
const config = {
  logType: 2, // 1: access log, 2: error log, 4: debug log
  rtmp: {
    port: 1935, // Default RTMP port
    chunk_size: 6000,
    gop_cache: true,
    ping: 60,
    ping_timeout: 30,
  },
  http: {
    port: 8000, // HTTP server port for status and HLS
    allow_origin: '*',
  },
};

// Initialize Node Media Server
const nms = new NodeMediaServer(config);

// Start the server
nms.run();

console.log('NodeMediaServer is running on rtmp://localhost:1935/live');
console.log('HTTP server is running on http://localhost:8000');
