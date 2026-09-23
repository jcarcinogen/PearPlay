// Support the documented directory test command, including ESM tests with await.
const { readdirSync } = require('node:fs');
const { join } = require('node:path');
const { pathToFileURL } = require('node:url');
(async () => {
  for (const name of readdirSync(__dirname).filter(name => name.endsWith('.test.mjs')).sort()) {
    await import(pathToFileURL(join(__dirname, name)).href);
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
