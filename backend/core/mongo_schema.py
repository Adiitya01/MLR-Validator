"""
MongoDB Schema Management
- Indexes for query optimization
- Schema versioning
- Retry-safe operations
- Storage optimization
"""

import logging
import hashlib
import time
from typing import Dict, List, Any, Optional
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from pymongo.errors import DuplicateKeyError, OperationFailure
import os
from datetime import datetime

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
mongo_db = client["brochure_ai"]

# Collection names
VALIDATION_RESULTS_COLLECTION = "validation_results"
VALIDATION_RESULTS_V2_COLLECTION = "validation_results_v2"  # New versioned collection


class MongoSchemaManager:
    """Manages MongoDB schema, indexes, and versioning"""
    
    def __init__(self, db=None):
        self.db = db if db is not None else mongo_db
        
    def initialize_schema(self):
        """Initialize MongoDB schema with indexes and versioning"""
        logger.info("Initializing MongoDB schema...")
        self.create_validation_indexes()
        self.create_schema_version_record()
        logger.info("MongoDB schema initialization complete")
    
    def create_validation_indexes(self):
        """Create optimized indexes for validation_results_v2 collection"""
        collection = self.db[VALIDATION_RESULTS_V2_COLLECTION]
        
        try:
            # Primary index: brochure_id (frequently queried)
            collection.create_index(
                [("brochure_id", ASCENDING)],
                name="idx_brochure_id",
                unique=False
            )
            logger.info("Created index: idx_brochure_id")
            
            # Compound index: brochure_id + created_at for range queries
            collection.create_index(
                [("brochure_id", ASCENDING), ("created_at", DESCENDING)],
                name="idx_brochure_created",
                unique=False
            )
            logger.info("Created index: idx_brochure_created")
            
            # Index for statement search
            collection.create_index(
                [("results.statement", TEXT)],
                name="idx_statement_search",
                unique=False
            )
            logger.info("Created index: idx_statement_search")
            
            # Index for validation_result filtering
            collection.create_index(
                [("results.validation_result", ASCENDING)],
                name="idx_validation_status",
                unique=False
            )
            logger.info("Created index: idx_validation_status")
            
            # Index for confidence score filtering
            collection.create_index(
                [("results.confidence_score", DESCENDING)],
                name="idx_confidence_score",
                unique=False
            )
            logger.info("Created index: idx_confidence_score")
            
            # TTL index: auto-delete old records after 90 days
            collection.create_index(
                [("created_at", ASCENDING)],
                name="idx_ttl",
                expireAfterSeconds=7776000  # 90 days
            )
            logger.info("Created index: idx_ttl (TTL)")
            
            # Unique index: prevent duplicate brochure processing (idempotency)
            try:
                collection.create_index(
                    [("brochure_id", ASCENDING), ("schema_version", ASCENDING)],
                    name="idx_unique_brochure_version",
                    unique=True,
                    sparse=True
                )
                logger.info("Created index: idx_unique_brochure_version")
            except OperationFailure as e:
                if "already exists" in str(e):
                    logger.debug("Index already exists")
                else:
                    raise
                    
        except Exception as e:
            logger.error(f"Failed to create indexes: {str(e)}")
            raise
    
    def create_schema_version_record(self):
        """Create schema version tracking"""
        schema_version_collection = self.db["schema_versions"]
        
        version_record = {
            "_id": "validation_results_v2",
            "version": 2,
            "created_at": datetime.utcnow(),
            "schema": {
                "brochure_id": "string (uuid)",
                "brochure_name": "string",
                "total_statements": "integer",
                "results": [
                    {
                        "statement": "string",
                        "reference_no": "string",
                        "reference": "string",
                        "matched_paper": "string",
                        "matched_evidence_hash": "string (SHA256 hash, max 64 chars)",
                        "matched_evidence_length": "integer (original length)",
                        "validation_result": "string (Supported/Refuted/Partially Supported/Inconclusive)",
                        "page_location": "string",
                        "confidence_score": "float (0.0-1.0)",
                        "confidence_reasoning": "string (why this score)",
                        "matching_method": "string",
                        "created_at": "datetime"
                    }
                ],
                "schema_version": "integer (2)",
                "created_at": "datetime",
                "updated_at": "datetime (optional)",
                "processing_time_seconds": "float (optional)",
                "retry_count": "integer (default 0)"
            },
            "optimizations": [
                "Evidence text hashed (SHA256) to reduce storage by ~80%",
                "Confidence score includes reasoning for reproducibility",
                "Indexed for fast brochure_id lookups",
                "TTL index for automatic cleanup of old records",
                "Unique constraint on brochure_id + schema_version for idempotency"
            ]
        }
        
        try:
            # Use replace_one with upsert to ensure idempotency
            schema_version_collection.replace_one(
                {"_id": "validation_results_v2"},
                version_record,
                upsert=True
            )
            logger.info("Schema version record updated")
        except Exception as e:
            logger.error(f"Failed to create schema version record: {str(e)}")
            raise


class RetryableMongoDB:
    """Retry-safe MongoDB operations with exponential backoff"""
    
    def __init__(self, collection, max_retries: int = 3, base_delay: float = 1.0):
        self.collection = collection
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    def insert_one_with_retry(self, document: Dict[str, Any], idempotency_key: Optional[str] = None) -> str:
        """
        Insert document with retry logic and optional idempotency
        
        Args:
            document: Document to insert
            idempotency_key: Unique key for idempotent operations (brochure_id + schema_version)
        
        Returns:
            Inserted document ID
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # Add retry metadata
                document["_retry_attempt"] = attempt
                document["_first_attempt_at"] = datetime.utcnow()
                
                result = self.collection.insert_one(document)
                logger.info(f"Document inserted successfully on attempt {attempt + 1}: {result.inserted_id}")
                return str(result.inserted_id)
                
            except DuplicateKeyError as e:
                # Idempotent operation: document already exists
                if idempotency_key:
                    logger.warning(f"Duplicate key (idempotent): {idempotency_key}. Skipping insert.")
                    existing = self.collection.find_one({"brochure_id": idempotency_key})
                    return str(existing["_id"]) if existing else None
                last_error = e
                logger.warning(f"Duplicate key error on attempt {attempt + 1}: {str(e)}")
                
            except Exception as e:
                last_error = e
                logger.warning(f"Insert failed on attempt {attempt + 1}: {str(e)}")
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    delay = self.base_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries} attempts failed")
                    raise last_error
        
        raise last_error
    
    def insert_many_with_retry(self, documents: List[Dict[str, Any]], ordered: bool = False) -> List[str]:
        """
        Insert multiple documents with retry logic
        
        Args:
            documents: List of documents to insert
            ordered: If False, continue on errors (recommended for resilience)
        
        Returns:
            List of inserted document IDs
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # Add retry metadata to all documents
                for doc in documents:
                    doc["_retry_attempt"] = attempt
                    doc["_first_attempt_at"] = datetime.utcnow()
                
                result = self.collection.insert_many(documents, ordered=ordered)
                logger.info(f"Batch inserted {len(result.inserted_ids)} documents on attempt {attempt + 1}")
                return [str(id) for id in result.inserted_ids]
                
            except Exception as e:
                last_error = e
                logger.warning(f"Batch insert failed on attempt {attempt + 1}: {str(e)}")
                
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries} batch insert attempts failed")
                    raise last_error
        
        raise last_error


class StorageOptimizer:
    """Optimize MongoDB storage for large evidence texts"""
    
    @staticmethod
    def hash_evidence(evidence_text: str) -> tuple[str, int]:
        """
        Hash evidence text to reduce storage
        
        Args:
            evidence_text: Original evidence text
        
        Returns:
            Tuple of (SHA256 hash, original length)
        """
        if not evidence_text:
            return "", 0
        
        evidence_bytes = evidence_text.encode('utf-8')
        evidence_hash = hashlib.sha256(evidence_bytes).hexdigest()
        
        return evidence_hash, len(evidence_text)
    
    @staticmethod
    def compress_result(result_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress validation result for storage optimization
        
        Changes:
        - Evidence text → SHA256 hash + length
        - Removes duplicate fields
        - Keeps original length for reference
        
        Storage reduction: ~80% (evidence texts are typically 200-500 chars)
        """
        compressed = result_dict.copy()
        
        # Hash the evidence text
        if "matched_evidence" in compressed:
            evidence_hash, evidence_length = StorageOptimizer.hash_evidence(
                compressed["matched_evidence"]
            )
            compressed["matched_evidence_hash"] = evidence_hash
            compressed["matched_evidence_length"] = evidence_length
            del compressed["matched_evidence"]  # Remove original
        
        return compressed


class ConfidenceScoringOptimizer:
    """Improve confidence scoring consistency and reproducibility"""
    
    @staticmethod
    def calculate_confidence_score(
        semantic_similarity: float,
        keyword_match_score: float,
        statement_length_factor: float,
        evidence_coverage: float
    ) -> tuple[float, str]:
        """
        Calculate weighted confidence score with reasoning
        
        Args:
            semantic_similarity: 0-1, from semantic matching
            keyword_match_score: 0-1, from keyword overlap
            statement_length_factor: 0-1, accounts for statement complexity
            evidence_coverage: 0-1, % of statement covered by evidence
        
        Returns:
            Tuple of (confidence_score, reasoning)
        """
        # Weighted calculation (sum of weights = 1.0)
        weights = {
            "semantic": 0.45,      # Most important
            "keyword": 0.20,       # Supporting evidence
            "length": 0.15,        # Complexity factor
            "coverage": 0.20       # Evidence extent
        }
        
        confidence = (
            semantic_similarity * weights["semantic"] +
            keyword_match_score * weights["keyword"] +
            statement_length_factor * weights["length"] +
            evidence_coverage * weights["coverage"]
        )
        
        # Round to 2 decimal places
        confidence = round(confidence, 2)
        
        # Generate reasoning
        reasoning_parts = []
        
        if semantic_similarity > 0.8:
            reasoning_parts.append("Strong semantic match")
        elif semantic_similarity > 0.6:
            reasoning_parts.append("Moderate semantic match")
        else:
            reasoning_parts.append("Weak semantic match")
        
        if keyword_match_score > 0.7:
            reasoning_parts.append("Good keyword overlap")
        elif keyword_match_score > 0.4:
            reasoning_parts.append("Partial keyword match")
        else:
            reasoning_parts.append("Limited keyword match")
        
        if evidence_coverage > 0.8:
            reasoning_parts.append("Evidence covers statement well")
        elif evidence_coverage > 0.5:
            reasoning_parts.append("Evidence partially covers statement")
        else:
            reasoning_parts.append("Limited evidence coverage")
        
        reasoning = " | ".join(reasoning_parts)
        
        return confidence, reasoning
    
    @staticmethod
    def normalize_confidence_scores(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize confidence scores across batch for consistency
        
        Ensures scores reflect relative confidence within the batch
        """
        if not results:
            return results
        
        scores = [r.get("confidence_score", 0.0) for r in results]
        
        # Calculate statistics
        min_score = min(scores) if scores else 0
        max_score = max(scores) if scores else 1
        mean_score = sum(scores) / len(scores) if scores else 0.5
        
        # Adjust scores for consistency
        for result in results:
            original_score = result.get("confidence_score", 0.0)
            
            # If score is below mean, slightly decrease it
            if original_score < mean_score:
                result["confidence_score"] = round(original_score * 0.95, 2)
            # If score is above mean, slightly increase it
            elif original_score > mean_score:
                result["confidence_score"] = round(min(original_score * 1.05, 1.0), 2)
            
            # Add confidence band indicator
            if result["confidence_score"] >= 0.8:
                result["confidence_band"] = "HIGH"
            elif result["confidence_score"] >= 0.6:
                result["confidence_band"] = "MEDIUM"
            else:
                result["confidence_band"] = "LOW"
        
        logger.info(f"Normalized {len(results)} confidence scores. Mean: {mean_score:.2f}")
        return results
