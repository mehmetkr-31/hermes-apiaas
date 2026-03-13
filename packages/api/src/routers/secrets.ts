import { db, encrypt, schema } from "@agiaas/db";
import { eq } from "drizzle-orm";
import { z } from "zod";
import { publicProcedure } from "../index";

const { hermesSecrets } = schema;

export const secretsRouter = {
	listSecrets: publicProcedure
		.input(z.object({ projectId: z.string() }))
		.handler(async ({ input }) => {
			const secrets = await db.query.hermesSecrets.findMany({
				where: eq(hermesSecrets.projectId, input.projectId),
				columns: { id: true, keyName: true, createdAt: true },
			});
			return { secrets };
		}),

	setSecret: publicProcedure
		.input(
			z.object({
				projectId: z.string(),
				keyName: z.string(),
				value: z.string(),
			}),
		)
		.handler(async ({ input }) => {
			const id = crypto.randomUUID();
			const encryptedValue = encrypt(input.value);

			await db
				.insert(hermesSecrets)
				.values({
					id,
					projectId: input.projectId,
					keyName: input.keyName,
					encryptedValue,
				})
				.onConflictDoUpdate({
					target: hermesSecrets.id,
					set: { encryptedValue },
				});

			return { success: true };
		}),

	deleteSecret: publicProcedure
		.input(z.object({ id: z.string() }))
		.handler(async ({ input }) => {
			await db.delete(hermesSecrets).where(eq(hermesSecrets.id, input.id));
			return { success: true };
		}),
};
