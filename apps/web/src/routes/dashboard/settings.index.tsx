import { Button } from "@agiaas/ui/components/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@agiaas/ui/components/card";
import { Input } from "@agiaas/ui/components/input";
import { Label } from "@agiaas/ui/components/label";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import {
	Bot,
	Check,
	Eye,
	EyeOff,
	GitBranch,
	Github,
	Key,
	Link2,
	Plus,
	Trash2,
	Webhook,
} from "lucide-react";
import { useState } from "react";
import { orpc } from "../../utils/orpc";

export const Route = createFileRoute("/dashboard/settings/")({
	component: GeneralSettings,
});

function SecretInput({
	id,
	label,
	value,
	onChange,
	placeholder,
	hint,
}: {
	id: string;
	label: string;
	value: string;
	onChange: (v: string) => void;
	placeholder?: string;
	hint?: string;
}) {
	const [show, setShow] = useState(false);
	return (
		<div className="space-y-1.5">
			<Label
				htmlFor={id}
				className="flex items-center gap-1.5 font-semibold text-muted-foreground text-xs uppercase tracking-wider"
			>
				<Key className="h-3 w-3" />
				{label}
			</Label>
			<div className="relative">
				<Input
					id={id}
					type={show ? "text" : "password"}
					value={value}
					onChange={(e) => onChange(e.target.value)}
					placeholder={placeholder}
					className="pr-10 font-mono text-sm"
				/>
				<button
					type="button"
					onClick={() => setShow(!show)}
					className="absolute top-2.5 right-3 text-muted-foreground hover:text-foreground"
					aria-label={show ? "Hide" : "Show"}
				>
					{show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
				</button>
			</div>
			{hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
		</div>
	);
}

function StatusDot({ ok, label }: { ok: boolean; label: string }) {
	return (
		<div className="flex items-center gap-2">
			<span
				className={`h-2 w-2 rounded-full ${ok ? "animate-pulse bg-green-500" : "bg-red-500"}`}
			/>
			<span className="font-medium text-xs">{label}</span>
		</div>
	);
}

function GeneralSettings() {
	const queryClient = useQueryClient();

	const { data: reposData } = useQuery({
		...orpc.github.listRepos.queryOptions(),
		staleTime: 60_000,
	});

	const { data: projectsData } = useQuery({
		...orpc.github.listProjects.queryOptions(),
		refetchInterval: 5000,
	});

	const { data: botsData } = useQuery({
		...orpc.bots.listBots.queryOptions(),
		refetchInterval: 5000,
	});

	const [botToken, setBotToken] = useState("");

	const [form, setForm] = useState({
		githubWebhookSecret: "",
		telegramChatId: "",
		botId: "",
		selectedRepo: "",
		llmModel: "NousResearch/Hermes-3-Llama-3.1-405B",
	});
	const set = (key: keyof typeof form) => (v: string) =>
		setForm((f) => ({ ...f, [key]: v }));

	// Mutators
	const addProjectMutation = useMutation(
		orpc.github.addProject.mutationOptions({
			onSuccess: () => {
				queryClient.invalidateQueries();
				setForm((f) => ({
					...f,
					githubWebhookSecret: "",
					telegramChatId: "",
					botId: "",
				}));
			},
		}),
	);

	const deleteProjectMutation = useMutation(
		orpc.github.deleteProject.mutationOptions({
			onSuccess: () => queryClient.invalidateQueries(),
		}),
	);

	const toggleProjectMutation = useMutation(
		orpc.github.toggleProject.mutationOptions({
			onSuccess: () => queryClient.invalidateQueries(),
		}),
	);

	const addBotMutation = useMutation(
		orpc.bots.addBot.mutationOptions({
			onSuccess: () => {
				queryClient.invalidateQueries();
				setBotToken("");
			},
		}),
	);

	const deleteBotMutation = useMutation(
		orpc.bots.deleteBot.mutationOptions({
			onSuccess: () => queryClient.invalidateQueries(),
		}),
	);

	const setPrimaryBotMutation = useMutation(
		orpc.bots.setPrimaryBot.mutationOptions({
			onSuccess: () => queryClient.invalidateQueries(),
		}),
	);

	const updateModelMutation = useMutation(
		orpc.github.updateModel.mutationOptions({
			onSuccess: () => queryClient.invalidateQueries(),
		}),
	);

	const repos = reposData?.repos ?? [];
	const projects = projectsData?.projects ?? [];

	const { data: ghCli } = useQuery({
		...orpc.github.getGhCliUser.queryOptions(),
		staleTime: 60_000,
	});

	const bots = botsData?.bots ?? [];

	const { data: webhookStatus } = useQuery({
		...orpc.github.getWebhookStatus.queryOptions(),
		refetchInterval: 3000,
	});

	const { data: tunnelData } = useQuery({
		...orpc.github.getTunnelUrl.queryOptions(),
		refetchInterval: 5000,
	});

	return (
		<div className="grid gap-8 lg:grid-cols-12">
			{/* Left: Status sidebar */}
			<div className="space-y-4 lg:col-span-5">
				{/* gh CLI info */}
				<Card
					className={
						ghCli?.ghUser
							? "border-green-500/20 bg-green-500/5"
							: "border-border/50"
					}
				>
					<CardHeader className="pb-2">
						<CardTitle className="flex items-center gap-2 text-sm">
							<Github className="h-4 w-4 text-primary" />
							GitHub (via gh CLI)
						</CardTitle>
					</CardHeader>
					<CardContent className="space-y-2">
						{ghCli?.ghUser ? (
							<>
								<StatusDot ok label={`Authenticated as @${ghCli.ghUser}`} />
								<p className="pt-1 text-[10px] text-muted-foreground">
									{repos.length} repositories accessible
								</p>
							</>
						) : (
							<>
								<StatusDot ok={false} label="gh CLI not authenticated" />
								<div className="pt-2">
									<p className="text-muted-foreground text-xs">
										Run this in your terminal:
									</p>
									<code className="mt-1 block rounded bg-muted p-2 text-xs">
										gh auth login
									</code>
								</div>
							</>
						)}
					</CardContent>
				</Card>

				{/* Connection status */}
				<Card className="border-border/50">
					<CardHeader className="pb-2">
						<CardTitle className="flex items-center gap-2 text-sm">
							<Link2 className="h-4 w-4 text-primary" />
							Service Status
						</CardTitle>
					</CardHeader>
					<CardContent className="space-y-3">
						<StatusDot
							ok={!!webhookStatus?.running}
							label={
								webhookStatus?.running
									? `Webhook Receiver Active (Port ${webhookStatus.port})`
									: "Webhook Receiver Offline"
							}
						/>
						<StatusDot
							ok={bots.length > 0}
							label={
								bots.length > 0
									? `${bots.length} Bots Active`
									: "No Bots Configured"
							}
						/>
					</CardContent>
				</Card>

				{/* Live tunnel URL */}
				<Card
					className={
						tunnelData?.url
							? "border-amber-500/30 bg-amber-500/5"
							: "border-border/50"
					}
				>
					<CardHeader className="pb-2">
						<CardTitle className="flex items-center gap-2 text-sm">
							<Webhook className="h-4 w-4 text-amber-500" />
							External Webhook URL
						</CardTitle>
					</CardHeader>
					<CardContent className="space-y-2">
						{tunnelData?.webhookUrl ? (
							<>
								<button
									type="button"
									className="w-full cursor-pointer break-all rounded-md bg-muted/60 px-3 py-2 text-left font-mono text-[11px] text-amber-400 transition-colors hover:bg-muted"
									onClick={() =>
										navigator.clipboard.writeText(tunnelData.webhookUrl)
									}
									title="Click to copy"
								>
									{tunnelData.webhookUrl}
								</button>
								<p className="text-[10px] text-muted-foreground">
									Copy this URL and add it to your GitHub Repo → Settings →
									Webhooks
								</p>
							</>
						) : (
							<p className="text-[11px] text-muted-foreground">
								<span className="animate-pulse">⏳</span> Starting tunnel…
								<br />
								<code className="text-[10px]">pnpm dev</code> must be running.
							</p>
						)}
					</CardContent>
				</Card>
			</div>

			{/* Right: Projects & Global Settings */}
			<div className="space-y-8 lg:col-span-7">
				{/* ── Active Projects List ── */}
				<div>
					<h3 className="mb-4 font-semibold text-lg tracking-tight">
						Monitored Projects
					</h3>
					{projects.length === 0 ? (
						<div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">
							No projects monitored yet. Add your first repository below.
						</div>
					) : (
						<div className="grid gap-4">
							{projects.map((p) => (
								<Card key={p.id} className={!p.isActive ? "opacity-60" : ""}>
									<CardHeader className="flex flex-row items-center justify-between pb-2">
										<CardTitle className="flex items-center gap-2 text-base">
											<GitBranch className="h-4 w-4 text-primary" />
											{p.repoFullName}
										</CardTitle>
										<div className="flex items-center gap-2">
											<button
												type="button"
												className={`rounded-full px-2 py-1 font-medium text-[10px] ${p.isActive ? "bg-green-500/10 text-green-500" : "bg-muted text-muted-foreground"}`}
												onClick={() =>
													toggleProjectMutation.mutate({
														id: p.id,
														isActive: !p.isActive,
													})
												}
											>
												{p.isActive ? "Active" : "Paused"}
											</button>
											<button
												type="button"
												className="rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
												onClick={() =>
													deleteProjectMutation.mutate({ id: p.id })
												}
												title="Delete Project"
											>
												<Trash2 className="h-4 w-4" />
											</button>
										</div>
									</CardHeader>
									<CardContent className="space-y-4 text-muted-foreground text-xs">
										<div className="flex flex-wrap gap-4">
											<div>
												<span className="font-semibold text-foreground">
													Chat ID:
												</span>{" "}
												{p.telegramChatId}
											</div>
											<div>
												<span className="font-semibold text-foreground">
													Bot:
												</span>{" "}
												{p.botId ? (
													<span className="inline-flex items-center gap-1 text-primary">
														@
														{bots.find((b) => b.id === p.botId)?.username ||
															"Unknown"}
													</span>
												) : (
													<span className="text-amber-500">❌ Not Linked</span>
												)}
											</div>
											<div>
												<span className="font-semibold text-foreground">
													Secret:
												</span>{" "}
												{p.webhookSecret ? "••••••••" : "Not Set"}
											</div>
										</div>

										<div className="flex items-center gap-3 border-t pt-3">
											<span className="font-semibold text-foreground">
												LLM Model:
											</span>
											<select
												value={p.llmModel}
												onChange={(e) =>
													updateModelMutation.mutate({
														id: p.id,
														llmModel: e.target.value,
													})
												}
												className="rounded border bg-background px-2 py-1 font-medium text-[11px] text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
											>
												<optgroup label="NousResearch (Recommended)">
													<option value="NousResearch/Hermes-3-Llama-3.1-405B">
														Hermes 3 Llama 3.1 405B
													</option>
													<option value="NousResearch/Hermes-3-Llama-3.1-70B">
														Hermes 3 Llama 3.1 70B
													</option>
													<option value="NousResearch/Hermes-3-Llama-3.1-8B">
														Hermes 3 Llama 3.1 8B
													</option>
												</optgroup>
												<optgroup label="OpenAI">
													<option value="gpt-4o">GPT-4o</option>
													<option value="gpt-4o-mini">GPT-4o Mini</option>
												</optgroup>
												<optgroup label="Anthropic">
													<option value="anthropic/claude-3-5-sonnet">
														Claude 3.5 Sonnet
													</option>
													<option value="anthropic/claude-3-5-haiku">
														Claude 3.5 Haiku
													</option>
												</optgroup>
												<optgroup label="Other">
													<option value="deepseek/deepseek-chat">
														DeepSeek V3
													</option>
													<option value="meta-llama/llama-3.3-70b-instruct">
														Llama 3.3 70B
													</option>
												</optgroup>
											</select>
											{updateModelMutation.isPending && (
												<span className="animate-pulse text-[10px]">
													Saving...
												</span>
											)}
										</div>
									</CardContent>
								</Card>
							))}
						</div>
					)}
				</div>

				{/* ── Add New Project Form ── */}
				<Card className="border-primary/20 bg-primary/5">
					<CardHeader>
						<CardTitle className="text-base">Add New Project</CardTitle>
						<CardDescription>
							Connect a new GitHub repository for Hermes to monitor and report
							via Telegram.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="space-y-1.5">
							<Label className="font-semibold text-muted-foreground text-xs uppercase tracking-wider">
								GitHub Repository
							</Label>
							<select
								value={form.selectedRepo}
								onChange={(e) => set("selectedRepo")(e.target.value)}
								className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
							>
								<option value="" disabled>
									Select a repository...
								</option>
								{repos.map(
									(r: { nameWithOwner: string; isPrivate: boolean }) => (
										<option key={r.nameWithOwner} value={r.nameWithOwner}>
											{r.isPrivate ? "🔒 " : "🌐 "}
											{r.nameWithOwner}
										</option>
									),
								)}
							</select>
						</div>

						<SecretInput
							id="webhookSecret"
							label="Webhook Secret"
							value={form.githubWebhookSecret}
							onChange={set("githubWebhookSecret")}
							placeholder="Enter webhook secret"
							hint="Must match the secret entered in GitHub Webhook settings"
						/>

						<div className="space-y-1.5">
							<Label className="font-semibold text-muted-foreground text-xs uppercase tracking-wider">
								Telegram Chat ID
							</Label>
							<Input
								value={form.telegramChatId}
								onChange={(e) => set("telegramChatId")(e.target.value)}
								placeholder="-100123456789"
								className="font-mono text-sm"
							/>
							<p className="text-[11px] text-muted-foreground">
								Required. The ID of the group or user where notifications will
								be sent.
							</p>
						</div>

						<div className="space-y-1.5">
							<Label className="font-semibold text-muted-foreground text-xs uppercase tracking-wider">
								Telegram Bot
							</Label>
							<select
								value={form.botId}
								onChange={(e) => set("botId")(e.target.value)}
								className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
							>
								<option value="">Select a bot...</option>
								{bots.map((b) => (
									<option key={b.id} value={b.id}>
										@{b.username} ({b.name})
									</option>
								))}
							</select>
							<p className="text-[11px] text-muted-foreground">
								Select which bot will handle notifications for this project.
							</p>
						</div>

						<div className="space-y-1.5">
							<Label className="font-semibold text-muted-foreground text-xs uppercase tracking-wider">
								Hermes Brain (Model)
							</Label>
							<select
								value={form.llmModel}
								onChange={(e) => set("llmModel")(e.target.value)}
								className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
							>
								<optgroup label="NousResearch (Recommended)">
									<option value="NousResearch/Hermes-3-Llama-3.1-405B">
										Hermes 3 Llama 3.1 405B
									</option>
									<option value="NousResearch/Hermes-3-Llama-3.1-70B">
										Hermes 3 Llama 3.1 70B
									</option>
									<option value="NousResearch/Hermes-3-Llama-3.1-8B">
										Hermes 3 Llama 3.1 8B
									</option>
								</optgroup>
								<optgroup label="OpenAI">
									<option value="gpt-4o">GPT-4o</option>
									<option value="gpt-4o-mini">GPT-4o Mini</option>
								</optgroup>
								<optgroup label="Anthropic">
									<option value="anthropic/claude-3-5-sonnet">
										Claude 3.5 Sonnet
									</option>
									<option value="anthropic/claude-3-5-haiku">
										Claude 3.5 Haiku
									</option>
								</optgroup>
								<optgroup label="Other">
									<option value="deepseek/deepseek-chat">DeepSeek V3</option>
									<option value="meta-llama/llama-3.3-70b-instruct">
										Llama 3.3 70B
									</option>
								</optgroup>
							</select>
							<p className="text-[11px] text-muted-foreground">
								This model will be used to analyze issues and propose fixes.
							</p>
						</div>

						<Button
							onClick={() =>
								addProjectMutation.mutate({
									repoFullName: form.selectedRepo,
									webhookSecret: form.githubWebhookSecret,
									telegramChatId: form.telegramChatId,
									botId: form.botId || undefined,
									llmModel: form.llmModel,
								})
							}
							disabled={
								addProjectMutation.isPending ||
								!form.selectedRepo ||
								!form.telegramChatId ||
								!form.githubWebhookSecret
							}
							className="w-full gap-2"
						>
							{addProjectMutation.isPending ? "Adding..." : "Add Project"}
						</Button>
					</CardContent>
				</Card>

				{/* ── Bot Management ── */}
				<Card>
					<CardHeader>
						<CardTitle className="flex items-center gap-2">
							<Bot className="h-5 w-5 text-primary" />
							Bot Management
						</CardTitle>
						<CardDescription>
							Register and manage Telegram bots. We'll automatically fetch their
							profile info.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-6">
						{/* Add Bot Form */}
						<div className="flex gap-2">
							<div className="relative flex-1">
								<Key className="absolute top-2.5 left-3 h-4 w-4 text-muted-foreground" />
								<Input
									value={botToken}
									onChange={(e) => setBotToken(e.target.value)}
									placeholder="Enter Bot Token (from @BotFather)"
									className="pl-9 font-mono text-sm"
									type="password"
								/>
							</div>
							<Button
								onClick={() => addBotMutation.mutate({ token: botToken })}
								disabled={addBotMutation.isPending || !botToken}
								className="gap-2"
							>
								{addBotMutation.isPending ? (
									<span className="animate-spin">⌛</span>
								) : (
									<Plus className="h-4 w-4" />
								)}
								Add Bot
							</Button>
						</div>

						{/* Bot List */}
						<div className="grid gap-3">
							{bots.length === 0 ? (
								<p className="py-4 text-center text-muted-foreground text-xs italic">
									No bots registered yet.
								</p>
							) : (
								bots.map((bot) => (
									<div
										key={bot.id}
										className="flex items-center justify-between rounded-lg border bg-card p-3 transition-colors hover:bg-accent/5"
									>
										<div className="flex items-center gap-3">
											<div className="h-10 w-10 overflow-hidden rounded-full border bg-muted">
												{bot.avatarUrl ? (
													<img
														src={bot.avatarUrl}
														alt={bot.name}
														className="h-full w-full object-cover"
													/>
												) : (
													<div className="flex h-full w-full items-center justify-center text-muted-foreground">
														<Bot className="h-5 w-5" />
													</div>
												)}
											</div>
											<div>
												<h4 className="font-bold text-sm leading-none">
													{bot.name}
												</h4>
												<p className="text-muted-foreground text-xs">
													@{bot.username}
												</p>
											</div>
										</div>
										<div className="flex items-center gap-2">
											{bot.isPrimary && (
												<span className="flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 font-semibold text-primary text-xs">
													<Check className="h-3 w-3" />
													Primary
												</span>
											)}
											{!bot.isPrimary && (
												<button
													type="button"
													onClick={() =>
														setPrimaryBotMutation.mutate({ id: bot.id })
													}
													className="rounded-md border px-2 py-1 font-medium text-[10px] transition-colors hover:bg-accent"
												>
													Make Primary
												</button>
											)}
											<button
												type="button"
												className="rounded p-1 text-muted-foreground hover:text-destructive"
												onClick={() => deleteBotMutation.mutate({ id: bot.id })}
											>
												<Trash2 className="h-4 w-4" />
											</button>
										</div>
									</div>
								))
							)}
						</div>
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
