import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createEnv } from "@t3-oss/env-core";
import dotenv from "dotenv";
import { z } from "zod";

const __dirname = dirname(fileURLToPath(import.meta.url));

function loadEnv() {
	const paths = [
		resolve(__dirname, "../../../.env"),
		resolve(process.cwd(), ".env"),
		resolve(process.cwd(), "../../.env"),
	];

	for (const envPath of paths) {
		if (existsSync(envPath)) {
			const result = dotenv.config({ path: envPath, override: true });
			if (result.parsed) {
				for (const key in result.parsed) {
					process.env[key] = result.parsed[key];
				}
			}
			return envPath;
		}
	}
	return null;
}

const loadedPath = loadEnv();

if (process.env.DATABASE_URL?.startsWith("file:./")) {
	const dbFile = process.env.DATABASE_URL.replace("file:./", "");
	const rootDir = loadedPath ? dirname(loadedPath) : process.cwd();
	process.env.DATABASE_URL = `file:${resolve(rootDir, dbFile)}`;
}

export const env = createEnv({
	server: {
		DATABASE_URL: z.string().min(1),
		BETTER_AUTH_SECRET: z.string().min(32),
		BETTER_AUTH_URL: z.string().min(1),
		CORS_ORIGIN: z.string().min(1),
		NODE_ENV: z
			.enum(["development", "production", "test"])
			.default("development"),
		DB_ENCRYPTION_KEY: z.string().min(32),
	},
	runtimeEnv: process.env,
	emptyStringAsUndefined: true,
	onValidationError: (error) => {
		console.error(
			"❌ Invalid environment variables:",
			JSON.stringify(error, null, 2),
		);
		throw new Error("Invalid environment variables");
	},
});
