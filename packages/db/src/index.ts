import { env } from "@hermes-on-call/env/server";
import { createClient } from "@libsql/client";
import { drizzle } from "drizzle-orm/libsql";

import * as schema from "./schema";

const client = createClient({
	url: env.DATABASE_URL,
});

export const db = drizzle({ client, schema });
export { schema };
