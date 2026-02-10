# 🚀 MLR Validator Deployment Guide

This guide contains instructions to deploy the project using **AWS S3** (Frontend) and **AWS EC2** (Backend).

---

## 🏗 Project Structure
- **/MLR_UI_React**: React Frontend (to be deployed on S3)
- **Root Files (app.py, Superscript.py, etc.)**: FastAPI Backend (to be deployed on EC2)
- **.env**: Configuration file (MUST be configured on EC2)

---

## 1️⃣ Frontend Deployment (AWS S3)

### Step A: Build the React App
On your local machine/build server:
```bash
cd MLR_UI_React
npm install
# IMPORTANT: Update .env.production or your API config to point to the EC2 Public IP
npm run build
```
This will create a `dist` folder.

### Step B: Setup S3
1. Create an S3 Bucket (e.g., `mlr-ui-prod`).
2. Go to **Properties** > **Static website hosting** > **Enable**.
   - Index document: `index.html`
3. Go to **Permissions** > **Block all public access** > **Turn OFF**.
4. Add **Bucket Policy**:
```json
{
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "PublicRead",
        "Effect": "Allow",
        "Principal": "*",
        "Action": "s3:GetObject",
        "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/*"
    }]
}
```
5. Upload everything inside the `dist` folder to the root of the bucket.

---

## 2️⃣ Backend Deployment (AWS EC2)

### Step A: Provision EC2
1. Launch an **Ubuntu 22.04 LTS** instance (`t2.medium` recommended).
2. **Security Group**:
   - Port 22 (SSH)
   - Port 80 (HTTP)
   - Port 8000 (FastAPI)

### Step B: System Preparation
SSH into your instance and run:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv redis-server postgresql postgresql-contrib -y
sudo systemctl start redis-server
```

### Step C: Deploy Backend Code
1. Upload the zip file via SCP or Download from your link.
2. Unzip and enter the folder:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step D: Database Setup (Postgres)
1. Switch to postgres user: `sudo -u postgres psql`
2. Run: 
   ```sql
   CREATE DATABASE brochure_app;
   CREATE USER postgres WITH PASSWORD 'postgres';
   GRANT ALL PRIVILEGES ON DATABASE brochure_app TO postgres;
   \q
   ```

### Step E: Configuration
Create a `.env` file in the root:
```env
GEMINI_API_KEY=your_key
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/brochure_app
MONGODB_URI=your_mongo_atlas_uri
SECRET_KEY=generate_a_random_string
SENDGRID_API_KEY=your_key
FROM_EMAIL=your_email
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Step F: Run with PM2 (Persistent)
```bash
sudo apt install nodejs npm -y
sudo npm install -g pm2
pm2 start "python3 -m uvicorn app:app --host 0.0.0.0 --port 8000" --name mlr-backend
```

---

## 3️⃣ Final Task: Initialize Database
Visit this URL in your browser once the backend is running:
`http://your-ec2-ip:8000/init-db`

---

## 📁 To Zip the project correctly (Excluding junk):
Run this in your terminal to create a clean zip:
```powershell
Compress-Archive -Path * -DestinationPath MLR_Project_Final.zip -Exclude "venv", "node_modules", ".git", ".next", "dist", "app.log", "test_results", "output"
```
