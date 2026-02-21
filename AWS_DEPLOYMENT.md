# ☁️ MLR Validator AWS Deployment Guide

This guide explains how to deploy the MLR Validator using the **Standard AWS Architecture**:
*   **Frontend**: AWS S3 (Static Website) + CloudFront (CDN)
*   **Backend**: AWS EC2 (Ubuntu) running Docker/Nginx
*   **Database**: AWS RDS (Postgres)
*   **File Storage**: AWS S3 (for PDFs)

---

## 🏗️ 1. Frontend: S3 + CloudFront
S3 is significantly cheaper and faster than EC2 for hosting static React files.

### Steps:
1.  **Build the App**:
    ```bash
    cd MLR_UI_React
    npm install
    npm run build  # This creates a 'dist' folder
    ```
2.  **Create S3 Bucket**:
    *   Name: `mlr-frontend-production` (or similar)
    *   Uncheck "Block all public access"
    *   Enable "Static website hosting" in properties
3.  **Upload**: Upload all contents of the `MLR_UI_React/dist/` folder to the bucket root.
4.  **CloudFront (Recommended)**:
    *   Create a CloudFront Distribution.
    *   Origin: Your S3 bucket website endpoint.
    *   Viewer Protocol Policy: "Redirect HTTP to HTTPS".
    *   This provides the SSL certificate for your frontend.

---

## 🖥️ 2. Backend: EC2 Instance Setup
The backend runs on an EC2 instance using the Docker configuration I created.

### Steps:
1.  **Launch EC2**:
    *   AMI: **Ubuntu 22.04 LTS**
    *   Instance Type: **t3.medium** (Minimum recommended for PDF processing + LLM orchestration)
    *   Security Group: Open ports **80 (HTTP)**, **443 (HTTPS)**, and **22 (SSH)**.
2.  **Install Docker**:
    ```bash
    sudo apt update && sudo apt install -y docker.io docker-compose
    sudo usermod -aG docker $USER && newgrp docker
    ```
3.  **Deploy Code**:
    *   Clone your repo to the EC2 instance.
    *   Create `.env.production` (see template below).
4.  **Launch Services**:
    ```bash
    cd MLR_AG/backend
    docker-compose up -d --build
    ```

---

## 🗄️ 3. Database: AWS RDS
Do **not** host the database inside EC2 for production. Use RDS.

*   **Engine**: PostgreSQL 15+
*   **Instance**: db.t3.micro (or small)
*   **Public Access**: No (Only allow access from your EC2 Security Group)
*   **Configuration**: Copy the "Connectivity & security" Endpoint into your `DATABASE_URL`.

---

## 📁 4. PDF Storage: AWS S3
The `s3_storage.py` I created will handle PDF uploads.

1.  **Create Bucket**: `mlr-validator-pdfs`
2.  **IAM Policy**: Create an IAM user with `AmazonS3FullAccess` to this bucket.
3.  **Credentials**: Add the `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` to your `.env.production`.

---

## 📝 5. Production Environment Template (`.env.production`)
Create this file on your EC2 instance:

```env
# --- Django ---
DEBUG=False
SECRET_KEY=generate-a-secure-key-here
ENVIRONMENT=production
ALLOWED_HOSTS=api.yourdomain.com,your-ec2-ip

# --- Database (RDS) ---
DATABASE_URL=postgres://user:password@mlr-db.xyz.region.rds.amazonaws.com:5432/brochure_app

# --- S3 Storage (for PDFs) ---
USE_S3_STORAGE=True
AWS_S3_BUCKET_NAME=mlr-validator-pdfs
AWS_S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# --- Celery & Redis ---
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_ALWAYS_EAGER=False

# --- Gemini API ---
GEMINI_API_KEY=your_key_here

# --- Frontend ---
# In S3 hosting, CORS must allow your S3 website URL or CloudFront domain
CORS_ORIGINS=https://your-cloudfront-domain.com
```

---

## 🛡️ 6. SSL / HTTPS
There are two ways to handle HTTPS for the API:
1.  **AWS Load Balancer (Recommended)**: Create an Application Load Balancer (ALB) and attach an AWS Certificate Manager (ACM) cert.
2.  **Certbot (Free)**: Run Certbot on the EC2 instance to get free Let's Encrypt certificates for the Nginx container.\