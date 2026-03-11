import { Badge } from "@hermes-on-call/ui/components/badge";
import { Card, CardContent } from "@hermes-on-call/ui/components/card";
import { Separator } from "@hermes-on-call/ui/components/separator";
import { Skeleton } from "@hermes-on-call/ui/components/skeleton";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Activity, Server, Terminal } from "lucide-react";
import { useEffect, useRef } from "react";
import { orpc } from "../../utils/orpc";

export const Route = createFileRoute("/dashboard/settings/logs")({
	component: LogsSettings,
});

function LogsSettings() {
	const scrollRef = useRef<HTMLDivElement>(null);

	const { data: logsData, isLoading } = useQuery({
		...orpc.onCall.getLogs.queryOptions(),
		refetchInterval: 1500,
	});

	useEffect(() => {
		if (scrollRef.current) {
			scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
		}
	}, [logsData]);

	const colorClass = (log: string) => {
		const l = log.toLowerCase();
		if (
			l.includes("error") ||
			l.includes("fail") ||
			l.includes("❌") ||
			l.includes("⚠️")
		)
			return "text-red-400 font-medium";
		if (
			l.includes("success") ||
			l.includes("resolv") ||
			l.includes("✅") ||
			l.includes("💡")
		)
			return "text-green-400 font-medium";
		if (l.includes("🚨") || l.includes("trigger") || l.includes("dispatch"))
			return "text-sky-400 font-bold";
		if (l.includes("github") || l.includes("pr ") || l.includes("issue"))
			return "text-violet-400 font-medium";
		return "text-zinc-400";
	};

	return (
		<Card
			className="flex flex-col overflow-hidden border-border bg-background shadow-xl"
			style={{ height: "calc(100vh - 200px)", minHeight: "500px" }}
		>
			<div className="flex items-center justify-between border-b bg-muted/50 px-4 py-3">
				<div className="flex items-center gap-3">
					<div className="mr-1 flex gap-1.5">
						<div className="h-3 w-3 rounded-full bg-red-500/40" />
						<div className="h-3 w-3 rounded-full bg-amber-500/40" />
						<div className="h-3 w-3 rounded-full bg-green-500/40" />
					</div>
					<Separator orientation="vertical" className="h-4" />
					<div className="flex items-center gap-2">
						<Terminal className="h-4 w-4 text-primary" />
						<span className="font-bold font-mono text-xs uppercase tracking-tight">
							Hermes Output Stream
						</span>
					</div>
				</div>
				<div className="flex items-center gap-3">
					{logsData?.logs && logsData.logs.length > 0 && (
						<div className="flex items-center gap-2 rounded-md border bg-background px-2 py-0.5 font-mono text-[10px]">
							<div className="h-1.5 w-1.5 animate-pulse rounded-full bg-green-500" />
							LIVE
						</div>
					)}
					<Badge variant="outline" className="h-5 font-mono text-[10px]">
						{logsData?.logs?.length || 0} lines
					</Badge>
				</div>
			</div>

			<CardContent className="flex-1 overflow-hidden bg-black/95 p-0">
				<div
					ref={scrollRef}
					className="absolute inset-0 overflow-y-auto overflow-x-hidden p-6 font-mono text-sm"
					style={{ position: "relative", height: "100%" }}
				>
					{isLoading && !logsData ? (
						<div className="space-y-3">
							{[...Array(10)].map((_, i) => (
								<Skeleton
									key={i}
									className="h-4 bg-zinc-900"
									style={{ width: `${60 + (i % 4) * 10}%` }}
								/>
							))}
						</div>
					) : logsData?.error ? (
						<div className="flex h-full flex-col items-center justify-center gap-3 text-destructive opacity-80">
							<Server className="h-12 w-12" />
							<div className="font-bold text-xs uppercase tracking-widest">
								Agent Not Running
							</div>
							<div className="max-w-sm rounded-lg border border-destructive/20 bg-destructive/10 px-4 py-2 text-center text-xs">
								{logsData.error}
							</div>
							<div className="text-[10px] text-muted-foreground">
								Run the agent script to start receiving logs.
							</div>
						</div>
					) : logsData?.logs && logsData.logs.length > 0 ? (
						<div className="space-y-1">
							{logsData.logs.map((log: string, i: number) => (
								<div
									key={i}
									className="fade-in slide-in-from-left-2 flex animate-in items-start gap-3 py-0.5 duration-300"
								>
									<span className="mt-1 w-8 shrink-0 select-none font-bold text-[10px] text-zinc-700 tabular-nums">
										{(i + 1).toString().padStart(3, "0")}
									</span>
									<span
										className={`break-all leading-relaxed ${colorClass(log)}`}
									>
										{log}
									</span>
								</div>
							))}
							<div className="h-4 pt-2">
								<span className="animate-pulse font-bold text-primary">_</span>
							</div>
						</div>
					) : (
						<div className="flex h-full flex-col items-center justify-center space-y-4 text-zinc-800">
							<Activity className="h-16 w-16 opacity-10" />
							<div className="space-y-1 text-center">
								<p className="font-bold text-xs uppercase tracking-widest opacity-50">
									Log Stream Empty
								</p>
								<p className="text-[10px] opacity-30">
									Waiting for agent activity...
								</p>
							</div>
						</div>
					)}
				</div>
			</CardContent>
		</Card>
	);
}
