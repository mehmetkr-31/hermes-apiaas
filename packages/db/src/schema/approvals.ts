import { sql } from "drizzle-orm";
import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const approvals = sqliteTable("approvals", {
	id: text("id").primaryKey(), // unique ID for the approval request
	status: text("status", {
		enum: ["pending", "approved", "rejected", "rollback"],
	})
		.notNull()
		.default("pending"),
	messageId: text("message_id"), // Telegram message ID
	chatId: text("chat_id"), // Telegram chat ID
	metadata: text("metadata"), // JSON metadata (e.g. repo, issue number, action type)
	createdAt: integer("created_at", { mode: "timestamp" })
		.notNull()
		.default(sql`(strftime('%s', 'now'))`),
});
