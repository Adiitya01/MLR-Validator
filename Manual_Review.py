import logging
import json
import os
import time
import numpy as np
from Gemini_version import GeminiClient

logger = logging.getLogger(__name__)


def validate_manual_review_multi(statement: str, pdf_files: list, references: list) -> dict:
    """
    Validate a single statement against MULTIPLE PDFs.
    Mirrors the aggregation logic from Gemini_version.validate_statement_against_all_papers.
    
    Args:
        statement: The claim to validate
        pdf_files: List of Gemini-uploaded PDF file objects
        references: List of reference labels (one per PDF)
    
    Returns:
        Aggregated result dict with combined evidence from all PDFs
    """
    logger.info(f"[MANUAL REVIEW MULTI] Validating against {len(pdf_files)} PDFs")
    
    individual_results = []
    
    for idx, (pdf_file, ref_label) in enumerate(zip(pdf_files, references), 1):
        try:
            # Throttle to avoid rate limiting
            if idx > 1:
                time.sleep(0.5)
            
            logger.info(f"[MANUAL REVIEW MULTI] [{idx}/{len(pdf_files)}] Validating against: {ref_label}")
            result = validate_manual_review(statement, pdf_file, ref_label)
            individual_results.append(result)
            logger.info(f"[MANUAL REVIEW MULTI] [{idx}] Result: {result.get('validation_result', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"[MANUAL REVIEW MULTI] [{idx}] ERROR: {str(e)}")
            individual_results.append({
                "statement": statement,
                "reference": ref_label,
                "validation_result": "Error",
                "matched_evidence": f"Request failed: {str(e)}",
                "page_location": "N/A",
                "confidence_score": 0.0,
                "analysis_summary": f"Error during validation: {str(e)}"
            })
    
    # If only one PDF, return its result directly
    if len(individual_results) == 1:
        return individual_results[0]
    
    # AGGREGATE results using priority: Supported > Contradicted > Not Found > Error
    supported = [r for r in individual_results if r.get("validation_result") == "Supported"]
    contradicted = [r for r in individual_results if r.get("validation_result") == "Contradicted"]
    not_found = [r for r in individual_results if r.get("validation_result") == "Not Found"]
    errors = [r for r in individual_results if r.get("validation_result") == "Error"]
    
    if supported:
        final_result = "Supported"
        result_list = supported
    elif contradicted:
        final_result = "Contradicted"
        result_list = contradicted
    elif not_found:
        final_result = "Not Found"
        result_list = not_found
    else:
        final_result = "Error"
        result_list = errors
    
    # Combine evidence from all relevant results
    combined_evidence_lines = []
    for res in result_list:
        ref = res.get("reference", "Unknown")
        evidence = str(res.get("matched_evidence", "")).strip()
        if evidence:
            combined_evidence_lines.append(f"[{ref}]: {evidence}")
        else:
            combined_evidence_lines.append(f"[{ref}]: No evidence text provided")
    
    combined_evidence = " | ".join(combined_evidence_lines)
    
    # Average confidence from relevant results
    scores = [r.get("confidence_score", 0.0) for r in result_list]
    avg_confidence = float(np.mean(scores)) if scores else 0.0
    
    # Combine page locations
    page_locations = [r.get("page_location", "") for r in result_list if r.get("page_location")]
    combined_page_location = " | ".join(page_locations)
    
    # Combine analysis summaries
    analysis_parts = [f"[{r.get('reference', '?')}]: {r.get('analysis_summary', '')}" for r in result_list if r.get("analysis_summary")]
    combined_analysis = " || ".join(analysis_parts)
    
    all_refs = ", ".join(references)
    
    aggregated = {
        "statement": statement,
        "reference": all_refs,
        "validation_result": final_result,
        "matched_evidence": combined_evidence,
        "page_location": combined_page_location,
        "confidence_score": round(avg_confidence, 4),
        "analysis_summary": combined_analysis,
        "pdfs_checked": len(pdf_files),
        "pdfs_supporting": len(supported)
    }
    
    logger.info(f"[MANUAL REVIEW MULTI] Final: {final_result} ({avg_confidence:.0%}) from {len(pdf_files)} PDFs")
    return aggregated


def validate_manual_review(statement: str, pdf_file, reference: str) -> dict:
    """
    Enhanced validation specifically for manual review requests.
    Uses the GeminiClient to process a single statement against a PDF.
    """
    
    # Initialize client (will load API key from .env)
    client = GeminiClient()
    
    if not client.client:
        logger.error("[MANUAL REVIEW] Gemini client failed to initialize")
        return {
            "statement": statement,
            "reference": reference,
            "validation_result": "Error",
            "matched_evidence": "Gemini API key is missing or invalid.",
            "page_location": "Check environment configuration",
            "confidence_score": 0.0,
            "analysis_summary": "Gemini client initialization failed"
        }

    prompt = f"""You are an expert scientific researcher and claim validator. 
A user is performing a MANUAL REVIEW of a claim against a specific document.

---CLAIM TO VALIDATE---
"{statement}"

---DOCUMENT CONTEXT---
Reference Label: {reference}

---TASK---
Thoroughly analyze the provided document to determine if this specific claim is supported.
1. Be extremely precise. Match specific numbers, dates, and names.
2. If the claim is supported, extract the EXACT text as evidence.
3. If it is contradicted, find the contradicting text.
4. If not mentioned, state that clearly.

---RESPONSE FORMAT (MANDATORY JSON)---
{{
    "validation_result": "Supported" or "Contradicted" or "Not Found",
    "matched_evidence": "Exact quotes from paper (max 5 sentences, separated by | if multiple)",
    "page_location": "Context describing where in paper evidence appears",
    "confidence_score": confidence_score_here,
    "analysis_summary": "Extremely detailed explanation of why this verdict was reached."
}
(where confidence_score_here is a float between 0.0 and 1.0 reflecting your actual certainty)}

CRITICAL RULES:
- Return ONLY valid JSON.
- matched_evidence MUST be verbatim text from the document.
- analysis_summary should be helpful for a human reviewer.
"""

    try:
        # Query Gemini using the pdf_file reference
        response_text = client._query_llm_with_pdf(prompt, pdf_file, temperature=0.1, max_output_tokens=2048)
        
        # Clean up response text if it has markdown blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        try:
            parsed = json.loads(response_text)
            
            # Ensure matched_evidence is a string
            if isinstance(parsed.get("matched_evidence"), list):
                parsed["matched_evidence"] = " | ".join([str(e).strip() for e in parsed["matched_evidence"] if e])
            
            parsed["statement"] = statement
            parsed["reference"] = reference
            return parsed
            
        except json.JSONDecodeError:
            # Fallback parsing for partial JSON
            logger.warning(f"[MANUAL REVIEW] JSON parse failed, attempting fallback")
            start = response_text.find('{')
            end = response_text.rfind('}')
            if start != -1 and end != -1:
                try:
                    parsed = json.loads(response_text[start:end+1])
                    parsed["statement"] = statement
                    parsed["reference"] = reference
                    return parsed
                except:
                    pass
            
            return {
                "statement": statement,
                "reference": reference,
                "validation_result": "Manual Review Required",
                "matched_evidence": response_text[:500],
                "page_location": "N/A",
                "confidence_score": 0.5,
                "analysis_summary": "Response received but could not be parsed into structured format."
            }
            
    except Exception as e:
        logger.error(f"[MANUAL REVIEW] Error: {str(e)}")
        return {
            "statement": statement,
            "reference": reference,
            "validation_result": "Error",
            "matched_evidence": f"Request failed: {str(e)}",
            "page_location": "N/A",
            "confidence_score": 0.0,
            "analysis_summary": f"System error during manual validation: {str(e)}"
        }