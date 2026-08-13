# Smart Garden Manager

A serverless AWS prototype for collecting, processing, storing, monitoring, and visualising simulated smart-garden sensor data.

The repository contains three simulator modes and two AWS data-ingestion paths:

- **API mode:** the sensor simulator sends HTTPS `POST /data` requests to API Gateway.
- **MQTT mode:** the sensor simulator publishes to AWS IoT Core on `sensor/data`.
- **Offline mode:** the sensor simulator generates readings locally without contacting AWS.

The AWS backend processes sensor readings with Lambda, stores the latest and historical values in DynamoDB, archives raw readings in an S3 data bucket, and sends SNS notifications when configured thresholds are exceeded. A static web dashboard reads the query API through API Gateway. The dashboard uses adaptive HTTP polling rather than push-based streaming.

> **Repository-verified scope:** This README describes the code and CloudFormation template contained in this repository. It does not claim that AWS resources are currently deployed or that an AWS account is configured.

---

## 1. Architecture

```text
                         +----------------------+
                         |  Sensor Simulator    |
                         | sensor_simulator.py  |
                         +----------+-----------+
                                    |
                    +---------------+---------------+
                    |                               |
                 API mode                        MQTT mode
                    |                               |
                    v                               v
             API Gateway                         IoT Core
              POST /data                       sensor/data
                    |                               |
                    +---------------+---------------+
                                    |
                                    v
                           Process Data Lambda
                                    |
              +---------------------+---------------------+
              |                     |                     |
              v                     v                     v
        DynamoDB Latest       DynamoDB History          S3
        current state         historical records     raw archive
                                    |
                                    v
                                  SNS
                           threshold alerts

Dashboard
    |
    v
API Gateway GET /data
    |
    v
Query Data Lambda
    |
    v
DynamoDB Latest + History

S3 Website Bucket (dashboard hosting)
    |
    +----------------------------------+
    |                                  |
    v                                  v
S3 Website URL                  [OPTIONAL]
(direct access)                 CloudFront Distribution
                                    |
                                    v
                              Better performance
                              HTTPS by default
                              Caching & CDN
                              ~$0.50-1.00/month

User Access:
  - Without CloudFront: http://bucket.s3-website-region.amazonaws.com
  - With CloudFront:    https://d123.cloudfront.net
```

### Dashboard delivery

The dashboard is uploaded to a dedicated S3 website bucket by the deployment script.

The current deployment uses **three S3 buckets** with different responsibilities:

1. **Data bucket** — stores raw sensor-data archives.
2. **Website bucket** — stores the dashboard files, including `index.html`, `style.css`, `dashboard.js`, and generated `config.js`.
3. **Lambda-code bucket** — stores packaged Lambda deployment artifacts used by CloudFormation.

The third bucket is a deployment-artifact bucket, not an application data store.

CloudFormation can optionally create a CloudFront distribution. CloudFront is **disabled by default** in `scripts/deploy.ps1` and can be enabled with `-EnableCloudFront $true`.

---

## 2. AWS resources defined by CloudFormation

The template is:

```text
templates/smart-garden.yaml
```

It defines the main application resources used by the project, including:

- AWS IoT Core Thing and IoT Policy
- IoT Topic Rule for `sensor/data`
- AWS Lambda functions:
  - Process Data Lambda
  - Query Data Lambda
- API Gateway REST API with:
  - `POST /data` → Process Data Lambda
  - `GET /data` → Query Data Lambda
  - `OPTIONS /data` → CORS support
- DynamoDB:
  - latest-value table
  - historical-data table
- S3 data bucket for raw sensor archives
- S3 website bucket for the dashboard
- S3 Lambda-code bucket for deployment artifacts
- SNS alert topic and optional email subscription
- CloudWatch alarms and dashboard
- Optional CloudFront distribution

The CloudFormation template uses pay-per-request DynamoDB billing, server-side encryption, and point-in-time recovery for the DynamoDB tables.

---

## 3. Repository structure

The repository contains these application files and scripts:

```text
Smart-Garden-main/
├── README.md
├── scripts/
│   ├── build.ps1
│   ├── cleanup.ps1
│   ├── deploy.ps1
│   ├── generate_env.py
│   ├── setup_mqtt.ps1
│   ├── test.ps1
│   └── verify-cleanup.ps1
├── src/
│   ├── dashboard/
│   │   ├── dashboard.js
│   │   ├── index.html
│   │   └── style.css
│   ├── lambda/
│   │   ├── process_data.py
│   │   └── query_data.py
│   └── simulator/
│       ├── mock_api.py
│       └── sensor_simulator.py
└── templates/
    └── smart-garden.yaml
```

`config.js` is **not committed to the repository**. It is generated by `scripts/deploy.ps1` from the deployed API URL and dashboard settings.

---

## 4. Sensor simulation

The simulator is:

```text
src/simulator/sensor_simulator.py
```

It generates readings containing at least:

```json
{
  "sensor_id": "sensor-001",
  "timestamp": "2026-08-12T12:00:00Z",
  "temperature": 22.5,
  "humidity": 62.0,
  "soil_moisture": 45.0
}
```

The simulator also supports additional sensor fields used by the processing Lambda when supplied, such as `location` and `battery`.

The simulator supports exactly one of the following ingestion modes per run:

```text
--offline
--api
--mqtt
```

### Examples

```powershell
python src/simulator/sensor_simulator.py --offline
```

```powershell
python src/simulator/sensor_simulator.py --api --interval 60
```

```powershell
python src/simulator/sensor_simulator.py --mqtt --interval 60
```

MQTT over WebSocket is also supported:

```powershell
python src/simulator/sensor_simulator.py --mqtt --websocket --interval 60
```

The simulator accepts configuration through command-line arguments and environment variables, including the API URL and IoT endpoint.

---

## 5. Offline mode

Offline mode is implemented in the sensor simulator.

```powershell
python src/simulator/sensor_simulator.py --offline
```

In this mode the simulator only generates and prints sensor readings locally. It does not send the readings to API Gateway or AWS IoT Core.

The repository also contains dashboard mock-data logic in `src/dashboard/dashboard.js`. The dashboard can use generated mock data when:

```javascript
window.USE_MOCK_DATA = true;
```

is set in its generated `config.js`.

The deployment script generates `config.js` with `USE_MOCK_DATA = false`, so the normal deployed dashboard uses the API.

---

## 6. API mode

API mode sends sensor data to the API Gateway endpoint.

```text
Sensor Simulator
      |
      | HTTPS POST
      v
API Gateway POST /data
      |
      v
Process Data Lambda
```

CloudFormation configures:

```text
POST /data
```

to invoke `ProcessDataFunction`.

The deployed API endpoint is exposed as the CloudFormation output:

```text
APIGatewayURL
```

with the form:

```text
https://<api-id>.execute-api.<region>.amazonaws.com/prod/data
```

The API can be disabled at deployment time with:

```powershell
.\scripts\deploy.ps1 -EnableAPI $false
```

The deployment script enables API Gateway by default.

---

## 7. MQTT mode

MQTT mode uses AWS IoT Core.

The simulator publishes sensor readings to:

```text
sensor/data
```

The standard MQTT/TLS connection uses port:

```text
8883
```

The simulator also supports MQTT over WebSocket on:

```text
443
```

### Certificate-based MQTT connection

For the standard TLS MQTT connection, the simulator uses:

- Root CA certificate
- Device certificate
- Device private key

The code checks for the required certificate/key files before starting the certificate-based MQTT connection.

The MQTT setup script is:

```text
scripts/setup_mqtt.ps1
```

The IoT resources and topic rule are defined in:

```text
templates/smart-garden.yaml
```

The IoT Topic Rule subscribes to:

```text
sensor/data
```

and invokes the Process Data Lambda.

---

## 8. Data processing Lambda

The main backend processing function is:

```text
src/lambda/process_data.py
```

For a valid sensor event it:

1. Parses the event.
2. Validates the input.
3. Extracts the sensor values.
4. Stores the latest sensor state in DynamoDB.
5. Stores the historical record in DynamoDB.
6. Archives the original input data in S3 when a data bucket is configured.
7. Checks the configured thresholds.
8. Publishes an SNS notification when one or more thresholds are exceeded.
9. Returns an HTTP-style Lambda response.

The Lambda uses environment variables for table names, S3 bucket, SNS topic ARN, logging/debug configuration, and threshold values.

---

## 9. SNS threshold logic

The processing Lambda checks six threshold conditions.

| Sensor | Low condition | High condition |
|---|---:|---:|
| Soil moisture | `< 30` | `> 80` |
| Temperature | `< 5 °C` | `> 35 °C` |
| Humidity | `< 40 %` | `> 90 %` |

The comparisons are strict:

- `30` is not below the soil-moisture low threshold.
- `80` is not above the soil-moisture high threshold.
- `35 °C` is not above the high-temperature threshold.
- `5 °C` is not below the low-temperature threshold.

If multiple conditions are violated by one reading, the Lambda collects all matching alerts and sends them together as one SNS notification when an SNS topic ARN is configured.

The dashboard uses the same numeric threshold values for its status indicators.

---

## 10. DynamoDB storage

The application uses two DynamoDB tables.

### Latest table

The latest table stores the current state for each sensor.

The primary key is:

```text
sensor_id
```

The processing Lambda writes fields including:

```text
sensor_id
temperature
humidity
soil_moisture
timestamp
last_updated
```

and optionally `location` and `battery` when present in the input.

### Historical table

The historical table stores individual readings.

Its primary key is:

```text
sensor_id
timestamp
```

Each historical record also receives a generated:

```text
record_id
```

and can contain `location` and `battery` when supplied.

The Query Data Lambda reads historical records directly using the `sensor_id` and timestamp key.

> The CloudFormation template also defines a `SensorDateIndex` GSI using `sensor_id` + `date`. The current `process_data.py` history item does not write a `date` attribute, and the query Lambda does not use this GSI.

---

## 11. S3 raw archive

The processing Lambda archives the original sensor input to the configured S3 data bucket.

The object key has this structure:

```text
raw-data/{sensor_id}/{YYYY}/{MM}/{DD}/{HH-MM-SS-microseconds}.json
```

For example:

```text
raw-data/sensor-001/2026/08/12/14-30-25-123456.json
```

The object content is one JSON record followed by a newline and is uploaded with:

```text
Content-Type: application/jsonl
```

Therefore, the archive is best described as **JSONL-style raw sensor records stored in `.json` S3 objects**, rather than as a multi-record JSON array.

The CloudFormation data bucket:

- has versioning enabled;
- uses server-side encryption with AES256;
- blocks public access;
- has a lifecycle rule for `raw-data/`;
- uses the configured data-retention period.

---

## 12. Query Data Lambda and API response

The query function is:

```text
src/lambda/query_data.py
```

The dashboard accesses it through:

```text
GET /data
```

The API accepts query parameters including:

```text
sensor_id
hours
```

The query Lambda reads the latest sensor record and historical records from DynamoDB and calculates statistics for the returned history.

The successful response body contains the following top-level fields:

```json
{
  "latest": {},
  "history": [],
  "stats": {},
  "count": 0,
  "sensor_id": "sensor-001",
  "time_range": "Last 24 hours",
  "query_timestamp": "2026-08-12T12:00:00Z",
  "metadata": {
    "api_version": "2.1",
    "source": "lambda-query-data",
    "debug_mode": false
  }
}
```

The dashboard uses:

```text
latest
history
stats
count
```

to update the current values, charts, statistics, and history table.

The Lambda returns an API Gateway-compatible response with:

```text
statusCode
headers
body
```

and JSON content type.

---

## 13. Dashboard

The dashboard consists of:

```text
src/dashboard/index.html
src/dashboard/style.css
src/dashboard/dashboard.js
```

It displays:

- current temperature;
- current humidity;
- current soil moisture;
- threshold/status indicators;
- historical charts;
- summary statistics;
- historical sensor records;
- the last update time.

The dashboard requests data from:

```text
GET /data?sensor_id=<sensor>&hours=<hours>
```

### Refresh behavior

The dashboard automatically polls the Query API using an adaptive refresh
interval based on the current local time:

| Time | Refresh interval |
|---|---:|
| 23:00–05:59 | 60 seconds |
| 06:00–07:59 | 45 seconds |
| 08:00–20:00 | 30 seconds |
| 21:00–22:59 | 45 seconds |

The dashboard performs an immediate data load when the dashboard starts.
When the browser tab is hidden, automatic refreshes are skipped. When the
dashboard becomes visible again, it immediately loads the latest data and
restarts the refresh timer.

A manual refresh is also available.

Therefore, the dashboard uses adaptive HTTP polling rather than
push-based real-time streaming.

---

## 14. `config.js` generation

`config.js` is generated by:

```text
scripts/deploy.ps1
```

The generated configuration contains the API URL from the deployed CloudFormation stack, sensor ID, timeout values, and refresh interval. The USE_MOCK_DATA flag is set to false for the deployed dashboard.

The generated configuration contains values including:

```javascript
window.SMART_GARDEN_CONFIG = {
    API_URL: "...",
    SENSOR_ID: "sensor-001",
    REQUEST_TIMEOUT: 15000,
    REFRESH_INTERVAL: 10000
};

window.USE_MOCK_DATA = false;
```

The deployed dashboard therefore normally uses the Query API.

Because `config.js` is generated during deployment, opening `index.html` directly from the repository without generating a configuration file first is not the normal deployment workflow.

---

## 15. Dashboard mock mode

`src/dashboard/dashboard.js` contains local mock-data generation.

When:

```javascript
window.USE_MOCK_DATA
```

is true, the dashboard generates local sample history/current values instead of requesting the API.

The generated deployment configuration sets:

```javascript
window.USE_MOCK_DATA = false;
```

so the deployed dashboard uses AWS API data.

The separate:

```text
src/simulator/mock_api.py
```

is a simplified local HTTP/mock-processing utility. Its response is not byte-for-byte identical to the production Process Data Lambda response.

---

## 16. Deployment

The main deployment script is:

```text
scripts/deploy.ps1
```

It:

1. Checks the AWS CLI/account configuration.
2. Determines the AWS region.
3. Requests an email address for SNS notifications when one is not supplied.
4. Creates/packages Lambda code.
5. Uploads Lambda packages to an S3 code bucket.
6. Deploys the CloudFormation stack.
7. Generates the dashboard `config.js`.
8. Uploads the dashboard files to the website bucket.
9. Displays deployment outputs.

### Basic deployment

From PowerShell:

```powershell
.\scripts\deploy.ps1
```

The script enables API Gateway by default.

### Enable CloudFront

```powershell
.\scripts\deploy.ps1 -EnableCloudFront $true
```

### Disable API Gateway

```powershell
.\scripts\deploy.ps1 -EnableAPI $false
```

### Specify email

```powershell
.\scripts\deploy.ps1 -Email "your-email@example.com"
```

The exact AWS region can also be supplied:

```powershell
.\scripts\deploy.ps1 -Region "us-west-2"
```

If no region is supplied to the script and no AWS CLI region is configured, the script falls back to:

```text
us-west-2
```

---

## 17. MQTT setup

The repository includes:

```text
scripts/setup_mqtt.ps1
```

for MQTT-related setup. The script performs the following steps:

1. Creates IoT certificates in `src/simulator/certs/`
2. Downloads the Root CA certificate from Amazon
3. Creates the IoT policy `smart-garden-iot-policy` with minimal permissions
4. Attaches the policy to the certificate
5. Generates the `.env` file using `generate_env.py`

The simulator can then use the generated MQTT endpoint/certificate configuration.

The MQTT connection supports:

```text
MQTT over TLS:       port 8883
MQTT over WebSocket: port 443
```

The simulator reads configuration from command-line arguments and/or environment variables, including:

```text
SMART_GARDEN_API_URL
SMART_GARDEN_IOT_ENDPOINT
SMART_GARDEN_IOT_TOPIC
```

and the certificate/key configuration used by the MQTT client.

---

## 18. Testing

The repository contains:

```text
scripts/test.ps1
```

The test script includes checks for:

- Python syntax compilation;
- local/offline Lambda-related tests;
- dashboard mock mode;
- simulator execution;
- AWS account configuration;
- CloudFormation stack status;
- API Gateway availability;
- DynamoDB tables.

Run:

```powershell
.\scripts\test.ps1
```

The exact tests performed depend on whether AWS CLI/account configuration and a deployed stack are available.

---

## 19. Cleanup

The repository provides:

```text
scripts/cleanup.ps1
```

and:

```text
scripts/verify-cleanup.ps1
```

for cleanup/verification operations.

Because the CloudFormation template uses retention policies for several resources, cleanup should be performed carefully and according to the behavior implemented by the scripts.

---

## 20. Monitoring

The CloudFormation template can create CloudWatch monitoring resources.

The template includes alarms for:

- Process Data Lambda errors;
- Query Data Lambda errors;
- IoT connection success metric.

The Lambda functions also write application logs to CloudWatch Logs.

When CloudWatch alarms are enabled, the template creates a CloudWatch dashboard containing Lambda invocation, duration, and error metrics.

---

## 21. Security-related implementation

The CloudFormation template includes several security controls:

- DynamoDB server-side encryption;
- DynamoDB point-in-time recovery;
- S3 server-side encryption;
- S3 public-access blocking;
- S3 policies denying non-HTTPS requests;
- IAM roles for Lambda and IoT actions;
- certificate-based MQTT/TLS support.

The API Gateway methods in the current template use:

```text
AuthorizationType: NONE
```

for the GET/POST data endpoints.

Therefore, this repository does **not** implement authenticated API access through Cognito or another API authorization mechanism.

---

## 22. Current data flow

### API ingestion

```text
sensor_simulator.py --api
        |
        v
HTTPS POST /data
        |
        v
API Gateway
        |
        v
Process Data Lambda
        |
        +----> DynamoDB latest
        |
        +----> DynamoDB history
        |
        +----> S3 raw archive
        |
        +----> SNS when thresholds are exceeded
```

### MQTT ingestion

```text
sensor_simulator.py --mqtt
        |
        v
AWS IoT Core
        |
        v
IoT Topic Rule: sensor/data
        |
        v
Process Data Lambda
        |
        +----> DynamoDB latest
        |
        +----> DynamoDB history
        |
        +----> S3 raw archive
        |
        +----> SNS when thresholds are exceeded
```

### Dashboard query

```text
Dashboard
    |
    | GET /data?sensor_id=...&hours=...
    v
API Gateway
    |
    v
Query Data Lambda
    |
    +----> DynamoDB latest
    |
    +----> DynamoDB history
    |
    v
JSON response
    |
    v
Dashboard
    |
    +----> current values
    +----> charts
    +----> statistics
    +----> history table

Adaptive polling: 30s (day) / 45s (transition) / 60s (night)
Refresh is paused while the browser tab is hidden
```

---

## 23. Implemented modes at a glance

| Mode | Implemented | AWS required | Data path |
|---|---|---|---|
| Offline simulator | Yes | No | Local simulator only |
| API simulator | Yes | Yes | Simulator → API Gateway → Process Lambda |
| MQTT simulator | Yes | Yes | Simulator → IoT Core → IoT Rule → Process Lambda |
| Dashboard API mode | Yes | Yes | Dashboard → GET API → Query Lambda |
| Dashboard mock mode | Yes | No | Dashboard-generated mock data |

Only one simulator ingestion mode is selected per run.

---

## 24. Important implementation details

### Threshold values

```text
Soil moisture:
  low  < 30 %
  high > 80 %

Temperature:
  low  < 5 °C
  high > 35 °C

Humidity:
  low  < 40 %
  high > 90 %
```

### Dashboard refresh

Adaptive HTTP polling:
- 30 seconds during daytime (08:00–20:00)
- 45 seconds during transition periods (06:00–07:59 and 21:00–22:59)
- 60 seconds during night mode (23:00–05:59)
- refresh is paused while the browser tab is hidden
```

### MQTT

```text
TLS MQTT:        8883
WebSocket MQTT:  443
Topic:           sensor/data
```

### S3 archive

```text
raw-data/{sensor_id}/{YYYY}/{MM}/{DD}/{timestamp}.json
Content-Type: application/jsonl
```

### API

```text
GET  /data → Query Data Lambda
POST /data → Process Data Lambda
```

### Dashboard configuration

```text
config.js → generated during deployment
```

---

## 25. Known repository limitations / exactness notes

The following points are intentionally documented so that the README does not claim functionality that is not present in the current repository:

1. `config.js` is generated during deployment and is not committed.
2. The deployed configuration uses API mode (`USE_MOCK_DATA = false`).
3. Dashboard updates use adaptive HTTP polling (30s/45s/60s depending on time of day) rather than a push/WebSocket data stream. The polling is paused when the browser tab is hidden.
4. The S3 archive uses `.json` object names but uploads JSONL-style content with `application/jsonl`.
5. Historical readings are stored in both DynamoDB and S3.
6. The `SensorDateIndex` GSI is defined in CloudFormation, but the current processing Lambda does not populate the `date` attribute and the query Lambda does not use this index.
7. The local dashboard mock-data path exists, but it is separate from the normal deployed API path.
8. `src/simulator/mock_api.py` is a simplified local mock and does not reproduce every field of the production Process Data Lambda response.
9. API GET/POST methods currently use `AuthorizationType: NONE`.
10. CloudFront is optional and disabled by default by `scripts/deploy.ps1`.
11. Cognito authentication is not implemented in the current repository.
12. Athena is not implemented in the current repository.

---

## 26. Presentation summary

For a technical presentation, the core data flow can be explained as:

```text
Sensor Simulator
      |
      +---- HTTPS ----> API Gateway ----+
      |                                 |
      +---- MQTT ----> IoT Core -> Rule-+
                                        |
                                        v
                                Process Data Lambda
                                  /      |       \
                                 /       |        \
                                v        v         v
                         DynamoDB     S3 Data      SNS
                         latest +     archive     alerts
                         history
                                ^
                                |
                         Query Data Lambda
                                ^
                                |
                         API Gateway GET /data
                                ^
                                |
                           Dashboard
```

The infrastructure is defined by CloudFormation. IAM provides permissions,
CloudWatch provides monitoring, and CloudFront is optional for dashboard
delivery.

For the S3 architecture, explain the current deployment as **two application
buckets plus one deployment-artifact bucket**: data archive, dashboard
website, and Lambda deployment packages.

## 27. Project status

The current implementation provides an end-to-end serverless smart-garden prototype:

- simulated environmental data;
- API and MQTT ingestion paths;
- Lambda-based processing;
- DynamoDB latest and historical storage;
- S3 raw-data archiving;
- SNS threshold alerts;
- API-based dashboard queries;
- adaptive dashboard polling (30s/45s/60s based on time of day);
- local simulator offline mode;
- dashboard mock-data support;
- CloudFormation infrastructure as code;
- optional CloudFront delivery;
- CloudWatch monitoring resources.

The README deliberately describes the **implemented repository behavior**, rather than promising additional services or features that are not present in the current code.
