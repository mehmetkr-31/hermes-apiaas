export function Logo({ className = "h-6 w-auto" }: { className?: string }) {
	return (
		<svg
			xmlns="http://www.w3.org/2000/svg"
			viewBox="0 0 100 100"
			className={className}
			fill="none"
			role="img"
		>
			<title>APIaaS Logo</title>
			<defs>
				<linearGradient id="logoGradient" x1="10%" y1="10%" x2="90%" y2="90%">
					<stop offset="0%" stopColor="hsl(var(--primary))" />
					<stop offset="100%" stopColor="#8b5cf6" />
				</linearGradient>
				<filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
					<feGaussianBlur stdDeviation="4" result="blur" />
					<feComposite in="SourceGraphic" in2="blur" operator="over" />
				</filter>
			</defs>

			{/* Hexagon Base - Represents Infrastructure/Services */}
			<path
				d="M50 8L86.6 29.13V70.87L50 92L13.4 70.87V29.13L50 8Z"
				stroke="url(#logoGradient)"
				strokeWidth="6"
				strokeLinejoin="round"
				className="opacity-90"
			/>

			{/* Inner Node 1 - AI Agent */}
			<circle cx="35" cy="40" r="6" fill="url(#logoGradient)" />

			{/* Inner Node 2 - API Gateway */}
			<circle cx="65" cy="40" r="6" fill="url(#logoGradient)" />

			{/* Inner Node 3 - Data Base */}
			<circle cx="50" cy="65" r="6" fill="url(#logoGradient)" />

			{/* Interconnections */}
			<path
				d="M38 45L47 60M62 45L53 60M42 40H58"
				stroke="url(#logoGradient)"
				strokeWidth="4"
				strokeLinecap="round"
				className="opacity-70"
			/>

			{/* Center Spark / Energy */}
			<path
				d="M50 30L53 45L65 48L53 51L50 66L47 51L35 48L47 45Z"
				fill="white"
				className="opacity-80"
			/>
		</svg>
	);
}
