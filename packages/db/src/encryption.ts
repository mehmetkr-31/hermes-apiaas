import crypto from "node:crypto";

const ALGORITHM = "aes-256-gcm";
const IV_LENGTH = 12;
const TAG_LENGTH = 16;

/**
 * Encrypts a string using AES-256-GCM.
 * Format: base64(iv + tag + ciphertext)
 */
export function encrypt(text: string): string {
	const key = getEncryptionKey();
	const iv = crypto.randomBytes(IV_LENGTH);
	const cipher = crypto.createCipheriv(ALGORITHM, key, iv);

	const encrypted = Buffer.concat([cipher.update(text, "utf8"), cipher.final()]);
	const tag = cipher.getAuthTag();

	// Combine IV + TAG + CIPHERTEXT
	return Buffer.concat([iv, tag, encrypted]).toString("base64");
}

/**
 * Decrypts a string using AES-256-GCM.
 */
export function decrypt(hash: string): string {
	const key = getEncryptionKey();
	const buffer = Buffer.from(hash, "base64");

	const iv = buffer.subarray(0, IV_LENGTH);
	const tag = buffer.subarray(IV_LENGTH, IV_LENGTH + TAG_LENGTH);
	const encrypted = buffer.subarray(IV_LENGTH + TAG_LENGTH);

	const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
	decipher.setAuthTag(tag);

	const decrypted = Buffer.concat([
		decipher.update(encrypted),
		decipher.final(),
	]);

	return decrypted.toString("utf8");
}

function getEncryptionKey(): Buffer {
	const secret = process.env.DB_ENCRYPTION_KEY;
	if (!secret) {
		throw new Error("DB_ENCRYPTION_KEY is not set in environment variables.");
	}

	// Ensure the key is 32 bytes for AES-256
	const buffer = Buffer.from(secret, "utf8");
	if (buffer.length !== 32) {
		// Fallback: hash the key if it's not 32 bytes, but better to enforce 32 bytes
		return crypto.createHash("sha256").update(secret).digest();
	}
	return buffer;
}
