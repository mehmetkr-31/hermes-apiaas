#!/usr/bin/env node
/**
 * Hermes Webhook Server Launcher
 *
 * Starts:
 *   1. python3 webhook_receiver.py  (port 8090)
 *   2. cloudflared tunnel --url http://localhost:8090
 *
 * When cloudflared emits the tunnel URL it writes it to:
 *   /tmp/hermes_tunnel_url.txt
 *
 * The API reads that file via the getTunnelUrl endpoint and
 * the dashboard shows the full webhook URL to copy into GitHub.
 */

import { execSync, spawn } from "node:child_process";
import crypto from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import "dotenv/config";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Load .env from project root
try {
	const rootEnvPath = resolve(__dirname, "../../.env");
	const envConfig = readFileSync(rootEnvPath, "utf-8");
	for (const line of envConfig.split("\n")) {
		const [key, ...valueParts] = line.split("=");
		if (key && valueParts.length > 0) {
			process.env[key.trim()] = valueParts.join("=").trim();
		}
	}
} catch (err) {
	console.warn(`[webhook-server] ⚠️ Could not load root .env: ${err.message}`);
}

function decrypt(hash) {
	const secret = process.env.DB_ENCRYPTION_KEY;
	if (!secret) return hash;

	// Ensure the key is 32 bytes for AES-256
	let key = Buffer.from(secret, "utf8");
	if (key.length !== 32) {
		key = crypto.createHash("sha256").update(secret).digest();
	}

	const buffer = Buffer.from(hash, "base64");
	const iv = buffer.subarray(0, 12);
	const tag = buffer.subarray(12, 28);
	const encrypted = buffer.subarray(28);

	const decipher = crypto.createDecipheriv("aes-256-gcm", key, iv);
	decipher.setAuthTag(tag);

	const decrypted = Buffer.concat([
		decipher.update(encrypted),
		decipher.final(),
	]);
	return decrypted.toString("utf8");
}
const RECEIVER_SCRIPT = resolve(
	__dirname,
	"../agent/scripts/on_call/webhook_receiver.py",
);
const TUNNEL_URL_FILE = "/tmp/hermes_tunnel_url.txt";
const DB_FILE = resolve(__dirname, "../../local.db");

/**
 * Automatically updates GitHub webhooks with the new tunnel URL.
 * Preserves the secret key from the database.
 */
async function updateGithubWebhooks(newUrl) {
	console.log(
		`[webhook-server] 🔄 Synchronizing GitHub webhooks with: ${newUrl}`,
	);
	const fullWebhookUrl = `${newUrl}/github/webhook`;

	try {
		// 1. Get repo and secret from DB
		const dbOutput = execSync(
			`sqlite3 "${DB_FILE}" "SELECT repo_full_name, webhook_secret FROM hermes_project WHERE is_active = 1;"`,
			{ encoding: "utf-8" },
		).trim();

		if (!dbOutput) {
			console.log(
				"[webhook-server] ⚠️ No active repositories found in database. Skipping sync.",
			);
			return;
		}

		const projects = dbOutput.split("\n").map((line) => {
			const [repo, secret] = line.split("|");
			return { repo, secret };
		});

		for (const { repo, secret } of projects) {
			console.log(`[webhook-server] 📡 Updating ${repo}...`);

			// 2. Find hook ID
			const hooksJson = execSync(`gh api repos/${repo}/hooks`, {
				encoding: "utf-8",
			});
			const hooks = JSON.parse(hooksJson);
			const targetHook = hooks.find(
				(h) => h.config.url.includes("trycloudflare.com") || hooks.length === 1,
			);

			if (!targetHook) {
				console.log(
					`[webhook-server] ❌ Could not find a suitable webhook to update for ${repo}.`,
				);
				continue;
			}

			// 3. Update hook
			const rawSecret = decrypt(secret);
			const patchData = JSON.stringify({
				config: {
					url: fullWebhookUrl,
					content_type: "json",
					secret: rawSecret,
				},
			});

			execSync(
				`echo '${patchData}' | gh api -X PATCH repos/${repo}/hooks/${targetHook.id} --input -`,
			);
			console.log(
				`[webhook-server] ✅ Successfully updated webhook for ${repo}.`,
			);
		}
	} catch (err) {
		console.error(
			`[webhook-server] ❌ Failed to update GitHub webhooks: ${err.message}`,
		);
	}
}

// ── 1. Start webhook_receiver.py ──────────────────────────────────────────────
const VENV_PYTHON = resolve(__dirname, "../../.venv/bin/python");
const PROJECT_ROOT = resolve(__dirname, "../../");

const receiver = spawn(VENV_PYTHON, [RECEIVER_SCRIPT], {
	stdio: "inherit",
	env: {
		...process.env,
		HERMES_PROJECT_ROOT: PROJECT_ROOT,
	},
});

receiver.on("exit", (code) => {
	console.log(`[webhook-server] receiver exited with code ${code}`);
});

console.log("[webhook-server] 🚀 webhook_receiver.py started on :8090");

// ── 2. Start cloudflared tunnel ───────────────────────────────────────────────
// Give the Python server 2s to come up before opening the tunnel
await new Promise((r) => setTimeout(r, 2000));

const cf = spawn(
	"cloudflared",
	[
		"tunnel",
		"--protocol",
		"http2",
		"--url",
		"http://localhost:8090",
		"--no-autoupdate",
	],
	{ stdio: ["ignore", "pipe", "pipe"] },
);

function parseTunnelUrl(line) {
	// cloudflared prints: https://xxx.trycloudflare.com
	const m = line.match(/https:\/\/[a-z0-9-]+\.trycloudflare\.com/);
	return m ? m[0] : null;
}

let tunnelUrl = null;

function handleCfOutput(data) {
	const text = data.toString();
	process.stdout.write(`[cloudflared] ${text}`);
	if (!tunnelUrl) {
		const url = parseTunnelUrl(text);
		if (url) {
			tunnelUrl = url;
			writeFileSync(TUNNEL_URL_FILE, url, "utf-8");
			console.log(`\n✅ Tunnel URL: ${url}`);
			console.log(`📋 GitHub Webhook URL: ${url}/github/webhook\n`);
			updateGithubWebhooks(url);
		}
	}
}

cf.stdout.on("data", handleCfOutput);
cf.stderr.on("data", handleCfOutput); // cloudflared logs to stderr

cf.on("exit", (code) => {
	console.log(`[webhook-server] cloudflared exited with code ${code}`);
});

// Cleanup on exit
process.on("SIGINT", () => {
	receiver.kill();
	cf.kill();
	process.exit(0);
});
process.on("SIGTERM", () => {
	receiver.kill();
	cf.kill();
	process.exit(0);
});
