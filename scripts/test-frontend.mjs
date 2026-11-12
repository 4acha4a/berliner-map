import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
const directory = mkdtempSync(join(tmpdir(), 'berliner-tests-'));
try {
  const compile = spawnSync(process.execPath, ['node_modules/typescript/bin/tsc', 'lib/location.ts', 'lib/map-location.ts', '--outDir', directory, '--module', 'commonjs', '--target', 'es2022', '--skipLibCheck', '--strict'], { stdio: 'inherit' });
  if (compile.status !== 0) process.exitCode = compile.status || 1;
  else {
    const tests = spawnSync(process.execPath, ['--test', 'tests/location.test.mjs'], { stdio: 'inherit', env: { ...process.env, LOCATION_TEST_BUILD: directory } });
    process.exitCode = tests.status ?? 1;
  }
} finally { rmSync(directory, { recursive: true, force: true }); }
