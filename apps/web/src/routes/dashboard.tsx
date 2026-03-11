import { useQuery } from "@tanstack/react-query";
import {
	createFileRoute,
	Link,
	Outlet,
	redirect,
} from "@tanstack/react-router";

import { getUser } from "@/functions/get-user";
import { orpc } from "@/utils/orpc";

export const Route = createFileRoute("/dashboard")({
	component: RouteComponent,
	beforeLoad: async () => {
		const session = await getUser();
		return { session };
	},
	loader: async ({ context }) => {
		if (!context.session) {
			throw redirect({
				to: "/login",
			});
		}
	},
});

function RouteComponent() {
	const { session } = Route.useRouteContext();

	const privateData = useQuery(orpc.privateData.queryOptions());

	return (
		<div className="flex flex-col gap-4 p-4">
			<div className="flex items-center justify-between border-b pb-4">
				<div>
					<h1 className="font-bold text-2xl">Dashboard</h1>
					<p className="text-muted-foreground">Welcome {session?.user.name}</p>
				</div>
				<Link
					to="/dashboard/on-call"
					className="rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary/90"
				>
					View On-Call Agent
				</Link>
			</div>
			<div>
				<p>API: {privateData.data?.message}</p>
			</div>
			<Outlet />
		</div>
	);
}
