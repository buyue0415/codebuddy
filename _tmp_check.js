const fs = require('fs');
const html = fs.readFileSync(
  'c:/Users/28312/WorkBuddy/2026-05-18-task-15/deliverables/bank-stock-system.html',
  'utf-8'
);
const scripts = html.match(/<script>([\s\S]*?)<\/script>/g) || [];
scripts.forEach((s, i) => {
  const code = s.replace(/<\/?script>/g, '');
  if (code.length > 100) {
    try {
      new Function(code);
      console.log(`Script ${i}: ${code.split('\n').length} lines - SYNTAX OK`);
    } catch(e) {
      console.log(`SCRIPT ${i} SYNTAX ERROR: ${e.message}`);
    }
  }
});
