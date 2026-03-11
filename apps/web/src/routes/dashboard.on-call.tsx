import { Button } from "@hermes-on-call/ui/components/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@hermes-on-call/ui/components/card";
import { Input } from "@hermes-on-call/ui/components/input";
import { Label } from "@hermes-on-call/ui/components/label";
import { Skeleton } from "@hermes-on-call/ui/components/skeleton";
import { useMutation, useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Activity, AlertCircle, Play, ServerCrash } from "lucide-react";
import { useState } from "react";
import { orpc } from "../utils/orpc";

export const Route = createFileRoute("/dashboard/on-call")({
	component: OnCallDashboard,
});

function OnCallDashboard() {
	const [mockUrl, setMockUrl] = useState("");

	const {
		data: logsData,
		refetch: refetchLogs,
		isLoading: isLogsLoading,
	} = useQuery({
		...orpc.onCall.getLogs.queryOptions(),
		refetchInterval: 3000, // Faster refresh for real-time feel
	});

	const triggerMutation = useMutation(
		orpc.onCall.triggerIncident.mutationOptions({
			onSuccess: () => {
				refetchLogs();
			},
		}),
	);

	return (
		<div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
			{/* Header Section */}
			<div className="flex flex-col gap-2">
				<h1 className="flex items-center gap-2 font-bold text-3xl tracking-tight">
					<Activity className="h-8 w-8 text-primary" />
					On-Call Agent Dashboard
				</h1>
				<p className="text-muted-foreground">
					Monitor production environments and trigger autonomous remediation
					scenarios. Test the self-healing API engine.
				</p>
			</div>

			<div className="grid grid-cols-1 gap-6 md:grid-cols-3">
				{/* Control Panel */}
				<Card className="h-fit border-border shadow-sm md:col-span-1">
					<CardHeader>
						<CardTitle className="flex items-center gap-2">
							<ServerCrash className="h-5 w-5 text-destructive" />
							Incident Control
						</CardTitle>
						<CardDescription>
							Simulate a production outage to watch the agent react.
						</CardDescription>
					</CardHeader>
					<CardContent className="flex flex-col gap-4">
						<div className="flex flex-col gap-2">
							<Label htmlFor="mockUrl" className="font-medium text-sm">
								Target Service URL
							</Label>
							<Input
								id="mockUrl"
								type="url"
								placeholder="e.g. http://localhost:8080"
								value={mockUrl}
								onChange={(e) => setMockUrl(e.target.value)}
							/>
						</div>
						<Button
							onClick={() => triggerMutation.mutate({ mockUrl })}
							disabled={triggerMutation.isPending}
							className="w-full font-semibold transition-all"
							variant={triggerMutation.isPending ? "secondary" : "default"}
						>
							{triggerMutation.isPending ? (
								<span className="flex items-center gap-2">
									<Activity className="h-4 w-4 animate-spin" />
									Triggering...
								</span>
							) : (
								<span className="flex items-center gap-2">
									<Play className="h-4 w-4" />
									Trigger Outage
								</span>
							)}
						</Button>

						{/* Status Messages */}
						{triggerMutation.isError && (
							<div className="flex items-center gap-2 rounded-md border border-destructive/20 bg-destructive/10 p-3 text-destructive text-sm">
								<AlertCircle className="h-4 w-4 shrink-0" />
								<span>{triggerMutation.error.message}</span>
							</div>
						)}
						{triggerMutation.isSuccess && (
							<div className="flex items-center gap-2 rounded-md border border-primary/20 bg-primary/10 p-3 text-primary text-sm">
								<Activity className="h-4 w-4 shrink-0" />
								<span>Agent deployed! Check logs...</span>
							</div>
						)}
					</CardContent>
				</Card>

				{/* Agent Logs Terminal */}
				<Card className="flex min-h-[500px] flex-col border-border shadow-sm md:col-span-2">
					<CardHeader className="border-b bg-muted/30">
						<CardTitle className="flex items-center justify-between font-mono text-muted-foreground text-sm uppercase tracking-wider">
							<span>Live Agent Telemetry</span>
							{logsData?.logs && logsData.logs.length > 0 && (
								<span className="relative flex h-2 w-2">
									<span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
									<span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
								</span>
							)}
						</CardTitle>
					</CardHeader>
					<CardContent className="relative flex-1 overflow-hidden rounded-b-xl bg-zinc-950 p-0">
						<div className="absolute inset-0 overflow-y-auto p-4 font-mono text-sm">
							{isLogsLoading && !logsData ? (
								<div className="flex flex-col gap-2">
									<Skeleton className="h-4 w-3/4 bg-zinc-800" />
									<Skeleton className="h-4 w-1/2 bg-zinc-800" />
									<Skeleton className="h-4 w-5/6 bg-zinc-800" />
								</div>
							) : logsData?.error ? (
								<span className="text-red-400">Error: {logsData.error}</span>
							) : logsData?.logs && logsData.logs.length > 0 ? (
								<div className="flex flex-col">
									{logsData.logs.map((log: string, i: number) => (
										<div
											key={i}
											className="break-words border-zinc-800/50 border-b py-1 hover:bg-zinc-900/50"
										>
											<span className="mr-2 select-none text-zinc-500 opacity-50">
												{String(i + 1).padStart(3, "0")}
											</span>
											<span
												className={
													log.toLowerCase().includes("error") ||
													log.toLowerCase().includes("fail")
														? "text-red-400"
														: log.toLowerCase().includes("success") ||
																log.toLowerCase().includes("resolv")
															? "text-green-400"
															: "text-zinc-300"
												}
											>
												{log}
											</span>
										</div>
									))}
								</div>
							) : (
								<div className="flex h-full select-none flex-col items-center justify-center space-y-4 text-zinc-600">
									<Activity className="h-10 w-10 opacity-20" />
									<p>Awaiting systemic anomalies...</p>
								</div>
							)}
						</div>
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
