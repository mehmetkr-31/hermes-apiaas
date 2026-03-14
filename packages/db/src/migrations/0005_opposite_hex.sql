CREATE TABLE `hermes_bots` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`username` text NOT NULL,
	`token` text NOT NULL,
	`avatar_url` text,
	`is_primary` integer DEFAULT false NOT NULL,
	`created_at` integer DEFAULT (strftime('%s', 'now')) NOT NULL
);
--> statement-breakpoint
ALTER TABLE `hermes_project` ADD `bot_id` text;