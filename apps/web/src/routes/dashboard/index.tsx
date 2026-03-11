import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@hermes-on-call/ui/components/card";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
	Activity,
	ArrowRight,
	Bot,
	GitBranch,
	Github,
	Link2,
	Webhook,
} from "lucide-react";
import { orpc } from "@/utils/orpc";

export const Route = createFileRoute("/dashboard/")({
	component: DashboardOverview,
});

function DashboardOverview() {
	const { data: projectsData, isLoading: isProjectsLoading } = useQuery({
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

	const projects = projectsData?.projects ?? [];
	const activeProjects = projects.filter(
		(p: { isActive: boolean }) => p.isActive,
	);

	return (
		<div className="py-8">
			<div className="mb-8 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
				<div>
					<h1 className="font-bold text-3xl tracking-tight">Overview</h1>
					<p className="text-muted-foreground">
						Welcome to your APIaaS command center.
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
				{/* Projects Metric */}
				<Card>
					<CardHeader className="flex flex-row items-center justify-between pb-2">
						<CardTitle className="font-medium text-sm">
							Monitored Projects
						</CardTitle>
						<GitBranch className="h-4 w-4 text-muted-foreground" />
					</CardHeader>
					<CardContent>
						<div className="font-bold text-2xl">
							{isProjectsLoading ? "-" : activeProjects.length}
						</div>
						<p className="text-muted-foreground text-xs">
							out of {projects.length} connected repos
						</p>
					</CardContent>
				</Card>

				{/* GH CLI Metric */}
				<Card>
					<CardHeader className="flex flex-row items-center justify-between pb-2">
						<CardTitle className="font-medium text-sm">
							GitHub Identity
						</CardTitle>
						<Github className="h-4 w-4 text-muted-foreground" />
					</CardHeader>
					<CardContent>
						<div className="font-bold text-2xl">
							{ghCli?.ghUser ? "Connected" : "Offline"}
						</div>
						<p className="truncate text-muted-foreground text-xs">
							{ghCli?.ghUser ? `@${ghCli.ghUser}` : "Requires gh auth login"}
						</p>
					</CardContent>
				</Card>

				{/* Webhook Status */}
				<Card>
					<CardHeader className="flex flex-row items-center justify-between pb-2">
						<CardTitle className="font-medium text-sm">
							Webhook Receiver
						</CardTitle>
						<Activity className="h-4 w-4 text-muted-foreground" />
					</CardHeader>
					<CardContent>
						<div className="flex items-center gap-2 font-bold text-2xl">
							<span className="relative flex h-3 w-3">
								{webhookStatus?.running ? (
									<>
										<span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
										<span className="relative inline-flex h-3 w-3 rounded-full bg-green-500" />
									</>
								) : (
									<span className="relative inline-flex h-3 w-3 rounded-full bg-red-500" />
								)}
							</span>
							{webhookStatus?.running ? "Active" : "Down"}
						</div>
						<p className="text-muted-foreground text-xs">
							{webhookStatus?.running
								? `Listening on Port ${webhookStatus.port}`
								: "Service unavailable"}
						</p>
					</CardContent>
				</Card>

				{/* Tunnel Status */}
				<Card>
					<CardHeader className="flex flex-row items-center justify-between pb-2">
						<CardTitle className="font-medium text-sm">Public Tunnel</CardTitle>
						<Webhook className="h-4 w-4 text-muted-foreground" />
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

			<div className="mt-8 grid gap-4 lg:grid-cols-2">
				<Card className="col-span-1">
					<CardHeader>
						<CardTitle className="flex items-center gap-2">
							<Bot className="h-5 w-5 text-primary" />
							Agent Status
						</CardTitle>
						<CardDescription>
							Autonomous on-call agent health and connectivity.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="flex items-center justify-between space-x-4 rounded-md border p-4">
							<div className="flex items-center space-x-4">
								<div className="rounded-full bg-green-500/10 p-2">
									<Link2 className="h-6 w-6 text-green-500" />
								</div>
								<div>
									<p className="font-medium text-sm leading-none">
										API Gateway
									</p>
									<p className="text-muted-foreground text-sm">
										Routing events to agentic mesh
									</p>
								</div>
							</div>
							<div className="font-medium text-green-500 text-sm">
								Operational
							</div>
						</div>
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
