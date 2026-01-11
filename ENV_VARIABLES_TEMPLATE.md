# Template for Render Free Tier Environment Variables
# Add these to Render Dashboard for each service

# ============================================
# BACKEND SERVICE ENVIRONMENT VARIABLES
# ============================================
# Render Dashboard → mlr-backend → Environment → Add these variables

ENVIRONMENT=production
LOG_LEVEL=INFO

# Security
SECRET_KEY=your-random-32-character-string-generate-this
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# API Keys
GEMINI_API_KEY=your-google-gemini-api-key

# Databases (Get from Supabase and MongoDB Atlas)
DATABASE_URL=postgresql://postgres:PASSWORD@HOST:6543/postgres
MONGODB_URI=mongodb+srv://mlr_user:PASSWORD@cluster.mongodb.net/mlr_db

# CORS Configuration (Update after frontend deployment)
CORS_ORIGINS=https://mlr-frontend-XXXXX.render.com

# API Configuration
API_HOST=0.0.0.0
# API_PORT is automatically $PORT in Render

# ============================================
# FRONTEND SERVICE ENVIRONMENT VARIABLES
# ============================================
# Render Dashboard → mlr-frontend → Environment → Add these variables

NODE_VERSION=18
REACT_APP_API_URL=https://mlr-backend-XXXXX.render.com
REACT_APP_ENV=production

# ============================================
# HOW TO GET VALUES
# ============================================

# SECRET_KEY
# → Use an online generator or run: python -c "import secrets; print(secrets.token_urlsafe(32))"
# → Minimum 32 characters

# GEMINI_API_KEY
# → Go to https://ai.google.dev
# → Click "Get API Key"
# → Create new API key
# → Copy the key

# DATABASE_URL (Supabase PostgreSQL)
# → Go to https://supabase.com
# → Open your project
# → Settings → Database → Connection String
# → Copy connection string
# → Replace [YOUR-PASSWORD] with actual password

# MONGODB_URI (MongoDB Atlas)
# → Go to https://cloud.mongodb.com
# → Open your cluster
# → Click "Connect" → "Connect your application"
# → Copy connection string
# → Replace PASSWORD with your database user password

# CORS_ORIGINS & REACT_APP_API_URL
# → These depend on your Render URLs after deployment
# → Update after frontend and backend are both deployed

# ============================================
# STEP BY STEP GUIDE
# ============================================

# 1. Generate SECRET_KEY (run in terminal):
#    python -c "import secrets; print(secrets.token_urlsafe(32))"
#    Copy the output and paste into SECRET_KEY field

# 2. Get GEMINI_API_KEY:
#    Visit: https://ai.google.dev
#    Click "Get API Key" → Create API key
#    Copy and paste

# 3. Setup Supabase (Free PostgreSQL):
#    Visit: https://supabase.com
#    Sign up → Create project
#    Settings → Database → copy connection string
#    Paste into DATABASE_URL

# 4. Setup MongoDB (Free M0 Cluster):
#    Visit: https://cloud.mongodb.com
#    Create account → Create cluster (M0 Free)
#    Create user → Get connection string
#    Paste into MONGODB_URI

# 5. Deploy Backend on Render:
#    Add above BACKEND variables
#    Deploy (will take 3-5 minutes)
#    Note the backend URL: https://mlr-backend-XXXXX.render.com

# 6. Deploy Frontend on Render:
#    Add FRONTEND variables with backend URL
#    Deploy (will take 1-2 minutes)
#    Note the frontend URL: https://mlr-frontend-YYYYY.render.com

# 7. Update Backend CORS:
#    Go back to mlr-backend → Environment
#    Update CORS_ORIGINS with frontend URL
#    Save (auto-restarts)

# ============================================
# FINAL CHECKLIST
# ============================================

# ✅ SECRET_KEY - Unique random string
# ✅ GEMINI_API_KEY - From Google AI
# ✅ DATABASE_URL - From Supabase
# ✅ MONGODB_URI - From MongoDB Atlas
# ✅ CORS_ORIGINS - Set to frontend URL
# ✅ REACT_APP_API_URL - Set to backend URL
# ✅ All variables added to Render Environment tabs
# ✅ Backend deployed and "Live"
# ✅ Frontend deployed and "Live"
# ✅ Services can communicate (tested)

# ============================================
# EXAMPLE (DO NOT USE - FOR REFERENCE ONLY)
# ============================================

# BACKEND EXAMPLE (NOT FOR PRODUCTION):
# ENVIRONMENT=production
# LOG_LEVEL=INFO
# SECRET_KEY=K8j4x9nZ2qW1p7mL3vR5sT8uDfGhBjCkLmNoP
# ALGORITHM=HS256
# ACCESS_TOKEN_EXPIRE_MINUTES=30
# GEMINI_API_KEY=AIzaSyDxxxxxxxxxxxxxxxxxxxxxxx
# DATABASE_URL=postgresql://postgres:myPassword123@aws-0-us-west-1.pooler.supabase.com:6543/postgres
# MONGODB_URI=mongodb+srv://mlr_user:securePass456@cluster0.xxxxx.mongodb.net/mlr_db
# CORS_ORIGINS=https://mlr-frontend-abcd1234.render.com
# API_HOST=0.0.0.0

# FRONTEND EXAMPLE:
# NODE_VERSION=18
# REACT_APP_API_URL=https://mlr-backend-xyz5678.render.com
# REACT_APP_ENV=production
