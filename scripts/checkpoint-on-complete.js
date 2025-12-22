#!/usr/bin/env node
// MAKER Framework - Create checkpoint when subagent completes
// Cross-platform Node.js implementation

const fs = require('fs');
const path = require('path');

const CHECKPOINT_DIR = '.maker-checkpoints';

// Ensure checkpoint directory exists
if (!fs.existsSync(CHECKPOINT_DIR)) {
    fs.mkdirSync(CHECKPOINT_DIR, { recursive: true });
}

// Generate timestamp
const now = new Date();
const timestamp = now.toISOString().replace(/[-:T]/g, '').slice(0, 15).replace('.', '_');
const checkpointFile = path.join(CHECKPOINT_DIR, `checkpoint_${timestamp}.json`);

// Read from stdin
let input = '';
process.stdin.setEncoding('utf8');

process.stdin.on('readable', () => {
    let chunk;
    while ((chunk = process.stdin.read()) !== null) {
        input += chunk;
    }
});

process.stdin.on('end', () => {
    // Save checkpoint
    fs.writeFileSync(checkpointFile, input || '{}');
    console.log(`Checkpoint saved: ${checkpointFile}`);
    process.exit(0);
});

// Handle case where stdin is empty/closed immediately
setTimeout(() => {
    if (!input) {
        fs.writeFileSync(checkpointFile, '{}');
        console.log(`Checkpoint saved: ${checkpointFile}`);
        process.exit(0);
    }
}, 100);
