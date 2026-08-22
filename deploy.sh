#!/bin/bash

# GameTeamAPI Deployment Script for Google Cloud Run
# Make sure to set these variables before running:
# - PROJECT_ID: Your Google Cloud Project ID
# - REGION: Your preferred region (e.g., us-central1)

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-"your-project-id"}
REGION=${REGION:-"us-central1"}
SERVICE_NAME="gameteam-api"
IMAGE_NAME="gameteam-api"

echo "Starting deployment to Google Cloud Run..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"

# Build and push Docker image
echo "Building Docker image..."
docker build -t gcr.io/$PROJECT_ID/$IMAGE_NAME:latest .

echo "Pushing image to Google Container Registry..."
docker push gcr.io/$PROJECT_ID/$IMAGE_NAME:latest

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image=gcr.io/$PROJECT_ID/$IMAGE_NAME:latest \
    --platform=managed \
    --region=$REGION \
    --allow-unauthenticated \
    --memory=512Mi \
    --cpu=1 \
    --max-instances=10 \
    --min-instances=0 \
    --concurrency=40 \
    --port=8080 \
    --set-env-vars=GCP_PROJECT_ID=$PROJECT_ID

echo "Deployment completed!"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform=managed --region=$REGION --format="value(status.url)")
echo "Service URL: $SERVICE_URL"

echo ""
echo "To set up the custom domain (api.gameteam.net):"
echo "1. Go to Google Cloud Console > Cloud Run > Manage Custom Domains"
echo "2. Add mapping for api.gameteam.net to $SERVICE_NAME"
echo "3. Update your DNS records as instructed"
