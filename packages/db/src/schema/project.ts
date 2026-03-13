import { sql } from "drizzle-orm";
import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const hermesProject = sqliteTable("hermes_project", {
	id: text("id").primaryKey(),
	repoFullName: text("repo_full_name").notNull().unique(), // e.g. "aLjTap/webTech"
	webhookSecret: text("webhook_secret").notNull(),
	telegramChatId: text("telegram_chat_id").notNull(),
	isActive: integer("is_active", { mode: "boolean" }).default(true).notNull(),
	llmModel: text("llm_model").default("gpt-4o-mini").notNull(),
	createdAt: integer("created_at", { mode: "timestamp" }).default(sql`(strftime('%s', 'now'))`).notNull(),
});
