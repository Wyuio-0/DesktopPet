
import urllib.request
import json
url = "https://api.github.com/repos/Wyuio-0/AmiyaDesktopPet/actions/runs"
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode())
    runs = data.get("workflow_runs", [])
    if runs:
        run = runs[0]
        print("Latest run:", run.get("id"), "status:", run.get("status"), "conclusion:", run.get("conclusion"))
        jobs_url = run["jobs_url"]
        with urllib.request.urlopen(jobs_url) as j_resp:
            j_data = json.loads(j_resp.read().decode())
            for job in j_data.get("jobs", []):
                print("  Job", job.get("name"), ":", job.get("conclusion"))

