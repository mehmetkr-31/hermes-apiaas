import { sql } from "drizzle-orm";
import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const hermesBots = sqliteTable("hermes_bots", {
	id: text("id").primaryKey(),
	name: text("name").notNull(),
	username: text("username").notNull(),
	token: text("token").notNull(), // Encrypted
	avatarUrl: text("avatar_url"),
	isPrimary: integer("is_primary", { mode: "boolean" }).default(false).notNull(),
	createdAt: integer("created_at", { mode: "timestamp" }).default(sql`(strftime('%s', 'now'))`).notNull(),
});
