import { Button } from "@hermes-on-call/ui/components/button";
import { useMutation, useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { orpc } from "../utils/orpc";

export const Route = createFileRoute("/dashboard/on-call")({
	component: OnCallDashboard,
});

function OnCallDashboard() {
	const [mockUrl, setMockUrl] = useState("");

	const { data: logsData, refetch: refetchLogs } = useQuery({
		...orpc.onCall.getLogs.queryOptions(),
		refetchInterval: 5000,
	});

	const triggerMutation = useMutation(
		orpc.onCall.triggerIncident.mutationOptions({
			onSuccess: () => {
				refetchLogs();
			},
		}),
	);

	return (
		<div className="flex flex-col gap-6 p-6">
			<div>
				<h1 className="font-bold text-3xl tracking-tight">
					On-Call Agent Dashboard
				</h1>
				<p className="text-muted-foreground">
					Monitor and trigger autonomous remediation scenarios.
				</p>
			</div>

			<div className="flex flex-col gap-4 rounded-xl border bg-card p-6">
				<h2 className="font-semibold text-xl">Incident Trigger</h2>
				<div className="flex items-center gap-4">
					<input
						type="text"
						placeholder="Mock URL (Optional)"
						className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:font-medium file:text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
						value={mockUrl}
						onChange={(e) => setMockUrl(e.target.value)}
					/>
					<Button
						onClick={() => triggerMutation.mutate({ mockUrl })}
						disabled={triggerMutation.isPending}
						className="whitespace-nowrap"
					>
						{triggerMutation.isPending ? "Triggering..." : "Trigger Incident"}
					</Button>
				</div>
				{triggerMutation.isError && (
					<p className="text-red-500 text-sm">
						Failed to trigger incident: {triggerMutation.error.message}
					</p>
				)}
				{triggerMutation.isSuccess && (
					<p className="text-green-500 text-sm">
						Incident triggered successfully! Background agent is responding.
					</p>
				)}
			</div>

			<div className="flex min-h-[400px] flex-1 flex-col gap-4 rounded-xl border bg-card p-6">
				<h2 className="font-semibold text-xl">Agent Activity Logs</h2>
				<div className="h-full max-h-[500px] overflow-y-auto rounded-md bg-black p-4 font-mono text-green-400 text-sm">
					{logsData?.error ? (
						<span className="text-red-400">{logsData.error}</span>
					) : logsData?.logs && logsData.logs.length > 0 ? (
						logsData.logs.map((log: string, i: number) => (
							<div key={i}>{log}</div>
						))
					) : (
						<span className="text-gray-500">Waiting for agent activity...</span>
					)}
				</div>
			</div>
		</div>
	);
}
