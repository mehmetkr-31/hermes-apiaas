import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";
import { sql } from "drizzle-orm";

export const agentLogs = sqliteTable("agent_logs", {
	id: text("id").primaryKey(),
	projectId: text("project_id").notNull(),
	agentName: text("agent_name").notNull(),
	action: text("action").notNull(),
	prompt: text("prompt"),
	response: text("response"),
	tokensUsed: integer("tokens_used").default(0),
	durationMs: integer("duration_ms").default(0),
	createdAt: integer("created_at", { mode: "timestamp" }).default(sql`(strftime('%s', 'now'))`).notNull(),
});
