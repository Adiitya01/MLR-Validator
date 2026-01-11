# MLR Deploy - Render FREE Tier Deployment Guide for POC

This guide provides step-by-step instructions to deploy the MLR validation tool on **Render Free Tier** for your Proof of Concept (POC).

## ⚠️ Important: Free Tier Limitations

| Feature | Free Tier | Impact |
|---------|-----------|--------|
| **Inactivity Timeout** | 15 minutes | Services spin down if idle → cold start on next request |
| **CPU/Memory** | Shared (512MB) | Good enough for POC testing |
| **Persistent Storage** | ❌ None | Use external databases only |
| **Cost** | $0/month | ✅ Perfect for POC |
| **Uptime SLA** | Not guaranteed | Acceptable for POC |

**Recommended:** For testing/POC - Free is fine. For production - upgrade to paid plan.

## Table of Contents
1. [Free Tier Setup](#free-tier-setup)
2. [External Database Services](#external-database-services)
3. [Deployment Steps](#deployment-steps)
4. [Cost Breakdown](#cost-breakdown-free-tier)
5. [Troubleshooting](#troubleshooting--free-tier)

---

## Prerequisites

### Accounts & Services (All Free)
- ✅ **Render Account** (https://render.com) - FREE
- ✅ **GitHub Repository** - PUBLIC (free tier requires public)
- ✅ **MongoDB Atlas** (https://www.mongodb.com/cloud/atlas) - FREE M0 cluster
- ✅ **Google Gemini API Key** (https://ai.google.dev) - FREE tier
- ✅ **Supabase PostgreSQL** (https://supabase.com) - FREE tier (2GB included) OR ElephantSQL

### Local Environment
- Python 3.11+
- Node.js 18+
- Git

---

## Free Tier Setup

### Step 1: Create Render Account & Connect GitHub

1. Go to https://render.com
2. Sign up with GitHub (free account)
3. Connect your GitHub account:
   - Click "Account" → "GitHub" → Authorize

### Step 2: Push Code to GitHub (Public Repository)

⚠️ **Free tier requires public repository**

```bash
# Initialize git if not done
git init
git add .
git commit -m "MLR deployment ready"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/mlr-deploy.git
git push -u origin main
```

---

## External Database Services

### Setup PostgreSQL (Supabase Free Tier)

1. Go to https://supabase.com
2. Sign up with GitHub
3. Create new project:
   - **Project name:** mlr-poc
   - **Region:** Closest to your location
   - **Click "Create new project"**

4. Wait for database creation (2-3 minutes)

5. Go to **Settings** → **Database** → Copy connection string:
   ```
   postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres
   ```

6. Save this as `DATABASE_URL` environment variable

### Setup MongoDB (Atlas Free Tier)

1. Go to https://www.mongodb.com/cloud/atlas
2. Create account and sign in
3. Create cluster:
   - Choose **M0 Free** tier
   - Select region
   - Click "Create"

4. Create database user:
   - **Username:** mlr_user
   - **Password:** Generate strong password
   - Save securely

5. Configure network access:
   - Go to **Network Access**
   - Add IP: `0.0.0.0/0` (allow all - POC only)

6. Get connection string:
   - Click **Databases** → **Connect** → **Connect your application**
   - Copy URI: `mongodb+srv://mlr_user:[PASSWORD]@[CLUSTER].mongodb.net/mlr_db`

---

## Deployment Steps

### Step 3: Deploy Backend API (FastAPI)

1. **Go to Render Dashboard** → Click **"New +"** → Select **"Web Service"**

2. **Connect Repository**
   - Select your GitHub repository (must be PUBLIC)
   - Confirm deployment branch is `main`

3. **Configure Service**
   - **Name:** `mlr-backend`
   - **Environment:** Python 3
   - **Region:** Choose closest to your location
   - **Branch:** main
   - **Build Command:**
     ```
     pip install --upgrade pip
     pip install -r requirements.txt
     ```
   - **Start Command:**
     ```
     uvicorn app:app --host 0.0.0.0 --port $PORT
     ```

4. **Select Plan: FREE** (bottom of page)

5. **Create Web Service**

4. **Select Plan: FREE** (bottom of page)

5. **Create Web Service**

6. **Set Environment Variables** (in Render Dashboard → Backend service → Environment):

   Copy these values from the services you created:
   ```
   ENVIRONMENT=production
   LOG_LEVEL=INFO
   SECRET_KEY=<generate-random-32-char-string>
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   GEMINI_API_KEY=<your-gemini-api-key>
   MONGODB_URI=<mongodb-connection-string-from-atlas>
   DATABASE_URL=<postgresql-connection-string-from-supabase>
   CORS_ORIGINS=https://mlr-frontend-<random>.render.com
   API_HOST=0.0.0.0
   ```

7. **Wait for Deployment**
   - Initial deploy takes 3-5 minutes
   - You'll see "Your service is live" when ready
   - Note the backend URL: `https://mlr-backend-xxx.render.com`

### Step 4: Deploy Frontend (React)

1. **Go to Render Dashboard** → Click **"New +"** → Select **"Static Site"**

2. **Connect Repository**
   - Select your GitHub repository
   - Branch: main

3. **Configure Service**
   - **Name:** `mlr-frontend`
   - **Build Command:**
     ```
     cd MLR_UI_React && npm install && npm run build
     ```
   - **Publish Directory:** `MLR_UI_React/dist`

4. **Select Plan: FREE**

5. **Create Static Site**

6. **Add Environment Variable**
   - Go to **Environment**
   - Add: `REACT_APP_API_URL=https://mlr-backend-xxx.render.com` (use your actual backend URL)

7. **Redeploy** → Frontend builds in 1-2 minutes

---

## Post-Deployment Configuration

### Step 5: Update Backend CORS

1. Go to Render Dashboard → **mlr-backend** service
2. Click **Environment**
3. Update `CORS_ORIGINS` with your frontend URL:
   ```
   https://mlr-frontend-xxx.render.com
   ```
4. Click **Save** → Backend auto-restarts

### Step 6: Test Deployment

1. **Open Frontend:** `https://mlr-frontend-xxx.render.com`

2. **Create Test Account:**
   - Click Sign Up
   - Enter credentials

3. **Test Pipeline:**
   - Upload sample PDF
   - Upload reference PDF
   - Click "Validate"
   - Check results

4. **Check Logs if Issues:**
   - Render Dashboard → **mlr-backend** → **Logs**
   - Look for error messages

---

## Free Tier Behavior & Tips

### Cold Starts
- First request after 15 minutes of inactivity may take 5-10 seconds
- ✅ Normal for free tier - service auto-wakes
- 💡 **Tip:** Keep backend "warm" with monitoring service (Uptimerobot free tier)

### Usage Limits
- **CPU:** Shared, ~512MB RAM
- **Bandwidth:** Unlimited
- **Builds:** Unlimited (but slow)
- **Deployments:** Git auto-deploys on push

### Optimizations for Free Tier
1. Keep `LOG_LEVEL=INFO` (not DEBUG)
2. Don't upload very large PDFs (>50MB)
3. Avoid heavy computations in background
4. Use external databases (not persistent storage)

---

## Cost Breakdown (Free Tier)

| Service | Cost |
|---------|------|
| Render Backend | FREE |
| Render Frontend | FREE |
| Supabase PostgreSQL | FREE (2GB) |
| MongoDB Atlas | FREE (M0) |
| Google Gemini API | FREE tier (60 req/min) |
| **TOTAL** | **$0/month** ✅ |

---

## Troubleshooting - Free Tier

### Issue: "Application crashed" in Render

**Solution 1:** Check logs
```
Render Dashboard → mlr-backend → Logs → See error
```

**Solution 2:** Rebuild
```
Render Dashboard → mlr-backend → Manual Deploy → Deploy latest commit
```

### Issue: Application works locally but fails on Render

**Check:**
1. All environment variables set in Render dashboard
2. External database connections (Supabase, MongoDB)
3. No local files being written (free tier has no persistent storage)

### Issue: Frontend shows "Cannot reach backend"

**Solution:**
1. Verify backend is deployed and showing "Live" status
2. Check `REACT_APP_API_URL` in frontend environment
3. Check CORS_ORIGINS in backend matches frontend URL
4. Restart backend: Dashboard → mlr-backend → Manual Deploy

### Issue: Cold start takes too long

**Solution (Optional):**
1. Use Uptimerobot (free tier) to ping backend every 5 minutes
2. Keeps service warm between requests

---

## Production Upgrade Path

When ready for production:

1. **Upgrade Render Plans:**
   - Backend: Standard ($12/month)
   - Frontend: Static (free, no cold starts)

2. **Upgrade Databases:**
   - PostgreSQL: Starter ($7/month) or managed
   - MongoDB: Paid tier if needed

3. **Add Monitoring:**
   - Sentry for error tracking
   - Datadog or New Relic for performance

---

## Final Checklist

- [ ] GitHub repository created (PUBLIC)
- [ ] Render account created and GitHub connected
- [ ] Supabase PostgreSQL database created
- [ ] MongoDB Atlas M0 cluster created
- [ ] Backend deployed on Render (status: Live)
- [ ] Frontend deployed on Render (status: Live)
- [ ] Environment variables set in both services
- [ ] CORS origins configured
- [ ] Tested signup and pipeline
- [ ] Monitored logs for errors
- [ ] Documented backend and frontend URLs
- [ ] Ready to share POC with team ✅

---

## Quick Links

| Service | Link |
|---------|------|
| **Render Dashboard** | https://dashboard.render.com |
| **Frontend** | `https://mlr-frontend-xxx.render.com` |
| **Backend API** | `https://mlr-backend-xxx.render.com` |
| **API Docs** | `https://mlr-backend-xxx.render.com/docs` |
| **Supabase Console** | https://app.supabase.com |
| **MongoDB Atlas** | https://cloud.mongodb.com |

---

**Last Updated:** January 2026  
**Tier:** Render Free Account ✅  
**Status:** Production Ready for POC
