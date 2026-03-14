import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createEnv } from "@t3-oss/env-core";
import dotenv from "dotenv";
import { z } from "zod";

const __dirname = dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: resolve(__dirname, "../../../.env") });

if (process.env.DATABASE_URL?.startsWith("file:./")) {
	const dbFile = process.env.DATABASE_URL.replace("file:./", "");
	process.env.DATABASE_URL = `file:${resolve(__dirname, "../../../", dbFile)}`;
}

export const env = createEnv({
	server: {
		DATABASE_URL: z.string().min(1),
		BETTER_AUTH_SECRET: z.string().min(32),
		BETTER_AUTH_URL: z.url(),
		CORS_ORIGIN: z.url(),
		NODE_ENV: z
			.enum(["development", "production", "test"])
			.default("development"),
		DB_ENCRYPTION_KEY: z.string().min(32),
	},
	runtimeEnv: process.env,
	emptyStringAsUndefined: true,
});
