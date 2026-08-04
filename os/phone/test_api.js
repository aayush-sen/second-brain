// Run: node test_api.js
const assert = require("assert");
process.env.PHONE_TOKEN = "sekrit";
const { auth } = require("./api/_lib");
const req = (h) => ({ headers: h });

assert(auth(req({ authorization: "Bearer sekrit" })), "valid token accepted");
assert(!auth(req({ authorization: "Bearer wrong!!" })), "wrong token rejected");
assert(!auth(req({ authorization: "Bearer sekri" })), "short token rejected");
assert(!auth(req({})), "missing header rejected");
process.env.PHONE_TOKEN = "";
assert(!auth(req({ authorization: "Bearer " })), "unset server token never authorizes");
console.log("test_api: all assertions pass");
