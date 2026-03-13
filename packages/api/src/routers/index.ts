import type { RouterClient } from "@orpc/server";

import { protectedProcedure, publicProcedure } from "../index";
import { githubRouter } from "./github";
import { metricsRouter } from "./metrics";
import { onCallRouter } from "./on-call";
import { secretsRouter } from "./secrets";
import { todoRouter } from "./todo";

export const appRouter = {
	healthCheck: publicProcedure.handler(() => {
		return "OK";
	}),
	privateData: protectedProcedure.handler(({ context }) => {
		return {
			message: "This is private",
			user: context.session?.user,
		};
	}),
	todo: todoRouter,
	onCall: onCallRouter,
	github: githubRouter,
	metrics: metricsRouter,
	secrets: secretsRouter,
};
export type AppRouter = typeof appRouter;
export type AppRouterClient = RouterClient<typeof appRouter>;
