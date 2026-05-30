const cp = require("child_process");
function run(req){ cp.exec("ping " + req.query.host); }    // vulnerable line 2
function safe(req){ cp.execFile("ping", [req.query.host]); } // safe line 3
