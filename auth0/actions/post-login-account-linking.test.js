/*
 * Tests for post-login-account-linking.js. No dependencies:
 *   node auth0/actions/post-login-account-linking.test.js
 *
 * The Action can take down every login, through a syntax error or an
 * uncaught throw, so both its shape and its logic are pinned here.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Module = require('node:module');

const FILE = path.join(__dirname, 'post-login-account-linking.js');
const DENY = 'Your account has been linked. Please sign in again.';
let failures = 0;
async function test(name, fn) {
  try { await fn(); console.log('ok   ' + name); }
  catch (e) { failures++; console.log('FAIL ' + name + '\n     ' + e.message); }
}

/* Stub require('auth0') with a scriptable ManagementClient. */
let mgmt;
const realLoad = Module._load;
Module._load = function (request, ...rest) {
  if (request === 'auth0') {
    return { ManagementClient: function () { return mgmt; } };
  }
  return realLoad.call(this, request, ...rest);
};
const action = require(FILE);

function run(user, m) {
  mgmt = m;
  const denied = [];
  const api = { access: { deny: (r) => denied.push(r) } };
  const event = { user, secrets: { domain: 'd', clientId: 'c', clientSecret: 's' } };
  return action.onExecutePostLogin(event, api).then(() => denied);
}
const leo = { email: 'leo@x', email_verified: true, user_id: 'apple|123', identities: [{}] };

(async () => {
  await test('parses as written', () => {
    new vm.Script(fs.readFileSync(FILE, 'utf8'));
  });

  await test('parses with every newline collapsed (the 2026-09-22 outage)', () => {
    new vm.Script(fs.readFileSync(FILE, 'utf8').replace(/\n/g, ' '));
  });

  await test('negative control: a // comment DOES break a collapsed paste', () => {
    /* Proves the check above can fail, i.e. that it tests something. */
    const bad = 'exports.f = () => { // a comment\n return 1; };';
    assert.throws(() => new vm.Script(bad.replace(/\n/g, ' ')));
    new vm.Script(bad); /* and it is fine with the newline intact */
  });

  await test('contains no // line comments in the code itself', () => {
    /* Strip block comments (the header mentions "//" in prose, which is
     * inert inside a block comment) and string literals, then look. */
    const code = fs.readFileSync(FILE, 'utf8')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/'(?:\\.|[^'\\])*'/g, "''");
    assert.equal(code.includes('//'), false);
  });

  await test('a Management API failure does NOT fail the login', async () => {
    const denied = await run(leo, { getUsersByEmail: async () => { throw new Error('429 Too Many Requests'); } });
    assert.deepEqual(denied, []);
  });

  await test('a linkUsers failure does NOT fail the login, and does not deny', async () => {
    const denied = await run(leo, {
      getUsersByEmail: async () => [{ email_verified: true, user_id: 'google-oauth2|9' }],
      linkUsers: async () => { throw new Error('timeout'); },
    });
    assert.deepEqual(denied, []);
  });

  await test('no other account: no deny', async () => {
    const denied = await run(leo, { getUsersByEmail: async () => [{ email_verified: true, user_id: 'apple|123' }] });
    assert.deepEqual(denied, []);
  });

  await test('a successful link denies with the exact string the app matches', async () => {
    let linkedTo;
    const denied = await run(leo, {
      getUsersByEmail: async () => [{ email_verified: true, user_id: 'google-oauth2|9' }],
      linkUsers: async (primary, secondary) => { linkedTo = [primary, secondary]; },
    });
    assert.deepEqual(denied, [DENY]);
    assert.deepEqual(linkedTo, ['google-oauth2|9', { provider: 'apple', user_id: '123' }]);
  });

  await test('an already-linked user never touches the Management API', async () => {
    const denied = await run({ ...leo, identities: [{}, {}] }, {
      getUsersByEmail: async () => { throw new Error('must not be called'); },
    });
    assert.deepEqual(denied, []);
  });

  await test('an unverified email never touches the Management API', async () => {
    const denied = await run({ ...leo, email_verified: false }, {
      getUsersByEmail: async () => { throw new Error('must not be called'); },
    });
    assert.deepEqual(denied, []);
  });

  console.log(failures === 0 ? '\nall passed' : '\n' + failures + ' failed');
  process.exit(failures === 0 ? 0 : 1);
})();
