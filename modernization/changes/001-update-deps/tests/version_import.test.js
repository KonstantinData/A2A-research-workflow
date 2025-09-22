/*
  Minimal test to verify that the updated dependencies can be imported without
  throwing errors.  This script is executed by the apply script after
  installing dependencies.  It returns 0 on success and non‑zero on failure.
*/
try {
  const pptxgen = require('pptxgenjs');
  const tailwind = require('tailwindcss');
  if (typeof pptxgen !== 'function' || typeof tailwind !== 'function') {
    console.error('Unexpected module types');
    process.exit(1);
  }
  console.log('Modules imported successfully');
  process.exit(0);
} catch (err) {
  console.error('Failed to import modules:', err);
  process.exit(1);
}