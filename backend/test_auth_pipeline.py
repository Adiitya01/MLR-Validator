
import requests
import time
import os

# CONFIG
BASE_URL = "http://127.0.0.1:8001/api"
EMAIL = f"testuser_{int(time.time())}@example.com"
PASSWORD = "StrongPassword123!"

def run_test():
    print(f"🚀 Starting Pipeline Test on {BASE_URL}")
    
    # 0. Health Check (New Compatibility Endpoint)
    print("\n[0] Checking Legacy Health...")
    resp = requests.get(f"{BASE_URL}/validator/health/")
    print(f"Status: {resp.status_code}, Response: {resp.json()}")
    if resp.status_code != 200:
        print("❌ Health Check Failed!")
        return
    # 1. Signup
    print(f"\n[1] Signing up as {EMAIL}...")
    try:
        resp = requests.post(f"{BASE_URL}/auth/signup/", json={
            "email": EMAIL,
            "password": PASSWORD,
            "full_name": "Test User"
        })
        print(f"Status: {resp.status_code}")
        if resp.status_code != 201:
            print("Signup Failed:", resp.text)
            return
    except Exception as e:
        print(f"Connection Failed: {e}")
        return

    # 2. Login
    print(f"\n[2] Logging in...")
    resp = requests.post(f"{BASE_URL}/auth/login/", json={
        "email": EMAIL,
        "password": PASSWORD
    })
    if resp.status_code != 200:
        print("Login Failed:", resp.text)
        return
        
    access_token = resp.json()['access']
    print("✅ Got Access Token")

    # 3. Use real PDF for upload
    REAL_PDF_PATH = r"C:\Users\aditya.pasare\Downloads\BD-164897 Midline compendium articles 20-25 (1).pdf"
    
    if not os.path.exists(REAL_PDF_PATH):
        print(f"❌ Real PDF not found at {REAL_PDF_PATH}. Creating dummy as fallback...")
        with open("dummy_brochure.pdf", "wb") as f:
            f.write(b"%PDF-1.4 dummy content")
        brochure_file = ('dummy_brochure.pdf', open('dummy_brochure.pdf', 'rb'), 'application/pdf')
    else:
        print(f"✅ Using real PDF: {REAL_PDF_PATH}")
        brochure_file = ('brochure_pdf', open(REAL_PDF_PATH, 'rb'), 'application/pdf')

    # Create dummy reference just for completion
    with open("dummy_ref.pdf", "wb") as f:
        f.write(b"%PDF-1.4 dummy reference content")

    # 4. Upload
    print(f"\n[4] Uploading Document for Validation...")
    headers = {"Authorization": f"Bearer {access_token}"}
    files = [
        ('brochure_pdf', brochure_file),
        ('reference_pdfs', ('dummy_ref.pdf', open('dummy_ref.pdf', 'rb'), 'application/pdf'))
    ]
    data = {"validation_type": "research"}
    
    resp = requests.post(
        f"{BASE_URL}/validator/upload/", 
        headers=headers,
        files=files,
        data=data
    )
    
    # Cleanup
    try:
        os.remove("dummy_brochure.pdf")
        os.remove("dummy_ref.pdf")
    except:
        pass

    if resp.status_code != 201:
        print("❌ Upload Failed:", resp.text)
        return
        
    job_data = resp.json()
    job_id = job_data['job_id']
    print(f"✅ Job Queued! ID: {job_id}")

    # 5. Check Status (Polling)
    print(f"\n[5] Checking Status for Job {job_id}...")
    for i in range(5):
        resp = requests.get(
            f"{BASE_URL}/validator/result/{job_id}/", 
            headers=headers
        )
        status_data = resp.json()
        state = status_data.get('status')
        print(f"   Attempt {i+1}: Status = {state}")
        
        if state in ['completed', 'failed']:
            print(f"\n🎉 Final Result: {state}")
            print("Result Data (Snippet):", str(status_data)[:200])
            break
        
        time.sleep(2)

if __name__ == "__main__":
    try:
        run_test()
    except KeyboardInterrupt:
        print("\nTest Cancelled")
