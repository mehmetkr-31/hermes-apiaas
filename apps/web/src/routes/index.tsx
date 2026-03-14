import { ASCIIText } from "@agiaas/ui/components/ASCIIText";
import { Button } from "@agiaas/ui/components/button";
import { Logo } from "@agiaas/ui/components/logo";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { orpc } from "../utils/orpc";

export const Route = createFileRoute("/")({
	component: HomeComponent,
});

function HomeComponent() {
	const healthCheck = useQuery(orpc.healthCheck.queryOptions());

	return (
		<div className="flex min-h-screen flex-col bg-zinc-950 text-white selection:bg-primary/30">
			{/* Minimal Header */}
			<header className="absolute top-0 z-50 flex w-full items-center justify-between p-6 md:px-12">
				<div className="flex items-center gap-3">
					<Logo className="h-8 w-auto" />
					<span className="font-bold text-xl tracking-tight">AGIaaS</span>
				</div>
				<Link to="/dashboard">
					<Button variant="ghost" className="font-medium">
						Dashboard
					</Button>
				</Link>
			</header>

			{/* Hero Section */}
			<section className="relative flex flex-1 flex-col items-center justify-center overflow-hidden py-24">
				{/* ASCII Background Layer */}
				<div className="pointer-events-none absolute inset-0 z-0 opacity-40">
					<ASCIIText
						text="AGIaaS"
						asciiFontSize={8}
						textFontSize={150}
						textColor="#ffffff"
						enableWaves={true}
						planeBaseHeight={10}
					/>
				</div>

				{/* Content Layer */}
				<div className="container relative z-10 mx-auto px-6 text-center">
					<h1 className="fade-in slide-in-from-bottom-8 mx-auto mb-10 max-w-4xl animate-in bg-gradient-to-b from-white to-white/40 bg-clip-text font-black text-5xl text-transparent tracking-tighter delay-100 duration-1000 lg:text-7xl">
						Build robust AI agents,
						<br />
						with zero friction.
					</h1>

					<div className="fade-in slide-in-from-bottom-12 flex animate-in flex-col items-center justify-center gap-4 delay-200 duration-1000 sm:flex-row">
						<Link to="/dashboard">
							<Button
								size="lg"
								className="h-14 rounded-2xl px-10 font-bold text-base shadow-2xl shadow-primary/20 transition-transform hover:scale-105 active:scale-95"
							>
								Get Started
								<ArrowRight className="ml-2 h-5 w-5" />
							</Button>
						</Link>
					</div>

					<div className="fade-in slide-in-from-bottom-16 mt-16 flex animate-in items-center justify-center gap-2 delay-300 duration-1000">
						<div
							className={`h-2 w-2 rounded-full ${healthCheck.data ? "animate-pulse bg-green-500" : "bg-red-500"}`}
						/>
						<span className="font-medium text-xs text-zinc-500 uppercase tracking-wide">
							{healthCheck.isLoading
								? "Checking status..."
								: healthCheck.data
									? "Systems Operational"
									: "Systems Offline"}
						</span>
					</div>
				</div>

				{/* Ambient Glows */}
				<div className="pointer-events-none absolute top-1/4 -left-20 h-96 w-96 rounded-full bg-primary/10 blur-[120px]" />
				<div className="pointer-events-none absolute -right-20 bottom-1/4 h-96 w-96 rounded-full bg-violet-600/10 blur-[120px]" />
			</section>
		</div>
	);
}
