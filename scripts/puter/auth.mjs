/**
 * One-time helper: open Puter login and print an auth token for IMAGE__API_KEY.
 * Usage: npm run auth --prefix scripts/puter
 */
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { getAuthToken } = require("@heyputer/puter.js/src/init.cjs");

const token = await getAuthToken();
console.log("\nPaste this into .env as IMAGE__API_KEY (and set IMAGE__PROVIDER=puter):\n");
console.log(token);
console.log("");
