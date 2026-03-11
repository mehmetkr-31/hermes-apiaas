import subprocess
import threading
from typing import List

class RemedySubagent:
    def __init__(self, name: str, command: str):
        self.name = name
        self.command = command
        self.status = "pending"
        self.output = ""

    def run(self):
        self.status = "running"
        try:
            result = subprocess.run(self.command, shell=True, capture_output=True, text=True)
            self.output = result.stdout + result.stderr
            self.status = "success" if result.returncode == 0 else "failed"
        except Exception as e:
            self.output = str(e)
            self.status = "error"

def parallel_remediation(tasks: List[dict]):
    agents = [RemedySubagent(t["name"], t["cmd"]) for t in tasks]
    threads = []
    
    for agent in agents:
        t = threading.Thread(target=agent.run)
        threads.append(t)
        t.start()
        print(f"Spawned subagent: {agent.name}")

    for t in threads:
        t.join()

    results = []
    for agent in agents:
        results.append({
            "agent": agent.name,
            "status": agent.status,
            "output": agent.output[:200] + "..." if len(agent.output) > 200 else agent.output
        })
    return results

if __name__ == "__main__":
    mock_tasks = [
        {"name": "DockerRestarter", "cmd": "docker restart api_service"},
        {"name": "CacheCleaner", "cmd": "redis-cli flushall"},
        {"name": "LogRotator", "cmd": "rm -rf /tmp/*.log"}
    ]
    # results = parallel_remediation(mock_tasks)
    # print(results)
    print("Remediation Orchestrator loaded.")
