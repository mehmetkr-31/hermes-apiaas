import { Badge } from "@hermes-on-call/ui/components/badge";
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
import { Separator } from "@hermes-on-call/ui/components/separator";
import { Skeleton } from "@hermes-on-call/ui/components/skeleton";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import {
	Activity,
	BookOpen,
	Bot,
	ChevronRight,
	Eye,
	EyeOff,
	GitBranch,
	Github,
	Key,
	Link2,
	Server,
	Settings2,
	Terminal,
	Trash2,
	Webhook,
	Zap,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { orpc } from "../utils/orpc";

export const Route = createFileRoute("/dashboard/settings")({
	component: SettingsDashboard,
});

// ─────────────────────────────────────────────────────────
// Types & helpers
// ─────────────────────────────────────────────────────────
type Tab = "settings" | "logs" | "activity";

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

// ─────────────────────────────────────────────────────────
// Settings tab
// ─────────────────────────────────────────────────────────
function SettingsTab() {
	const queryClient = useQueryClient();

	const { data: reposData } = useQuery({
		...orpc.github.listRepos.queryOptions(),
		staleTime: 60_000,
	});

	const { data: projectsData } = useQuery({
		...orpc.github.listProjects.queryOptions(),
		refetchInterval: 5000,
	});

	const { data: telegramConfig } = useQuery({
		...orpc.github.getGlobalTelegramBotConfig.queryOptions(),
		refetchInterval: 5000,
	});

	const [tgForm, setTgForm] = useState({ telegramBotToken: "" });
	const [seededTg, setSeededTg] = useState(false);
	useEffect(() => {
		if (!seededTg && telegramConfig?.telegramBotToken) {
			setTgForm({ telegramBotToken: telegramConfig.telegramBotToken });
			setSeededTg(true);
		}
	}, [telegramConfig, seededTg]);

	const [form, setForm] = useState({
		githubWebhookSecret: "",
		telegramChatId: "",
		selectedRepo: "",
	});
	const set = (key: keyof typeof form) => (v: string) =>
		setForm((f) => ({ ...f, [key]: v }));

	// Mutators
	const addProjectMutation = useMutation(
		orpc.github.addProject.mutationOptions({
			onSuccess: () => {
				queryClient.invalidateQueries();
				setForm((f) => ({ ...f, webhookSecret: "", telegramChatId: "" })); // Keep repo selected
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

	const saveTgMutation = useMutation(
		orpc.github.saveGlobalTelegramBotConfig.mutationOptions({
			onSuccess: () => queryClient.invalidateQueries(),
		}),
	);

	const repos = reposData?.repos ?? [];
	const projects = projectsData?.projects ?? [];

	const { data: ghCli } = useQuery({
		...orpc.github.getGhCliUser.queryOptions(),
		staleTime: 60_000,
	});

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
			<div className="space-y-4 lg:col-span-4">
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
								<StatusDot ok label={`@${ghCli.ghUser}`} />
								<p className="pt-1 text-[10px] text-muted-foreground">
									{repos.length} repo erişilebilir
								</p>
							</>
						) : (
							<>
								<StatusDot ok={false} label="gh CLI not authenticated" />
								<p className="pt-1 text-[10px] text-muted-foreground">
									Run{" "}
									<code className="rounded bg-muted px-1">gh auth login</code>
								</p>
							</>
						)}
					</CardContent>
				</Card>

				{/* Connection status */}
				<Card className="border-border/50">
					<CardHeader className="pb-2">
						<CardTitle className="flex items-center gap-2 text-sm">
							<Link2 className="h-4 w-4 text-primary" />
							Status
						</CardTitle>
					</CardHeader>
					<CardContent className="space-y-3">
						<StatusDot
							ok={!!webhookStatus?.running}
							label={
								webhookStatus?.running
									? `Webhook :${webhookStatus.port}`
									: "Webhook Offline"
							}
						/>
						<StatusDot
							ok={!!telegramConfig?.telegramBotToken}
							label={
								telegramConfig?.telegramBotToken
									? "Telegram Configured"
									: "Telegram Not Set"
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
							Webhook URL
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
									Tıkla → kopyala → GitHub repo → Settings → Webhooks
								</p>
							</>
						) : (
							<p className="text-[11px] text-muted-foreground">
								<span className="animate-pulse">⏳</span> Tunnel başlatılıyor…
								<br />
								<code className="text-[10px]">pnpm dev</code> çalışıyor olmalı.
							</p>
						)}
						<div className="mt-1 space-y-1 text-[11px] text-muted-foreground">
							<div className="flex items-center gap-1">
								<ChevronRight className="h-3 w-3" /> Content-type:
								application/json
							</div>
							<div className="flex items-center gap-1">
								<ChevronRight className="h-3 w-3" /> Events: Issues, PRs,
								Workflow runs
							</div>
							<div className="flex items-center gap-1">
								<ChevronRight className="h-3 w-3" /> Secret: webhook secret
								alanına gir
							</div>
						</div>
					</CardContent>
				</Card>

				{/* Telegram commands */}
				<Card className="border-border/50">
					<CardHeader className="pb-2">
						<CardTitle className="flex items-center gap-2 text-sm">
							<Bot className="h-4 w-4 text-blue-400" />
							Telegram Commands
						</CardTitle>
					</CardHeader>
					<CardContent className="space-y-1.5 font-mono text-[11px]">
						{[
							["/status", "Aktif olaylar"],
							["/logs [n]", "Son N satır log"],
							["/rollback <id>", "Action'ı yeniden çalıştır"],
							["/issue <no>", "Issue detayı"],
							["/approve", "Onayla"],
						].map(([cmd, desc]) => (
							<div key={cmd} className="flex items-start gap-2">
								<span className="font-bold text-primary">{cmd}</span>
								<span className="text-muted-foreground">{desc}</span>
							</div>
						))}
					</CardContent>
				</Card>
			</div>

			{/* Right: Projects & Global Settings */}
			<div className="space-y-8 lg:col-span-8">
				{/* ── Active Projects List ── */}
				<div>
					<h3 className="mb-4 font-semibold text-lg tracking-tight">
						İzlenen Projeler
					</h3>
					{projects.length === 0 ? (
						<div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">
							Henüz izlenen bir repo yok. Aşağıdan yeni proje ekleyin.
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
												{p.isActive ? "Aktif" : "Pasif"}
											</button>
											<button
												type="button"
												className="rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
												onClick={() =>
													deleteProjectMutation.mutate({ id: p.id })
												}
												title="Prejeyi Sil"
											>
												<Trash2 className="h-4 w-4" />
											</button>
										</div>
									</CardHeader>
									<CardContent className="flex gap-4 text-muted-foreground text-xs">
										<div>
											<span className="font-semibold text-foreground">
												Chat ID:
											</span>{" "}
											{p.telegramChatId}
										</div>
										<div>
											<span className="font-semibold text-foreground">
												Secret:
											</span>{" "}
											{p.webhookSecret ? "••••••••" : "Yok"}
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
						<CardTitle className="text-base">Yeni Proje Ekle</CardTitle>
						<CardDescription>
							Hermes'in olaylarını izleyip Telegram'a bildireceği yeni bir
							GitHub reposu bağla.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="space-y-1.5">
							<Label className="font-semibold text-muted-foreground text-xs uppercase tracking-wider">
								Repo
							</Label>
							<select
								value={form.selectedRepo}
								onChange={(e) => set("selectedRepo")(e.target.value)}
								className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
							>
								<option value="" disabled>
									Repo Seçin...
								</option>
								{repos.map((r) => (
									<option key={r.nameWithOwner} value={r.nameWithOwner}>
										{r.isPrivate ? "🔒 " : "🌐 "}
										{r.nameWithOwner}
										{r.description ? ` — ${r.description.slice(0, 50)}` : ""}
									</option>
								))}
							</select>
						</div>

						<SecretInput
							id="webhookSecret"
							label="Webhook Secret"
							value={form.githubWebhookSecret}
							onChange={set("githubWebhookSecret")}
							placeholder="my-super-secret-key"
							hint="GitHub → repo → Settings → Webhooks → Secret"
						/>

						<div className="space-y-1.5">
							<Label className="font-semibold text-muted-foreground text-xs uppercase tracking-wider">
								Telegram Chat ID (Bu projeye özel)
							</Label>
							<Input
								value={form.telegramChatId}
								onChange={(e) => set("telegramChatId")(e.target.value)}
								placeholder="-100123456789"
								className="font-mono text-sm"
							/>
							<p className="text-[11px] text-muted-foreground">
								Zorunlu. Bu projenin bildirimleri hangi grupta/kişide görünecek?
							</p>
						</div>

						<Button
							onClick={() =>
								addProjectMutation.mutate({
									repoFullName: form.selectedRepo,
									webhookSecret: form.githubWebhookSecret,
									telegramChatId: form.telegramChatId,
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
							{addProjectMutation.isPending ? "Ekleniyor..." : "Projeyi Ekle"}
						</Button>
					</CardContent>
				</Card>

				{/* ── Global Telegram Config ── */}
				<Card>
					<CardHeader>
						<CardTitle className="flex items-center gap-2">
							<Bot className="h-5 w-5 text-blue-400" />
							Global Telegram Bot
						</CardTitle>
						<CardDescription>
							Tüm projeler için kullanılacak ortak Telegram Botu'nun Token'ı.
							(@BotFather)
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						<SecretInput
							id="tgToken"
							label="Bot Token"
							value={tgForm.telegramBotToken}
							onChange={(val) => setTgForm({ telegramBotToken: val })}
							placeholder="123456789:ABCdef..."
						/>
						<Button
							onClick={() => saveTgMutation.mutate(tgForm)}
							disabled={saveTgMutation.isPending || !tgForm.telegramBotToken}
							variant="secondary"
							className="gap-2"
						>
							{saveTgMutation.isPending
								? "Kaydediliyor..."
								: "Bot Token Kaydet"}
						</Button>
					</CardContent>
				</Card>
			</div>
		</div>
	);
}

// ─────────────────────────────────────────────────────────
// Logs tab (Hermes telemetry stream)
// ─────────────────────────────────────────────────────────
function LogsTab() {
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
			style={{ height: "calc(100vh - 280px)", minHeight: "500px" }}
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
							{[...Array(6)].map((_, i) => (
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
								Run:{" "}
								<code className="rounded bg-zinc-900 px-1">
									python webhook_receiver.py
								</code>
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
									Buffer Empty
								</p>
								<p className="text-[10px] opacity-30">
									Agent henüz çalışmadı veya log yok.
								</p>
							</div>
						</div>
					)}
				</div>
			</CardContent>
		</Card>
	);
}

// ─────────────────────────────────────────────────────────
// GitHub Activity tab
// ─────────────────────────────────────────────────────────
function GitHubActivityTab() {
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
		<div className="grid gap-6 lg:grid-cols-12">
			{/* Stats row */}
			<div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:col-span-12">
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
							? `Port ${webhookStatus.port} ●`
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
						label: "GitHub Events",
						value: `${githubLogs.length} events`,
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
			<div className="lg:col-span-12">
				<Card>
					<CardHeader>
						<CardTitle className="flex items-center gap-2 text-base">
							<Zap className="h-4 w-4 text-amber-500" />
							GitHub Event Feed
						</CardTitle>
						<CardDescription>
							GitHub webhook'larından Hermes'e gelen real-time olaylar
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
									<p className="font-semibold text-sm">GitHub olayı yok</p>
									<p className="text-xs opacity-60">
										Webhook sunucusu çalışıyorken repo'da PR veya Issue aç
									</p>
								</div>
							</div>
						)}
					</CardContent>
				</Card>
			</div>
		</div>
	);
}

// ─────────────────────────────────────────────────────────
// Main page component
// ─────────────────────────────────────────────────────────
function SettingsDashboard() {
	const [activeTab, setActiveTab] = useState<Tab>("settings");

	const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
		{
			id: "settings",
			label: "Ayarlar",
			icon: <Settings2 className="h-4 w-4" />,
		},
		{
			id: "logs",
			label: "Hermes Logs",
			icon: <Terminal className="h-4 w-4" />,
		},
		{
			id: "activity",
			label: "GitHub Aktivite",
			icon: <Github className="h-4 w-4" />,
		},
	];

	return (
		<div className="flex flex-col gap-8 py-4">
			{/* Header */}
			<div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
				<div className="space-y-1">
					<div className="flex items-center gap-2">
						<Badge
							variant="outline"
							className="border-primary/20 bg-primary/5 px-2 py-0 font-mono text-primary text-xs"
						>
							GitHub Integration
						</Badge>
					</div>
					<h1 className="font-extrabold text-4xl tracking-tighter">
						Hermes Control Panel
					</h1>
					<p className="text-lg text-muted-foreground">
						GitHub entegrasyonunu yapılandır, logları izle ve olayları yönet.
					</p>
				</div>
			</div>

			{/* Tab bar */}
			<div className="flex w-fit gap-1 rounded-xl border border-border bg-muted/30 p-1">
				{tabs.map((tab) => (
					<button
						key={tab.id}
						type="button"
						onClick={() => setActiveTab(tab.id)}
						className={`flex items-center gap-2 rounded-lg px-4 py-2 font-medium text-sm transition-all ${
							activeTab === tab.id
								? "bg-background text-foreground shadow-sm"
								: "text-muted-foreground hover:text-foreground"
						}`}
					>
						{tab.icon}
						{tab.label}
					</button>
				))}
			</div>

			{/* Tab content */}
			<div>
				{activeTab === "settings" && <SettingsTab />}
				{activeTab === "logs" && <LogsTab />}
				{activeTab === "activity" && <GitHubActivityTab />}
			</div>
		</div>
	);
}
