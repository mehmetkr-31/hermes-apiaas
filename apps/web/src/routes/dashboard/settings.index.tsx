import { Badge } from "@agiaas/ui/components/badge";
import { Button } from "@agiaas/ui/components/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@agiaas/ui/components/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@agiaas/ui/components/dialog";
import { Input } from "@agiaas/ui/components/input";
import { Label } from "@agiaas/ui/components/label";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectSeparator,
	SelectTrigger,
	SelectValue,
} from "@agiaas/ui/components/select";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import {
	Bot,
	Check,
	Copy,
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
import { toast } from "sonner";
import { orpc } from "../../utils/orpc";

export const Route = createFileRoute("/dashboard/settings/")({
	component: GeneralSettings,
});

function VercelIcon(props: React.SVGProps<SVGSVGElement>) {
	return (
		<svg role="img" viewBox="0 0 24 24" fill="currentColor" {...props}>
			<title>Vercel</title>
			<path d="m12 1.608 12 20.784H0Z" />
		</svg>
	);
}

function CloudflareIcon(props: React.SVGProps<SVGSVGElement>) {
	return (
		<svg role="img" viewBox="0 0 24 24" fill="currentColor" {...props}>
			<title>Cloudflare</title>
			<path d="M16.5088 16.8447c.1475-.5068.0908-.9707-.1553-1.3154-.2246-.3164-.6045-.499-1.0615-.5205l-8.6592-.1123a.1559.1559 0 0 1-.1333-.0713c-.0283-.042-.0351-.0986-.021-.1553.0278-.084.1123-.1484.2036-.1562l8.7359-.1123c1.0351-.0489 2.1601-.8868 2.5537-1.9136l.499-1.3013c.0215-.0561.0293-.1128.0147-.168-.5625-2.5463-2.835-4.4453-5.5499-4.4453-2.5039 0-4.6284 1.6177-5.3876 3.8614-.4927-.3658-1.1187-.5625-1.794-.499-1.2026.119-2.1665 1.083-2.2861 2.2856-.0283.31-.0069.6128.0635.894C1.5683 13.171 0 14.7754 0 16.752c0 .1748.0142.3515.0352.5273.0141.083.0844.1475.1689.1475h15.9814c.0909 0 .1758-.0645.2032-.1553l.12-.4268zm2.7568-5.5634c-.0771 0-.1611 0-.2383.0112-.0566 0-.1054.0415-.127.0976l-.3378 1.1744c-.1475.5068-.0918.9707.1543 1.3164.2256.3164.6055.498 1.0625.5195l1.8437.1133c.0557 0 .1055.0263.1329.0703.0283.043.0351.1074.0214.1562-.0283.084-.1132.1485-.204.1553l-1.921.1123c-1.041.0488-2.1582.8867-2.5527 1.914l-.1406.3585c-.0283.0713.0215.1416.0986.1416h6.5977c.0771 0 .1474-.0489.169-.126.1122-.4082.1757-.837.1757-1.2803 0-2.6025-2.125-4.727-4.7344-4.727" />
		</svg>
	);
}

function SentryIcon(props: React.SVGProps<SVGSVGElement>) {
	return (
		<svg role="img" viewBox="0 0 24 24" fill="currentColor" {...props}>
			<title>Sentry</title>
			<path d="M13.91 2.505c-.873-1.448-2.972-1.448-3.844 0L6.904 7.92a15.478 15.478 0 0 1 8.53 12.811h-2.221A13.301 13.301 0 0 0 5.784 9.814l-2.926 5.06a7.65 7.65 0 0 1 4.435 5.848H2.194a.365.365 0 0 1-.298-.534l1.413-2.402a5.16 5.16 0 0 0-1.614-.913L.296 19.275a2.182 2.182 0 0 0 .812 2.999 2.24 2.24 0 0 0 1.086.288h6.983a9.322 9.322 0 0 0-3.845-8.318l1.11-1.922a11.47 11.47 0 0 1 4.95 10.24h5.915a17.242 17.242 0 0 0-7.885-15.28l2.244-3.845a.37.37 0 0 1 .504-.13c.255.14 9.75 16.708 9.928 16.9a.365.365 0 0 1-.327.543h-2.287c.029.612.029 1.223 0 1.831h2.297a2.206 2.206 0 0 0 1.922-3.31z" />
		</svg>
	);
}

function EmptyField({ children = "Not Set" }: { children?: React.ReactNode }) {
	return (
		<span className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 font-medium text-muted-foreground text-xs ring-1 ring-muted-foreground/20 ring-inset">
			{children}
		</span>
	);
}

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
			{hint && <p className="text-muted-foreground text-xs">{hint}</p>}
		</div>
	);
}

function CopyButton({ text, label }: { text: string; label?: string }) {
	const [copied, setCopied] = useState(false);

	const onCopy = async () => {
		if (!text) return;
		await navigator.clipboard.writeText(text);
		setCopied(true);
		toast.success("Copied to clipboard", {
			description: text,
		});
		setTimeout(() => setCopied(false), 2000);
	};

	return (
		<button
			type="button"
			onClick={onCopy}
			className="group flex w-full min-w-0 max-w-full items-center justify-between gap-2.5 overflow-hidden rounded-md bg-muted/40 px-3 py-1.5 text-left font-mono text-muted-foreground text-xs leading-tight transition-all hover:bg-muted hover:text-foreground active:scale-[0.98]"
			title={text}
		>
			<span className="min-w-0 truncate">{label || text}</span>
			{copied ? (
				<Check className="h-3.5 w-3.5 shrink-0 text-primary" />
			) : (
				<Copy className="h-3.5 w-3.5 shrink-0 opacity-40 transition-opacity group-hover:opacity-100" />
			)}
		</button>
	);
}

function StatusDot({ ok, label }: { ok: boolean; label: string }) {
	return (
		<div className="flex items-center gap-2.5">
			<div className="relative flex h-2 w-2">
				{ok && (
					<span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
				)}
				<span
					className={`relative inline-flex h-2 w-2 rounded-full ${ok ? "bg-primary" : "bg-destructive shadow-[0_0_8px_rgba(var(--destructive),0.5)]"}`}
				/>
			</div>
			<span className="font-medium text-xs tracking-tight">{label}</span>
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

	const baseUrl = tunnelData?.webhookUrl?.replace("/github/webhook", "");

	return (
		<div className="mx-auto max-w-6xl">
			<div className="grid grid-cols-1 gap-8 overflow-visible lg:grid-cols-4 lg:gap-10">
				{/* Left: Status sidebar */}
				<div className="space-y-6 lg:col-span-1">
					{/* gh CLI info */}
					<Card
						className={
							ghCli?.ghUser
								? "border-primary/20 bg-primary/5"
								: "border-border/40"
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
									<p className="pt-1 text-muted-foreground text-xs">
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
					<Card className="border-border/40">
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
								? "border-primary/20 bg-primary/5"
								: "border-border/40"
						}
					>
						<CardHeader className="pb-2">
							<CardTitle className="flex items-center gap-2 text-sm">
								<Webhook className="h-4 w-4 text-primary" />
								External Webhook URL
							</CardTitle>
						</CardHeader>
						<CardContent className="space-y-2 overflow-x-visible">
							{tunnelData?.webhookUrl ? (
								<>
									<CopyButton text={tunnelData.webhookUrl} />
									<p className="text-muted-foreground text-xs">
										Copy this URL and add it to your GitHub Repo → Settings →
										Webhooks
									</p>
								</>
							) : (
								<p className="text-muted-foreground text-xs">
									<span className="animate-pulse">⏳</span> Starting tunnel…
									<br />
									<code className="text-xs">pnpm dev</code> must be running.
								</p>
							)}
						</CardContent>
					</Card>
				</div>

				{/* Right: Projects & Global Settings */}
				<div className="space-y-12 lg:col-span-3">
					{/* ── Active Projects List ── */}
					<div>
						<div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
							<h3 className="font-semibold text-lg tracking-tight">
								Monitored Projects
							</h3>
							<Dialog>
								<DialogTrigger>
									<Button size="sm" className="gap-2">
										<Plus className="h-4 w-4" />
										Add Project
									</Button>
								</DialogTrigger>
								<DialogContent className="sm:max-w-[500px]">
									<DialogHeader>
										<DialogTitle>Add New Project</DialogTitle>
										<DialogDescription>
											Connect a new GitHub repository for Hermes to monitor and
											report via Telegram.
										</DialogDescription>
									</DialogHeader>
									<div className="grid gap-4 py-4">
										<div className="space-y-1.5">
											<Label className="font-semibold text-muted-foreground text-xs uppercase tracking-wider">
												GitHub Repository
											</Label>
											<Select
												value={form.selectedRepo}
												onValueChange={(val) => val && set("selectedRepo")(val)}
											>
												<SelectTrigger className="w-full">
													<SelectValue placeholder="Select a repository..." />
												</SelectTrigger>
												<SelectContent>
													{repos.map(
														(r: {
															nameWithOwner: string;
															isPrivate: boolean;
														}) => (
															<SelectItem
																key={r.nameWithOwner}
																value={r.nameWithOwner}
															>
																<div className="flex items-center gap-2">
																	<span>{r.isPrivate ? "🔒" : "🌐"}</span>
																	<span>{r.nameWithOwner}</span>
																</div>
															</SelectItem>
														),
													)}
												</SelectContent>
											</Select>
										</div>

										<SecretInput
											id="dialogWebhookSecret"
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
											<p className="text-muted-foreground text-xs">
												Required. The ID of the group or user where
												notifications will be sent.
											</p>
										</div>

										<div className="space-y-1.5">
											<Label className="font-semibold text-muted-foreground text-xs uppercase tracking-wider">
												Telegram Bot
											</Label>
											<Select
												value={form.botId}
												onValueChange={(val) => val && set("botId")(val)}
											>
												<SelectTrigger className="w-full">
													<SelectValue placeholder="Select a bot..." />
												</SelectTrigger>
												<SelectContent>
													{bots.map((b) => (
														<SelectItem key={b.id} value={b.id}>
															@{b.username} ({b.name})
														</SelectItem>
													))}
												</SelectContent>
											</Select>
											<p className="text-muted-foreground text-xs">
												Select which bot will handle notifications for this
												project.
											</p>
										</div>

										<div className="space-y-1.5">
											<Label className="font-semibold text-muted-foreground text-xs uppercase tracking-wider">
												Hermes Brain (Model)
											</Label>
											<Select
												value={form.llmModel}
												onValueChange={(val) => val && set("llmModel")(val)}
											>
												<SelectTrigger className="w-full">
													<SelectValue placeholder="Select a model..." />
												</SelectTrigger>
												<SelectContent>
													<SelectGroup>
														<SelectLabel>
															NousResearch (Recommended)
														</SelectLabel>
														<SelectItem value="NousResearch/Hermes-3-Llama-3.1-405B">
															Hermes 3 Llama 3.1 405B
														</SelectItem>
														<SelectItem value="NousResearch/Hermes-3-Llama-3.1-70B">
															Hermes 3 Llama 3.1 70B
														</SelectItem>
														<SelectItem value="NousResearch/Hermes-3-Llama-3.1-8B">
															Hermes 3 Llama 3.1 8B
														</SelectItem>
													</SelectGroup>
													<SelectSeparator />
													<SelectGroup>
														<SelectLabel>OpenAI</SelectLabel>
														<SelectItem value="gpt-4o">GPT-4o</SelectItem>
														<SelectItem value="gpt-4o-mini">
															GPT-4o Mini
														</SelectItem>
													</SelectGroup>
													<SelectSeparator />
													<SelectGroup>
														<SelectLabel>Anthropic</SelectLabel>
														<SelectItem value="anthropic/claude-3-5-sonnet">
															Claude 3.5 Sonnet
														</SelectItem>
														<SelectItem value="anthropic/claude-3-5-haiku">
															Claude 3.5 Haiku
														</SelectItem>
													</SelectGroup>
													<SelectSeparator />
													<SelectGroup>
														<SelectLabel>Other</SelectLabel>
														<SelectItem value="deepseek/deepseek-chat">
															DeepSeek V3
														</SelectItem>
														<SelectItem value="meta-llama/llama-3.3-70b-instruct">
															Llama 3.3 70B
														</SelectItem>
													</SelectGroup>
												</SelectContent>
											</Select>
											<p className="text-muted-foreground text-xs">
												This model will be used to analyze issues and propose
												fixes.
											</p>
										</div>
									</div>
									<div className="flex justify-end">
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
											className="gap-2"
										>
											{addProjectMutation.isPending
												? "Adding..."
												: "Add Project"}
										</Button>
									</div>
								</DialogContent>
							</Dialog>
						</div>
						{projects.length === 0 ? (
							<div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed py-12 text-center text-muted-foreground">
								<div className="rounded-full bg-muted p-3">
									<GitBranch className="h-6 w-6 text-muted-foreground/70" />
								</div>
								<div className="max-w-[200px]">
									<p className="font-medium text-foreground text-sm">
										No projects monitored
									</p>
									<p className="text-xs">
										Add your first repository below to get started.
									</p>
								</div>
							</div>
						) : (
							<div className="grid grid-cols-1 gap-4 lg:grid-cols-1">
								{projects.map((p) => (
									<Card
										key={p.id}
										className={`group overflow-hidden transition-all duration-300 hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5 sm:max-w-2xl ${!p.isActive ? "opacity-60 grayscale-[0.5]" : ""}`}
									>
										<CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-3">
											<div className="flex min-w-0 items-center gap-2.5">
												<div className="shrink-0 rounded-md bg-primary/10 p-1.5 transition-colors group-hover:bg-primary/20">
													<GitBranch className="h-4 w-4 text-primary" />
												</div>
												<CardTitle className="truncate font-bold text-sm tracking-tight">
													{p.repoFullName}
												</CardTitle>
											</div>
											<div className="flex shrink-0 items-center gap-2">
												<button
													type="button"
													className="cursor-pointer"
													onClick={() =>
														toggleProjectMutation.mutate({
															id: p.id,
															isActive: !p.isActive,
														})
													}
												>
													<Badge
														variant={p.isActive ? "default" : "secondary"}
														className="h-5 px-1.5 text-[10px]"
													>
														{p.isActive ? "Active" : "Paused"}
													</Badge>
												</button>
												<button
													type="button"
													className="rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
													onClick={() =>
														deleteProjectMutation.mutate({ id: p.id })
													}
													title="Delete Project"
												>
													<Trash2 className="h-3.5 w-3.5" />
												</button>
											</div>
										</CardHeader>
										<CardContent className="space-y-4 p-4 pt-0 text-[11px] text-muted-foreground">
											<div className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
												<div className="space-y-3">
													<div className="flex flex-col gap-1">
														<span className="font-semibold text-[9px] text-foreground uppercase tracking-widest opacity-70">
															Chat ID
														</span>
														<span
															className="truncate font-medium font-mono"
															title={p.telegramChatId}
														>
															{p.telegramChatId}
														</span>
													</div>
													<div className="flex flex-col gap-1">
														<span className="font-semibold text-[9px] text-foreground uppercase tracking-widest opacity-70">
															Telegram Bot
														</span>
														{p.botId ? (
															<span className="inline-flex items-center gap-1.5 truncate font-medium text-primary">
																<Bot className="h-3 w-3" />@
																{bots.find((b) => b.id === p.botId)?.username ||
																	"Unknown"}
															</span>
														) : (
															<EmptyField>Not Linked</EmptyField>
														)}
													</div>
												</div>

												<div className="space-y-3">
													<div className="flex flex-col gap-1">
														<span className="font-semibold text-[9px] text-foreground uppercase tracking-widest opacity-70">
															Webhook Secret
														</span>
														{p.webhookSecret ? (
															<span className="font-medium font-mono">
																••••••••
															</span>
														) : (
															<EmptyField>Not Set</EmptyField>
														)}
													</div>
													<div className="flex flex-col gap-1">
														<span className="font-semibold text-[9px] text-foreground uppercase tracking-widest opacity-70">
															Hermes Brain
														</span>
														<Select
															value={p.llmModel}
															onValueChange={(val) =>
																val &&
																updateModelMutation.mutate({
																	id: p.id,
																	llmModel: val,
																})
															}
														>
															<SelectTrigger className="mt-0.5 h-7 w-full border-none bg-muted/30 px-2 text-[10px] transition-colors hover:bg-muted/50">
																<SelectValue placeholder="Select model" />
															</SelectTrigger>
															<SelectContent>
																<SelectGroup>
																	<SelectLabel className="text-[10px]">
																		NousResearch
																	</SelectLabel>
																	<SelectItem
																		value="NousResearch/Hermes-3-Llama-3.1-405B"
																		className="text-[11px]"
																	>
																		Hermes 3 405B
																	</SelectItem>
																	<SelectItem
																		value="NousResearch/Hermes-3-Llama-3.1-70B"
																		className="text-[11px]"
																	>
																		Hermes 3 70B
																	</SelectItem>
																	<SelectItem
																		value="NousResearch/Hermes-3-Llama-3.1-8B"
																		className="text-[11px]"
																	>
																		Hermes 3 8B
																	</SelectItem>
																</SelectGroup>
																<SelectSeparator />
																<SelectGroup>
																	<SelectLabel className="text-[10px]">
																		OpenAI
																	</SelectLabel>
																	<SelectItem
																		value="gpt-4o"
																		className="text-[11px]"
																	>
																		GPT-4o
																	</SelectItem>
																	<SelectItem
																		value="gpt-4o-mini"
																		className="text-[11px]"
																	>
																		GPT-4o Mini
																	</SelectItem>
																</SelectGroup>
															</SelectContent>
														</Select>
														{updateModelMutation.isPending && (
															<span className="animate-pulse text-[9px]">
																Saving...
															</span>
														)}
													</div>
												</div>
											</div>

											{/* Integration Webhooks - Compact Collapsible-like section */}
											{baseUrl && (
												<div className="mt-4 space-y-2.5 rounded-md border border-border/40 bg-muted/20 p-3">
													<div className="mb-1 flex items-center justify-between">
														<span className="font-semibold text-[10px] text-foreground uppercase tracking-widest opacity-80">
															Webhooks
														</span>
													</div>
													<div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
														<div className="flex items-center justify-between gap-3 rounded bg-background/50 p-1.5 ring-1 ring-border/50">
															<div className="flex shrink-0 items-center gap-1.5 opacity-70">
																<Github className="h-3 w-3" />
																<span className="font-medium text-[10px]">
																	GitHub
																</span>
															</div>
															<CopyButton
																text={`${baseUrl}/github/webhook`}
																label="Copy"
															/>
														</div>
														<div className="flex items-center justify-between gap-3 rounded bg-background/50 p-1.5 ring-1 ring-border/50">
															<div className="flex shrink-0 items-center gap-1.5 opacity-70">
																<VercelIcon className="h-3 w-3" />
																<span className="font-medium text-[10px]">
																	Vercel
																</span>
															</div>
															<CopyButton
																text={`${baseUrl}/vercel/webhook`}
																label="Copy"
															/>
														</div>
														<div className="flex items-center justify-between gap-3 rounded bg-background/50 p-1.5 ring-1 ring-border/50">
															<div className="flex shrink-0 items-center gap-1.5 opacity-70">
																<CloudflareIcon className="h-3 w-3" />
																<span className="font-medium text-[10px]">
																	CF
																</span>
															</div>
															<CopyButton
																text={`${baseUrl}/cloudflare/webhook`}
																label="Copy"
															/>
														</div>
														<div className="flex items-center justify-between gap-3 rounded bg-background/50 p-1.5 ring-1 ring-border/50">
															<div className="flex shrink-0 items-center gap-1.5 opacity-70">
																<SentryIcon className="h-3 w-3" />
																<span className="font-medium text-[10px]">
																	Sentry
																</span>
															</div>
															<CopyButton
																text={`${baseUrl}/sentry/webhook`}
																label="Copy"
															/>
														</div>
													</div>
												</div>
											)}
										</CardContent>
									</Card>
								))}
							</div>
						)}
					</div>

					{/* ── Bot Management ── */}
					<Card className="overflow-hidden border-border/40">
						<CardHeader className="p-4">
							<CardTitle className="flex items-center gap-2 font-bold text-sm">
								<Bot className="h-4 w-4 text-primary" />
								Bot Management
							</CardTitle>
							<CardDescription className="text-xs">
								Register and manage Telegram bots. We&apos;ll automatically
								fetch their profile info.
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-6 p-4 pt-0">
							{/* Add Bot Form */}
							<div className="flex flex-col gap-2 sm:flex-row">
								<div className="relative flex-1">
									<Key className="absolute top-2.5 left-3 h-4 w-4 text-muted-foreground" />
									<Input
										value={botToken}
										onChange={(e) => setBotToken(e.target.value)}
										placeholder="Enter Bot Token"
										className="h-9 pl-9 font-mono text-xs"
										type="password"
									/>
								</div>
								<Button
									onClick={() => addBotMutation.mutate({ token: botToken })}
									disabled={addBotMutation.isPending || !botToken}
									className="h-9 w-full gap-2 px-4 text-xs sm:w-auto"
								>
									{addBotMutation.isPending ? (
										<span className="animate-spin text-[10px]">⌛</span>
									) : (
										<Plus className="h-4 w-4" />
									)}
									Add Bot
								</Button>
							</div>

							{/* Bot List */}
							<div className="grid gap-2">
								{bots.length === 0 ? (
									<div className="flex flex-col items-center justify-center gap-2.5 overflow-hidden rounded-lg border border-dashed py-6 text-center text-muted-foreground">
										<Bot className="h-5 w-5 opacity-20" />
										<p className="text-[10px]">No bots registered yet.</p>
									</div>
								) : (
									bots.map((bot) => (
										<div
											key={bot.id}
											className="flex flex-col justify-between gap-3 rounded-lg border bg-card p-2.5 transition-colors hover:bg-accent/5 sm:flex-row sm:items-center"
										>
											<div className="flex min-w-0 items-center gap-2.5">
												<div className="h-8 w-8 shrink-0 overflow-hidden rounded-full border bg-muted">
													{bot.avatarUrl ? (
														<img
															src={bot.avatarUrl}
															alt={bot.name}
															className="h-full w-full object-cover"
														/>
													) : (
														<div className="flex h-full w-full items-center justify-center text-muted-foreground">
															<Bot className="h-4 w-4" />
														</div>
													)}
												</div>
												<div className="min-w-0">
													<h4 className="truncate font-bold text-xs leading-none">
														{bot.name}
													</h4>
													<p className="truncate text-[10px] text-muted-foreground">
														@{bot.username}
													</p>
												</div>
											</div>
											<div className="flex shrink-0 items-center gap-2 self-end sm:self-auto">
												{bot.isPrimary ? (
													<Badge
														variant="secondary"
														className="h-5 gap-1 px-1.5 text-[10px]"
													>
														<Check className="h-3 w-3" />
														Primary
													</Badge>
												) : (
													<Button
														variant="outline"
														size="sm"
														onClick={() =>
															setPrimaryBotMutation.mutate({ id: bot.id })
														}
														className="h-6 px-2 text-[10px]"
													>
														Make Primary
													</Button>
												)}
												<button
													type="button"
													className="rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
													onClick={() =>
														deleteBotMutation.mutate({ id: bot.id })
													}
												>
													<Trash2 className="h-3.5 w-3.5" />
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
		</div>
	);
}
