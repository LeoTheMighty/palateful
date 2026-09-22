// WRITES to the real account — skips unless PALATEFUL_E2E_ALLOW_WRITES=1.
//
// Repro from palateful-cc (2026-09-22). The server sends `quantity` as a JSON
// string ("2.5") and the client does `json['quantity'] as num?`, which throws
// while parsing — HTTP stays 200, so nothing server-side ever errors. A
// `null` quantity parses fine, which is why an EMPTY list, or items added with
// a blank quantity, load normally.
//
// So a test that opens an empty list PASSES on the broken cart. This one puts
// an item WITH a quantity in a list and re-opens it; the assertion is that the
// item is present AND the load-error is absent. Until cc's fix deploys, the
// correct result of this script is FAIL at the re-open step.
//
// Data safety: creates exactly one list and one item, both tagged
// `[e2e-walk]`; deletes them in `finally` through the API (not the UI under
// test); refuses to delete anything not tagged by THIS run; and asserts every
// list that existed before is still there, unchanged, afterwards. Leo's own
// lists are never opened.
import { expect, test } from "@playwright/test";
import { authSettled, enableSemantics } from "../lib/flutter.js";
import { E2E_PREFIX, api, captureApiAuth, idOf, listsOf, requireWriteOptIn } from "../lib/writes.js";

async function allLists(page: Parameters<typeof api>[0], auth: Parameters<typeof api>[1]) {
  const out: Array<{ id: string; name: string }> = [];
  for (let offset = 0; offset < 5_000; offset += 100) {
    const r = await api(page, auth, "GET", `/v1/shopping-lists?limit=100&offset=${offset}`);
    expect(r.ok(), `GET lists → HTTP ${r.status()}`).toBe(true);
    const page_ = listsOf(await r.json());
    out.push(...page_);
    if (page_.length < 100) break;
  }
  return out;
}

test("cart: an item with a quantity is still there when its list is re-opened", async ({ page }, info) => {
  requireWriteOptIn();
  const auth = captureApiAuth(page);
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const listName = `${E2E_PREFIX} cart ${stamp}`;
  const itemName = `${E2E_PREFIX} flour`;
  const created: { listId?: string; itemIds: string[] } = { itemIds: [] };

  // Learn created ids from the app's own responses. The item POST succeeds
  // server-side (201) even when the CLIENT fails to parse it, so its id is in
  // the body regardless of what the UI then says.
  page.on("response", async (r) => {
    if (r.request().method() !== "POST" || !r.url().startsWith(`${process.env.PALATEFUL_E2E_API_BASE ?? "https://api.palateful.app"}/v1/shopping-lists`)) return;
    const body = await r.json().catch(() => null);
    const id = idOf(body);
    if (!id) return;
    if (/\/items$/.test(new URL(r.url()).pathname)) created.itemIds.push(id);
    else if (/\/shopping-lists$/.test(new URL(r.url()).pathname)) created.listId = id;
  });

  let before: Array<{ id: string; name: string }> = [];
  try {
    await test.step("open the cart signed in", async () => {
      await page.goto("/#/cart", { waitUntil: "load" });
      expect(await authSettled(page), "not signed in — capture a session first").toBe(true);
      await enableSemantics(page);
      await expect.poll(() => auth.header() !== undefined, { message: "app made no API call to learn auth from" }).toBe(true);
      before = await allLists(page, auth);
      await info.attach("lists-before.txt", { body: before.map((l) => `${l.id}  ${l.name}`).join("\n"), contentType: "text/plain" });
    });

    await test.step("create a tagged list", async () => {
      await page.getByRole("button", { name: /New List/i }).click();
      await page.getByRole("textbox").last().fill(listName);
      await page.getByRole("button", { name: /^Create$/ }).click();
      await expect.poll(() => created.listId, { message: "list POST never returned an id", timeout: 20_000 }).toBeTruthy();
    });

    await test.step("add an item WITH a quantity (the bug needs one)", async () => {
      await page.goto(`/#/shopping-lists/${created.listId}`, { waitUntil: "load" });
      expect(await authSettled(page)).toBe(true);
      await enableSemantics(page);
      await page.getByRole("textbox", { name: /^Item/ }).fill(itemName);
      await page.getByRole("textbox", { name: /^Qty/ }).fill("2.5");
      const unit = page.getByRole("textbox", { name: /^Unit/ });
      await unit.fill("cup");
      await unit.press("Enter"); // onSubmitted → _addItem; the add button has no label
      await expect.poll(() => created.itemIds.length, { message: "item POST never returned an id", timeout: 20_000 }).toBeGreaterThan(0);
      // Evidence, not the assertion: on the broken path the UI reports a
      // failure for an item the server DID create. Never retry the add.
      const addFailed = (await page.getByText("Failed to add item").count()) > 0;
      await info.attach("add-item-ui.txt", { body: `"Failed to add item" shown: ${addFailed}`, contentType: "text/plain" });
    });

    await test.step("re-open the list — the discriminating step", async () => {
      await page.reload({ waitUntil: "load" });
      expect(await authSettled(page)).toBe(true);
      await enableSemantics(page);
      await expect(page.getByText("Failed to load shopping list"), "BUG REPRODUCED: the list with a quantity item fails to load").toHaveCount(0);
      await expect(page.getByText(itemName).first(), "item missing from its re-opened list").toBeVisible();
      await expect(page.getByText(/2\.5/).first(), "quantity 2.5 not shown").toBeVisible();
    });
  } finally {
    await test.step("clean up via the API, and prove nothing else changed", async () => {
      // If the list id was lost mid-run, find THIS run's list by its unique name.
      if (!created.listId && auth.header()) {
        created.listId = (await allLists(page, auth)).find((l) => l.name === listName)?.id;
      }
      if (created.listId) {
        const r = await api(page, auth, "GET", `/v1/shopping-lists/${created.listId}`);
        const name = String(((await r.json().catch(() => ({}))) as { name?: unknown }).name ?? "");
        // Refuse to delete anything this run did not create.
        expect(name, `refusing to delete list ${created.listId}: not this run's list`).toBe(listName);
        for (const itemId of created.itemIds) {
          await api(page, auth, "DELETE", `/v1/shopping-lists/${created.listId}/items/${itemId}`);
        }
        const del = await api(page, auth, "DELETE", `/v1/shopping-lists/${created.listId}`);
        expect(del.ok(), `DELETE list → HTTP ${del.status()}`).toBe(true);
        const gone = await api(page, auth, "GET", `/v1/shopping-lists/${created.listId}`);
        expect(gone.ok(), "test list still readable after DELETE").toBe(false);
      }
      if (before.length > 0) {
        const after = await allLists(page, auth);
        expect(after, "a pre-existing list changed or disappeared").toEqual(before);
      }
    });
  }
});
