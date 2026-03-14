import { ASCIIText } from "@agiaas/ui/components/ASCIIText";
import { Button } from "@agiaas/ui/components/button";
import { Logo } from "@agiaas/ui/components/logo";
import { createFileRoute, Link } from "@tanstack/react-router";
import { HomeLayout } from "fumadocs-ui/layouts/home";
import { ArrowRight } from "lucide-react";
import { baseOptions } from "@/lib/layout.shared";

export const Route = createFileRoute("/")({
	component: Home,
});

function Home() {
	return (
		<HomeLayout {...baseOptions()}>
			<div className="relative flex min-h-[calc(100vh-64px)] flex-1 flex-col overflow-hidden bg-zinc-950 text-white selection:bg-fd-primary/30">
				{/* ASCII Background Layer */}
				<div className="pointer-events-none absolute inset-0 z-0 opacity-40">
					<ASCIIText
						text="AGIAAS"
						asciiFontSize={8}
						textFontSize={typeof window !== "undefined" && window.innerWidth < 768 ? 80 : 150}
						textColor="#ffffff"
						enableWaves={true}
						planeBaseHeight={10}
					/>
				</div>

				{/* Content Layer */}
				<div className="container relative z-10 mx-auto flex flex-1 flex-col justify-center px-6 py-20 text-center sm:py-24">
					<div className="mb-8 flex justify-center">
						<Logo className="h-16 w-auto sm:h-20" />
					</div>

					<h1 className="fade-in slide-in-from-bottom-8 mx-auto mb-8 max-w-4xl animate-in bg-gradient-to-b from-white to-white/40 bg-clip-text font-black text-4xl text-transparent tracking-tighter delay-100 duration-1000 sm:text-6xl lg:text-7xl">
						Documentation,
						<br />
						simplified.
					</h1>

					<p className="fade-in slide-in-from-bottom-10 mx-auto mb-10 max-w-2xl animate-in text-base text-zinc-400 delay-150 duration-1000 sm:mb-12 sm:text-lg">
						Learn how to build, deploy, and manage autonomous AI agents with
						AGIAAS. Everything you need to master our intelligent incident
						management platform.
					</p>

					<div className="fade-in slide-in-from-bottom-12 flex animate-in flex-col items-center justify-center gap-4 delay-200 duration-1000 sm:flex-row">
						<Link to="/docs/$" params={{ _splat: "" }}>
							<Button
								size="lg"
								className="h-12 w-full rounded-2xl px-10 font-bold text-base shadow-2xl shadow-primary/20 transition-transform hover:scale-105 active:scale-95 sm:h-14 sm:w-auto"
							>
								Explore Docs
								<ArrowRight className="ml-2 h-5 w-5" />
							</Button>
						</Link>
					</div>
				</div>

				{/* Ambient Glows */}
				<div className="pointer-events-none absolute top-1/4 -left-20 h-96 w-96 rounded-full bg-fd-primary/10 blur-[120px]" />
				<div className="pointer-events-none absolute -right-20 bottom-1/4 h-96 w-96 rounded-full bg-violet-600/10 blur-[120px]" />
			</div>
		</HomeLayout>
	);
}
