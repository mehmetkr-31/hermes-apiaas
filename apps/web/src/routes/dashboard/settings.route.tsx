import { createFileRoute, Link, Outlet } from "@tanstack/react-router";
import { Github, Settings2, Terminal } from "lucide-react";

export const Route = createFileRoute("/dashboard/settings")({
	component: SettingsLayout,
});

function SettingsLayout() {
	const tabs = [
		{
			id: "settings",
			label: "General Settings",
			icon: <Settings2 className="h-4 w-4" />,
			to: "/dashboard/settings",
		},
		{
			id: "logs",
			label: "Hermes Logs",
			icon: <Terminal className="h-4 w-4" />,
			to: "/dashboard/settings/logs",
		},
		{
			id: "activity",
			label: "GitHub Activity",
			icon: <Github className="h-4 w-4" />,
			to: "/dashboard/settings/activity",
		},
		{
			id: "secrets",
			label: "Secrets",
			icon: <Settings2 className="h-4 w-4" />, // Or a different icon like Lock
			to: "/dashboard/settings/secrets",
		},
	];

	return (
		<div className="flex flex-col gap-6 p-6">
			<div>
				<h1 className="font-bold text-3xl tracking-tight">Settings</h1>
				<p className="text-muted-foreground">
					Manage your projects, monitoring logs, and GitHub integration.
				</p>
			</div>

			<div className="flex flex-col gap-8 lg:flex-row">
				<aside className="lg:w-64">
					<nav className="flex flex-col gap-2">
						{tabs.map((tab) => (
							<Link
								key={tab.id}
								to={tab.to}
								activeProps={{ className: "bg-primary/10 text-primary" }}
								inactiveProps={{
									className: "text-muted-foreground hover:bg-muted",
								}}
								className="flex items-center gap-3 rounded-lg px-3 py-2 font-medium transition-all"
								activeOptions={{ exact: tab.id === "settings" }}
							>
								{tab.icon}
								{tab.label}
							</Link>
						))}
					</nav>
				</aside>

				<main className="flex-1">
					<Outlet />
				</main>
			</div>
		</div>
	);
}
