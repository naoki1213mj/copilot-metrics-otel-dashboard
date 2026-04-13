import { cpSync, existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const dashboardDirectory = join(scriptDirectory, '..');
const distDirectory = join(dashboardDirectory, 'dist');
const deployDirectory = join(dashboardDirectory, 'deploy');

if (!existsSync(distDirectory)) {
  throw new Error('Build output directory "dist" was not found.');
}

rmSync(deployDirectory, { force: true, recursive: true });
mkdirSync(deployDirectory, { recursive: true });

cpSync(distDirectory, join(deployDirectory, 'dist'), { recursive: true });
cpSync(join(dashboardDirectory, 'server.js'), join(deployDirectory, 'server.js'));

writeFileSync(
  join(deployDirectory, 'package.json'),
  `${JSON.stringify(
    {
      name: 'dashboard-runtime',
      private: true,
      type: 'module',
      scripts: {
        start: 'node server.js',
      },
      engines: {
        node: '>=20',
      },
    },
    null,
    2,
  )}\n`,
);
