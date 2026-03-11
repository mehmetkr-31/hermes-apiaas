import { db, schema } from "@hermes-on-call/db";

const { hermesProject, globalConfig } = schema;

import { eq } from "drizzle-orm";
import { z } from "zod";
import { publicProcedure } from "../index";

export const githubRouter = {
	listProjects: publicProcedure.handler(async () => {
		const result = await db.query.hermesProject.findMany({
			orderBy: (projects, { desc }) => [desc(projects.createdAt)],
		});
		return { projects: result };
	}),

	addProject: publicProcedure
		.input(
			z.object({
				repoFullName: z.string(),
				webhookSecret: z.string().min(1),
				telegramChatId: z.string(),
			}),
		)
		.handler(async ({ input }) => {
			const { repoFullName, webhookSecret, telegramChatId } = input;
			const id = crypto.randomUUID();

			await db
				.insert(hermesProject)
				.values({
					id,
					repoFullName,
					webhookSecret,
					telegramChatId,
					isActive: true,
				})
				.onConflictDoUpdate({
					target: hermesProject.repoFullName,
					set: {
						webhookSecret,
						telegramChatId,
						isActive: true,
					},
				});
			return { success: true };
		}),

	toggleProject: publicProcedure
		.input(z.object({ id: z.string(), isActive: z.boolean() }))
		.handler(async ({ input }) => {
			await db
				.update(hermesProject)
				.set({ isActive: input.isActive })
				.where(eq(hermesProject.id, input.id));
			return { success: true };
		}),

	deleteProject: publicProcedure
		.input(z.object({ id: z.string() }))
		.handler(async ({ input }) => {
			await db.delete(hermesProject).where(eq(hermesProject.id, input.id));
			return { success: true };
		}),

	saveGlobalTelegramBotConfig: publicProcedure
		.input(z.object({ telegramBotToken: z.string() }))
		.handler(async ({ input }) => {
			await db
				.insert(globalConfig)
				.values({
					key: "TELEGRAM_BOT_TOKEN",
					value: input.telegramBotToken,
				})
				.onConflictDoUpdate({
					target: globalConfig.key,
					set: {
						value: input.telegramBotToken,
					},
				});
			return { success: true };
		}),

	getGlobalTelegramBotConfig: publicProcedure.handler(async () => {
		const result = await db.query.globalConfig.findFirst({
			where: eq(globalConfig.key, "TELEGRAM_BOT_TOKEN"),
		});
		if (result?.value) {
			const t = result.value;
			return { telegramBotToken: `${t.slice(0, 8)}...` };
		}
		return { telegramBotToken: "" };
	}),

	listRepos: publicProcedure.handler(async () => {
		try {
			const { execSync } = await import("node:child_process");
			const raw = execSync(
				"gh repo list --limit 100 --json nameWithOwner,isPrivate,description 2>/dev/null",
				{ encoding: "utf-8" },
			).trim();
			const repos = JSON.parse(raw) as {
				nameWithOwner: string;
				isPrivate: boolean;
				description: string;
			}[];
			return { repos };
		} catch (_error) {
			return { repos: [] };
		}
	}),

	getGhCliUser: publicProcedure.handler(async () => {
		let ghUser = "";
		try {
			const { execSync } = await import("node:child_process");
			ghUser = execSync("gh api user --jq .login 2>/dev/null", {
				encoding: "utf-8",
			}).trim();
		} catch (_error) {
			// gh not configured
		}
		return {
			ghUser,
			isConfigured: !!ghUser,
		};
	}),

	getWebhookStatus: publicProcedure.handler(async () => {
		try {
			const response = await fetch("http://localhost:8090/health", {
				signal: AbortSignal.timeout(2000),
			});
			return { running: response.ok, port: 8090 };
		} catch (_error) {
			return { running: false, port: 8090 };
		}
	}),

	getTunnelUrl: publicProcedure.handler(async () => {
		try {
			const fs = await import("node:fs/promises");
			const url = (
				await fs.readFile("/tmp/hermes_tunnel_url.txt", "utf-8")
			).trim();
			return { url, webhookUrl: `${url}/github/webhook` };
		} catch (_error) {
			return { url: "", webhookUrl: "" };
		}
	}),
};
