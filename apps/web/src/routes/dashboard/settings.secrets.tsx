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
import { Eye, EyeOff, Key, Trash2 } from "lucide-react";
import { useState } from "react";
import { orpc } from "../../utils/orpc";

export const Route = createFileRoute("/dashboard/settings/secrets")({
	component: SecretsSettings,
});

function SecretInput({
	id,
	label,
	value,
	onChange,
	placeholder,
}: {
	id: string;
	label: string;
	value: string;
	onChange: (v: string) => void;
	placeholder?: string;
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
		</div>
	);
}

function SecretsSettings() {
	const queryClient = useQueryClient();
	const [selectedProjectId, setSelectedProjectId] = useState<string>("");
	const [newSecret, setNewSecret] = useState({ keyName: "", value: "" });

	const { data: projectsData } = useQuery({
		...orpc.github.listProjects.queryOptions(),
	});

	const { data: secretsData } = useQuery({
		...orpc.secrets.listSecrets.queryOptions({
			input: { projectId: selectedProjectId },
		}),
		enabled: !!selectedProjectId,
	});

	const setSecretMutation = useMutation(
		orpc.secrets.setSecret.mutationOptions({
			onSuccess: () => {
				queryClient.invalidateQueries();
				setNewSecret({ keyName: "", value: "" });
			},
		}),
	);

	const deleteSecretMutation = useMutation(
		orpc.secrets.deleteSecret.mutationOptions({
			onSuccess: () => queryClient.invalidateQueries(),
		}),
	);

	const projects = projectsData?.projects ?? [];
	const secrets = secretsData?.secrets ?? [];

	return (
		<div className="space-y-8">
			<Card>
				<CardHeader>
					<CardTitle>Secrets Management</CardTitle>
					<CardDescription>
						Manage secure API keys and environment variables for your agents.
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-6">
					<div className="space-y-1.5">
						<Label className="font-semibold text-muted-foreground text-xs uppercase tracking-wider">
							Select Project
						</Label>
						<select
							value={selectedProjectId}
							onChange={(e) => setSelectedProjectId(e.target.value)}
							className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
						>
							<option value="">Select a project...</option>
							{projects.map((p) => (
								<option key={p.id} value={p.id}>
									{p.repoFullName}
								</option>
							))}
						</select>
					</div>

					{selectedProjectId && (
						<div className="space-y-6 border-t pt-6">
							{/* New Secret Form */}
							<div className="grid gap-4 sm:grid-cols-2">
								<div className="space-y-1.5">
									<Label className="text-xs uppercase tracking-wider">
										Key Name (e.g. OPENAI_API_KEY)
									</Label>
									<Input
										value={newSecret.keyName}
										onChange={(e) =>
											setNewSecret({ ...newSecret, keyName: e.target.value })
										}
										placeholder="MY_SECRET_KEY"
										className="font-mono text-xs"
									/>
								</div>
								<SecretInput
									id="newSecretValue"
									label="Value"
									value={newSecret.value}
									onChange={(val) => setNewSecret({ ...newSecret, value: val })}
									placeholder="sk-..."
								/>
							</div>
							<Button
								onClick={() =>
									setSecretMutation.mutate({
										projectId: selectedProjectId,
										keyName: newSecret.keyName,
										value: newSecret.value,
									})
								}
								disabled={
									!newSecret.keyName ||
									!newSecret.value ||
									setSecretMutation.isPending
								}
								className="w-full"
							>
								{setSecretMutation.isPending
									? "Saving..."
									: "Add/Update Secret"}
							</Button>

							{/* Secrets List */}
							<div className="space-y-4">
								<h4 className="font-semibold text-sm">Stored Secrets</h4>
								{secrets.length === 0 ? (
									<p className="text-muted-foreground text-xs italic">
										No secrets stored for this project.
									</p>
								) : (
									<div className="grid gap-2">
										{secrets.map((s) => (
											<div
												key={s.id}
												className="flex items-center justify-between rounded-md border bg-muted/50 p-2"
											>
												<code className="font-bold text-xs">{s.keyName}</code>
												<div className="flex items-center gap-2">
													<span className="text-[10px] text-muted-foreground">
														{new Date(s.createdAt).toLocaleDateString()}
													</span>
													<Button
														variant="ghost"
														size="icon"
														className="h-7 w-7 text-muted-foreground hover:text-destructive"
														onClick={() =>
															deleteSecretMutation.mutate({ id: s.id })
														}
													>
														<Trash2 className="h-3.5 w-3.5" />
													</Button>
												</div>
											</div>
										))}
									</div>
								)}
							</div>
						</div>
					)}
				</CardContent>
			</Card>
		</div>
	);
}
