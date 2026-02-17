import requests
import os
import time
import json
from pathlib import Path

BASE_URL = "http://127.0.0.1:8001/api"
EMAIL = "stress_test_user@example.com"
PASSWORD = "Password123!"

RESEARCH_PDF = r"C:\Users\aditya.pasare\Downloads\BD-164897 Midline compendium articles 20-25 (1).pdf"
DRUG_PDF = r"C:\Users\aditya.pasare\Downloads\BD_Drugs list - ICC (All Antibiotics)_20250911.pdf"

def run_stress_test():
    print("🔥 Starting MLR Pipeline Stress Test 🔥")
    
    # 1. Signup / Login
    print("\n[1] Authenticating...")
    session = requests.Session()
    
    # Try signup (ignore if exists)
    requests.post(f"{BASE_URL}/auth/signup/", json={
        "email": EMAIL,
        "password": PASSWORD,
        "full_name": "Stress Test User"
    })
    
    login_resp = session.post(f"{BASE_URL}/auth/login/", json={
        "email": EMAIL,
        "password": PASSWORD
    })
    
    if login_resp.status_code != 200:
        print(f"❌ Login failed: {login_resp.text}")
        return
    
    token = login_resp.json().get('access')
    session.headers.update({"Authorization": f"Bearer {token}"})
    print("✅ Authenticated")

    # 1.5 Security Check (Unauthorized request)
    print("\n[1.5] Security Check: testing unauthorized access...")
    no_auth_resp = requests.get(f"{BASE_URL}/validator/history/")
    if no_auth_resp.status_code == 401:
        print("✅ Security Check Passed: Unauthorized access blocked (401)")
    else:
        print(f"❌ Security Check Failed: Got status {no_auth_resp.status_code}")

    jobs = []

    # 2. Queue Research Job
    if os.path.exists(RESEARCH_PDF):
        print(f"\n[2] Queuing RESEARCH job: {Path(RESEARCH_PDF).name}")
        with open(RESEARCH_PDF, 'rb') as f:
            files = {
                'brochure_pdf': f,
                'reference_pdfs': ('dummy_ref.pdf', b'%PDF-1.4\n%test')
            }
            data = {'validation_type': 'research'}
            resp = session.post(f"{BASE_URL}/validator/upload/", files=files, data=data)
            if resp.status_code == 201:
                job_id = resp.json()['job_id']
                print(f"✅ Research Job Queued: {job_id}")
                jobs.append((job_id, "research"))
            else:
                print(f"❌ Research Queue Failed: {resp.text}")
    else:
        print(f"⚠️ Research PDF not found: {RESEARCH_PDF}")

    # 3. Queue Drug Job
    if os.path.exists(DRUG_PDF):
        print(f"\n[3] Queuing DRUG job: {Path(DRUG_PDF).name}")
        with open(DRUG_PDF, 'rb') as f:
            files = {
                'brochure_pdf': f,
                'reference_pdfs': ('dummy_ref.pdf', b'%PDF-1.4\n%test')
            }
            data = {'validation_type': 'drug'}
            resp = session.post(f"{BASE_URL}/validator/upload/", files=files, data=data)
            if resp.status_code == 201:
                job_id = resp.json()['job_id']
                print(f"✅ Drug Job Queued: {job_id}")
                jobs.append((job_id, "drug"))
            else:
                print(f"❌ Drug Queue Failed: {resp.text}")
    else:
        print(f"⚠️ Drug PDF not found: {DRUG_PDF}")

    if not jobs:
        print("❌ No jobs queued. Exiting.")
        return

    # 4. Monitor Jobs
    print("\n[4] Monitoring Jobs (Real Async check)...")
    completed = []
    start_time = time.time()
    
    while len(completed) < len(jobs) and (time.time() - start_time) < 300: # 5 mins max
        for i, (job_id, jtype) in enumerate(jobs):
            if job_id in completed:
                continue
                
            resp = session.get(f"{BASE_URL}/validator/result/{job_id}/")
            if resp.status_code == 200:
                data = resp.json()
                status = data.get('status')
                print(f"   - Job {job_id[:8]} ({jtype}): {status}")
                if status in ['completed', 'failed']:
                    completed.append(job_id)
                    print(f"     ✅ Job {jtype} finished with status: {status}")
            else:
                print(f"   - Error checking job {job_id[:8]}: {resp.status_code}")
        
        if len(completed) < len(jobs):
            time.sleep(5)

    print("\n[5] Stress Test Results Summary")
    print(f"Total Jobs: {len(jobs)}")
    print(f"Completed: {len(completed)}")
    print(f"Total Time: {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    run_stress_test()
