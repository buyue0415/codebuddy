// npm 包装器：强制 IPv4，解决 EADDRNOTAVAIL
const dns = require('dns');
dns.setDefaultResultOrder('ipv4first');

const { execSync } = require('child_process');
const path = require('path');

const npmCli = path.join(
  process.env.APPDATA || '',
  '..', 'Local', 'npm-cache', '_npx'
);

console.log('Installing with IPv4-first DNS...');
try {
  execSync(
    `"${process.execPath}" "${require.resolve('npm/bin/npm-cli.js')}" install --registry https://registry.npmmirror.com --no-audit --no-fund`,
    { stdio: 'inherit', cwd: __dirname }
  );
  console.log('✅ Install complete');
} catch (e) {
  // Try fallback: use npm directly
  console.log('Trying npm directly...');
  try {
    execSync(
      'npm install --registry https://registry.npmmirror.com --no-audit --no-fund',
      { stdio: 'inherit', cwd: __dirname, env: { ...process.env, NODE_OPTIONS: '--dns-result-order=ipv4first' } }
    );
    console.log('✅ Install complete');
  } catch (e2) {
    console.error('Install failed:', e2.message);
    process.exit(1);
  }
}
