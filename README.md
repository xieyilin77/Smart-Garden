# Smart-Garden-Manager
# 🌱 Smart Garden Manager

A serverless IoT solution for intelligent garden monitoring on AWS.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [AWS Services](#aws-services)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Thresholds & Alerts](#thresholds--alerts)
- [Testing](#testing)
- [Monitoring & Debugging](#monitoring--debugging)
- [Troubleshooting](#troubleshooting)
- [Timeline](#timeline)
- [Contributing](#contributing)
- [License](#license)

---

## 📖 Overview

The **Smart Garden Manager** is a cloud-native application that monitors and analyzes environmental data from a simulated smart garden. Virtual IoT sensors generate measurements such as soil moisture, temperature, and humidity, which are sent securely to AWS. The collected data is automatically processed, stored, and displayed in a modern web dashboard.

This project demonstrates how a scalable, event-driven cloud application can be built using AWS services while following serverless and Infrastructure as Code (IaC) principles.

### Project Goal

Develop a functional prototype that represents the complete lifecycle of IoT data - from data generation and cloud processing to storage, monitoring, and visualization.

### Key Objectives

- ✅ Simulate environmental sensor data
- ✅ Process incoming data automatically using AWS Lambda
- ✅ Store current sensor values in Amazon DynamoDB
- ✅ Archive historical data in Amazon S3
- ✅ Display live and historical information in a static web dashboard
- ✅ Send notifications when predefined thresholds are exceeded
- ✅ Deploy the infrastructure using AWS CloudFormation

---

## 🏗️ Architecture

┌─────────────────────────────────────────────────────────────────────┐
│                        AWS Cloud                                    │
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐   │
│  │   IoT Core   │────▶│   Lambda     │────▶│   DynamoDB       │   │
│  │  (MQTT)      │     │  Processor   │     │  - Latest Values │   │
│  └──────────────┘     └──────────────┘     │  - History       │   │
│         │                    │              └──────────────────┘   │
│         │                    │                     │               │
│         │              ┌─────▼─────┐         ┌─────▼─────┐       │
│         │              │   S3      │         │  API      │       │
│         │              │  Archive  │         │  Gateway  │       │
│         │              └───────────┘         └───────────┘       │
│         │                                         │               │
│         │                                    ┌────▼────┐         │
│         │                                    │ Lambda  │         │
│         │                                    │  Query  │         │
│         │                                    └─────────┘         │
│         │                                         │               │
│         │                              ┌──────────▼──────────┐   │
│         │                              │   CloudFront + S3   │   │
│         │                              │    Dashboard        │   │
│         │                              └─────────────────────┘   │
│         │                                                         │
│  ┌──────▼──────┐                  ┌──────────────────────────┐   │
│  │  Sensor     │                  │  SNS Alerts              │   │
│  │  Simulator  │─────────────────▶│  - Email Notifications   │   │
│  └─────────────┘                  └──────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

### Data Flow

1. **Sensor Simulator** generates environmental data (temperature, humidity, soil moisture)
2. Data is published to **AWS IoT Core** via MQTT
3. **IoT Rule** triggers the **Lambda Data Processor**
4. Lambda processes the data:
   - Stores latest values in **DynamoDB** (Latest Table)
   - Archives historical data in **DynamoDB** (History Table)
   - Stores raw data in **S3** for long-term archiving
   - Checks thresholds and sends **SNS alerts** if exceeded
5. **API Gateway** exposes a REST API for data retrieval
6. **Lambda Query** fetches data from DynamoDB
7. **Dashboard** displays data using Chart.js visualizations
8. **CloudFront** delivers the dashboard globally with low latency
9. **CloudWatch** monitors Lambda errors and triggers alarms

---

## ✨ Features

### Core Features

| Feature | Description |
|---------|-------------|
| **Real-time Monitoring** | Live sensor data display with auto-refresh (30s) |
| **Historical Data** | View trends over customizable time ranges |
| **Data Visualization** | Interactive charts for temperature, humidity, and soil moisture |
| **Threshold Alerts** | Email notifications when values exceed limits |
| **Data Archiving** | Automatic storage of raw data in S3 |
| **API Access** | REST API for programmatic data access |

### Technical Features

| Feature | Description |
|---------|-------------|
| **Serverless Architecture** | No servers to manage, auto-scaling |
| **Infrastructure as Code** | Full infrastructure defined in CloudFormation |
| **Event-Driven Processing** | Lambda triggered by IoT messages |
| **CORS Support** | Dashboard can be hosted anywhere |
| **Responsive Design** | Works on desktop, tablet, and mobile |
| **Dark/Light Theme** | Modern gradient UI |

---

## 🛠️ AWS Services

| Service | Purpose | Sandbox Compatible |
|---------|---------|-------------------|
| **AWS IoT Core** | MQTT broker for sensor data ingestion | ✅ Yes |
| **AWS Lambda** | Serverless compute for data processing and API | ✅ Yes |
| **Amazon DynamoDB** | NoSQL database for current and historical data | ✅ Yes |
| **Amazon S3** | Data archival and static website hosting | ✅ Yes |
| **Amazon API Gateway** | REST API for dashboard backend | ✅ Yes |
| **Amazon CloudFront** | CDN for fast dashboard delivery | ✅ Yes |
| **Amazon SNS** | Email notifications for alerts | ✅ Yes |
| **Amazon CloudWatch** | Monitoring and logging | ✅ Yes |
| **AWS CloudFormation** | Infrastructure as Code | ✅ Yes |
| **AWS IAM** | Security (using LabRole) | ✅ Yes |

---

## 📋 Prerequisites

### Required

- AWS Account with Sandbox access
- AWS CLI installed and configured
- Python 3.9 or higher
- Git (optional)
- VS Code or any text editor

### AWS Sandbox Restrictions

| Restriction | Workaround |
|-------------|------------|
| IAM Role creation restricted | Use pre-created **LabRole** |
| t2.micro Cloud9 restricted | Use local development with VS Code |
| EC2 instance limits | Not needed (serverless architecture) |

### AWS CLI Configuration

```bash
# Configure AWS CLI
aws configure

# Enter your credentials:
# AWS Access Key ID: [YOUR_ACCESS_KEY]
# AWS Secret Access Key: [YOUR_SECRET_KEY]
# Default region name: [eu-central-1]
# Default output format: [json]
```

### Repository Structure
smart-garden-manager/
│
├── 📁 templates/
│   └── 📄 smart-garden.yaml          # CloudFormation Template (KOMPLETT)
│
├── 📁 src/
│   ├── 📁 dashboard/
│   │   ├── 📄 index.html             # Dashboard (KOMPLETT)
│   │   ├── 📄 style.css              # Styling (KOMPLETT)
│   │   └── 📄 dashboard.js           # JavaScript (KOMPLETT)
│   │
│   └── 📁 simulator/
│       └── 📄 sensor_simulator.py    # Sensor-Simulation (KOMPLETT)
│
├── 📁 scripts/
│   ├── 📄 deploy.sh                  # Deployment Script
│   └── 📄 test.sh                    # Test Script
│
└── 📄 README.md                      # Dokumentation

## 🚀 Deployment

### Run Deployment
```bash
# Navigate to scripts directory
cd scripts

# Make deployment script executable
chmod +x deploy.sh

# Execute deployment
./deploy.sh
```

### Start Sensor Simulation
```bash
# Navigate to simulator directory
cd ../src/simulator

# Install required dependencies
pip install AWSIoTPythonSDK boto3

# Start sensor simulation
python sensor_simulator.py --config sensor_config.json
```

### Access Dashboard
```bash
# Get CloudFront URL from outputs
aws cloudformation describe-stacks \
  --stack-name smart-garden \
  --query 'Stacks[0].Outputs[?OutputKey==`WebsiteURL`].OutputValue' \
  --output text
```

### Run Tests (Optional)
```bash
cd ../../scripts
chmod +x test.sh
./test.sh
```



# ============================================
  # COST ESTIMATION (Nur zur Information)
  # ============================================
  EstimatedMonthlyCost:
    Description: Estimated monthly cost (Free Tier eligible)
    Value: |
      ┌─────────────────────────────────────────────────────────┐
      │  SMART GARDEN MANAGER - KOSTENSCHÄTZUNG (Free Tier)   │
      ├─────────────────────────────────────────────────────────┤
      │  AWS Lambda (128MB, 1M Invocations)  →  ~$0.00/Monat  │
      │  Amazon DynamoDB (PAY_PER_REQUEST)   →  ~$0.00/Monat  │
      │  Amazon S3 (5GB Storage, 20k GET)    →  ~$0.00/Monat  │
      │  AWS IoT Core (1M Messages)          →  ~$0.00/Monat  │
      │  Amazon SNS (1.000 Publish)          →  ~$0.00/Monat  │
      │  Amazon CloudFront (1TB Transfer)    →  ~$0.00/Monat  │
      │  API Gateway (1M Requests)           →  ~$0.00/Monat  │
      │  Amazon CloudWatch (10 Alarme)       →  ~$0.00/Monat  │
      ├─────────────────────────────────────────────────────────┤
      │  GESCHÄTZT: < $5.00 / Monat                           │
      │  (Bei normaler Nutzung sogar kostenlos!)              │
      └─────────────────────────────────────────────────────────┘

📋 Was das Skript prüft
Nr.	Ressource	Prüfbefehl
1	CloudFormation Stack	describe-stacks
2	S3 Buckets	s3 ls
3	DynamoDB Tables	dynamodb list-tables
4	Lambda Functions	lambda list-functions
5	API Gateway	apigateway get-rest-apis
6	IoT Things	iot list-things
7	IoT Policies	iot list-policies
8	IoT Rules	iot list-topic-rules
9	SNS Topics	sns list-topics
10	CloudFront	cloudfront list-distributions
11	EventBridge	events list-rules
12	CloudWatch Logs	logs describe-log-groups
13	IAM Roles	iam list-roles