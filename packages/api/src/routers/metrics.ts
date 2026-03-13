import { db, schema } from "@agiaas/db";
import { desc, sql } from "drizzle-orm";
import { publicProcedure } from "../index";

const { agentLogs } = schema;

export const metricsRouter = {
	getDashboardStats: publicProcedure.handler(async () => {
		// Calculate total runs, total tokens, and average duration
		const stats = await db
			.select({
				totalRuns: sql<number>`count(*)`,
				totalTokens: sql<number>`coalesce(sum(${agentLogs.tokensUsed}), 0)`,
				avgDuration: sql<number>`coalesce(avg(${agentLogs.durationMs}), 0)`,
			})
			.from(agentLogs);

		// Get recent agents logs
		const recentLogs = await db.query.agentLogs.findMany({
			orderBy: [desc(agentLogs.createdAt)],
			limit: 10,
		});

		return {
			stats: stats[0],
			recentLogs,
		};
	}),
};
