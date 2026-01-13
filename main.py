# main.py

import argparse
import logging
import sys
import json
from app.website_loader import load_website_content
from app.text_cleaner import clean_text, chunk_text
from app.summarizer import summarize_company
from app.prompt_generator import generate_user_prompts
from app.evaluator import evaluate_visibility

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def run_simple_pipeline(url: str, points: str = ""):
    """Simplified pipeline: URL + Points -> Prompts"""
    logger.info(f"Starting Simple Pipeline for: {url}")
    
    try:
        # 1. Gather Context
        raw_text = ""
        if url:
            logger.info("Fetching website context...")
            raw_text = load_website_content(url)
        
        clean = clean_text(raw_text)
        chunks = chunk_text(clean)

        # 2. Analyze Company
        logger.info("Combining website info and manual points...")
        company_profile = summarize_company(chunks, manual_points=points)
        logger.info(f"Targeting: {company_profile.company_name}")

        # 3. Generate Prompts
        logger.info("Generating AI Search Visibility test prompts...")
        prompts = generate_user_prompts(company_profile)

        # 4. Display Result
        print("\n" + "═" * 60)
        print(f" COMPANY: {company_profile.company_name}")
        print(f" INDUSTRY: {company_profile.industry}")
        print("═" * 60)
        print("\n[SUGGESTED AI TEST PROMPTS]")
        for i, p in enumerate(prompts, 1):
            print(f" {i}. [{p.intent_category}]")
            print(f"    \"{p.prompt_text}\"\n")
        print("═" * 60)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple GEO Prompt Pipeline")
    parser.add_argument("url", nargs="?", default="", help="Company website URL")
    parser.add_argument("--points", "-p", default="", help="Manual points/details about the company")
    
    args = parser.parse_args()
    
    if not args.url and not args.points:
        logger.error("Please provide either a URL or manual points.")
        sys.exit(1)
        
    run_simple_pipeline(args.url, args.points)
