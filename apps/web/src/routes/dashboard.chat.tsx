import { Button } from "@hermes-on-call/ui/components/button";
import {
	Card,
	CardContent,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@hermes-on-call/ui/components/card";
import { Input } from "@hermes-on-call/ui/components/input";
import { useMutation } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import {
	Bot,
	Loader2,
	Send,
	User,
	Zap,
} from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { orpc } from "../utils/orpc";

export const Route = createFileRoute("/dashboard/chat")({
	component: HermesCommander,
});

type Message = {
	role: "user" | "hermes";
	content: string;
	timestamp: Date;
};

function HermesCommander() {
	const [input, setInput] = useState("");
	const [messages, setMessages] = useState<Message[]>([
		{
			role: "hermes",
			content: "I am Hermes. How can I assist you with your systems today?",
			timestamp: new Date(),
		},
	]);
	const scrollRef = useRef<HTMLDivElement>(null);

	const chatMutation = useMutation(
		orpc.onCall.chat.mutationOptions({
			onSuccess: (data) => {
				setMessages((prev) => [
					...prev,
					{
						role: "hermes",
						content: data.response || "No response received.",
						timestamp: new Date(),
					},
				]);
			},
		}),
	);

	const handleSend = () => {
		if (!input.trim() || chatMutation.isPending) return;

		const userMsg: Message = {
			role: "user",
			content: input,
			timestamp: new Date(),
		};

		setMessages((prev) => [...prev, userMsg]);
		setInput("");
		chatMutation.mutate({ message: input });
	};

	useEffect(() => {
		if (scrollRef.current) {
			scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
		}
	}, [messages]);

	return (
		<div className="flex flex-col gap-6 py-4 h-[calc(100vh-140px)]">
			<div className="flex flex-col gap-1">
				<div className="flex items-center gap-2 text-primary font-mono text-xs uppercase tracking-widest">
					<Zap className="h-3 w-3 fill-primary" />
					Direct Uplink
				</div>
				<h1 className="font-extrabold text-3xl tracking-tighter">Hermes Commander</h1>
			</div>

			<Card className="flex flex-col flex-1 overflow-hidden border-primary/10 bg-background shadow-xl">
				<CardHeader className="border-b bg-muted/30 py-3">
					<CardTitle className="flex items-center gap-2 text-sm font-medium">
						<Bot className="h-4 w-4 text-primary" />
						Hermes v1.2.0 (Active)
					</CardTitle>
				</CardHeader>
				
				<CardContent className="flex-1 overflow-hidden p-0 relative bg-zinc-950/5">
					<div 
						ref={scrollRef}
						className="h-full p-4 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800"
					>
						<div className="space-y-4">
							{messages.map((m, i) => (
								<div
									key={i}
									className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : "flex-row"}`}
								>
									<div className={`mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border ${m.role === "user" ? "bg-primary text-primary-foreground border-primary" : "bg-muted border-border"}`}>
										{m.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4 text-primary" />}
									</div>
									<div className={`flex flex-col gap-1 max-w-[80%] ${m.role === "user" ? "items-end" : "items-start"}`}>
										<div className={`rounded-2xl px-4 py-2 text-sm ${m.role === "user" ? "bg-primary text-primary-foreground rounded-tr-none" : "bg-card border border-border rounded-tl-none"}`}>
											<div className="whitespace-pre-wrap font-sans leading-relaxed">
												{m.content}
											</div>
										</div>
										<span className="text-[10px] text-muted-foreground font-mono">
											{m.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
										</span>
									</div>
								</div>
							))}
							{chatMutation.isPending && (
								<div className="flex gap-3">
									<div className="mt-1 flex h-8 w-8 items-center justify-center rounded-full border bg-muted border-border">
										<Bot className="h-4 w-4 text-primary" />
									</div>
									<div className="flex flex-col gap-1">
										<div className="flex items-center gap-2 rounded-2xl bg-card border border-border rounded-tl-none px-4 py-2 text-sm italic text-muted-foreground">
											<Loader2 className="h-3 w-3 animate-spin" />
											Hermes is thinking...
										</div>
									</div>
								</div>
							)}
						</div>
					</div>
				</CardContent>

				<CardFooter className="border-t p-3 bg-background">
					<form 
						onSubmit={(e) => { e.preventDefault(); handleSend(); }}
						className="flex w-full items-center gap-2"
					>
						<Input
							placeholder="Type a command or ask a question..."
							value={input}
							onChange={(e) => setInput(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter" && !e.shiftKey) {
									e.preventDefault();
									handleSend();
								}
							}}
							className="flex-1 bg-muted/50 border-border focus-visible:ring-primary h-11"
						/>
						<Button 
							type="submit" 
							disabled={chatMutation.isPending || !input.trim()}
							size="icon"
							className="h-11 w-11 shadow-md transition-all active:scale-95"
						>
							<Send className="h-4 w-4" />
						</Button>
					</form>
				</CardFooter>
			</Card>
		</div>
	);
}
