import { Button } from "@agiaas/ui/components/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@agiaas/ui/components/card";
import { Label } from "@agiaas/ui/components/label";
import { Textarea } from "@agiaas/ui/components/textarea";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Bot, Play, Terminal, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { orpc } from "@/utils/orpc";

export const Route = createFileRoute("/dashboard/playground")({
	component: Playground,
});

function Playground() {
	const [input, setInput] = useState("");
	const [simulationLogs, setSimulationLogs] = useState<string[]>([]);
	const [isSimulating, setIsSimulating] = useState(false);
	const scrollRef = useRef<HTMLDivElement>(null);

	const { data: projectsData } = useQuery({
		...orpc.github.listProjects.queryOptions(),
	});

	const [selectedProject, setSelectedProject] = useState("");

	useEffect(() => {
		if (scrollRef.current) {
			scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
		}
	}, []);

	const runSimulation = () => {
		if (!input.trim()) return;

		setIsSimulating(true);
		setSimulationLogs([
			"[SYSTEM] Initializing Hermes Agent...",
			"[SYSTEM] Connecting to GitHub API...",
		]);

		// Simulate agent steps
		const steps = [
			`[AGENT] Thinking: User wants to ${input.substring(0, 30)}...`,
			"[AGENT] Searching codebase for relevant components...",
			"[GITHUB] Successfully fetched repository metadata.",
			"[AGENT] Proposed change: Refactor the authentication middleware.",
			"[INCIDENT] Potential issue detected in 'auth.ts'.",
			"[AGENT] Fixing the bug and creating a Pull Request...",
			"[GITHUB] Pull Request #42 created successfully.",
			"[TELEGRAM] Notification sent to the team.",
			"[SYSTEM] Task completed.",
		];

		let i = 0;
		const interval = setInterval(() => {
			if (i < steps.length) {
				setSimulationLogs((prev) => [...prev, steps[i]]);
				i++;
			} else {
				clearInterval(interval);
				setIsSimulating(false);
			}
		}, 800);
	};

	const projects = projectsData?.projects ?? [];

	return (
		<div className="py-8">
			<div className="mb-8 items-center justify-between gap-4 md:flex">
				<div>
					<h1 className="font-bold text-3xl tracking-tight">
						Agent Playground
					</h1>
					<p className="text-muted-foreground text-sm">
						Test your agents in a sandbox environment before connecting them to
						live repositories.
					</p>
				</div>
				<div className="mt-4 flex items-center gap-2 md:mt-0">
					<div className="flex items-center gap-1.5 rounded-full bg-amber-500/10 px-3 py-1 font-semibold text-amber-500 text-xs">
						<Zap className="h-3.5 w-3.5" />
						SANDBOX MODE
					</div>
				</div>
			</div>

			<div className="grid gap-6 lg:grid-cols-2">
				{/* Workspace / Input */}
				<div className="space-y-6">
					<Card className="h-full">
						<CardHeader>
							<CardTitle className="text-base">Prompt Editor</CardTitle>
							<CardDescription>
								Describe a task or paste a GitHub Issue body to see how the
								agent responds.
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							<div className="space-y-2">
								<Label className="font-bold text-muted-foreground text-xs uppercase tracking-wider">
									Target Project
								</Label>
								<select
									value={selectedProject}
									onChange={(e) => setSelectedProject(e.target.value)}
									className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm focus:ring-2 focus:ring-ring"
								>
									<option value="">Select project context...</option>
									{projects.map((p) => (
										<option key={p.id} value={p.id}>
											{p.repoFullName}
										</option>
									))}
								</select>
							</div>

							<div className="space-y-2">
								<Label className="font-bold text-muted-foreground text-xs uppercase tracking-wider">
									Prompt / Issue Text
								</Label>
								<Textarea
									placeholder="e.g. Please check why the login page is failing on Firefox..."
									className="min-h-[200px] font-mono text-sm leading-relaxed"
									value={input}
									onChange={(e) => setInput(e.target.value)}
								/>
							</div>

							<Button
								className="w-full gap-2"
								onClick={runSimulation}
								disabled={isSimulating || !input.trim()}
							>
								{isSimulating ? (
									<>
										<Zap className="h-4 w-4 animate-pulse fill-current" />
										Running Agent...
									</>
								) : (
									<>
										<Play className="h-4 w-4" />
										Run Simulation
									</>
								)}
							</Button>
						</CardContent>
					</Card>
				</div>

				{/* Output / Console */}
				<div className="space-y-6">
					<Card
						className="flex flex-col border-border bg-black shadow-2xl"
						style={{ height: "500px" }}
					>
						<CardHeader className="flex-row items-center justify-between border-white/5 border-b bg-zinc-900/50 py-3">
							<CardTitle className="flex items-center gap-2 font-mono text-primary-foreground text-sm uppercase tracking-tighter">
								<Terminal className="h-4 w-4" />
								Hermes Console Output
							</CardTitle>
							{isSimulating && (
								<div className="flex items-center gap-2">
									<div className="h-2 w-2 animate-ping rounded-full bg-green-500" />
									<span className="font-bold text-[10px] text-green-500">
										STREAMING
									</span>
								</div>
							)}
						</CardHeader>
						<CardContent
							className="flex-1 overflow-auto p-4 font-mono text-xs"
							ref={scrollRef}
						>
							{simulationLogs.length === 0 ? (
								<div className="flex h-full flex-col items-center justify-center space-y-3 text-zinc-400 opacity-20">
									<Bot className="h-12 w-12" />
									<p>Awaiting simulation input...</p>
								</div>
							) : (
								<div className="space-y-1.5 text-zinc-300">
									{simulationLogs.map((log, i) => (
										<div
											key={i}
											className="fade-in slide-in-from-left-2 animate-in duration-300"
										>
											<span className="mr-2 text-zinc-600">[{i}]</span>
											<span
												className={
													log.includes("[SYSTEM]")
														? "text-sky-400"
														: log.includes("[AGENT]")
															? "text-violet-400"
															: log.includes("[GITHUB]")
																? "text-emerald-400"
																: log.includes("[TELEGRAM]")
																	? "text-amber-400"
																	: log.includes("[INCIDENT]")
																		? "font-bold text-rose-400"
																		: ""
												}
											>
												{log}
											</span>
										</div>
									))}
									{isSimulating && (
										<span className="animate-pulse font-bold text-zinc-500">
											_
										</span>
									)}
								</div>
							)}
						</CardContent>
					</Card>
				</div>
			</div>
		</div>
	);
}
