import NodeMediaServer from 'node-media-server';
import dotenv from 'dotenv';

dotenv.config();

/**
 * First NodeMediaServer instance (existing):
 */
const config1 = {
  logType: 2, // error logs only
  rtmp: {
    port: 1935,         // Existing RTMP port
    chunk_size: 6000,
    gop_cache: true,
    ping: 60,
    ping_timeout: 30,
  },
  http: {
    port: 8000,         // Existing status/HLS port
    allow_origin: '*',
  },
};

const nms1 = new NodeMediaServer(config1);
nms1.run();
console.log('NodeMediaServer #1 is running on rtmp://localhost:1935/live/streamkey');
console.log('HTTP server #1 is running on http://localhost:8000');


/**
 * Second NodeMediaServer instance (NEW):
 */
const config2 = {
  logType: 2,
  rtmp: {
    port: 1936,         // New RTMP port
    chunk_size: 6000,
    gop_cache: true,
    ping: 60,
    ping_timeout: 30,
  },
  http: {
    port: 8001,         // Another HTTP port for status/HLS
    allow_origin: '*',
  },
};

const nms2 = new NodeMediaServer(config2);
nms2.run();
console.log('NodeMediaServer #2 is running on rtmp://localhost:1936/live/watermill');
console.log('HTTP server #2 is running on http://localhost:8001');
