import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@hermes-on-call/ui/components/card";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { BookOpen, Bot, Github, Webhook, Zap } from "lucide-react";
import { orpc } from "../../utils/orpc";

export const Route = createFileRoute("/dashboard/settings/activity")({
	component: ActivitySettings,
});

function ActivitySettings() {
	const { data: ghCli } = useQuery(orpc.github.getGhCliUser.queryOptions());
	const { data: tgConfig } = useQuery(
		orpc.github.getGlobalTelegramBotConfig.queryOptions(),
	);
	const { data: webhookStatus } = useQuery({
		...orpc.github.getWebhookStatus.queryOptions(),
		refetchInterval: 3000,
	});
	const { data: logsData } = useQuery({
		...orpc.onCall.getLogs.queryOptions(),
		refetchInterval: 2000,
	});

	// Parse GitHub-related log lines
	const githubLogs =
		logsData?.logs?.filter((l: string) =>
			/github|pr |pull request|issue|webhook|action|workflow/i.test(l),
		) || [];

	return (
		<div className="space-y-6">
			{/* Stats row */}
			<div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
				{[
					{
						icon: <Github className="h-5 w-5 text-primary" />,
						label: "GitHub CLI",
						value: ghCli?.ghUser ? `@${ghCli.ghUser}` : "Not connected",
						ok: ghCli?.isConfigured,
					},
					{
						icon: <Webhook className="h-5 w-5 text-amber-500" />,
						label: "Webhook Server",
						value: webhookStatus?.running
							? `Active (Port ${webhookStatus.port})`
							: "Offline",
						ok: webhookStatus?.running,
					},
					{
						icon: <Bot className="h-5 w-5 text-blue-400" />,
						label: "Telegram",
						value: tgConfig?.telegramBotToken ? "Configured" : "Not set",
						ok: !!tgConfig?.telegramBotToken,
					},
					{
						icon: <BookOpen className="h-5 w-5 text-green-500" />,
						label: "Observed Events",
						value: `${githubLogs.length} events logged`,
						ok: githubLogs.length > 0,
					},
				].map((stat) => (
					<Card key={stat.label} className="border-border/50">
						<CardContent className="px-4 pt-4 pb-3">
							<div className="flex items-start justify-between">
								<div>{stat.icon}</div>
								<div
									className={`mt-1 h-2 w-2 rounded-full ${stat.ok ? "bg-green-500" : "bg-zinc-600"}`}
								/>
							</div>
							<div className="mt-3">
								<div className="truncate font-bold text-sm">{stat.value}</div>
								<div className="text-[11px] text-muted-foreground">
									{stat.label}
								</div>
							</div>
						</CardContent>
					</Card>
				))}
			</div>

			{/* Events feed */}
			<Card>
				<CardHeader>
					<CardTitle className="flex items-center gap-2 text-base">
						<Zap className="h-4 w-4 text-amber-500" />
						Real-time Workflow Activity
					</CardTitle>
					<CardDescription>
						Live stream of GitHub webhooks and automated agent triggers.
					</CardDescription>
				</CardHeader>
				<CardContent>
					{githubLogs.length > 0 ? (
						<div className="space-y-2">
							{githubLogs.slice(-20).map((log: string, i: number) => (
								<div
									key={i}
									className="flex items-start gap-3 rounded-lg border border-border/50 bg-muted/30 px-3 py-2"
								>
									<div className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-400" />
									<span className="break-all font-mono text-violet-300 text-xs leading-relaxed">
										{log}
									</span>
								</div>
							))}
						</div>
					) : (
						<div className="flex flex-col items-center justify-center gap-4 py-16 text-muted-foreground">
							<Github className="h-12 w-12 opacity-20" />
							<div className="space-y-1 text-center">
								<p className="font-semibold text-sm">No Events Detected</p>
								<p className="text-xs opacity-60">
									Waiting for GitHub webhooks or periodic monitoring triggers...
								</p>
							</div>
						</div>
					)}
				</CardContent>
			</Card>
		</div>
	);
}
