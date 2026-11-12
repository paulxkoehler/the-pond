// Tiny MQTT-over-websocket broker for tests (stands in for the public relay).
const aedes = require('aedes')();
const { createServer } = require('aedes-server-factory');
const port = +process.argv[2] || 8899;
createServer(aedes, { ws: true }).listen(port, '127.0.0.1', () => console.log('relay on ' + port));
