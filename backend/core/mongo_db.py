from pymongo import MongoClient
import os
import logging
from mongo_schema import MongoSchemaManager, RetryableMongoDB, StorageOptimizer, ConfidenceScoringOptimizer, VALIDATION_RESULTS_V2_COLLECTION

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI") or "mongodb://localhost:27017"

client = MongoClient(MONGO_URI)
mongo_db = client["brochure_ai"]

# Legacy collection (for backwards compatibility)
validation_collection = mongo_db["validation_results"]

# New versioned collection (v2)
validation_collection_v2 = mongo_db[VALIDATION_RESULTS_V2_COLLECTION]

# Initialize schema and indexes
schema_manager = MongoSchemaManager(db=mongo_db)
try:
    schema_manager.initialize_schema()
    logger.info("✓ MongoDB schema initialized with indexes and versioning")
except Exception as e:
    logger.error(f"⚠ MongoDB schema initialization failed: {str(e)}")
    logger.info("⚠ Continuing without schema initialization (non-critical)")

# Create retry-safe wrapper for new collection
retry_db = RetryableMongoDB(validation_collection_v2, max_retries=3, base_delay=1.0)
