#!/usr/bin/env node
// MAKER Framework - Validate output from Write/Edit operations
// Cross-platform Node.js implementation

const fs = require('fs');

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
    try {
        const data = JSON.parse(input || '{}');
        const filePath = data.tool_input?.file_path || data.tool_input?.path;

        if (!filePath) {
            process.exit(0); // No file path, skip validation
        }

        // Basic validation - file exists and is not empty
        if (fs.existsSync(filePath)) {
            const stats = fs.statSync(filePath);
            if (stats.size > 0) {
                console.log(`Validation passed: ${filePath} exists and has content`);
            } else {
                console.error(`Warning: ${filePath} is empty`);
            }
        }
    } catch (e) {
        // JSON parse error or other issue - don't block
    }
    process.exit(0);
});

// Handle case where stdin is empty/closed immediately
setTimeout(() => {
    process.exit(0);
}, 100);
