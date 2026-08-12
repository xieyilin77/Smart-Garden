# 🌱 Smart Garden Manager

A serverless, event-driven IoT monitoring and analysis platform built with AWS.

The Smart Garden Manager simulates environmental sensor data such as temperature, humidity, soil moisture, battery level, sensor ID, location, and timestamp.

The project supports three official simulation modes:

- **Offline** – local sensor-data generation without AWS
- **API** – HTTPS ingestion through Amazon API Gateway
- **MQTT** – MQTT ingestion through AWS IoT Core

Both online ingestion paths use the same processing Lambda. Sensor data is validated, processed and stored in Amazon DynamoDB and Amazon S3. Amazon SNS provides threshold notifications, while a web dashboard retrieves and visualizes current and historical sensor data.

The AWS infrastructure is deployed as Infrastructure as Code (IaC) using AWS CloudFormation.

---

# 📋 Table of Contents

1. Project Overview
2. Project Structure & File Responsibilities
3. System Architecture & Data Flow
4. AWS Services & Dependencies
5. Infrastructure as Code with CloudFormation
6. Offline Deployment & Testing
7. Online Deployment – API Gateway Option
8. Online Deployment – IoT Core/MQTT Option
9. Security, Monitoring & Cost Optimization
10. Troubleshooting, Cleanup & Presentation Questions
11. Technologies Used
12. Future Improvements

---

# 1. Project Overview

## 1.1 Project Goal

The goal of the Smart Garden Manager is to demonstrate how environmental IoT data can be generated, transmitted, processed, stored, monitored and visualized using AWS serverless services.

A Python-based sensor simulator replaces physical hardware so that the complete application can be developed and tested locally before connecting it to AWS.

The project demonstrates the following sensor-data lifecycle:

```text
GENERATE
   ↓
INGEST
   ↓
VALIDATE
   ↓
PROCESS
   ↓
STORE
   ↓
QUERY
   ↓
VISUALIZE
   ↓
MONITOR
   ↓
ALERT
```

## 1.2 Main Features

- Simulated garden sensor measurements
- Offline sensor simulation
- HTTPS sensor-data ingestion through API Gateway
- MQTT sensor-data ingestion through AWS IoT Core
- Common processing Lambda for both online ingestion paths
- Current sensor-state storage in DynamoDB
- Historical sensor-data storage in DynamoDB
- Raw-data archival in S3
- Local mock API for offline backend testing
- REST API for dashboard queries
- Static web dashboard hosted in S3
- Optional CloudFront distribution
- SNS threshold notifications
- CloudWatch logging, metrics and alarms
- CloudFormation-based infrastructure deployment
- PowerShell deployment and cleanup automation
- Configurable sensor intervals for cost optimization

---

# 2. Project Structure & File Responsibilities

```text
Smart-Garden/
│
├── templates/
│   └── smart-garden.yaml
│
├── src/
│   │
│   ├── lambda/
│   │   ├── process_data.py
│   │   ├── query_data.py
│   │   └── requirements.txt
│   │
│   ├── simulator/
│   │   ├── sensor_simulator.py
│   │   ├── mock_api.py
│   │   └── test_connection_websocket.py
│   │
│   └── dashboard/
│       ├── index.html
│       ├── style.css
│       └── dashboard.js
│
├── scripts/
│   ├── build.ps1
│   ├── deploy.ps1
│   ├── setup_and_run.ps1
│   ├── generate_env.py
│   ├── test.ps1
│   ├── cleanup.ps1
│   └── verify-cleanup.ps1
│
├── .gitignore
└── README.md
```

## 2.1 Core Application Files

| File | Responsibility | Dependencies |
|---|---|---|
| `smart-garden.yaml` | Defines AWS infrastructure | CloudFormation |
| `process_data.py` | Validates, processes and stores incoming sensor data | DynamoDB, S3, SNS, IAM |
| `query_data.py` | Retrieves sensor data for the dashboard | DynamoDB, API Gateway, IAM |
| `sensor_simulator.py` | Official sensor-data generator and transmitter | Python, Requests, AWS IoT SDK |
| `mock_api.py` | Local backend simulator for offline testing | Flask, Flask-CORS |
| `index.html` | Dashboard structure | Web browser |
| `style.css` | Dashboard styling | HTML |
| `dashboard.js` | Dashboard logic and API communication | API Gateway, generated `config.js` |
| `deploy.ps1` | Builds, deploys and configures the AWS environment | AWS CLI, CloudFormation |
| `build.ps1` | Creates deployment artifacts | PowerShell |
| `test.ps1` | Runs project tests and validation | PowerShell |
| `cleanup.ps1` | Removes deployed resources | AWS CLI, CloudFormation |
| `verify-cleanup.ps1` | Verifies resource cleanup | AWS CLI |
| `generate_env.py` | Generates local environment configuration | Python |

---

## 2.2 Official Sensor Simulator

The official simulator is:

```text
src/simulator/sensor_simulator.py
```

It supports exactly three operating modes:

```text
--offline
--api
--mqtt
```

Examples:

```powershell
python sensor_simulator.py --offline --interval 60
```

```powershell
python sensor_simulator.py --api --interval 60
```

```powershell
python sensor_simulator.py --mqtt --interval 60
```

Only one mode can be selected at a time.

The default sensor interval is:

```text
60 seconds
```

The simulator generates realistic sensor values including:

- Temperature
- Humidity
- Soil moisture
- Battery
- Sensor ID
- Location
- Timestamp

The simulator also supports sensor locations such as:

```text
indoor
outdoor
greenhouse
```

---

## 2.3 Local Mock API

```text
src/simulator/mock_api.py
```

`mock_api.py` is a **local backend testing utility**.

It does not deploy anything to AWS.

Instead, it simulates the behavior of the API Gateway/Lambda backend locally.

The local mock API provides:

```text
POST /prod/data
GET  /prod/query
```

Received data is stored temporarily in memory.

The mock API is useful for:

- Offline backend testing
- API development
- Dashboard testing
- Testing sensor-data processing behavior
- Testing alert conditions without AWS

It is not part of the deployed AWS architecture.

---

## 2.4 MQTT/WebSocket Test Utility

```text
src/simulator/test_connection_websocket.py
```

This is an optional connectivity test utility.

It can be used to test MQTT/WebSocket connectivity separately from the main simulator.

The official MQTT implementation remains:

```text
sensor_simulator.py
```

---

## 2.5 Generated Configuration – `config.js`

`config.js` is a generated deployment artifact.

It is not manually maintained as a source file.

The deployment process is:

```text
CloudFormation
      ↓
API Gateway URL
      ↓
deploy.ps1
      ↓
config.js
      ↓
dashboard.js
```

The file contains runtime configuration such as the current API Gateway URL.

Do not hard-code the API Gateway URL inside `dashboard.js`.

Do not commit generated deployment configuration as permanent source code.

---

# 3. System Architecture & Data Flow

The application is organized into five logical layers.

```text
┌──────────────────────────────────────────────┐
│ Layer 5 – PRESENTATION                       │
│ S3 Dashboard + optional CloudFront            │
├──────────────────────────────────────────────┤
│ Layer 4 – API                                │
│ API Gateway + Query Lambda                    │
├──────────────────────────────────────────────┤
│ Layer 3 – PROCESSING                         │
│ Process Lambda + SNS                         │
├──────────────────────────────────────────────┤
│ Layer 2 – STORAGE                            │
│ DynamoDB + S3                                │
├──────────────────────────────────────────────┤
│ Layer 1 – INGESTION                          │
│ Sensor Simulator + API Gateway / IoT Core   │
└──────────────────────────────────────────────┘

Cross-cutting:
IAM        → Security and permissions
CloudWatch → Logs, metrics and alarms

Infrastructure:
CloudFormation → Infrastructure as Code
```

The five layers are logical architecture layers. They remain inside one CloudFormation template to preserve resource dependencies.

---

## 3.1 API Gateway Data Flow

```text
Python Sensor Simulator
        ↓
HTTPS POST /data
        ↓
API Gateway
        ↓
Process Lambda
        ↓
┌──────────┼──────────┐
↓          ↓          ↓
DynamoDB   S3         SNS
```

---

## 3.2 IoT Core / MQTT Data Flow

```text
Python Sensor Simulator
        ↓
MQTT Publish
        ↓
AWS IoT Core
        ↓
IoT Topic Rule
        ↓
Process Lambda
        ↓
┌──────────┼──────────┐
↓          ↓          ↓
DynamoDB   S3         SNS
```

The MQTT topic used by the architecture is:

```text
sensor/data
```

---

## 3.3 Dashboard Data Flow

```text
Browser
   ↓
CloudFront (optional)
   ↓
S3 Website Bucket
   ↓
dashboard.js
   ↓
config.js
   ↓
API Gateway GET /data
   ↓
Query Lambda
   ↓
DynamoDB
   ↓
JSON Response
   ↓
Dashboard
```

---

# 4. AWS Services & Dependencies

| AWS Service | Role |
|---|---|
| AWS IoT Core | Receives MQTT sensor messages |
| Amazon API Gateway | Provides HTTPS REST endpoints |
| AWS Lambda | Processes incoming data and retrieves dashboard data |
| Amazon DynamoDB | Stores current and historical sensor data |
| Amazon S3 | Stores archived sensor data and dashboard files |
| Amazon SNS | Sends sensor threshold notifications |
| Amazon CloudFront | Optional global distribution of the dashboard |
| AWS IAM | Controls permissions between AWS services |
| Amazon CloudWatch | Provides logs, metrics, dashboards and alarms |
| AWS CloudFormation | Creates and manages the AWS infrastructure |

---

## 4.1 Main Dependency Chain

```text
Sensor Simulator
      │
      ├──────────────→ API Gateway
      │                     │
      │                     ▼
      │              Process Lambda
      │                     │
      │              ┌──────┼──────┐
      │              ↓      ↓      ↓
      │           DynamoDB S3     SNS
      │
      └──────────────→ IoT Core
                            │
                            ▼
                       IoT Rule
                            │
                            ▼
                     Process Lambda
```

For dashboard queries:

```text
Dashboard
    ↓
API Gateway GET
    ↓
Query Lambda
    ↓
DynamoDB
    ↓
JSON
    ↓
Dashboard
```

---

# 5. Why Two DynamoDB Tables?

The project uses two functional DynamoDB tables.

## 5.1 Historical Data Table

```text
smart-garden-sensor-data
```

Purpose:

- Store historical measurements
- Support time-series queries
- Provide data for charts
- Preserve previous sensor readings

The primary key uses:

```text
sensor_id
timestamp
```

This allows sensor readings to be stored over time.

## 5.2 Latest State Table

```text
smart-garden-sensor-latest
```

Purpose:

- Store only the latest value for each sensor
- Quickly retrieve the current sensor state
- Avoid scanning historical data for current values

Example:

```text
sensor-001
Temperature: 24.5°C
Humidity: 61%
Soil Moisture: 48%
Battery: 93%
```

## 5.3 Why Separate Them?

The access patterns are different:

```text
Latest Table
→ "What is the current value?"

History Table
→ "What values were recorded over time?"
```

Separating these responsibilities makes the application easier to query and understand.

---

# 6. Why Two Functional S3 Buckets?

The project uses two functional S3 buckets plus one deployment-artifact bucket.

## 6.1 Sensor Data Bucket

```text
DataBucket
```

Purpose:

- Archive raw sensor data
- Store IoT Rule error objects
- Preserve sensor-data history outside DynamoDB

The bucket uses encryption, versioning and lifecycle rules.

## 6.2 Website Bucket

```text
WebsiteBucket
```

Purpose:

- Store the static dashboard
- Store HTML, CSS and JavaScript files
- Serve the web application directly or through CloudFront

## 6.3 Lambda Deployment Bucket

A third S3 bucket is used for deployment artifacts.

Purpose:

```text
process-data.zip
query-data.zip
```

This bucket is a technical deployment dependency rather than an application data store.

Therefore the architecture can be explained as:

```text
S3 Data Bucket
→ Sensor data

S3 Website Bucket
→ Dashboard

S3 Lambda Bucket
→ Deployment packages
```

---

# 7. API Gateway vs. AWS IoT Core

The project supports two online ingestion paths.

## 7.1 API Gateway

API Gateway is used for HTTPS/REST communication.

```text
Sensor Simulator
      ↓
HTTPS POST
      ↓
API Gateway
      ↓
Process Lambda
```

Advantages:

- Easy to test
- Simple HTTPS interface
- Easy PowerShell testing
- Suitable for REST clients

Example:

```powershell
python sensor_simulator.py --api --interval 60
```

---

## 7.2 AWS IoT Core

AWS IoT Core is used for MQTT communication.

```text
Sensor Simulator
      ↓
MQTT
      ↓
AWS IoT Core
      ↓
IoT Rule
      ↓
Process Lambda
```

Advantages:

- Designed for IoT devices
- MQTT protocol
- Certificate-based authentication
- Topic-based communication

Example:

```powershell
python sensor_simulator.py --mqtt --interval 60
```

---

## 7.3 Can the Project Switch Between Them?

Yes.

The processing, storage and dashboard layers remain unchanged.

Only the ingestion path changes:

```text
API Mode:

Sensor → API Gateway → Process Lambda


MQTT Mode:

Sensor → IoT Core → IoT Rule → Process Lambda
```

Both ultimately use:

```text
Process Lambda
       ↓
DynamoDB
S3
SNS
```

Only one simulator mode should be selected at a time.

---

# 8. Why Process Lambda and Query Lambda Are Separate

The project separates data writing and data reading.

## Process Lambda

```text
Incoming Sensor Data
        ↓
Process Lambda
        ↓
Validate
        ↓
Store
        ↓
DynamoDB
S3
SNS
```

Responsibilities:

- Validate sensor data
- Process values
- Update latest sensor state
- Store historical data
- Archive raw data
- Trigger notifications

## Query Lambda

```text
Dashboard
    ↓
API Gateway GET
    ↓
Query Lambda
    ↓
DynamoDB
    ↓
JSON
```

Responsibilities:

- Retrieve latest sensor values
- Retrieve historical measurements
- Prepare dashboard responses

## Why Separate Them?

The separation provides:

- Clear responsibilities
- Easier testing
- Easier debugging
- Independent security permissions
- Better maintainability
- Easier future scaling

The architecture follows the principle:

```text
Process Lambda
= WRITE / PROCESS

Query Lambda
= READ / QUERY
```

---

# 9. Infrastructure as Code with CloudFormation

The main infrastructure template is:

```text
templates/smart-garden.yaml
```

CloudFormation defines the AWS resources and their relationships.

Logical structure:

```text
Parameters
   ↓
Conditions
   ↓
Resources
   ├── S3
   ├── DynamoDB
   ├── IoT Core
   ├── Lambda
   ├── SNS
   ├── API Gateway
   ├── CloudFront
   ├── IAM
   └── CloudWatch
   ↓
Outputs
```

CloudFormation references such as:

```yaml
!Ref
!GetAtt
!Sub
```

connect resources and resolve dependencies.

---

# 10. Offline Deployment & Testing

Offline mode does not require AWS.

## 10.1 Prerequisites

```powershell
python --version
```

Install simulator dependencies:

```powershell
pip install requests
```

For MQTT:

```powershell
pip install AWSIoTPythonSDK
```

For local mock API:

```powershell
pip install flask flask-cors
```

---

## 10.2 Offline Sensor Test

Navigate to:

```powershell
cd src\simulator
```

Run:

```powershell
python sensor_simulator.py --offline --interval 60
```

For a quick test:

```powershell
python sensor_simulator.py --offline --interval 2 --max-readings 3
```

Expected behavior:

```text
Mode: OFFLINE
Sensor ID: sensor-001
Interval: 60 seconds

Reading:
Temperature: ...
Humidity: ...
Soil Moisture: ...
Battery: ...
```

No AWS service is required.

---

## 10.3 Local Mock API

Start the mock API:

```powershell
python mock_api.py
```

The local backend provides:

```text
POST /prod/data
GET /prod/query
```

The mock API stores received data in memory.

It is intended for development and testing and does not create AWS resources.

---

# 11. Online Deployment – API Gateway Option

## 11.1 Configure AWS

```powershell
aws configure
```

Verify:

```powershell
aws sts get-caller-identity
```

The project examples use:

```text
us-west-2
```

Keep the region consistent during deployment.

---

## 11.2 Deploy

Navigate to:

```powershell
cd scripts
```

Run:

```powershell
.\deploy.ps1
```

With email notifications:

```powershell
.\deploy.ps1 -Email "your-email@example.com"
```

With CloudFront:

```powershell
.\deploy.ps1 -Email "your-email@example.com" -EnableCloudFront $true
```

The deployment process creates or updates the CloudFormation stack and configures the application.

---

## 11.3 Test API Mode

```powershell
cd src\simulator
```

Quick test:

```powershell
python sensor_simulator.py --api --interval 2 --max-readings 3
```

Normal test:

```powershell
python sensor_simulator.py --api --interval 60
```

If necessary, specify the API URL:

```powershell
python sensor_simulator.py `
    --api `
    --api-url "https://YOUR_API_ID.execute-api.us-west-2.amazonaws.com/prod/data" `
    --interval 60
```

---

# 12. Online Deployment – IoT Core / MQTT Option

## 12.1 Required Components

MQTT requires:

- AWS IoT Thing
- X.509 certificate
- Private key
- Root CA
- IoT policy
- AWS IoT endpoint
- MQTT topic

Never commit certificates or private keys to GitHub.

---

## 12.2 MQTT Data Flow

```text
Sensor Simulator
      ↓
X.509 Certificate
      ↓
AWS IoT Core
      ↓
sensor/data
      ↓
IoT Topic Rule
      ↓
Process Lambda
      ↓
DynamoDB + S3 + SNS
```

---

## 12.3 MQTT Test

```powershell
cd src\simulator
```

Quick test:

```powershell
python sensor_simulator.py --mqtt --interval 2 --max-readings 3
```

Normal test:

```powershell
python sensor_simulator.py --mqtt --interval 60
```

WebSocket mode, when configured:

```powershell
python sensor_simulator.py --mqtt --websocket --interval 60
```

---

# 13. Generated `config.js`

The dashboard does not permanently store the API Gateway URL in the source code.

The deployment process is:

```text
CloudFormation
      ↓
API Gateway URL
      ↓
deploy.ps1
      ↓
config.js
      ↓
dashboard.js
```

This makes the deployment portable.

If a new stack creates a different API Gateway URL, the generated configuration can be updated automatically.

---

# 14. CloudFront – Optional

CloudFront is controlled through:

```text
EnableCloudFront
```

## Development

Keep CloudFront disabled:

```powershell
.\deploy.ps1
```

Architecture:

```text
Browser
   ↓
S3 Website
```

## Final Presentation

Enable CloudFront:

```powershell
.\deploy.ps1 -EnableCloudFront $true
```

Architecture:

```text
Browser
   ↓
CloudFront
   ↓
S3 Website
```

CloudFront is therefore an optional presentation and distribution layer rather than a mandatory dependency of the application logic.

---

# 15. Security & Monitoring

## 15.1 IAM

IAM controls permissions between services.

The Lambda execution role provides permissions for:

- DynamoDB
- S3
- SNS
- CloudWatch Logs
- required IoT operations

## 15.2 IoT Security

MQTT uses X.509 certificates.

The IoT policy controls:

```text
Connect
Publish
Subscribe
Receive
```

Private keys must never be committed to GitHub.

## 15.3 S3 Security

The data bucket uses:

- Server-side encryption
- Public access blocking
- HTTPS-only access
- Lifecycle management

The website bucket can be accessed directly during development or through CloudFront when CloudFront is enabled.

## 15.4 CloudWatch

CloudWatch provides:

- Lambda logs
- Metrics
- Error alarms
- Application monitoring
- Troubleshooting information

---

# 16. Cost Optimization

The project is designed as a low-cost serverless application.

It does not require:

```text
EC2
RDS
```

## 16.1 Sensor Interval

The default interval is:

```text
60 seconds
```

For normal operation:

```powershell
python sensor_simulator.py --api --interval 60
```

For MQTT:

```powershell
python sensor_simulator.py --mqtt --interval 60
```

A 60-second interval generates significantly fewer requests than a 5-second interval.

For short tests use:

```powershell
python sensor_simulator.py --api --interval 2 --max-readings 3
```

or:

```powershell
python sensor_simulator.py --mqtt --interval 2 --max-readings 3
```

## 16.2 CloudFront

Keep CloudFront disabled during development:

```powershell
.\deploy.ps1
```

Enable it only for the final presentation:

```powershell
.\deploy.ps1 -EnableCloudFront $true
```

## 16.3 Additional Cost Controls

- Avoid continuously running the simulator
- Use `--max-readings` for tests
- Use a 60-second interval for demonstrations
- Keep CloudFront disabled unless required
- Use DynamoDB on-demand billing
- Use S3 lifecycle policies
- Keep CloudWatch retention reasonable
- Delete old test data
- Clean up the CloudFormation stack after testing
- Monitor AWS Billing and Cost Management

---

# 17. Troubleshooting

## API does not work

Check:

```text
1. API Gateway URL
2. API Gateway /data resource
3. POST method
4. Lambda integration
5. Lambda permissions
6. CloudWatch logs
7. Request JSON
```

## MQTT does not work

Check:

```text
1. IoT endpoint
2. IoT Thing
3. Certificate
4. Private key
5. Root CA
6. IoT policy
7. sensor/data topic
8. IoT Rule
9. Lambda permission
10. CloudWatch logs
```

## Dashboard shows no data

Check:

```text
1. config.js
2. API Gateway GET /data
3. Query Lambda
4. DynamoDB
5. Browser console
6. S3 dashboard files
7. CloudFront if enabled
```

## Local mock API does not start

Install:

```powershell
pip install flask flask-cors
```

Then:

```powershell
cd src\simulator
python mock_api.py
```

---

# 18. Cleanup

After testing:

```powershell
cd scripts
.\cleanup.ps1
```

Then:

```powershell
.\verify-cleanup.ps1
```

Verify that unnecessary AWS resources have been removed.

Pay particular attention to:

- CloudFormation
- Lambda
- DynamoDB
- S3
- API Gateway
- IoT Core
- SNS
- CloudFront
- CloudWatch
- IAM resources

The S3 buckets and other resources use retention settings in parts of the infrastructure, so verify retained resources manually when necessary.

---

# 19. Final Testing Checklist

| Test | Expected Result |
|---|---|
| Offline simulator | Sensor data generated locally |
| Mock API | Local backend accepts sensor data |
| API POST | Sensor data reaches Process Lambda |
| Process Lambda | Data is validated and processed |
| Latest DynamoDB | Current sensor state is stored |
| History DynamoDB | Historical measurement is stored |
| S3 data bucket | Raw data is archived |
| SNS | Alert is sent when a threshold is exceeded |
| API GET | Dashboard data is returned |
| Query Lambda | Dashboard query is processed |
| Dashboard | Sensor values are displayed |
| MQTT | Data reaches IoT Core |
| IoT Rule | Lambda is triggered |
| CloudWatch | Logs and alarms are available |
| CloudFront | Dashboard is available when enabled |
| Cleanup | Unnecessary resources are removed |

---

# 20. Presentation Questions

## Why did you choose serverless?

The application uses managed and serverless AWS services such as Lambda, API Gateway, DynamoDB and S3. This reduces infrastructure management and is suitable for a small IoT monitoring application.

## Why do you use both API Gateway and IoT Core?

API Gateway provides a simple HTTPS interface for REST-based ingestion and testing. IoT Core is designed for MQTT-based IoT communication.

## Can you switch between API and MQTT?

Yes. The official sensor simulator supports `--api` and `--mqtt`. Both paths use the same Process Lambda and the same storage and alerting layers.

## Why are there two DynamoDB tables?

One table stores the latest state of each sensor, while the second stores historical sensor measurements.

## Why are there two functional S3 buckets?

One stores sensor-data archives and the other hosts the dashboard. A third S3 bucket is used only for Lambda deployment packages.

## Why are Process Lambda and Query Lambda separate?

Process Lambda handles incoming sensor data and writes data. Query Lambda reads data for the dashboard. Separating these responsibilities improves maintainability and testing.

## What is `mock_api.py`?

`mock_api.py` is a local backend testing utility. It simulates the API Gateway/Lambda behavior without connecting to AWS.

## What happened to `api_simulator.py`?

`api_simulator.py` was removed from the project. The official simulator is now `sensor_simulator.py`, while `mock_api.py` is used for local backend testing.

## Why is `config.js` generated?

The API Gateway URL is created dynamically during CloudFormation deployment. Therefore `deploy.ps1` generates `config.js` with the current endpoint instead of hard-coding it in the dashboard.

## Why is CloudFront optional?

The dashboard can work directly with S3 during development. CloudFront is enabled for the final presentation when a CDN layer is desired.

## Why use 60 seconds?

A 60-second interval reduces the number of requests and therefore reduces unnecessary AWS usage and cost while still providing enough data for a demonstration.

## What happens when a sensor sends data?

The sensor sends data through API Gateway or IoT Core. The Process Lambda validates and processes the data, updates the latest DynamoDB record, stores historical data, archives raw data in S3 and can publish an SNS alert when a threshold is exceeded.

## Why use CloudFormation?

CloudFormation defines the AWS infrastructure as code. This makes the deployment repeatable and reduces manual configuration errors.

---

# Technologies Used

## Programming Languages

- Python
- JavaScript
- HTML5
- CSS3
- PowerShell

## AWS Services

- AWS IoT Core
- AWS Lambda
- Amazon API Gateway
- Amazon DynamoDB
- Amazon S3
- Amazon SNS
- Amazon CloudFront
- Amazon CloudWatch
- AWS IAM
- AWS CloudFormation

## Development Tools

- Visual Studio Code
- AWS CLI
- Git
- GitHub
- Python pip
- PowerShell

## Local Testing

- Flask
- Flask-CORS
- Python-based sensor simulation

---

# Future Improvements

Possible future extensions include:

- Real physical garden sensors
- Automatic irrigation control
- Additional environmental sensors
- Machine-learning-based anomaly detection
- Mobile application
- Multiple garden locations
- User authentication
- Advanced analytics
- CI/CD deployment
- Automated integration testing
- Predictive plant-care recommendations

---

# License

This project was created as an AWS Capstone Project for educational purposes.