const cp = require("child_process");
function handler(req){ cp.execFile("ping", [req.query.host]); }  // safe: arg array, no shell
