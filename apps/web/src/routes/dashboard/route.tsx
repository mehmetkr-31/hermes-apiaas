import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, Outlet } from "@tanstack/react-router";
import { Bot, Github, LayoutDashboard, Settings2 } from "lucide-react";
import { Logo } from "@/components/Logo";
import { orpc } from "@/utils/orpc";

export const Route = createFileRoute("/dashboard")({
	component: RouteComponent,
});

function RouteComponent() {
	const { data: projectsData } = useQuery({
		...orpc.github.listProjects.queryOptions(),
		refetchInterval: 5000,
	});
	const { data: ghCli } = useQuery({
		...orpc.github.getGhCliUser.queryOptions(),
		refetchInterval: 30000,
	});

	const activeProjects =
		projectsData?.projects?.filter((p) => p.isActive) || [];
	const isConfigured = ghCli?.isConfigured && activeProjects.length > 0;

	const navItems = [
		{
			to: "/dashboard",
			label: "Overview",
			icon: <LayoutDashboard className="h-4 w-4" />,
		},
		{
			to: "/dashboard/playground",
			label: "Playground",
			icon: <Bot className="h-4 w-4" />,
		},
		{
			to: "/dashboard/settings",
			label: "GitHub & Secrets",
			icon: <Github className="h-4 w-4" />,
		},
	];

	return (
		<div className="flex h-full flex-col">
			{/* Main Header */}
			<header className="flex h-14 items-center justify-between border-b bg-background px-6">
				<div className="flex items-center gap-3">
					<Logo className="h-7 w-auto" />
					<span className="font-bold text-lg tracking-tight">AGIaaS</span>
				</div>
				<div className="flex items-center gap-4">
					<div className="font-mono text-muted-foreground text-xs">
						v1.0.0-beta
					</div>
				</div>
			</header>

			{/* Subnav */}
			<div className="flex items-center gap-1 border-b bg-muted/30 px-4 py-2 backdrop-blur-sm">
				{navItems.map((item) => (
					<Link
						key={item.to}
						to={item.to}
						className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-muted-foreground text-sm transition-colors hover:text-foreground [&.active]:bg-muted [&.active]:font-medium [&.active]:text-foreground"
						activeOptions={{ exact: true }}
						activeProps={{ className: "bg-muted font-medium text-foreground" }}
					>
						{item.icon}
						{item.label}
					</Link>
				))}

				{/* Config status pill */}
				<div className="ml-auto flex items-center gap-2 text-xs">
					{isConfigured ? (
						<div className="flex items-center gap-1.5 rounded-full border border-green-500/20 bg-green-500/10 px-3 py-1">
							<div className="h-1.5 w-1.5 animate-pulse rounded-full bg-green-500" />
							<span className="font-medium text-green-600 dark:text-green-400">
								{activeProjects.length} Projects Monitored
							</span>
						</div>
					) : (
						<Link
							to="/dashboard/settings"
							className="flex items-center gap-1.5 rounded-full border border-amber-500/20 bg-amber-500/10 px-3 py-1 transition-colors hover:bg-amber-500/20"
						>
							<Settings2 className="h-3 w-3 text-amber-500" />
							<span className="font-medium text-amber-600 dark:text-amber-400">
								Setup required
							</span>
						</Link>
					)}
				</div>
			</div>

			{/* Page content */}
			<div className="flex-1 overflow-auto">
				<div className="container mx-auto max-w-7xl px-6">
					<Outlet />
				</div>
			</div>
		</div>
	);
}
