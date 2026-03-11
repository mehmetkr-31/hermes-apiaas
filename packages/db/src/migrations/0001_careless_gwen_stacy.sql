CREATE TABLE `global_config` (
	`key` text PRIMARY KEY NOT NULL,
	`value` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `hermes_project` (
	`id` text PRIMARY KEY NOT NULL,
	`repo_full_name` text NOT NULL,
	`webhook_secret` text NOT NULL,
	`telegram_chat_id` text NOT NULL,
	`is_active` integer DEFAULT true NOT NULL,
	`created_at` integer DEFAULT (strftime('%s', 'now')) NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `hermes_project_repo_full_name_unique` ON `hermes_project` (`repo_full_name`);