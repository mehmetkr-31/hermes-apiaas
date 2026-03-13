CREATE TABLE `agent_logs` (
	`id` text PRIMARY KEY NOT NULL,
	`project_id` text NOT NULL,
	`agent_name` text NOT NULL,
	`action` text NOT NULL,
	`prompt` text,
	`response` text,
	`tokens_used` integer DEFAULT 0,
	`duration_ms` integer DEFAULT 0,
	`created_at` integer DEFAULT (strftime('%s', 'now')) NOT NULL
);
--> statement-breakpoint
CREATE TABLE `hermes_secrets` (
	`id` text PRIMARY KEY NOT NULL,
	`project_id` text NOT NULL,
	`key_name` text NOT NULL,
	`encrypted_value` text NOT NULL,
	`created_at` integer DEFAULT (strftime('%s', 'now')) NOT NULL
);
--> statement-breakpoint
ALTER TABLE `hermes_project` ADD `llm_model` text DEFAULT 'gpt-4o-mini' NOT NULL;