import assert from 'node:assert/strict';
import { formatCompactIN, formatIN, formatKm, formatPct, gapBandLabel } from './format';

assert.equal(formatIN(10800000), '1,08,00,000');
assert.equal(formatIN(1234), '1,234');
assert.equal(formatIN(null), '–');
assert.equal(formatCompactIN(10800000), '1.08 crore');
assert.equal(formatCompactIN(1240000), '12.4 lakh');
assert.equal(formatCompactIN(9500), '9,500');
assert.equal(formatPct(0.434), '43%');
assert.equal(formatKm(12.34), '12.3 km');
assert.equal(formatKm(1240.6), '1,241 km');
assert.equal(gapBandLabel(5), 'Critical');
console.log('format ok');
