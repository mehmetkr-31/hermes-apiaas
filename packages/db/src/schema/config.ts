import { sqliteTable, text } from "drizzle-orm/sqlite-core";

export const globalConfig = sqliteTable("global_config", {
	key: text("key").primaryKey(),
	value: text("value").notNull(),
});
