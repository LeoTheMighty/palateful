-- ============================================================
-- Invitation System Test Data
-- ============================================================
-- Idempotent: uses ON CONFLICT DO NOTHING where possible.
--
-- Test users:
--   alice   (@alice)   - Power user, owns recipe books & pantry
--   bob     (@bob)     - Alice's friend, some shared resources
--   charlie (@charlie) - Receives invitations, hasn't responded to some
--   diana   (@diana)   - Minimal user, joins via links
--   eve     (no account) - Email-only invite target (eve@test.com)
-- ============================================================

BEGIN;

-- ============================================================
-- 1. Test Users
-- ============================================================

INSERT INTO users (id, auth0_id, email, name, username, email_verified, has_completed_onboarding, created_at, updated_at)
VALUES
    ('a0000000-0000-0000-0000-000000000001', 'test-alice', 'alice@test.com', 'Alice Johnson', 'alice', true, true, now() - interval '30 days', now()),
    ('a0000000-0000-0000-0000-000000000002', 'test-bob', 'bob@test.com', 'Bob Smith', 'bob', true, true, now() - interval '28 days', now()),
    ('a0000000-0000-0000-0000-000000000003', 'test-charlie', 'charlie@test.com', 'Charlie Brown', 'charlie', true, true, now() - interval '20 days', now()),
    ('a0000000-0000-0000-0000-000000000004', 'test-diana', 'diana@test.com', 'Diana Prince', 'diana', true, true, now() - interval '10 days', now())
ON CONFLICT (auth0_id) DO NOTHING;

-- ============================================================
-- 2. Resources to share
-- ============================================================

-- Recipe Books (no owner_id, ownership via join table)
INSERT INTO recipe_books (id, name, description, created_at, updated_at)
VALUES
    ('b0000000-0000-0000-0000-000000000001', 'Italian Classics', 'Traditional Italian recipes', now() - interval '25 days', now()),
    ('b0000000-0000-0000-0000-000000000002', 'Quick Weeknight Meals', 'Easy 30-minute recipes', now() - interval '20 days', now()),
    ('b0000000-0000-0000-0000-000000000003', 'Holiday Baking', 'Cookies, pies, and cakes', now() - interval '15 days', now())
ON CONFLICT (id) DO NOTHING;

-- Alice owns all three recipe books
INSERT INTO recipe_book_users (user_id, recipe_book_id, role, created_at, updated_at)
VALUES
    ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'owner', now() - interval '25 days', now()),
    ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 'owner', now() - interval '20 days', now()),
    ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 'owner', now() - interval '15 days', now())
ON CONFLICT DO NOTHING;

-- Bob is already an editor on "Italian Classics"
INSERT INTO recipe_book_users (user_id, recipe_book_id, role, invited_by_id, created_at, updated_at)
VALUES
    ('a0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000001', 'editor', 'a0000000-0000-0000-0000-000000000001', now() - interval '20 days', now())
ON CONFLICT DO NOTHING;

-- Pantries (no owner_id, ownership via join table)
INSERT INTO pantries (id, name, created_at, updated_at)
VALUES
    ('c0000000-0000-0000-0000-000000000001', 'Home Kitchen', now() - interval '25 days', now()),
    ('c0000000-0000-0000-0000-000000000002', 'Vacation House', now() - interval '10 days', now())
ON CONFLICT (id) DO NOTHING;

-- Alice owns both pantries
INSERT INTO pantry_users (user_id, pantry_id, role, created_at, updated_at)
VALUES
    ('a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'owner', now() - interval '25 days', now()),
    ('a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000002', 'owner', now() - interval '10 days', now())
ON CONFLICT DO NOTHING;

-- Shopping Lists (has owner_id)
INSERT INTO shopping_lists (id, name, status, owner_id, is_shared, created_at, updated_at)
VALUES
    ('d0000000-0000-0000-0000-000000000001', 'Weekly Groceries', 'in_progress', 'a0000000-0000-0000-0000-000000000001', false, now() - interval '3 days', now()),
    ('d0000000-0000-0000-0000-000000000002', 'Party Supplies', 'pending', 'a0000000-0000-0000-0000-000000000001', true, now() - interval '5 days', now())
ON CONFLICT (id) DO NOTHING;

-- Alice is owner-member of her shopping lists
INSERT INTO shopping_list_users (shopping_list_id, user_id, role, created_at, updated_at)
VALUES
    ('d0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'owner', now() - interval '3 days', now()),
    ('d0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'owner', now() - interval '5 days', now())
ON CONFLICT DO NOTHING;

-- Meal Events (has owner_id)
INSERT INTO meal_events (id, title, scheduled_at, meal_type, status, owner_id, created_at, updated_at)
VALUES
    ('e0000000-0000-0000-0000-000000000001', 'Sunday Pasta Night', now() + interval '5 days', 'dinner', 'planned', 'a0000000-0000-0000-0000-000000000001', now() - interval '2 days', now()),
    ('e0000000-0000-0000-0000-000000000002', 'Birthday Brunch', now() + interval '12 days', 'lunch', 'planned', 'a0000000-0000-0000-0000-000000000001', now() - interval '1 day', now())
ON CONFLICT (id) DO NOTHING;

-- Alice is host of her meal events
INSERT INTO meal_event_participants (meal_event_id, user_id, status, role, created_at, updated_at)
VALUES
    ('e0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'accepted', 'host', now() - interval '2 days', now()),
    ('e0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'accepted', 'host', now() - interval '1 day', now())
ON CONFLICT DO NOTHING;

-- ============================================================
-- 3. Invitations (various statuses)
-- ============================================================

-- Pending: Alice invited Charlie to "Quick Weeknight Meals" (recipe book)
INSERT INTO invitations (id, from_user_id, to_user_id, resource_type, resource_id, role_offered, status, message, expires_at, created_at, updated_at)
VALUES
    ('f0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000003',
     'recipe_book', 'b0000000-0000-0000-0000-000000000002', 'editor', 'pending',
     'Hey Charlie! Want to collaborate on our weeknight meals?',
     now() + interval '30 days', now() - interval '2 days', now())
ON CONFLICT (id) DO NOTHING;

-- Pending: Alice invited Charlie to "Home Kitchen" pantry
INSERT INTO invitations (id, from_user_id, to_user_id, resource_type, resource_id, role_offered, status, message, expires_at, created_at, updated_at)
VALUES
    ('f0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000003',
     'pantry', 'c0000000-0000-0000-0000-000000000001', 'editor', 'pending',
     'Share my pantry so we can track ingredients together',
     now() + interval '30 days', now() - interval '1 day', now())
ON CONFLICT (id) DO NOTHING;

-- Pending: Alice invited Diana to "Sunday Pasta Night" (meal event)
INSERT INTO invitations (id, from_user_id, to_user_id, resource_type, resource_id, role_offered, status, message, expires_at, created_at, updated_at)
VALUES
    ('f0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000004',
     'meal_event', 'e0000000-0000-0000-0000-000000000001', 'guest', 'pending',
     'Join us for pasta!',
     now() + interval '30 days', now() - interval '12 hours', now())
ON CONFLICT (id) DO NOTHING;

-- Pending: Alice invited Diana to "Party Supplies" shopping list
INSERT INTO invitations (id, from_user_id, to_user_id, resource_type, resource_id, role_offered, status, message, expires_at, created_at, updated_at)
VALUES
    ('f0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000004',
     'shopping_list', 'd0000000-0000-0000-0000-000000000002', 'editor', 'pending',
     'Help me pick up party supplies!',
     now() + interval '30 days', now() - interval '6 hours', now())
ON CONFLICT (id) DO NOTHING;

-- Accepted: Bob accepted Alice's invite to "Holiday Baking"
INSERT INTO invitations (id, from_user_id, to_user_id, resource_type, resource_id, role_offered, status, message, responded_at, expires_at, created_at, updated_at)
VALUES
    ('f0000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000002',
     'recipe_book', 'b0000000-0000-0000-0000-000000000003', 'editor', 'accepted',
     'Let''s bake together this holiday season!',
     now() - interval '3 days', now() + interval '27 days', now() - interval '10 days', now())
ON CONFLICT (id) DO NOTHING;

-- Bob is now a member of Holiday Baking (from accepted invite)
INSERT INTO recipe_book_users (user_id, recipe_book_id, role, invited_by_id, created_at, updated_at)
VALUES
    ('a0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000003', 'editor', 'a0000000-0000-0000-0000-000000000001', now() - interval '3 days', now())
ON CONFLICT DO NOTHING;

-- Declined: Charlie declined Bob's invite to "Vacation House" pantry
INSERT INTO invitations (id, from_user_id, to_user_id, resource_type, resource_id, role_offered, status, responded_at, expires_at, created_at, updated_at)
VALUES
    ('f0000000-0000-0000-0000-000000000006', 'a0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000003',
     'pantry', 'c0000000-0000-0000-0000-000000000002', 'viewer', 'declined',
     now() - interval '5 days', now() + interval '25 days', now() - interval '8 days', now())
ON CONFLICT (id) DO NOTHING;

-- Revoked: Alice revoked an invite to Charlie for "Weekly Groceries"
INSERT INTO invitations (id, from_user_id, to_user_id, resource_type, resource_id, role_offered, status, expires_at, created_at, updated_at)
VALUES
    ('f0000000-0000-0000-0000-000000000007', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000003',
     'shopping_list', 'd0000000-0000-0000-0000-000000000001', 'editor', 'revoked',
     now() + interval '30 days', now() - interval '7 days', now())
ON CONFLICT (id) DO NOTHING;

-- Email-only: Alice invited eve@test.com (no account) to "Birthday Brunch"
INSERT INTO invitations (id, from_user_id, to_user_id, to_email, resource_type, resource_id, role_offered, status, message, expires_at, created_at, updated_at)
VALUES
    ('f0000000-0000-0000-0000-000000000008', 'a0000000-0000-0000-0000-000000000001', NULL, 'eve@test.com',
     'meal_event', 'e0000000-0000-0000-0000-000000000002', 'guest', 'pending',
     'You''re invited to my birthday brunch! Sign up on Palateful to join!',
     now() + interval '30 days', now() - interval '1 day', now())
ON CONFLICT (id) DO NOTHING;

-- Email-only: Alice invited eve@test.com to "Holiday Baking" recipe book
INSERT INTO invitations (id, from_user_id, to_user_id, to_email, resource_type, resource_id, role_offered, status, message, expires_at, created_at, updated_at)
VALUES
    ('f0000000-0000-0000-0000-000000000009', 'a0000000-0000-0000-0000-000000000001', NULL, 'eve@test.com',
     'recipe_book', 'b0000000-0000-0000-0000-000000000003', 'viewer', 'pending',
     'Check out our holiday baking recipes!',
     now() + interval '30 days', now() - interval '12 hours', now())
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 4. Invite Links
-- ============================================================

-- Active link: Alice's link to "Italian Classics" (unlimited uses)
INSERT INTO invite_links (id, token, created_by_id, resource_type, resource_id, role_offered, max_uses, use_count, is_active, expires_at, created_at, updated_at)
VALUES
    ('10000000-0000-0000-0000-000000000001', 'italian-classics-abc', 'a0000000-0000-0000-0000-000000000001',
     'recipe_book', 'b0000000-0000-0000-0000-000000000001', 'viewer',
     NULL, 1, true, now() + interval '60 days', now() - interval '15 days', now())
ON CONFLICT (id) DO NOTHING;

-- Active link: Alice's link to "Sunday Pasta Night" (max 5 uses, 2 used)
INSERT INTO invite_links (id, token, created_by_id, resource_type, resource_id, role_offered, max_uses, use_count, is_active, expires_at, created_at, updated_at)
VALUES
    ('10000000-0000-0000-0000-000000000002', 'pasta-night-xyz1234', 'a0000000-0000-0000-0000-000000000001',
     'meal_event', 'e0000000-0000-0000-0000-000000000001', 'guest',
     5, 2, true, now() + interval '10 days', now() - interval '3 days', now())
ON CONFLICT (id) DO NOTHING;

-- Deactivated link: Alice deactivated a pantry link
INSERT INTO invite_links (id, token, created_by_id, resource_type, resource_id, role_offered, max_uses, use_count, is_active, created_at, updated_at)
VALUES
    ('10000000-0000-0000-0000-000000000003', 'pantry-old-link0000', 'a0000000-0000-0000-0000-000000000001',
     'pantry', 'c0000000-0000-0000-0000-000000000001', 'editor',
     10, 3, false, now() - interval '20 days', now())
ON CONFLICT (id) DO NOTHING;

-- Expired link: Alice's expired shopping list link
INSERT INTO invite_links (id, token, created_by_id, resource_type, resource_id, role_offered, max_uses, use_count, is_active, expires_at, created_at, updated_at)
VALUES
    ('10000000-0000-0000-0000-000000000004', 'groceries-expired00', 'a0000000-0000-0000-0000-000000000001',
     'shopping_list', 'd0000000-0000-0000-0000-000000000001', 'editor',
     NULL, 0, true, now() - interval '2 days', now() - interval '32 days', now())
ON CONFLICT (id) DO NOTHING;

-- Full link: Bob's link that hit max uses
INSERT INTO invite_links (id, token, created_by_id, resource_type, resource_id, role_offered, max_uses, use_count, is_active, expires_at, created_at, updated_at)
VALUES
    ('10000000-0000-0000-0000-000000000005', 'baking-full-link000', 'a0000000-0000-0000-0000-000000000002',
     'recipe_book', 'b0000000-0000-0000-0000-000000000003', 'viewer',
     2, 2, true, now() + interval '30 days', now() - interval '5 days', now())
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 5. Activity log entries
-- ============================================================

INSERT INTO activities (id, user_id, action, resource_type, resource_id, details, created_at, updated_at)
VALUES
    -- Bob joined Italian Classics (via earlier invite, before this system)
    (gen_random_uuid(), 'a0000000-0000-0000-0000-000000000002', 'joined', 'recipe_book', 'b0000000-0000-0000-0000-000000000001',
     '{"via": "invitation", "role": "editor"}', now() - interval '20 days', now()),
    -- Bob joined Holiday Baking via invitation
    (gen_random_uuid(), 'a0000000-0000-0000-0000-000000000002', 'joined', 'recipe_book', 'b0000000-0000-0000-0000-000000000003',
     '{"via": "invitation", "invitation_id": "f0000000-0000-0000-0000-000000000005", "role": "editor"}', now() - interval '3 days', now()),
    -- Diana joined Italian Classics via invite link
    (gen_random_uuid(), 'a0000000-0000-0000-0000-000000000004', 'joined', 'recipe_book', 'b0000000-0000-0000-0000-000000000001',
     '{"via": "invite_link", "invite_link_id": "10000000-0000-0000-0000-000000000001", "role": "viewer"}', now() - interval '5 days', now())
ON CONFLICT DO NOTHING;

-- Diana is a viewer on Italian Classics (joined via link)
INSERT INTO recipe_book_users (user_id, recipe_book_id, role, invited_by_id, created_at, updated_at)
VALUES
    ('a0000000-0000-0000-0000-000000000004', 'b0000000-0000-0000-0000-000000000001', 'viewer', 'a0000000-0000-0000-0000-000000000001', now() - interval '5 days', now())
ON CONFLICT DO NOTHING;

-- ============================================================
-- 6. Ingredients (~34)
-- ============================================================

INSERT INTO ingredients (id, canonical_name, category, default_unit, created_at, updated_at)
VALUES
    ('11000000-0000-0000-0000-000000000001', 'tomato', 'produce', 'count', now(), now()),
    ('11000000-0000-0000-0000-000000000002', 'mozzarella', 'dairy', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000003', 'fresh basil', 'produce', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000004', 'olive oil', 'oils', 'ml', now(), now()),
    ('11000000-0000-0000-0000-000000000005', 'garlic', 'produce', 'count', now(), now()),
    ('11000000-0000-0000-0000-000000000006', 'parmesan cheese', 'dairy', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000007', 'spaghetti', 'pasta', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000008', 'egg', 'dairy', 'count', now(), now()),
    ('11000000-0000-0000-0000-000000000009', 'pancetta', 'meat', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000010', 'black pepper', 'spices', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000011', 'chicken breast', 'meat', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000012', 'breadcrumbs', 'baking', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000013', 'arborio rice', 'grains', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000014', 'white wine', 'beverages', 'ml', now(), now()),
    ('11000000-0000-0000-0000-000000000015', 'cremini mushrooms', 'produce', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000016', 'crusty bread', 'bakery', 'count', now(), now()),
    ('11000000-0000-0000-0000-000000000017', 'butter', 'dairy', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000018', 'lemon', 'produce', 'count', now(), now()),
    ('11000000-0000-0000-0000-000000000019', 'long grain rice', 'grains', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000020', 'beef sirloin', 'meat', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000021', 'soy sauce', 'condiments', 'ml', now(), now()),
    ('11000000-0000-0000-0000-000000000022', 'fresh ginger', 'produce', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000023', 'spinach', 'produce', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000024', 'bell pepper', 'produce', 'count', now(), now()),
    ('11000000-0000-0000-0000-000000000025', 'broccoli', 'produce', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000026', 'all-purpose flour', 'baking', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000027', 'granulated sugar', 'baking', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000028', 'chocolate chips', 'baking', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000029', 'vanilla extract', 'baking', 'ml', now(), now()),
    ('11000000-0000-0000-0000-000000000030', 'baking soda', 'baking', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000031', 'cocoa powder', 'baking', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000032', 'powdered sugar', 'baking', 'g', now(), now()),
    ('11000000-0000-0000-0000-000000000033', 'heavy cream', 'dairy', 'ml', now(), now()),
    ('11000000-0000-0000-0000-000000000034', 'salt', 'spices', 'g', now(), now())
ON CONFLICT DO NOTHING;

-- ============================================================
-- 7. Recipes (15 — 5 per recipe book)
-- ============================================================

INSERT INTO recipes (id, name, description, servings, prep_time, cook_time, recipe_book_id, created_at, updated_at)
VALUES
    -- Italian Classics
    ('13000000-0000-0000-0000-000000000001', 'Margherita Pizza', 'Classic Neapolitan pizza with fresh mozzarella, tomatoes, and basil', 4, 30, 15, 'b0000000-0000-0000-0000-000000000001', now() - interval '24 days', now()),
    ('13000000-0000-0000-0000-000000000002', 'Spaghetti Carbonara', 'Authentic Roman carbonara with guanciale, egg, and pecorino', 4, 10, 20, 'b0000000-0000-0000-0000-000000000001', now() - interval '23 days', now()),
    ('13000000-0000-0000-0000-000000000003', 'Chicken Parmesan', 'Crispy breaded chicken topped with marinara and melted mozzarella', 4, 20, 25, 'b0000000-0000-0000-0000-000000000001', now() - interval '22 days', now()),
    ('13000000-0000-0000-0000-000000000004', 'Mushroom Risotto', 'Creamy arborio rice with sautéed cremini mushrooms and parmesan', 4, 10, 35, 'b0000000-0000-0000-0000-000000000001', now() - interval '21 days', now()),
    ('13000000-0000-0000-0000-000000000005', 'Bruschetta al Pomodoro', 'Toasted crusty bread topped with fresh tomato, garlic, and basil', 6, 15, 5, 'b0000000-0000-0000-0000-000000000001', now() - interval '20 days', now()),
    -- Quick Weeknight Meals
    ('13000000-0000-0000-0000-000000000006', 'Garlic Butter Chicken', 'Pan-seared chicken basted in garlic butter with a squeeze of lemon', 4, 10, 20, 'b0000000-0000-0000-0000-000000000002', now() - interval '19 days', now()),
    ('13000000-0000-0000-0000-000000000007', 'One-Pan Lemon Herb Rice', 'Fluffy lemon-scented rice with wilted spinach, all in one pan', 4, 5, 25, 'b0000000-0000-0000-0000-000000000002', now() - interval '18 days', now()),
    ('13000000-0000-0000-0000-000000000008', 'Beef Stir Fry', 'Quick stir-fried beef sirloin with crisp vegetables and soy glaze', 4, 15, 10, 'b0000000-0000-0000-0000-000000000002', now() - interval '17 days', now()),
    ('13000000-0000-0000-0000-000000000009', 'Spinach & Mushroom Pasta', 'Simple spaghetti tossed with sautéed mushrooms, spinach, and parmesan', 4, 10, 15, 'b0000000-0000-0000-0000-000000000002', now() - interval '16 days', now()),
    ('13000000-0000-0000-0000-000000000010', 'Sheet Pan Roasted Vegetables', 'Colorful roasted peppers, broccoli, and mushrooms with garlic', 4, 15, 30, 'b0000000-0000-0000-0000-000000000002', now() - interval '15 days', now()),
    -- Holiday Baking
    ('13000000-0000-0000-0000-000000000011', 'Chocolate Chip Cookies', 'Classic chewy cookies loaded with chocolate chips', 24, 15, 12, 'b0000000-0000-0000-0000-000000000003', now() - interval '14 days', now()),
    ('13000000-0000-0000-0000-000000000012', 'Vanilla Buttercream Cake', 'Tender vanilla cake layered with rich buttercream frosting', 12, 30, 35, 'b0000000-0000-0000-0000-000000000003', now() - interval '13 days', now()),
    ('13000000-0000-0000-0000-000000000013', 'Lemon Bars', 'Buttery shortbread crust topped with tangy lemon curd', 16, 15, 40, 'b0000000-0000-0000-0000-000000000003', now() - interval '12 days', now()),
    ('13000000-0000-0000-0000-000000000014', 'Double Chocolate Brownies', 'Fudgy brownies with cocoa and chocolate chips', 16, 15, 25, 'b0000000-0000-0000-0000-000000000003', now() - interval '11 days', now()),
    ('13000000-0000-0000-0000-000000000015', 'Sugar Cookie Cutouts', 'Buttery roll-and-cut cookies perfect for decorating', 36, 45, 10, 'b0000000-0000-0000-0000-000000000003', now() - interval '10 days', now())
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 8. Recipe Steps
-- ============================================================

INSERT INTO recipe_steps (id, recipe_id, step_number, instruction, active_time_minutes, created_at, updated_at)
VALUES
    -- Margherita Pizza (5 steps)
    ('14000000-0000-0000-0000-000000000001', '13000000-0000-0000-0000-000000000001', 1, 'Mix flour, salt, and yeast with warm water to form a dough. Knead for 8 minutes until smooth and elastic.', 10, now(), now()),
    ('14000000-0000-0000-0000-000000000002', '13000000-0000-0000-0000-000000000001', 2, 'Cover dough and let it rise in a warm place for 1 hour until doubled in size.', 2, now(), now()),
    ('14000000-0000-0000-0000-000000000003', '13000000-0000-0000-0000-000000000001', 3, 'Preheat oven to 500°F. Stretch dough into a 12-inch round on a floured surface.', 5, now(), now()),
    ('14000000-0000-0000-0000-000000000004', '13000000-0000-0000-0000-000000000001', 4, 'Spread crushed tomatoes over dough, leaving a 1-inch border. Top with torn mozzarella and a drizzle of olive oil.', 5, now(), now()),
    ('14000000-0000-0000-0000-000000000005', '13000000-0000-0000-0000-000000000001', 5, 'Bake for 10-12 minutes until crust is golden and cheese is bubbling. Top with fresh basil leaves.', 2, now(), now()),
    -- Spaghetti Carbonara (4 steps)
    ('14000000-0000-0000-0000-000000000006', '13000000-0000-0000-0000-000000000002', 1, 'Bring a large pot of salted water to a boil. Cook spaghetti until al dente, reserving 1 cup pasta water.', 3, now(), now()),
    ('14000000-0000-0000-0000-000000000007', '13000000-0000-0000-0000-000000000002', 2, 'While pasta cooks, crisp pancetta in a large skillet over medium heat for 5-6 minutes.', 8, now(), now()),
    ('14000000-0000-0000-0000-000000000008', '13000000-0000-0000-0000-000000000002', 3, 'Whisk together eggs, grated parmesan, and a generous amount of black pepper in a bowl.', 3, now(), now()),
    ('14000000-0000-0000-0000-000000000009', '13000000-0000-0000-0000-000000000002', 4, 'Toss hot pasta with pancetta, remove from heat, then quickly stir in the egg mixture. Add pasta water as needed for a creamy sauce.', 3, now(), now()),
    -- Chicken Parmesan (5 steps)
    ('14000000-0000-0000-0000-000000000010', '13000000-0000-0000-0000-000000000003', 1, 'Pound chicken breasts to ½-inch thickness between sheets of plastic wrap.', 5, now(), now()),
    ('14000000-0000-0000-0000-000000000011', '13000000-0000-0000-0000-000000000003', 2, 'Set up breading station: flour in one dish, beaten eggs in another, breadcrumbs mixed with parmesan in a third. Coat each chicken breast.', 8, now(), now()),
    ('14000000-0000-0000-0000-000000000012', '13000000-0000-0000-0000-000000000003', 3, 'Heat olive oil in a large oven-safe skillet over medium-high heat. Pan-fry chicken 3 minutes per side until golden.', 8, now(), now()),
    ('14000000-0000-0000-0000-000000000013', '13000000-0000-0000-0000-000000000003', 4, 'Spoon crushed tomatoes over each chicken breast and top with sliced mozzarella.', 3, now(), now()),
    ('14000000-0000-0000-0000-000000000014', '13000000-0000-0000-0000-000000000003', 5, 'Bake at 425°F for 15 minutes until cheese is melted and chicken reaches 165°F internal temperature.', 2, now(), now()),
    -- Mushroom Risotto (5 steps)
    ('14000000-0000-0000-0000-000000000015', '13000000-0000-0000-0000-000000000004', 1, 'Slice cremini mushrooms. Sauté in butter over medium-high heat until golden brown, about 6 minutes. Set aside.', 8, now(), now()),
    ('14000000-0000-0000-0000-000000000016', '13000000-0000-0000-0000-000000000004', 2, 'In the same pot, sauté minced garlic for 30 seconds. Add arborio rice and toast for 2 minutes, stirring constantly.', 4, now(), now()),
    ('14000000-0000-0000-0000-000000000017', '13000000-0000-0000-0000-000000000004', 3, 'Pour in white wine and stir until fully absorbed.', 2, now(), now()),
    ('14000000-0000-0000-0000-000000000018', '13000000-0000-0000-0000-000000000004', 4, 'Add warm broth one ladle at a time, stirring frequently, until rice is creamy and al dente — about 18 minutes total.', 20, now(), now()),
    ('14000000-0000-0000-0000-000000000019', '13000000-0000-0000-0000-000000000004', 5, 'Fold in the sautéed mushrooms, grated parmesan, and a knob of butter. Season with salt and pepper.', 3, now(), now()),
    -- Bruschetta al Pomodoro (4 steps)
    ('14000000-0000-0000-0000-000000000020', '13000000-0000-0000-0000-000000000005', 1, 'Dice tomatoes and combine with minced garlic, torn basil, a drizzle of olive oil, and a pinch of salt. Let sit for 10 minutes.', 8, now(), now()),
    ('14000000-0000-0000-0000-000000000021', '13000000-0000-0000-0000-000000000005', 2, 'Slice crusty bread into ½-inch thick pieces.', 3, now(), now()),
    ('14000000-0000-0000-0000-000000000022', '13000000-0000-0000-0000-000000000005', 3, 'Toast bread under the broiler or on a grill for 1-2 minutes per side until golden.', 4, now(), now()),
    ('14000000-0000-0000-0000-000000000023', '13000000-0000-0000-0000-000000000005', 4, 'Rub toasted bread with a cut garlic clove, spoon the tomato mixture on top, and finish with a drizzle of olive oil.', 3, now(), now()),
    -- Garlic Butter Chicken (4 steps)
    ('14000000-0000-0000-0000-000000000024', '13000000-0000-0000-0000-000000000006', 1, 'Season chicken breasts generously with salt and pepper on both sides.', 2, now(), now()),
    ('14000000-0000-0000-0000-000000000025', '13000000-0000-0000-0000-000000000006', 2, 'Heat olive oil in a large skillet over medium-high heat. Sear chicken for 5 minutes per side until golden brown.', 12, now(), now()),
    ('14000000-0000-0000-0000-000000000026', '13000000-0000-0000-0000-000000000006', 3, 'Reduce heat to medium-low. Add butter and minced garlic to the pan, tilting to pool the butter, and baste chicken for 2 minutes.', 4, now(), now()),
    ('14000000-0000-0000-0000-000000000027', '13000000-0000-0000-0000-000000000006', 4, 'Squeeze fresh lemon juice over the chicken. Rest for 5 minutes before slicing and serving with pan juices.', 2, now(), now()),
    -- One-Pan Lemon Herb Rice (4 steps)
    ('14000000-0000-0000-0000-000000000028', '13000000-0000-0000-0000-000000000007', 1, 'Melt butter in a large pan over medium heat. Add minced garlic and toast the rice for 2 minutes, stirring frequently.', 4, now(), now()),
    ('14000000-0000-0000-0000-000000000029', '13000000-0000-0000-0000-000000000007', 2, 'Add 2 cups water, juice of one lemon, and a pinch of salt. Bring to a boil, then cover and reduce heat to low.', 3, now(), now()),
    ('14000000-0000-0000-0000-000000000030', '13000000-0000-0000-0000-000000000007', 3, 'Simmer covered for 18 minutes until rice is tender and liquid is absorbed. Do not lift the lid.', 1, now(), now()),
    ('14000000-0000-0000-0000-000000000031', '13000000-0000-0000-0000-000000000007', 4, 'Fluff rice with a fork and fold in fresh spinach until wilted. Zest the remaining lemon over the top.', 3, now(), now()),
    -- Beef Stir Fry (5 steps)
    ('14000000-0000-0000-0000-000000000032', '13000000-0000-0000-0000-000000000008', 1, 'Slice beef sirloin into thin strips against the grain.', 5, now(), now()),
    ('14000000-0000-0000-0000-000000000033', '13000000-0000-0000-0000-000000000008', 2, 'Whisk together soy sauce, minced ginger, and minced garlic for the stir fry sauce.', 3, now(), now()),
    ('14000000-0000-0000-0000-000000000034', '13000000-0000-0000-0000-000000000008', 3, 'Heat oil in a wok or large skillet over high heat. Stir-fry sliced bell peppers and broccoli florets for 3 minutes. Remove and set aside.', 4, now(), now()),
    ('14000000-0000-0000-0000-000000000035', '13000000-0000-0000-0000-000000000008', 4, 'In the same wok, sear beef strips in batches for 2 minutes per batch until browned.', 4, now(), now()),
    ('14000000-0000-0000-0000-000000000036', '13000000-0000-0000-0000-000000000008', 5, 'Return vegetables to the wok, pour the sauce over everything, and toss until evenly coated and heated through.', 2, now(), now()),
    -- Spinach & Mushroom Pasta (4 steps)
    ('14000000-0000-0000-0000-000000000037', '13000000-0000-0000-0000-000000000009', 1, 'Cook spaghetti in a large pot of salted boiling water until al dente. Reserve ½ cup pasta water, then drain.', 3, now(), now()),
    ('14000000-0000-0000-0000-000000000038', '13000000-0000-0000-0000-000000000009', 2, 'Heat olive oil in a large skillet. Sauté sliced mushrooms until golden, about 5 minutes. Add minced garlic and cook 30 seconds.', 7, now(), now()),
    ('14000000-0000-0000-0000-000000000039', '13000000-0000-0000-0000-000000000009', 3, 'Add spinach to the skillet and cook until just wilted, about 1 minute.', 2, now(), now()),
    ('14000000-0000-0000-0000-000000000040', '13000000-0000-0000-0000-000000000009', 4, 'Toss the drained pasta with the vegetables, adding reserved pasta water as needed. Finish with grated parmesan and freshly cracked pepper.', 3, now(), now()),
    -- Sheet Pan Roasted Vegetables (4 steps)
    ('14000000-0000-0000-0000-000000000041', '13000000-0000-0000-0000-000000000010', 1, 'Preheat oven to 425°F. Cut bell peppers into strips, break broccoli into florets, and quarter the mushrooms.', 10, now(), now()),
    ('14000000-0000-0000-0000-000000000042', '13000000-0000-0000-0000-000000000010', 2, 'Toss all vegetables with olive oil, minced garlic, salt, and pepper on a large rimmed sheet pan.', 3, now(), now()),
    ('14000000-0000-0000-0000-000000000043', '13000000-0000-0000-0000-000000000010', 3, 'Spread vegetables in a single layer and roast for 25-30 minutes, tossing halfway through, until tender and caramelized.', 2, now(), now()),
    ('14000000-0000-0000-0000-000000000044', '13000000-0000-0000-0000-000000000010', 4, 'Remove from oven and season with additional salt and pepper to taste.', 2, now(), now()),
    -- Chocolate Chip Cookies (5 steps)
    ('14000000-0000-0000-0000-000000000045', '13000000-0000-0000-0000-000000000011', 1, 'Preheat oven to 375°F. Cream together softened butter and sugar with a hand mixer until light and fluffy, about 3 minutes.', 5, now(), now()),
    ('14000000-0000-0000-0000-000000000046', '13000000-0000-0000-0000-000000000011', 2, 'Beat in eggs one at a time, then add vanilla extract and mix until combined.', 3, now(), now()),
    ('14000000-0000-0000-0000-000000000047', '13000000-0000-0000-0000-000000000011', 3, 'Whisk together flour, baking soda, and salt in a separate bowl. Gradually mix dry ingredients into the wet until just combined.', 4, now(), now()),
    ('14000000-0000-0000-0000-000000000048', '13000000-0000-0000-0000-000000000011', 4, 'Fold in chocolate chips. Scoop rounded tablespoons of dough onto parchment-lined baking sheets, spacing 2 inches apart.', 5, now(), now()),
    ('14000000-0000-0000-0000-000000000049', '13000000-0000-0000-0000-000000000011', 5, 'Bake for 10-12 minutes until edges are golden but centers are still soft. Cool on the pan for 5 minutes before transferring to a wire rack.', 2, now(), now()),
    -- Vanilla Buttercream Cake (6 steps)
    ('14000000-0000-0000-0000-000000000050', '13000000-0000-0000-0000-000000000012', 1, 'Preheat oven to 350°F. Grease and flour two 9-inch round cake pans.', 5, now(), now()),
    ('14000000-0000-0000-0000-000000000051', '13000000-0000-0000-0000-000000000012', 2, 'Whisk together flour, baking soda, and salt. In a separate large bowl, cream butter and sugar until light and fluffy.', 8, now(), now()),
    ('14000000-0000-0000-0000-000000000052', '13000000-0000-0000-0000-000000000012', 3, 'Add eggs one at a time to the butter mixture, then vanilla. Alternate adding the flour mixture and heavy cream in batches, mixing until smooth.', 5, now(), now()),
    ('14000000-0000-0000-0000-000000000053', '13000000-0000-0000-0000-000000000012', 4, 'Divide batter evenly between the prepared pans. Bake for 30-35 minutes until a toothpick inserted in the center comes out clean. Cool completely.', 3, now(), now()),
    ('14000000-0000-0000-0000-000000000054', '13000000-0000-0000-0000-000000000012', 5, 'For the frosting: beat softened butter until smooth, then gradually add powdered sugar and vanilla. Add cream a tablespoon at a time until spreadable.', 10, now(), now()),
    ('14000000-0000-0000-0000-000000000055', '13000000-0000-0000-0000-000000000012', 6, 'Place one cake layer on a plate and spread frosting on top. Add the second layer, then frost the top and sides. Chill 15 minutes before serving.', 10, now(), now()),
    -- Lemon Bars (5 steps)
    ('14000000-0000-0000-0000-000000000056', '13000000-0000-0000-0000-000000000013', 1, 'Preheat oven to 350°F. Mix flour, powdered sugar, and cold cubed butter until crumbly. Press firmly into a greased 9x13 pan.', 8, now(), now()),
    ('14000000-0000-0000-0000-000000000057', '13000000-0000-0000-0000-000000000013', 2, 'Bake the shortbread base for 18-20 minutes until lightly golden around the edges.', 1, now(), now()),
    ('14000000-0000-0000-0000-000000000058', '13000000-0000-0000-0000-000000000013', 3, 'While the base bakes, whisk together eggs, sugar, fresh lemon juice, lemon zest, and a tablespoon of flour.', 5, now(), now()),
    ('14000000-0000-0000-0000-000000000059', '13000000-0000-0000-0000-000000000013', 4, 'Pour the lemon filling over the hot crust and return to the oven. Bake for 20 more minutes until the filling is set.', 2, now(), now()),
    ('14000000-0000-0000-0000-000000000060', '13000000-0000-0000-0000-000000000013', 5, 'Cool completely in the pan, then dust generously with powdered sugar before cutting into squares.', 3, now(), now()),
    -- Double Chocolate Brownies (4 steps)
    ('14000000-0000-0000-0000-000000000061', '13000000-0000-0000-0000-000000000014', 1, 'Preheat oven to 350°F. Melt butter in a saucepan over low heat, then whisk in cocoa powder until smooth. Remove from heat.', 5, now(), now()),
    ('14000000-0000-0000-0000-000000000062', '13000000-0000-0000-0000-000000000014', 2, 'Stir in sugar, then beat in eggs one at a time. Add vanilla extract and mix until well combined.', 4, now(), now()),
    ('14000000-0000-0000-0000-000000000063', '13000000-0000-0000-0000-000000000014', 3, 'Gently fold in flour and chocolate chips until just mixed — do not overmix. Pour batter into a greased 8x8 baking pan.', 3, now(), now()),
    ('14000000-0000-0000-0000-000000000064', '13000000-0000-0000-0000-000000000014', 4, 'Bake for 22-25 minutes until a toothpick comes out with moist crumbs (not wet batter). Cool completely before cutting.', 2, now(), now()),
    -- Sugar Cookie Cutouts (5 steps)
    ('14000000-0000-0000-0000-000000000065', '13000000-0000-0000-0000-000000000015', 1, 'Cream together softened butter and sugar until light and fluffy. Beat in the egg and vanilla extract.', 5, now(), now()),
    ('14000000-0000-0000-0000-000000000066', '13000000-0000-0000-0000-000000000015', 2, 'Whisk together flour, baking soda, and salt. Gradually mix the dry ingredients into the wet until a soft dough forms.', 4, now(), now()),
    ('14000000-0000-0000-0000-000000000067', '13000000-0000-0000-0000-000000000015', 3, 'Wrap the dough tightly in plastic wrap and refrigerate for at least 1 hour until firm.', 2, now(), now()),
    ('14000000-0000-0000-0000-000000000068', '13000000-0000-0000-0000-000000000015', 4, 'Roll chilled dough to ¼-inch thickness on a floured surface. Cut shapes with cookie cutters and place on parchment-lined baking sheets.', 15, now(), now()),
    ('14000000-0000-0000-0000-000000000069', '13000000-0000-0000-0000-000000000015', 5, 'Bake at 350°F for 8-10 minutes until edges are just set but not browned. Cool, then decorate with a simple glaze of powdered sugar and milk.', 5, now(), now())
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 9. Recipe Ingredients
-- ============================================================

INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity_display, unit_display, quantity_normalized, unit_normalized, order_index, created_at, updated_at)
VALUES
    -- Margherita Pizza
    ('13000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000026', 3.000, 'cups', 360.000, 'g', 0, now(), now()),
    ('13000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000002', 8.000, 'oz', 227.000, 'g', 1, now(), now()),
    ('13000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000001', 4.000, 'whole', 4.000, 'count', 2, now(), now()),
    ('13000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000003', 0.250, 'cup', 10.000, 'g', 3, now(), now()),
    ('13000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000004', 2.000, 'tbsp', 30.000, 'ml', 4, now(), now()),
    ('13000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000034', 1.000, 'tsp', 6.000, 'g', 5, now(), now()),
    -- Spaghetti Carbonara
    ('13000000-0000-0000-0000-000000000002', '11000000-0000-0000-0000-000000000007', 1.000, 'lb', 454.000, 'g', 0, now(), now()),
    ('13000000-0000-0000-0000-000000000002', '11000000-0000-0000-0000-000000000009', 6.000, 'oz', 170.000, 'g', 1, now(), now()),
    ('13000000-0000-0000-0000-000000000002', '11000000-0000-0000-0000-000000000008', 4.000, 'large', 4.000, 'count', 2, now(), now()),
    ('13000000-0000-0000-0000-000000000002', '11000000-0000-0000-0000-000000000006', 1.000, 'cup', 100.000, 'g', 3, now(), now()),
    ('13000000-0000-0000-0000-000000000002', '11000000-0000-0000-0000-000000000010', 1.000, 'tsp', 3.000, 'g', 4, now(), now()),
    -- Chicken Parmesan
    ('13000000-0000-0000-0000-000000000003', '11000000-0000-0000-0000-000000000011', 4.000, 'pieces', 900.000, 'g', 0, now(), now()),
    ('13000000-0000-0000-0000-000000000003', '11000000-0000-0000-0000-000000000012', 1.000, 'cup', 108.000, 'g', 1, now(), now()),
    ('13000000-0000-0000-0000-000000000003', '11000000-0000-0000-0000-000000000006', 0.500, 'cup', 50.000, 'g', 2, now(), now()),
    ('13000000-0000-0000-0000-000000000003', '11000000-0000-0000-0000-000000000008', 2.000, 'large', 2.000, 'count', 3, now(), now()),
    ('13000000-0000-0000-0000-000000000003', '11000000-0000-0000-0000-000000000001', 2.000, 'cups', 480.000, 'g', 4, now(), now()),
    ('13000000-0000-0000-0000-000000000003', '11000000-0000-0000-0000-000000000002', 8.000, 'oz', 227.000, 'g', 5, now(), now()),
    ('13000000-0000-0000-0000-000000000003', '11000000-0000-0000-0000-000000000004', 3.000, 'tbsp', 45.000, 'ml', 6, now(), now()),
    -- Mushroom Risotto
    ('13000000-0000-0000-0000-000000000004', '11000000-0000-0000-0000-000000000013', 1.500, 'cups', 278.000, 'g', 0, now(), now()),
    ('13000000-0000-0000-0000-000000000004', '11000000-0000-0000-0000-000000000015', 12.000, 'oz', 340.000, 'g', 1, now(), now()),
    ('13000000-0000-0000-0000-000000000004', '11000000-0000-0000-0000-000000000014', 0.500, 'cup', 120.000, 'ml', 2, now(), now()),
    ('13000000-0000-0000-0000-000000000004', '11000000-0000-0000-0000-000000000006', 0.750, 'cup', 75.000, 'g', 3, now(), now()),
    ('13000000-0000-0000-0000-000000000004', '11000000-0000-0000-0000-000000000017', 3.000, 'tbsp', 42.000, 'g', 4, now(), now()),
    ('13000000-0000-0000-0000-000000000004', '11000000-0000-0000-0000-000000000005', 3.000, 'cloves', 3.000, 'count', 5, now(), now()),
    -- Bruschetta al Pomodoro
    ('13000000-0000-0000-0000-000000000005', '11000000-0000-0000-0000-000000000016', 1.000, 'loaf', 1.000, 'count', 0, now(), now()),
    ('13000000-0000-0000-0000-000000000005', '11000000-0000-0000-0000-000000000001', 6.000, 'whole', 6.000, 'count', 1, now(), now()),
    ('13000000-0000-0000-0000-000000000005', '11000000-0000-0000-0000-000000000005', 2.000, 'cloves', 2.000, 'count', 2, now(), now()),
    ('13000000-0000-0000-0000-000000000005', '11000000-0000-0000-0000-000000000003', 0.250, 'cup', 10.000, 'g', 3, now(), now()),
    ('13000000-0000-0000-0000-000000000005', '11000000-0000-0000-0000-000000000004', 3.000, 'tbsp', 45.000, 'ml', 4, now(), now()),
    ('13000000-0000-0000-0000-000000000005', '11000000-0000-0000-0000-000000000034', 0.500, 'tsp', 3.000, 'g', 5, now(), now()),
    -- Garlic Butter Chicken
    ('13000000-0000-0000-0000-000000000006', '11000000-0000-0000-0000-000000000011', 4.000, 'pieces', 900.000, 'g', 0, now(), now()),
    ('13000000-0000-0000-0000-000000000006', '11000000-0000-0000-0000-000000000017', 4.000, 'tbsp', 57.000, 'g', 1, now(), now()),
    ('13000000-0000-0000-0000-000000000006', '11000000-0000-0000-0000-000000000005', 6.000, 'cloves', 6.000, 'count', 2, now(), now()),
    ('13000000-0000-0000-0000-000000000006', '11000000-0000-0000-0000-000000000018', 1.000, 'whole', 1.000, 'count', 3, now(), now()),
    ('13000000-0000-0000-0000-000000000006', '11000000-0000-0000-0000-000000000004', 2.000, 'tbsp', 30.000, 'ml', 4, now(), now()),
    ('13000000-0000-0000-0000-000000000006', '11000000-0000-0000-0000-000000000034', 1.000, 'tsp', 6.000, 'g', 5, now(), now()),
    ('13000000-0000-0000-0000-000000000006', '11000000-0000-0000-0000-000000000010', 0.500, 'tsp', 1.500, 'g', 6, now(), now()),
    -- One-Pan Lemon Herb Rice
    ('13000000-0000-0000-0000-000000000007', '11000000-0000-0000-0000-000000000019', 1.500, 'cups', 278.000, 'g', 0, now(), now()),
    ('13000000-0000-0000-0000-000000000007', '11000000-0000-0000-0000-000000000018', 2.000, 'whole', 2.000, 'count', 1, now(), now()),
    ('13000000-0000-0000-0000-000000000007', '11000000-0000-0000-0000-000000000017', 2.000, 'tbsp', 28.000, 'g', 2, now(), now()),
    ('13000000-0000-0000-0000-000000000007', '11000000-0000-0000-0000-000000000005', 2.000, 'cloves', 2.000, 'count', 3, now(), now()),
    ('13000000-0000-0000-0000-000000000007', '11000000-0000-0000-0000-000000000023', 3.000, 'cups', 90.000, 'g', 4, now(), now()),
    -- Beef Stir Fry
    ('13000000-0000-0000-0000-000000000008', '11000000-0000-0000-0000-000000000020', 1.000, 'lb', 454.000, 'g', 0, now(), now()),
    ('13000000-0000-0000-0000-000000000008', '11000000-0000-0000-0000-000000000021', 3.000, 'tbsp', 45.000, 'ml', 1, now(), now()),
    ('13000000-0000-0000-0000-000000000008', '11000000-0000-0000-0000-000000000022', 1.000, 'tbsp', 6.000, 'g', 2, now(), now()),
    ('13000000-0000-0000-0000-000000000008', '11000000-0000-0000-0000-000000000005', 3.000, 'cloves', 3.000, 'count', 3, now(), now()),
    ('13000000-0000-0000-0000-000000000008', '11000000-0000-0000-0000-000000000024', 2.000, 'whole', 2.000, 'count', 4, now(), now()),
    ('13000000-0000-0000-0000-000000000008', '11000000-0000-0000-0000-000000000025', 2.000, 'cups', 182.000, 'g', 5, now(), now()),
    -- Spinach & Mushroom Pasta
    ('13000000-0000-0000-0000-000000000009', '11000000-0000-0000-0000-000000000007', 1.000, 'lb', 454.000, 'g', 0, now(), now()),
    ('13000000-0000-0000-0000-000000000009', '11000000-0000-0000-0000-000000000023', 4.000, 'cups', 120.000, 'g', 1, now(), now()),
    ('13000000-0000-0000-0000-000000000009', '11000000-0000-0000-0000-000000000015', 8.000, 'oz', 227.000, 'g', 2, now(), now()),
    ('13000000-0000-0000-0000-000000000009', '11000000-0000-0000-0000-000000000005', 4.000, 'cloves', 4.000, 'count', 3, now(), now()),
    ('13000000-0000-0000-0000-000000000009', '11000000-0000-0000-0000-000000000004', 3.000, 'tbsp', 45.000, 'ml', 4, now(), now()),
    ('13000000-0000-0000-0000-000000000009', '11000000-0000-0000-0000-000000000006', 0.500, 'cup', 50.000, 'g', 5, now(), now()),
    -- Sheet Pan Roasted Vegetables
    ('13000000-0000-0000-0000-000000000010', '11000000-0000-0000-0000-000000000024', 3.000, 'whole', 3.000, 'count', 0, now(), now()),
    ('13000000-0000-0000-0000-000000000010', '11000000-0000-0000-0000-000000000025', 3.000, 'cups', 273.000, 'g', 1, now(), now()),
    ('13000000-0000-0000-0000-000000000010', '11000000-0000-0000-0000-000000000015', 8.000, 'oz', 227.000, 'g', 2, now(), now()),
    ('13000000-0000-0000-0000-000000000010', '11000000-0000-0000-0000-000000000004', 3.000, 'tbsp', 45.000, 'ml', 3, now(), now()),
    ('13000000-0000-0000-0000-000000000010', '11000000-0000-0000-0000-000000000005', 4.000, 'cloves', 4.000, 'count', 4, now(), now()),
    ('13000000-0000-0000-0000-000000000010', '11000000-0000-0000-0000-000000000034', 1.000, 'tsp', 6.000, 'g', 5, now(), now()),
    -- Chocolate Chip Cookies
    ('13000000-0000-0000-0000-000000000011', '11000000-0000-0000-0000-000000000026', 2.250, 'cups', 270.000, 'g', 0, now(), now()),
    ('13000000-0000-0000-0000-000000000011', '11000000-0000-0000-0000-000000000017', 1.000, 'cup', 227.000, 'g', 1, now(), now()),
    ('13000000-0000-0000-0000-000000000011', '11000000-0000-0000-0000-000000000027', 0.750, 'cup', 150.000, 'g', 2, now(), now()),
    ('13000000-0000-0000-0000-000000000011', '11000000-0000-0000-0000-000000000008', 2.000, 'large', 2.000, 'count', 3, now(), now()),
    ('13000000-0000-0000-0000-000000000011', '11000000-0000-0000-0000-000000000028', 2.000, 'cups', 340.000, 'g', 4, now(), now()),
    ('13000000-0000-0000-0000-000000000011', '11000000-0000-0000-0000-000000000029', 1.000, 'tsp', 5.000, 'ml', 5, now(), now()),
    ('13000000-0000-0000-0000-000000000011', '11000000-0000-0000-0000-000000000030', 1.000, 'tsp', 5.000, 'g', 6, now(), now()),
    -- Vanilla Buttercream Cake
    ('13000000-0000-0000-0000-000000000012', '11000000-0000-0000-0000-000000000026', 3.000, 'cups', 360.000, 'g', 0, now(), now()),
    ('13000000-0000-0000-0000-000000000012', '11000000-0000-0000-0000-000000000027', 1.500, 'cups', 300.000, 'g', 1, now(), now()),
    ('13000000-0000-0000-0000-000000000012', '11000000-0000-0000-0000-000000000017', 1.000, 'cup', 227.000, 'g', 2, now(), now()),
    ('13000000-0000-0000-0000-000000000012', '11000000-0000-0000-0000-000000000008', 4.000, 'large', 4.000, 'count', 3, now(), now()),
    ('13000000-0000-0000-0000-000000000012', '11000000-0000-0000-0000-000000000029', 2.000, 'tsp', 10.000, 'ml', 4, now(), now()),
    ('13000000-0000-0000-0000-000000000012', '11000000-0000-0000-0000-000000000033', 1.000, 'cup', 240.000, 'ml', 5, now(), now()),
    ('13000000-0000-0000-0000-000000000012', '11000000-0000-0000-0000-000000000030', 1.500, 'tsp', 7.500, 'g', 6, now(), now()),
    -- Lemon Bars
    ('13000000-0000-0000-0000-000000000013', '11000000-0000-0000-0000-000000000026', 2.000, 'cups', 240.000, 'g', 0, now(), now()),
    ('13000000-0000-0000-0000-000000000013', '11000000-0000-0000-0000-000000000017', 1.000, 'cup', 227.000, 'g', 1, now(), now()),
    ('13000000-0000-0000-0000-000000000013', '11000000-0000-0000-0000-000000000027', 1.500, 'cups', 300.000, 'g', 2, now(), now()),
    ('13000000-0000-0000-0000-000000000013', '11000000-0000-0000-0000-000000000008', 4.000, 'large', 4.000, 'count', 3, now(), now()),
    ('13000000-0000-0000-0000-000000000013', '11000000-0000-0000-0000-000000000018', 4.000, 'whole', 4.000, 'count', 4, now(), now()),
    ('13000000-0000-0000-0000-000000000013', '11000000-0000-0000-0000-000000000032', 0.500, 'cup', 60.000, 'g', 5, now(), now()),
    -- Double Chocolate Brownies
    ('13000000-0000-0000-0000-000000000014', '11000000-0000-0000-0000-000000000026', 1.000, 'cup', 120.000, 'g', 0, now(), now()),
    ('13000000-0000-0000-0000-000000000014', '11000000-0000-0000-0000-000000000017', 0.500, 'cup', 113.000, 'g', 1, now(), now()),
    ('13000000-0000-0000-0000-000000000014', '11000000-0000-0000-0000-000000000027', 1.000, 'cup', 200.000, 'g', 2, now(), now()),
    ('13000000-0000-0000-0000-000000000014', '11000000-0000-0000-0000-000000000008', 2.000, 'large', 2.000, 'count', 3, now(), now()),
    ('13000000-0000-0000-0000-000000000014', '11000000-0000-0000-0000-000000000031', 0.500, 'cup', 43.000, 'g', 4, now(), now()),
    ('13000000-0000-0000-0000-000000000014', '11000000-0000-0000-0000-000000000028', 1.000, 'cup', 170.000, 'g', 5, now(), now()),
    ('13000000-0000-0000-0000-000000000014', '11000000-0000-0000-0000-000000000029', 1.000, 'tsp', 5.000, 'ml', 6, now(), now()),
    -- Sugar Cookie Cutouts
    ('13000000-0000-0000-0000-000000000015', '11000000-0000-0000-0000-000000000026', 3.000, 'cups', 360.000, 'g', 0, now(), now()),
    ('13000000-0000-0000-0000-000000000015', '11000000-0000-0000-0000-000000000017', 1.000, 'cup', 227.000, 'g', 1, now(), now()),
    ('13000000-0000-0000-0000-000000000015', '11000000-0000-0000-0000-000000000027', 1.000, 'cup', 200.000, 'g', 2, now(), now()),
    ('13000000-0000-0000-0000-000000000015', '11000000-0000-0000-0000-000000000008', 1.000, 'large', 1.000, 'count', 3, now(), now()),
    ('13000000-0000-0000-0000-000000000015', '11000000-0000-0000-0000-000000000029', 2.000, 'tsp', 10.000, 'ml', 4, now(), now()),
    ('13000000-0000-0000-0000-000000000015', '11000000-0000-0000-0000-000000000030', 0.500, 'tsp', 2.500, 'g', 5, now(), now()),
    ('13000000-0000-0000-0000-000000000015', '11000000-0000-0000-0000-000000000032', 1.000, 'cup', 120.000, 'g', 6, now(), now())
ON CONFLICT DO NOTHING;

-- ============================================================
-- 10. Pantry Ingredients (Home Kitchen)
-- ============================================================

INSERT INTO pantry_ingredients (pantry_id, ingredient_id, quantity_display, unit_display, quantity_normalized, unit_normalized, expires_at, created_at, updated_at)
VALUES
    -- Staples (no expiry or far out)
    ('c0000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000004', 500.000, 'ml', 500.000, 'ml', NULL, now() - interval '10 days', now()),
    ('c0000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000034', 500.000, 'g', 500.000, 'g', NULL, now() - interval '10 days', now()),
    ('c0000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000010', 100.000, 'g', 100.000, 'g', NULL, now() - interval '10 days', now()),
    ('c0000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000026', 2000.000, 'g', 2000.000, 'g', now() + interval '90 days', now() - interval '10 days', now()),
    ('c0000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000027', 1000.000, 'g', 1000.000, 'g', now() + interval '90 days', now() - interval '10 days', now()),
    ('c0000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000007', 500.000, 'g', 500.000, 'g', now() + interval '180 days', now() - interval '10 days', now()),
    ('c0000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000021', 300.000, 'ml', 300.000, 'ml', now() + interval '365 days', now() - interval '10 days', now()),
    ('c0000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000029', 50.000, 'ml', 50.000, 'ml', now() + interval '180 days', now() - interval '10 days', now()),
    ('c0000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000030', 200.000, 'g', 200.000, 'g', now() + interval '365 days', now() - interval '10 days', now()),
    -- Perishables (some near expiry)
    ('c0000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000017', 227.000, 'g', 227.000, 'g', now() + interval '14 days', now() - interval '5 days', now()),
    ('c0000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000008', 12.000, 'count', 12.000, 'count', now() + interval '10 days', now() - interval '3 days', now()),
    ('c0000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000006', 150.000, 'g', 150.000, 'g', now() + interval '30 days', now() - interval '7 days', now()),
    ('c0000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000011', 450.000, 'g', 450.000, 'g', now() + interval '2 days', now() - interval '3 days', now()),
    ('c0000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000033', 240.000, 'ml', 240.000, 'ml', now() + interval '5 days', now() - interval '4 days', now()),
    ('c0000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000023', 150.000, 'g', 150.000, 'g', now() + interval '3 days', now() - interval '2 days', now())
ON CONFLICT DO NOTHING;

-- ============================================================
-- 11. Shopping List Items
-- ============================================================

-- Weekly Groceries (~8 items — ingredients for upcoming meals)
INSERT INTO shopping_list_items (id, shopping_list_id, name, quantity, unit, ingredient_id, category, priority, added_by_user_id, created_at, updated_at)
VALUES
    ('12000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001', 'Arborio Rice', 1.00, 'bag', '11000000-0000-0000-0000-000000000013', 'grains', 2, 'a0000000-0000-0000-0000-000000000001', now() - interval '2 days', now()),
    ('12000000-0000-0000-0000-000000000002', 'd0000000-0000-0000-0000-000000000001', 'Cremini Mushrooms', 12.00, 'oz', '11000000-0000-0000-0000-000000000015', 'produce', 2, 'a0000000-0000-0000-0000-000000000001', now() - interval '2 days', now()),
    ('12000000-0000-0000-0000-000000000003', 'd0000000-0000-0000-0000-000000000001', 'White Wine', 1.00, 'bottle', '11000000-0000-0000-0000-000000000014', 'beverages', 3, 'a0000000-0000-0000-0000-000000000001', now() - interval '2 days', now()),
    ('12000000-0000-0000-0000-000000000004', 'd0000000-0000-0000-0000-000000000001', 'Fresh Basil', 1.00, 'bunch', '11000000-0000-0000-0000-000000000003', 'produce', 2, 'a0000000-0000-0000-0000-000000000001', now() - interval '2 days', now()),
    ('12000000-0000-0000-0000-000000000005', 'd0000000-0000-0000-0000-000000000001', 'Pancetta', 6.00, 'oz', '11000000-0000-0000-0000-000000000009', 'meat', 2, 'a0000000-0000-0000-0000-000000000001', now() - interval '2 days', now()),
    ('12000000-0000-0000-0000-000000000006', 'd0000000-0000-0000-0000-000000000001', 'Mozzarella', 16.00, 'oz', '11000000-0000-0000-0000-000000000002', 'dairy', 2, 'a0000000-0000-0000-0000-000000000001', now() - interval '2 days', now()),
    ('12000000-0000-0000-0000-000000000007', 'd0000000-0000-0000-0000-000000000001', 'Tomatoes', 8.00, 'whole', '11000000-0000-0000-0000-000000000001', 'produce', 2, 'a0000000-0000-0000-0000-000000000001', now() - interval '2 days', now()),
    ('12000000-0000-0000-0000-000000000008', 'd0000000-0000-0000-0000-000000000001', 'Lemons', 4.00, 'whole', '11000000-0000-0000-0000-000000000018', 'produce', 3, 'a0000000-0000-0000-0000-000000000001', now() - interval '2 days', now())
ON CONFLICT (id) DO NOTHING;

-- Party Supplies (~6 items)
INSERT INTO shopping_list_items (id, shopping_list_id, name, quantity, unit, ingredient_id, category, priority, added_by_user_id, created_at, updated_at)
VALUES
    ('12000000-0000-0000-0000-000000000009', 'd0000000-0000-0000-0000-000000000002', 'Chocolate Chips', 2.00, 'bags', '11000000-0000-0000-0000-000000000028', 'baking', 2, 'a0000000-0000-0000-0000-000000000001', now() - interval '4 days', now()),
    ('12000000-0000-0000-0000-000000000010', 'd0000000-0000-0000-0000-000000000002', 'Vanilla Extract', 1.00, 'bottle', '11000000-0000-0000-0000-000000000029', 'baking', 2, 'a0000000-0000-0000-0000-000000000001', now() - interval '4 days', now()),
    ('12000000-0000-0000-0000-000000000011', 'd0000000-0000-0000-0000-000000000002', 'Cocoa Powder', 1.00, 'can', '11000000-0000-0000-0000-000000000031', 'baking', 3, 'a0000000-0000-0000-0000-000000000001', now() - interval '4 days', now()),
    ('12000000-0000-0000-0000-000000000012', 'd0000000-0000-0000-0000-000000000002', 'Heavy Cream', 2.00, 'pints', '11000000-0000-0000-0000-000000000033', 'dairy', 2, 'a0000000-0000-0000-0000-000000000001', now() - interval '4 days', now()),
    ('12000000-0000-0000-0000-000000000013', 'd0000000-0000-0000-0000-000000000002', 'Powdered Sugar', 2.00, 'lbs', '11000000-0000-0000-0000-000000000032', 'baking', 3, 'a0000000-0000-0000-0000-000000000001', now() - interval '4 days', now()),
    ('12000000-0000-0000-0000-000000000014', 'd0000000-0000-0000-0000-000000000002', 'Crusty Bread', 2.00, 'loaves', '11000000-0000-0000-0000-000000000016', 'bakery', 3, 'a0000000-0000-0000-0000-000000000001', now() - interval '4 days', now())
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 12. Meal Events — link existing + add new
-- ============================================================

-- Update existing meal events to link recipes
UPDATE meal_events SET recipe_id = '13000000-0000-0000-0000-000000000002' WHERE id = 'e0000000-0000-0000-0000-000000000001';  -- Sunday Pasta Night → Carbonara
UPDATE meal_events SET recipe_id = '13000000-0000-0000-0000-000000000012' WHERE id = 'e0000000-0000-0000-0000-000000000002';  -- Birthday Brunch → Vanilla Cake

-- New meal events
INSERT INTO meal_events (id, title, description, scheduled_at, meal_type, status, recipe_id, owner_id, created_at, updated_at)
VALUES
    ('e0000000-0000-0000-0000-000000000003', 'Taco Tuesday', 'Weekly taco night with the crew', now() + interval '3 days', 'dinner', 'planned', NULL, 'a0000000-0000-0000-0000-000000000001', now() - interval '1 day', now()),
    ('e0000000-0000-0000-0000-000000000004', 'Meal Prep Sunday', 'Batch cook garlic butter chicken for the week', now() + interval '7 days', 'lunch', 'planned', '13000000-0000-0000-0000-000000000006', 'a0000000-0000-0000-0000-000000000001', now(), now()),
    ('e0000000-0000-0000-0000-000000000005', 'Quick Lunch', 'Simple bruschetta for a light lunch', now() + interval '1 day', 'lunch', 'planned', '13000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000002', now(), now())
ON CONFLICT (id) DO NOTHING;

-- Participants for new events
INSERT INTO meal_event_participants (meal_event_id, user_id, status, role, created_at, updated_at)
VALUES
    -- Taco Tuesday: Alice hosts, Bob accepted, Charlie invited
    ('e0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'accepted', 'host', now() - interval '1 day', now()),
    ('e0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000002', 'accepted', 'guest', now() - interval '1 day', now()),
    ('e0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000003', 'invited', 'guest', now() - interval '1 day', now()),
    -- Meal Prep Sunday: Alice hosts, Diana maybe
    ('e0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'accepted', 'host', now(), now()),
    ('e0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000004', 'maybe', 'guest', now(), now()),
    -- Quick Lunch: Bob hosts, Alice accepted
    ('e0000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000002', 'accepted', 'host', now(), now()),
    ('e0000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'accepted', 'guest', now(), now())
ON CONFLICT DO NOTHING;

COMMIT;

-- ============================================================
-- Summary
-- ============================================================

SELECT 'Users' AS entity, count(*) AS count FROM users WHERE auth0_id LIKE 'test-%'
UNION ALL
SELECT 'Recipe Books', count(*) FROM recipe_books WHERE id::text LIKE 'b0000000%'
UNION ALL
SELECT 'Recipes', count(*) FROM recipes WHERE id::text LIKE '13000000%'
UNION ALL
SELECT 'Recipe Steps', count(*) FROM recipe_steps WHERE id::text LIKE '14000000%'
UNION ALL
SELECT 'Ingredients', count(*) FROM ingredients WHERE id::text LIKE '11000000%'
UNION ALL
SELECT 'Pantries', count(*) FROM pantries WHERE id::text LIKE 'c0000000%'
UNION ALL
SELECT 'Pantry Items', count(*) FROM pantry_ingredients WHERE pantry_id::text LIKE 'c0000000%'
UNION ALL
SELECT 'Shopping Lists', count(*) FROM shopping_lists WHERE id::text LIKE 'd0000000%'
UNION ALL
SELECT 'Shopping Items', count(*) FROM shopping_list_items WHERE id::text LIKE '12000000%'
UNION ALL
SELECT 'Meal Events', count(*) FROM meal_events WHERE id::text LIKE 'e0000000%'
UNION ALL
SELECT 'Invitations', count(*) FROM invitations WHERE id::text LIKE 'f0000000%'
UNION ALL
SELECT 'Invite Links', count(*) FROM invite_links WHERE id::text LIKE '10000000%'
UNION ALL
SELECT 'Activities', count(*) FROM activities;
