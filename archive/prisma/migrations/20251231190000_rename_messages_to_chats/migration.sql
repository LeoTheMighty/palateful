-- Rename messages table to chats
ALTER TABLE "messages" RENAME TO "chats";

-- Rename the index
ALTER INDEX "messages_thread_id_idx" RENAME TO "chats_thread_id_idx";

-- Rename the foreign key constraint
ALTER TABLE "chats" RENAME CONSTRAINT "messages_thread_id_fkey" TO "chats_thread_id_fkey";

-- Rename the primary key constraint
ALTER TABLE "chats" RENAME CONSTRAINT "messages_pkey" TO "chats_pkey";
