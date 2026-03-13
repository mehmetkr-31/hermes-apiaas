import time
from scripts.on_call.monitor import get_system_stats, check_endpoints
from scripts.on_call.reasoning import mixture_of_agents_debate
from scripts.on_call.research import web_research, session_research
from scripts.on_call.remediation import parallel_remediation
from scripts.on_call.reporter import send_telegram_message, format_incident_report
from scripts.on_call.runbook_generator import generate_runbook

def run_on_call_loop():
    print("On-Call Agent is now on duty. 🎯")
    while True:
        stats = get_system_stats()
        endpoints = check_endpoints()
        
        # Detect anomaly
        critical_endpoints = [ep for ep in endpoints if ep["status"] == "down"]
        if critical_endpoints or stats["cpu_percent"] > 90:
            print("🚨 Anomaly detected! Starting investigation...")
            
            context = f"System Stats: {stats}\nBroken Endpoints: {critical_endpoints}"
            
            # Step 2: Reason
            analysis = mixture_of_agents_debate(context)
            
            # Step 3: Research
            web_findings = web_research(analysis)
            history = session_research(analysis)
            
            # Step 4: Remediate (Parallel)
            # In a real scenario, the agent would decide these commands based on analysis
            fix_tasks = [
                {"name": "Restarter", "cmd": "echo 'Restarting service...'"},
                {"name": "CacheManager", "cmd": "echo 'Clearing cache...'"}
            ]
            remedy_results = parallel_remediation(fix_tasks)
            
            # Step 5: Report
            report_data = {
                "timestamp": time.ctime(),
                "summary": f"Detected failures in {len(critical_endpoints)} services.",
                "actions": "\n".join([f"- {r['agent']}: {r['status']}" for r in remedy_results]),
                "result": "System stabilized (Simulated)"
            }
            report_text = format_incident_report(report_data)
            send_telegram_message(report_text)
            
            # Step 6: Learn
            generate_runbook({
                "title": f"Incident {time.ctime()}",
                "root_cause": analysis,
                "symptoms": context,
                "resolution": report_data["actions"],
                "lessons": "Autonomous remediation successful."
            })
            
            print("✅ Incident resolved and documented.")
            
        time.sleep(120)

if __name__ == "__main__":
    run_on_call_loop()
