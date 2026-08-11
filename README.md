# 🌱 Smart Garden Manager

A serverless, event-driven IoT monitoring and analysis platform built with AWS.

The Smart Garden Manager simulates environmental sensor data such as temperature, humidity, soil moisture, battery level, sensor ID, location, and timestamp.

The project supports three official sensor simulation modes:

- **Offline** – local testing without AWS
- **API** – HTTPS ingestion through Amazon API Gateway
- **MQTT** – secure MQTT ingestion through AWS IoT Core

Both online ingestion paths use the same processing Lambda. Sensor data is validated, processed and stored in Amazon DynamoDB and Amazon S3. Amazon SNS can send threshold alerts, while a web dashboard retrieves and visualizes current and historical sensor data.

The AWS infrastructure is deployed as Infrastructure as Code (IaC) using AWS CloudFormation.

---

# 📋 Table of Contents

1. [Project Overview](#1-project-overview)
2. [Project Structure & File Responsibilities](#2-project-structure--file-responsibilities)
3. [System Architecture & Data Flow](#3-system-architecture--data-flow)
4. [AWS Services & Dependencies](#4-aws-services--dependencies)
5. [Infrastructure as Code with CloudFormation](#5-infrastructure-as-code-with-cloudformation)
6. [Offline Deployment & Testing](#6-offline-deployment--testing)
7. [Online Deployment – API Gateway Option](#7-online-deployment--api-gateway-option)
8. [Online Deployment – IoT Core/MQTT Option](#8-online-deployment--iot-coremqtt-option)
9. [Security, Monitoring & Cost Optimization](#9-security-monitoring--cost-optimization)
10. [Troubleshooting, Cleanup & Presentation Questions](#10-troubleshooting-cleanup--presentation-questions)
11. [Technologies Used](#technologies-used)
12. [Future Improvements](#future-improvements)

---

# 1. Project Overview

## 1.1 Project Goal

The goal of the Smart Garden Manager is to demonstrate how environmental IoT data can be generated, transmitted, processed, stored, monitored and visualized using AWS serverless services.

A Python-based sensor simulator replaces physical hardware so that the complete application can be developed and tested locally before connecting it to AWS.

The project demonstrates a complete sensor-data lifecycle:

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
- Common Lambda processing layer for both online ingestion paths
- Current sensor-state storage in DynamoDB
- Historical sensor-data storage in DynamoDB
- Raw-data archival in S3
- REST API for dashboard queries
- Static web dashboard hosted in S3
- Optional CloudFront distribution
- SNS threshold alerts
- CloudWatch logging and monitoring
- CloudFormation-based infrastructure deployment
- PowerShell deployment and cleanup automation
- Configurable sensor intervals for cost control

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
│   │   ├── api_simulator.py
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

| File | Responsibility | Main Dependencies |
|---|---|---|
| `smart-garden.yaml` | Defines the AWS infrastructure | CloudFormation |
| `process_data.py` | Validates and processes incoming sensor data | DynamoDB, S3, SNS, IAM |
| `query_data.py` | Retrieves data for the dashboard | DynamoDB, API Gateway, IAM |
| `sensor_simulator.py` | Official sensor simulator | Python, Requests, AWS IoT SDK |
| `index.html` | Dashboard structure | Web browser |
| `style.css` | Dashboard styling | `index.html` |
| `dashboard.js` | Dashboard logic and API communication | API Gateway, generated `config.js` |
| `deploy.ps1` | Builds, deploys and configures the application | AWS CLI, CloudFormation |
| `build.ps1` | Creates deployment artifacts | PowerShell |
| `test.ps1` | Runs project tests and validation | PowerShell |
| `cleanup.ps1` | Removes deployed resources | AWS CLI, CloudFormation |
| `verify-cleanup.ps1` | Verifies cleanup | AWS CLI |
| `generate_env.py` | Generates local environment configuration | Python |

## 2.2 Generated Configuration

### `config.js`

`config.js` is **not a manually maintained source file**.

It is generated automatically by `deploy.ps1` after CloudFormation has created the API Gateway endpoint.

The process is:

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

The generated file contains runtime configuration such as the current API Gateway URL.

It should not be manually edited or committed as a permanent source file.

## 2.3 Legacy and Test Utilities

The following files are **not part of the primary application flow**.

### `api_simulator.py`

**Status: Legacy / Test Utility**

This is an older standalone API Gateway simulator.

It can generate sensor data and send it directly to an API Gateway endpoint.

It is retained for compatibility and additional API testing.

It is **not the official sensor simulator** and should not be used as the primary project entry point.

The official simulator is:

```powershell
python sensor_simulator.py --api --interval 60
```

The legacy utility can still be used for isolated API testing:

```powershell
python api_simulator.py --test
```

When using this utility, an explicit API URL should preferably be supplied rather than relying on its legacy default configuration.

### `mock_api.py`

**Status: Optional Local Test Utility**

This file can be used to simulate an API locally without connecting to AWS.

It is useful for development and testing of API-related behavior.

It is not part of the deployed AWS architecture.

### `test_connection_websocket.py`

**Status: Optional MQTT/WebSocket Test Utility**

This file is used for testing MQTT/WebSocket connectivity.

It is not required for the standard API or MQTT deployment path.

The primary MQTT implementation is contained in:

```text
sensor_simulator.py
```

---

# 3. System Architecture & Data Flow

The application is organized into five logical layers.

```text
┌──────────────────────────────────────────────────────────────┐
│ LAYER 5 – PRESENTATION                                       │
│ S3 Dashboard + optional CloudFront                           │
├──────────────────────────────────────────────────────────────┤
│ LAYER 4 – API                                                 │
│ API Gateway + Query Lambda                                    │
├──────────────────────────────────────────────────────────────┤
│ LAYER 3 – PROCESSING                                          │
│ Process Lambda + SNS                                          │
├──────────────────────────────────────────────────────────────┤
│ LAYER 2 – STORAGE                                             │
│ DynamoDB + S3                                                 │
├──────────────────────────────────────────────────────────────┤
│ LAYER 1 – INGESTION                                           │
│ Sensor Simulator + API Gateway / IoT Core                    │
└──────────────────────────────────────────────────────────────┘

Cross-cutting:
IAM        → Security and permissions
CloudWatch → Logs, metrics and monitoring

Infrastructure:
CloudFormation → Creates and connects AWS resources
```

## 3.1 API Gateway Ingestion

```text
Python Sensor Simulator
        ↓
HTTPS POST
        ↓
API Gateway
        ↓
Process Lambda
        ↓
┌───────┼────────┐
↓       ↓        ↓
DynamoDB S3      SNS
```

## 3.2 IoT Core / MQTT Ingestion

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
┌───────┼────────┐
↓       ↓        ↓
DynamoDB S3      SNS
```

## 3.3 Dashboard Data Flow

```text
Browser
   ↓
CloudFront (optional)
   ↓
S3 Dashboard
   ↓
dashboard.js
   ↓
config.js
   ↓
API Gateway GET
   ↓
Query Lambda
   ↓
DynamoDB
   ↓
JSON Response
   ↓
Dashboard
```

## 3.4 Switching Between API and MQTT

The official simulator supports:

```powershell
python sensor_simulator.py --offline --interval 60

python sensor_simulator.py --api --interval 60

python sensor_simulator.py --mqtt --interval 60
```

Only one operating mode should be selected at a time.

The important architectural point is that API Gateway and IoT Core use the same processing Lambda:

```text
                    ┌── API Gateway ──┐
                    │                 │
Sensor Simulator ───┤                 ▼
                    │          Process Lambda
                    │                 │
                    └── IoT Core ─────┘
                                      │
                         ┌────────────┼────────────┐
                         ↓            ↓            ↓
                      DynamoDB       S3           SNS
```

Changing the ingestion method does not require redesigning the storage or dashboard layers.

---

# 4. AWS Services & Dependencies

| AWS Service | Role in the Project | Main Connections |
|---|---|---|
| AWS IoT Core | Receives MQTT sensor messages | Thing, certificate, policy, IoT Rule |
| Amazon API Gateway | HTTPS REST API | Lambda |
| AWS Lambda | Processes and queries sensor data | IAM, DynamoDB, S3, SNS, CloudWatch |
| Amazon DynamoDB | Stores latest and historical measurements | Lambda |
| Amazon S3 | Stores raw data and dashboard files | Lambda, dashboard, CloudFront |
| Amazon SNS | Sends threshold notifications | Process Lambda |
| Amazon CloudFront | Optional dashboard distribution | S3 |
| AWS IAM | Controls permissions | Lambda, IoT, S3, CloudFormation |
| Amazon CloudWatch | Logs, metrics and alarms | Lambda and other AWS services |
| AWS CloudFormation | Creates and manages infrastructure | All defined AWS resources |

## 4.1 Main Dependency Chain

```text
Sensor Simulator
      │
      ├──────────────→ API Gateway
      │                     │
      │                     ▼
      └──────────────→ IoT Core → IoT Rule
                            │
                            ▼
                    Process Lambda
                            │
              ┌─────────────┼─────────────┐
              ↓             ↓             ↓
           DynamoDB         S3            SNS
              │
              ↓
         Query Lambda
              │
              ↓
         API Gateway
              │
              ↓
          Dashboard
```

IAM supplies permissions between services.

CloudWatch provides observability and troubleshooting information.

---

# 5. Infrastructure as Code with CloudFormation

The main infrastructure template is:

```text
templates/smart-garden.yaml
```

CloudFormation creates and connects the AWS resources instead of requiring every resource to be created manually.

## 5.1 Logical Template Structure

```text
Parameters
   ↓
Conditions
   ↓
Resources
   ├── IoT Core
   ├── DynamoDB
   ├── S3
   ├── Lambda
   ├── SNS
   ├── API Gateway
   ├── CloudFront
   ├── IAM
   └── CloudWatch
   ↓
Outputs
```

The application is logically divided into five layers, but these layers remain inside one CloudFormation template.

CloudFormation uses resource references such as:

```yaml
!Ref
!GetAtt
!Sub
```

to connect resources and resolve dependencies.

## 5.2 CloudFront Control

CloudFront is optional.

Development:

```powershell
.\deploy.ps1
```

Final presentation:

```powershell
.\deploy.ps1 -EnableCloudFront $true
```

The PowerShell parameter is converted into the CloudFormation parameter used by the infrastructure template.

## 5.3 Automatic API Configuration

The deployment process is:

```text
CloudFormation
      ↓
API Gateway created
      ↓
API Gateway URL returned as CloudFormation Output
      ↓
deploy.ps1
      ↓
config.js generated
      ↓
Dashboard uploaded to S3
```

This avoids permanently hard-coding the API Gateway URL in `dashboard.js`.

---

# 6. Offline Deployment & Testing

Offline mode allows the simulator and dashboard to be tested without AWS.

## 6.1 Prerequisites

Recommended local environment:

- Windows 10/11
- Visual Studio Code
- Python 3.9+
- Git
- AWS CLI for online deployment
- Internet connection only when AWS services are required

Check:

```powershell
python --version
aws --version
git --version
```

## 6.2 Install Simulator Dependencies

From the simulator directory:

```powershell
pip install requests AWSIoTPythonSDK
```

Optional:

```powershell
pip install python-dotenv
```

## 6.3 Offline Sensor Test

Navigate to:

```powershell
cd src\simulator
```

Quick test:

```powershell
python sensor_simulator.py --offline --interval 2 --max-readings 3
```

Normal simulation:

```powershell
python sensor_simulator.py --offline --interval 60
```

Stop with:

```text
CTRL+C
```

Expected behavior:

```text
Mode: OFFLINE
Sensor ID: sensor-001
Interval: 60 seconds

READING 000001
Temperature: ...
Humidity: ...
Soil Moisture: ...
Battery: ...
```

No AWS request should be generated in offline mode.

## 6.4 Offline Dashboard Test

Start a local web server:

```powershell
cd src\dashboard
python -m http.server 8000
```

Open:

```text
http://localhost:8000
```

For local mock-data testing, the dashboard can be configured to use mock data.

---

# 7. Online Deployment – API Gateway Option

Option 1 is recommended for the first AWS integration test because it does not require MQTT certificate configuration.

## 7.1 Configure AWS CLI

```powershell
aws configure
```

Verify:

```powershell
aws sts get-caller-identity
```

The deployment examples use:

```text
us-west-2
```

Keep the deployment region consistent.

## 7.2 Deploy AWS Infrastructure

Navigate to:

```powershell
cd scripts
```

Deploy:

```powershell
.\deploy.ps1
```

With SNS email:

```powershell
.\deploy.ps1 -Email "your-email@example.com"
```

For final presentation with CloudFront:

```powershell
.\deploy.ps1 -Email "your-email@example.com" -EnableCloudFront $true
```

The deployment script:

1. Checks AWS access
2. Determines the deployment region
3. Verifies required project files
4. Creates Lambda deployment packages
5. Uploads deployment artifacts
6. Creates or updates the CloudFormation stack
7. Reads CloudFormation outputs
8. Retrieves the API Gateway URL
9. Generates `config.js`
10. Uploads dashboard files
11. Verifies the generated configuration
12. Displays deployed endpoints

## 7.3 Test API Mode

Navigate to:

```powershell
cd src\simulator
```

Quick test:

```powershell
python sensor_simulator.py --api --interval 2 --max-readings 3
```

Normal simulation:

```powershell
python sensor_simulator.py --api --interval 60
```

If an explicit endpoint is required:

```powershell
python sensor_simulator.py `
    --api `
    --api-url "https://YOUR_API_ID.execute-api.us-west-2.amazonaws.com/prod/data" `
    --interval 60
```

The API URL can also be supplied through:

```powershell
$env:SMART_GARDEN_API_URL="https://YOUR_API_ID.execute-api.us-west-2.amazonaws.com/prod/data"
```

## 7.4 Test API Directly

Example:

```powershell
$body = @{
    sensor_id = "sensor-001"
    temperature = 24.5
    humidity = 61.2
    soil_moisture = 42.7
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "YOUR_API_GATEWAY_URL" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body
```

Expected result:

```text
HTTP 200
```

Then verify:

1. Process Lambda executed
2. DynamoDB contains the measurement
3. S3 contains the raw-data object
4. SNS generated an alert if a threshold was exceeded
5. CloudWatch contains Lambda logs

---

# 8. Online Deployment – IoT Core/MQTT Option

Option 2 uses AWS IoT Core and MQTT.

## 8.1 Required IoT Components

The MQTT simulator requires:

- IoT Thing
- X.509 device certificate
- Private key
- Root CA certificate
- IoT policy
- AWS IoT endpoint
- MQTT topic

Example local certificate structure:

```text
src/
└── simulator/
    └── certs/
        ├── device-certificate.pem.crt
        ├── device-private-key.pem.key
        └── root-CA.crt
```

Never commit private keys or certificates to GitHub.

## 8.2 MQTT Data Flow

```text
Sensor Simulator
      ↓
X.509 Certificate
      ↓
AWS IoT Core
      ↓
MQTT Topic
      ↓
IoT Topic Rule
      ↓
Process Lambda
      ↓
DynamoDB + S3 + SNS
```

The MQTT topic must be consistent between:

- simulator
- IoT policy
- IoT Rule

## 8.3 MQTT Setup

The project includes:

```text
scripts/setup_and_run.ps1
```

This script prepares the MQTT environment, including certificate and policy configuration.

Despite the historical filename, the script is primarily a **setup/configuration utility** and should not be interpreted as the main simulator itself.

After the MQTT configuration is prepared, run:

```powershell
cd src\simulator
```

Quick test:

```powershell
python sensor_simulator.py --mqtt --interval 2 --max-readings 3
```

Normal simulation:

```powershell
python sensor_simulator.py --mqtt --interval 60
```

Explicit certificate paths can be supplied when required:

```powershell
python sensor_simulator.py `
    --mqtt `
    --interval 60 `
    --cert ".\certs\device-certificate.pem.crt" `
    --private-key ".\certs\device-private-key.pem.key" `
    --root-ca ".\certs\root-CA.crt"
```

If MQTT over WebSocket is supported by the simulator:

```powershell
python sensor_simulator.py --mqtt --websocket --interval 60
```

## 8.4 Switching Between API and MQTT

Yes.

The official simulator supports:

```text
--offline
--api
--mqtt
```

Examples:

```powershell
python sensor_simulator.py --offline --interval 60

python sensor_simulator.py --api --interval 60

python sensor_simulator.py --mqtt --interval 60
```

Only one operating mode should be selected at a time.

The ingestion method can be changed without redesigning the processing, storage or dashboard layers.

---

# 9. Security, Monitoring & Cost Optimization

## 9.1 Security

### IAM

IAM controls what each AWS service is allowed to do.

The project follows the principle of least privilege.

The processing Lambda requires permissions for the AWS resources it actually uses, such as:

```text
dynamodb:PutItem
s3:PutObject
sns:Publish
CloudWatch Logs permissions
```

Administrator permissions should not be required by the application Lambda.

### IoT Security

MQTT authentication uses X.509 certificates.

The IoT policy controls permitted MQTT actions and resources.

Private keys and certificates must never be committed to GitHub.

The `.gitignore` excludes sensitive certificate and environment files.

### S3 / CloudFront

When CloudFront is enabled, the intended architecture is:

```text
Internet
   ↓
CloudFront
   ↓
S3 Dashboard Bucket
```

S3 access should be configured according to the selected CloudFront architecture.

## 9.2 Monitoring

CloudWatch is used for:

- Lambda logs
- Error investigation
- Application monitoring
- Metrics
- Alarms

Recommended troubleshooting sequence:

```text
Sensor Simulator
       ↓
API Gateway / IoT Core
       ↓
Lambda
       ↓
DynamoDB / S3
       ↓
Query Lambda
       ↓
API Gateway GET
       ↓
Dashboard
```

## 9.3 Cost Optimization

The project is designed as a low-cost serverless application.

It does not require EC2 or RDS.

### Sensor Interval

For normal demonstrations use:

```text
60 seconds
```

instead of sending data every few seconds.

For quick tests:

```powershell
python sensor_simulator.py --api --interval 2 --max-readings 3
```

or:

```powershell
python sensor_simulator.py --mqtt --interval 2 --max-readings 3
```

### CloudFront

Development:

```powershell
.\deploy.ps1
```

Final presentation:

```powershell
.\deploy.ps1 -EnableCloudFront $true
```

### Additional Cost Controls

- Avoid continuously running the simulator
- Use limited test readings
- Keep CloudFront disabled when unnecessary
- Remove old S3 test data
- Use appropriate S3 lifecycle policies
- Use reasonable CloudWatch log retention
- Use on-demand DynamoDB capacity for small workloads
- Delete the CloudFormation stack after testing
- Monitor AWS Billing and Cost Management

Actual AWS costs depend on region, usage, account type, Free Tier eligibility and current AWS pricing.

---

# 10. Troubleshooting, Cleanup & Presentation Questions

## 10.1 Troubleshooting

### Offline simulator does not start

Check:

```powershell
python --version
pip install requests AWSIoTPythonSDK
python sensor_simulator.py --help
```

### API request fails

Check in this order:

```text
1. API Gateway URL
2. API Gateway stage/deployment
3. POST method
4. Lambda integration
5. Lambda CloudWatch logs
6. IAM permissions
7. Request JSON
```

### MQTT does not work

Check:

```text
1. AWS IoT endpoint
2. IoT Thing
3. Certificate
4. Private key
5. Root CA
6. IoT policy
7. MQTT topic
8. IoT Rule
9. Lambda permission
10. CloudWatch logs
```

### Dashboard shows no data

Check:

```text
1. Generated config.js
2. API Gateway GET endpoint
3. Query Lambda
4. DynamoDB table
5. Browser developer console
6. S3 dashboard files
7. CloudFront distribution, if enabled
```

If DynamoDB is empty, follow the ingestion path backwards.

### CloudFront dashboard is not updated

Check:

```text
1. Dashboard uploaded to S3
2. Generated config.js contains the correct endpoint
3. CloudFront distribution status
4. Browser cache
5. CloudFront invalidation
```

---

## 10.2 Cleanup

After testing:

```powershell
cd scripts
.\cleanup.ps1
```

Then verify:

```powershell
.\verify-cleanup.ps1
```

Check that unused resources have been removed:

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

S3 buckets may need to be emptied before they can be deleted.

---

## 10.3 Final Testing Checklist

| Test | Expected Result |
|---|---|
| Offline simulator | Sensor data is generated locally |
| Offline dashboard | Dashboard loads with mock data |
| API POST | Successful HTTP response |
| Processing Lambda | Measurement is processed |
| DynamoDB Latest | Current value is stored |
| DynamoDB History | Historical record is stored |
| S3 archive | Raw-data object is created |
| API GET | JSON data is returned |
| Dashboard | Sensor values are displayed |
| MQTT | Data reaches IoT Core |
| IoT Rule | Lambda is triggered |
| SNS | Alert is generated when threshold is exceeded |
| CloudWatch | Logs are available |
| CloudFront | Dashboard is accessible when enabled |
| Cleanup | Unused resources are removed |

---

## 10.4 Presentation Questions

### Why did you choose a serverless architecture?

The application uses managed and serverless services such as Lambda, DynamoDB, API Gateway and S3. This reduces infrastructure management and allows the application to scale without managing servers.

### Why do you use both API Gateway and IoT Core?

API Gateway provides a simple HTTPS interface for REST-based ingestion and testing. IoT Core is designed specifically for MQTT-based IoT communication.

### Can you switch between API and MQTT?

Yes. The official sensor simulator supports `--api` and `--mqtt`. Both ingestion paths use the same processing Lambda.

### Why do you use two DynamoDB tables?

The latest-state table provides efficient access to the current sensor state, while the historical table stores measurements over time.

### Why do you use S3?

S3 provides durable object storage for raw sensor data and hosts the static dashboard.

### Why do you use Lambda?

Lambda processes sensor data without requiring a continuously running server.

### Why do you use SNS?

SNS provides notification functionality when predefined sensor thresholds are exceeded.

### Why do you use CloudWatch?

CloudWatch provides logs, metrics and alarms that help monitor and troubleshoot the application.

### Why do you use CloudFormation?

CloudFormation defines the infrastructure as code, making the deployment repeatable and reducing manual configuration.

### How do you reduce costs?

I use a 60-second sensor interval, limit test readings, keep optional CloudFront disabled during development, use lifecycle and retention policies, avoid unnecessary continuous execution, and clean up AWS resources after testing.

### What happens when a sensor sends data?

The data enters through API Gateway or IoT Core. The processing Lambda validates and processes it, stores current and historical values in DynamoDB, archives raw data in S3, and can publish an SNS alert when a threshold is exceeded.

### What is `api_simulator.py`?

`api_simulator.py` is a legacy/test utility retained for additional API testing. It is not the primary simulator used by the final architecture. The official simulator is `sensor_simulator.py`, which supports offline, API and MQTT modes.

### Why is `config.js` not maintained manually?

The API Gateway URL is created dynamically by CloudFormation. Therefore `deploy.ps1` generates `config.js` after deployment so that the dashboard always receives the current API endpoint.

### How would you improve the project in the future?

Possible improvements include physical garden sensors, automatic irrigation, anomaly detection, user authentication, multiple garden locations, mobile access, advanced analytics, CI/CD deployment and automated integration testing.

---

# Technologies Used

## Programming

- Python
- JavaScript
- HTML5
- CSS3
- PowerShell

## AWS

- AWS IoT Core
- AWS Lambda
- Amazon DynamoDB
- Amazon S3
- Amazon API Gateway
- Amazon CloudFront
- Amazon SNS
- Amazon CloudWatch
- AWS IAM
- AWS CloudFormation

## Development Tools

- Visual Studio Code
- AWS CLI
- Git
- GitHub
- Python pip
- Python virtual environment

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

---

# License

This project was created as an AWS Capstone Project for educational purposes.