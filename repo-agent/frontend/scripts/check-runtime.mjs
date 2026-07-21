import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const major = Number.parseInt(process.versions.node.split('.')[0], 10);

if (!Number.isFinite(major) || major < 18) {
  console.error(`\nRepoAgent requires Node.js 18 or newer; current version is ${process.version}.`);
  console.error('Activate the project environment first: conda activate repo-agent\n');
  process.exit(1);
}

if (!existsSync(join(frontendRoot, 'node_modules', '.bin', 'ng'))) {
  console.error('\nAngular dependencies are not installed for RepoAgent.');
  console.error(`Run: cd ${frontendRoot} && npm install --verbose\n`);
  process.exit(1);
}

console.log(`RepoAgent frontend preflight passed (Node ${process.version}).`);
