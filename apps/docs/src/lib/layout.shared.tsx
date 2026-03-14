import { Logo } from "@agiaas/ui/components/logo";
import type { BaseLayoutProps } from "fumadocs-ui/layouts/shared";

export const gitConfig = {
	user: "mehmetkr-31",
	repo: "agiaas",
	branch: "main",
};

export function baseOptions(): BaseLayoutProps {
	return {
		nav: {
			title: (
				<div className="flex items-center gap-2">
					<Logo className="h-6 w-auto" />
					<span className="font-bold text-lg tracking-tight">AGIaaS Docs</span>
				</div>
			),
		},
		githubUrl: `https://github.com/${gitConfig.user}/${gitConfig.repo}`,
	};
}
