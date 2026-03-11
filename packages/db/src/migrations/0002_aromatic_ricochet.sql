CREATE TABLE `approvals` (
	`id` text PRIMARY KEY NOT NULL,
	`status` text DEFAULT 'pending' NOT NULL,
	`message_id` text,
	`chat_id` text,
	`metadata` text,
	`created_at` integer DEFAULT (strftime('%s', 'now')) NOT NULL
);
