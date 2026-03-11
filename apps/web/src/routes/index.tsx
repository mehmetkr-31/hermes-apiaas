import { Button } from "@hermes-on-call/ui/components/button";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, Zap } from "lucide-react";
import ASCIIText from "../components/ASCIIText";
import { orpc } from "../utils/orpc";

export const Route = createFileRoute("/")({
	component: HomeComponent,
});

function HomeComponent() {
	const healthCheck = useQuery(orpc.healthCheck.queryOptions());

	return (
		<div className="flex min-h-screen flex-col bg-zinc-950 text-white selection:bg-primary/30">
			{/* Hero Section */}
			<section className="relative flex flex-1 flex-col items-center justify-center overflow-hidden py-24">
				{/* ASCII Background Layer */}
				<div className="pointer-events-none absolute inset-0 z-0 opacity-40">
					<ASCIIText
						text="APIaaS"
						asciiFontSize={8}
						textFontSize={150}
						textColor="#ffffff"
						enableWaves={true}
						planeBaseHeight={10}
					/>
				</div>

				{/* Content Layer */}
				<div className="container relative z-10 mx-auto px-6 text-center">
					<div className="fade-in slide-in-from-bottom-4 mb-8 inline-flex animate-in items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 font-semibold text-primary text-xs uppercase tracking-wider duration-1000">
						<Zap className="h-3 w-3 fill-primary" />
						Agentic API Infrastructure
					</div>

					<h1 className="fade-in slide-in-from-bottom-8 mx-auto mb-8 max-w-4xl animate-in bg-gradient-to-b from-white to-white/40 bg-clip-text font-black text-5xl text-transparent tracking-tighter delay-100 duration-1000 lg:text-7xl">
						Build robust AI agents,
						<br />
						with zero friction.
					</h1>

					<p className="fade-in slide-in-from-bottom-12 mx-auto mb-12 max-w-2xl animate-in text-lg text-zinc-400 delay-200 duration-1000">
						Deploy scalable, reliable, and secure agentic APIs in seconds. Focus
						on your AI logic, we handle the infrastructure.
					</p>

					<div className="fade-in slide-in-from-bottom-16 flex animate-in flex-col items-center justify-center gap-4 delay-300 duration-1000 sm:flex-row">
						<Link to="/dashboard">
							<Button
								size="lg"
								className="h-14 rounded-2xl px-8 font-bold text-base shadow-2xl shadow-primary/20 transition-transform hover:scale-105 active:scale-95"
							>
								Enter Dashboard
								<ArrowRight className="ml-2 h-5 w-5" />
							</Button>
						</Link>
					</div>

					<div className="fade-in slide-in-from-bottom-20 mt-12 flex animate-in items-center justify-center gap-2 delay-500 duration-1000">
						<div
							className={`h-2.5 w-2.5 rounded-full ${healthCheck.data ? "animate-pulse bg-green-500" : "bg-red-500"}`}
						/>
						<span className="font-medium text-sm text-zinc-500">
							{healthCheck.isLoading
								? "Checking API status..."
								: healthCheck.data
									? "API is online and operational"
									: "API is offline"}
						</span>
					</div>
				</div>

				{/* Ambient Glows */}
				<div className="pointer-events-none absolute top-1/4 -left-20 h-96 w-96 rounded-full bg-primary/10 blur-[120px]" />
				<div className="pointer-events-none absolute -right-20 bottom-1/4 h-96 w-96 rounded-full bg-violet-600/10 blur-[120px]" />
			</section>

			<footer className="container mx-auto border-zinc-900 px-6 py-8 text-center text-sm text-zinc-600">
				APIaaS Platform ● Built for AI Agents
			</footer>
		</div>
	);
}
