/*
 * Auth0 post-login Action: "Palateful Account Linking".
 *
 * THIS FILE IS THE SOURCE OF TRUTH. To deploy: open this file, copy its whole
 * contents, paste into Auth0 -> Actions -> Library -> the Action -> Deploy.
 * Do not copy it from chat or terminal output.
 *
 * Safe to paste even if newlines get collapsed. It uses only block comments
 * and explicit semicolons, so it is still valid JavaScript on a single line.
 * On 2026-09-22 an earlier version with // line comments lost its newlines
 * in a terminal paste. Each // then commented out the rest of the code,
 * closing braces included. Auth0 rejected it as ACTION_MALFORMED, and every
 * login failed until it was redeployed. A syntax error in a post-login Action
 * takes down all logins at once, and the dashboard lets it deploy.
 *
 * Linking is best-effort and must never fail a login. The Management API is
 * called on every login for a verified single-identity user. An uncaught
 * error there (rate limit, timeout, 5xx, M2M token quota) used to fail the
 * whole login, and retrying would then succeed.
 *
 * The deny string is pinned in the app's tests
 * (app/test/core/services/auth_service_login_test.dart). Change both
 * together.
 */
exports.onExecutePostLogin = async (event, api) => {
  if (!event.user.email || !event.user.email_verified) { return; }
  if (event.user.identities && event.user.identities.length > 1) { return; }

  let linked = false;
  try {
    const { ManagementClient } = require('auth0');
    const management = new ManagementClient({
      domain: event.secrets.domain,
      clientId: event.secrets.clientId,
      clientSecret: event.secrets.clientSecret,
    });
    const users = await management.getUsersByEmail(event.user.email);
    const existingUser = users.find(
      (u) => u.email_verified && u.user_id !== event.user.user_id,
    );
    if (!existingUser) { return; }

    const [provider, ...userIdParts] = event.user.user_id.split('|');
    await management.linkUsers(existingUser.user_id, {
      provider: provider,
      user_id: userIdParts.join('|'),
    });
    linked = true;
  } catch (err) {
    /* Visible in Auth0 -> Monitoring -> Logs and in this Action's logs. */
    console.log('account-linking skipped:', err && err.message);
    return;
  }

  if (linked) {
    api.access.deny('Your account has been linked. Please sign in again.');
  }
};
