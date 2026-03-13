import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@agiaas/ui/components/card";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
	Activity,
	ArrowRight,
	Bot,
	GitBranch,
	Github,
	Webhook,
} from "lucide-react";
import { orpc } from "@/utils/orpc";

export const Route = createFileRoute("/dashboard/")({
	component: DashboardOverview,
});

function DashboardOverview() {
	const { data: projectsData } = useQuery({
		...orpc.github.listProjects.queryOptions(),
		refetchInterval: 5000,
	});

	const { data: ghCli } = useQuery({
		...orpc.github.getGhCliUser.queryOptions(),
		staleTime: 60_000,
	});

	const { data: webhookStatus } = useQuery({
		...orpc.github.getWebhookStatus.queryOptions(),
		refetchInterval: 5000,
	});

	const { data: tunnelData } = useQuery({
		...orpc.github.getTunnelUrl.queryOptions(),
		refetchInterval: 5000,
	});

	const { data: metricsData } = useQuery({
		...orpc.metrics.getDashboardStats.queryOptions(),
		refetchInterval: 10000,
	});

	const projects = projectsData?.projects ?? [];
	const activeProjects = projects.filter(
		(p: { isActive: boolean }) => p.isActive,
	);

	const stats = metricsData?.stats ?? {
		totalRuns: 0,
		totalTokens: 0,
		avgDuration: 0,
	};
	const recentLogs = metricsData?.recentLogs ?? [];

	return (
		<div className="py-8">
			<div className="mb-8 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
				<div>
					<h1 className="font-bold text-3xl tracking-tight">Overview</h1>
					<p className="text-muted-foreground">
						Welcome to your AGIaaS command center.
					</p>
				</div>
				<Link
					to="/dashboard/settings"
					className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground text-sm shadow transition-colors hover:bg-primary/90"
				>
					Configure Services
					<ArrowRight className="h-4 w-4" />
				</Link>
			</div>

			<div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
				{/* Agent Runs Metric */}
				<Card>
					<CardHeader className="flex flex-row items-center justify-between pb-2">
						<CardTitle className="font-medium text-sm">
							Total Agent Runs
						</CardTitle>
						<Activity className="h-4 w-4 text-primary" />
					</CardHeader>
					<CardContent>
						<div className="font-bold text-2xl">{stats.totalRuns}</div>
						<p className="text-muted-foreground text-xs">
							Autonomous task executions
						</p>
					</CardContent>
				</Card>

				{/* Tokens Metric */}
				<Card>
					<CardHeader className="flex flex-row items-center justify-between pb-2">
						<CardTitle className="font-medium text-sm">
							Tokens Processed
						</CardTitle>
						<Bot className="h-4 w-4 text-muted-foreground" />
					</CardHeader>
					<CardContent>
						<div className="font-bold text-2xl">
							{(stats.totalTokens / 1000).toFixed(1)}k
						</div>
						<p className="text-muted-foreground text-xs">
							Total LLM token usage
						</p>
					</CardContent>
				</Card>

				{/* Success Rate (Mock for now or can be derived) */}
				<Card>
					<CardHeader className="flex flex-row items-center justify-between pb-2">
						<CardTitle className="font-medium text-sm">Success Rate</CardTitle>
						<Activity className="h-4 w-4 text-green-500" />
					</CardHeader>
					<CardContent>
						<div className="font-bold text-2xl">98.2%</div>
						<p className="text-muted-foreground text-xs">
							Tasks completed without error
						</p>
					</CardContent>
				</Card>

				{/* Tunnel Status */}
				<Card>
					<CardHeader className="flex flex-row items-center justify-between pb-2">
						<CardTitle className="font-medium text-sm">Public Tunnel</CardTitle>
						<Webhook className="h-4 w-4 text-amber-500" />
					</CardHeader>
					<CardContent>
						<div className="font-bold text-2xl">
							{tunnelData?.url ? "Online" : "Starting"}
						</div>
						<p className="truncate text-muted-foreground text-xs">
							{tunnelData?.url ? tunnelData.url : "Waiting for tunnel..."}
						</p>
					</CardContent>
				</Card>
			</div>

			<div className="mt-8 grid gap-4 lg:grid-cols-7">
				<Card className="lg:col-span-4">
					<CardHeader>
						<CardTitle>Recent Activity</CardTitle>
						<CardDescription>
							History of recent agent actions and task executions.
						</CardDescription>
					</CardHeader>
					<CardContent>
						<div className="space-y-8">
							{recentLogs.length === 0 ? (
								<p className="py-8 text-center text-muted-foreground text-sm">
									No activity recorded yet.
								</p>
							) : (
								recentLogs.map((log) => (
									<div key={log.id} className="flex items-center">
										<div className="space-y-1">
											<p className="font-medium text-sm leading-none">
												{log.action}
											</p>
											<p className="text-muted-foreground text-xs">
												{log.agentName} •{" "}
												{new Date(log.createdAt).toLocaleString()}
											</p>
										</div>
										<div className="ml-auto font-medium text-xs">
											{log.tokensUsed} tokens
										</div>
									</div>
								))
							)}
						</div>
					</CardContent>
				</Card>

				<Card className="lg:col-span-3">
					<CardHeader>
						<CardTitle className="flex items-center gap-2">
							<Github className="h-5 w-5 text-primary" />
							Connected Systems
						</CardTitle>
						<CardDescription>
							Core services and integration health.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="flex items-center justify-between rounded-md border p-4">
							<div className="flex items-center gap-4">
								<Github className="h-5 w-5" />
								<div>
									<p className="font-medium text-sm">gh CLI</p>
									<p className="text-muted-foreground text-xs">
										{ghCli?.ghUser ? `@${ghCli.ghUser}` : "Not logged in"}
									</p>
								</div>
							</div>
							<div
								className={`h-2 w-2 rounded-full ${ghCli?.ghUser ? "bg-green-500" : "bg-red-500"}`}
							/>
						</div>

						<div className="flex items-center justify-between rounded-md border p-4">
							<div className="flex items-center gap-4">
								<Webhook className="h-5 w-5" />
								<div>
									<p className="font-medium text-sm">Webhook Receiver</p>
									<p className="text-muted-foreground text-xs">
										{webhookStatus?.running ? "Listening" : "Offline"}
									</p>
								</div>
							</div>
							<div
								className={`h-2 w-2 rounded-full ${webhookStatus?.running ? "bg-green-500" : "bg-red-500"}`}
							/>
						</div>

						<div className="flex items-center justify-between rounded-md border p-4">
							<div className="flex items-center gap-4">
								<GitBranch className="h-5 w-5" />
								<div>
									<p className="font-medium text-sm">Active Projects</p>
									<p className="text-muted-foreground text-xs">
										{activeProjects.length} repos active
									</p>
								</div>
							</div>
							<div className="font-bold text-xs">{activeProjects.length}</div>
						</div>
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
