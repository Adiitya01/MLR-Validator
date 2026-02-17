"""
TEST SCRIPT FOR VALIDATION API
Quick tests for all endpoints
"""

import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8000/api/validation"

def print_header(text):
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")

# ============================================================================
# TEST 1: HEALTH CHECK
# ============================================================================
def test_health():
    print_header("TEST 1: Health Check")
    response = requests.get(f"{BASE_URL}/health")
    print(json.dumps(response.json(), indent=2))
    assert response.status_code == 200
    print("✅ Health check passed")

# ============================================================================
# TEST 2: EXTRACT FROM PDF
# ============================================================================
def test_extract(pdf_path):
    print_header("TEST 2: Extract from PDF")
    
    if not Path(pdf_path).exists():
        print(f"⚠️  PDF not found: {pdf_path}")
        print("   Skipping extraction test")
        return None
    
    with open(pdf_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(f"{BASE_URL}/extract", files=files)
    
    result = response.json()
    print(json.dumps(result, indent=2))
    
    if response.status_code == 200 and result.get('success'):
        print(f"✅ Extraction successful - {result['total_records']} records found")
        return result
    else:
        print("❌ Extraction failed")
        return None

# ============================================================================
# TEST 3: CONVERT TO VALIDATION FORMAT
# ============================================================================
def test_convert(records):
    print_header("TEST 3: Convert to Validation Format")
    
    if not records:
        print("⚠️  No records to convert")
        return None
    
    payload = {
        "records": records,
        "references": {
            "1": "Test Reference 1",
            "2": "Test Reference 2"
        }
    }
    
    response = requests.post(
        f"{BASE_URL}/convert",
        json=payload,
        headers={'Content-Type': 'application/json'}
    )
    
    result = response.json()
    print(json.dumps(result, indent=2))
    
    if response.status_code == 200 and result.get('success'):
        print(f"✅ Conversion successful - {result['total_rows']} rows generated")
        return result.get('validation_rows')
    else:
        print("❌ Conversion failed")
        return None

# ============================================================================
# TEST 4: VALIDATE STATEMENTS
# ============================================================================
def test_validate(reference_pdfs):
    print_header("TEST 4: Validate Statements")
    
    # Check if reference PDFs exist
    existing_pdfs = [p for p in reference_pdfs if Path(p).exists()]
    
    if not existing_pdfs:
        print(f"⚠️  No reference PDFs found")
        print("   Skipping validation test")
        return None
    
    print(f"Using {len(existing_pdfs)} reference PDF(s)")
    
    # Prepare multipart form data
    files = [('files', open(pdf, 'rb')) for pdf in existing_pdfs]
    data = {
        'statement': 'amikacin. pH. 3.5-5.5',
        'reference_no': '1',
        'reference_text': 'Johnson et al. (2020). pH stability of antibiotics.'
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/validate",
            files=files,
            data=data
        )
        
        result = response.json()
        print(json.dumps(result, indent=2))
        
        if response.status_code == 200 and result.get('success'):
            print(f"✅ Validation successful")
            print(f"   Summary: {result['summary']}")
            return result
        else:
            print("❌ Validation failed")
            return None
    finally:
        for f in files:
            f[1].close()

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================
def main():
    print("\n" + "🧪 VALIDATION API TEST SUITE".center(70))
    print("="*70)
    
    # Test 1: Health Check
    try:
        test_health()
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return
    
    # Test 2: Extract (if PDF exists)
    pdf_path = "Downloads/BD_Drugs_list - ICC (All Antibiotics)_20250911.pdf"
    extracted = test_extract(pdf_path)
    
    # Test 3: Convert
    if extracted:
        records = extracted.get('records', [])
        converted = test_convert(records)
    
    # Test 4: Validate
    reference_pdfs = [
        "Downloads/reference_paper_1.pdf",
        "Downloads/reference_paper_2.pdf",
    ]
    test_validate(reference_pdfs)
    
    print_header("TEST SUITE COMPLETE")
    print("✅ All available tests completed")

if __name__ == "__main__":
    print("\n📝 Make sure to:")
    print("   1. Start the server: python -m uvicorn app:app --reload")
    print("   2. Update PDF paths in this script")
    print("   3. Run this script: python test_api.py\n")
    
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to API")
        print("   Make sure the server is running on http://localhost:8000")
    except Exception as e:
        print(f"❌ ERROR: {e}")
