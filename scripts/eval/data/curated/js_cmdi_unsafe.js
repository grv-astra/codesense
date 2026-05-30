const cp = require("child_process");
function handler(req){ cp.exec("ping " + req.query.host); }  // command injection
