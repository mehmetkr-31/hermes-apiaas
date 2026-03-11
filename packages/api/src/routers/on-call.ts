import { z } from "zod";

import { publicProcedure } from "../index";

export const onCallRouter = {
	triggerIncident: publicProcedure
		.input(z.object({ mockUrl: z.string().optional() }))
		.handler(async ({ input }) => {
			try {
				const response = await fetch("http://localhost:8090/webhook", {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
					},
					body: JSON.stringify(input),
				});

				if (!response.ok) {
					throw new Error("Failed to trigger agent");
				}
				return await response.json();
			} catch (error) {
				console.error("Agent error:", error);
				return { error: "Agent is not running or failed to trigger." };
			}
		}),

	getLogs: publicProcedure.handler(async () => {
		try {
			const response = await fetch("http://localhost:8000/api/logs");
			if (!response.ok) {
				throw new Error("Failed to get logs");
			}
			return await response.json();
		} catch (error) {
			return {
				logs: [],
				error: "Agent is not running or failed to fetch logs.",
			};
		}
	}),
};
