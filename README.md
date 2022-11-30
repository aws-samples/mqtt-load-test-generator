# MQTT Load Test Generator

The **MQTT Load Test Generator** is a simple implementation to test and measure the MQTT connection between an Edge location and an AWS IoT endpoint.

MQTT messages are send to the AWS IoT endoint using a Python script running on an Edge device either natively or inside a Docker container. Sent Timestamps and sequence numbers can then analysed by the backend running in the AWS cloud.

![Alt text](documentation/images/Architecture_Diagram.png?raw=true "Architecture Overview")

## Table of Contents- [MQTT Load Test Generator](#mqtt-load-test-generator)

- [MQTT Load Test Generator](#mqtt-load-test-generator)
  - [Table of Contents- MQTT Load Test Generator](#table-of-contents--mqtt-load-test-generator)
  - [Solution Overview](#solution-overview)
  - [Repository Overview](#repository-overview)
  - [Getting started - Setting up the solution](#getting-started---setting-up-the-solution)
    - [Prerequisites](#prerequisites)
    - [1. Clone the Repository](#1-clone-the-repository)
    - [Optional - Create AWS IoT Thing](#optional---create-aws-iot-thing)
    - [2. Environment Preparation](#2-environment-preparation)
    - [3. Download Amazon RootCA Certificate & copy IoT Thing certificates](#3-download-amazon-rootca-certificate--copy-iot-thing-certificates)
    - [4. Create Cloudformation Stack](#4-create-cloudformation-stack)
    - [5. Send Data from the Edge Device to AWS IoT Core](#5-send-data-from-the-edge-device-to-aws-iot-core)
    - [6. Run the Glue Crawler](#6-run-the-glue-crawler)
    - [7. Create Views in Amazon Athena](#7-create-views-in-amazon-athena)
    - [8. Analyse Data in Amazon Athena](#8-analyse-data-in-amazon-athena)
  - [Solution Cleanup](#solution-cleanup)
    - [1. Delete the Cloudformation Stack](#1-delete-the-cloudformation-stack)
    - [2. Manually remove S3 Buckets](#2-manually-remove-s3-buckets)
    - [3. Manually remove IoT Thing](#3-manually-remove-iot-thing)
    - [4. Manually remove local Certificates](#4-manually-remove-local-certificates)
    - [5. Manually remove Athena Workgroup](#5-manually-remove-athena-workgroup)

## Solution Overview

Working with IoT Devices on the Edge and centralized Services in AWS, troubleshooting connection issues, packet drops or temporary loss of connectivity can be frustrating and time-consuming. This solution can help to make connectivity issues visible by putting some load on the connection. The basic idea of the solution is generating a JSON Payload at the Edge, sending it to the AWS IoT Core using MQTT and then analysing the latency and packet loss using the data that was sent/received. To test the connection for different message sizes, the payload contains customizable dummy data which is not being used for later analyses.

MQTT JSON Payload generated and send by the Python script on the Edge location:

```
id - Incremented message counter
source_timestamp_unix - UNIX Timestamp at the time the message was sent
destination_timestamp_unix - UNIX Timestamp at the time the message was received by IoT Core (added by an IoT Rule in IoT Core)
```

Once an MQTT message is received by the AWS IoT Core endpoint, an IoT Rule will add the current timestamp (destination_timestamp_unix) to the message and forward it to a Kinesis Firehose Delivery Stream. Data is then being converted to Apache Parquet format to speed up analyses and is stored in an S3 bucket. An AWS Glue Crawler is used for updating the AWS Glue Data Catalog. The data can then be queried using pre defined or customized Amazon Athena queries.

`main.py` Python Script Arguments:

- `--host`: IoT broker host address (e.g. AWS IoT Core Endpoint)
- `--port`: IoT broker port (e.g. AWS IoT Core Endpoint port)
- `--qos`: Broker publishing QoS [Default: 1]
- `--topic`: IoT topic to subscribe/publish to
- `--username`: IoT broker username
- `--password`: IoT broker password
- `--cafile`: IoT broker CA certificate file path
- `--cert`: Client device certificate file path
- `--key`: Client private key file path
- `--frequency`: Delay between published messages in seconds [Default: 1]
- `--not-add-timestamp`: Do not add timestamp to published messages
- `--total-count`: Number of messages to publish [Default: infinite]
- `--message`: JSON Payload to include in published message (e.g. '{ \"AdditionalAttribute\": \"Value\" }')
- `--client-id`: Client ID for MQTT client (IoT Thing Name)
- `--proxy-host`: Proxy Host to use for MQTT connection
- `--proxy-port`: Proxy Port to use for MQTT connection


## Repository Overview

The repository consists of the following directories:

- cloudformation - Cloudformation templates for setting up AWS services (Kinesis, S3, Athena, etc.)
- generic - Python scripts and other related files

## Getting started - Setting up the solution

### Prerequisites

- Python 3
- AWS CLI
- IoT Thing connected to AWS IoT Core (Private Key & Certificate available)
- Valid AWS CLI credentials

### 1. Clone the Repository

  ```bash
  git clone <REPOSITORY_URL>
  ```

### Optional - Create AWS IoT Thing

```bash
export AWS_ACCOUNT_ID=<AWS_ACCOUNT_ID>
export AWS_REGION=<AWS_REGION>
export IOT_THING_NAME=<THING_NAME>
export IOT_POLICY_NAME=<IOT_POLICY_NAME_TO_CREATE>
export IOT_TOPIC=performance/mqtt # Can be changed to any other topic, however the Cloudformation Parameter needs to be adjusted accordingly

cd <REPOSITORY_PATH>
mkdir certs

# Prepare Policy Document for IOT Policy
touch policy.json && cat <<EOF >policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iot:Connect",
      "Resource": "arn:aws:iot:$AWS_REGION:$AWS_ACCOUNT_ID:client/${iot:Connection.Thing.ThingName}",
      "Condition": {
        "Bool": { "iot:Connection.Thing.IsAttached": "true" }
      }
    },
    {
      "Effect": "Allow",
      "Action": "iot:Publish",
      "Resource": "arn:aws:iot:$AWS_REGION:$AWS_ACCOUNT_ID:topic/$IOT_TOPIC"
    }
  ]
}
EOF

# Create IoT Thing
aws iot create-thing \
  --thing-name $IOT_THING_NAME

# Create IOT Certificate
IOT_CERTIFICATE_ARN=$(
  aws iot create-keys-and-certificate \
    --set-as-active \
    --certificate-pem-outfile certs/certificate.pem.crt \
    --private-key-outfile certs/private.pem.key \
    --query certificateArn --output text
)

# Create IoT Certificate Policy
aws iot create-policy \
  --policy-name $IOT_POLICY_NAME \
  --policy-document file://policy.json

# Delete temporary Policy Document
rm policy.json

# Attach IoT Policy to Certificate
aws iot attach-policy \
  --target $IOT_CERTIFICATE_ARN \
  --policy-name $IOT_POLICY_NAME

# Attach Certificate to IOT Thing
aws iot attach-thing-principal \
  --principal $IOT_CERTIFICATE_ARN \
  --thing-name $IOT_THING_NAME
```

### 2. Environment Preparation

Create Python virtual environment:

  ```bash
  python -m venv venv
  ```

Activate the virtual environment:

  ```bash
  source venv/bin/activate
  ```

Install the requirements:

  ```bash
  cd <REPOSITORY_PATH>
  pip install -r generic/requirements.txt
  ```

### 3. Download Amazon RootCA Certificate & copy IoT Thing certificates

  ```bash
  cd <REPOSITORY_PATH>
  mkdir certs
  wget https://www.amazontrust.com/repository/AmazonRootCA1.pem -O certs/AmazonRootCA1.pem
  ```

  Copy IoT Thing Certificate & Private Key into `certs` directory.

### 4. Create Cloudformation Stack

  ```bash
  cd <REPOSITORY_PATH>
  aws cloudformation deploy --stack-name mqtt-load-test-generator --template-file cloudformation/template.yml --capabilities CAPABILITY_NAMED_IAM
  ```

The Cloudformation template supports some Parameters (e.g. IoT Topic, etc.), the command above will use the defaults.

### 5. Send Data from the Edge Device to AWS IoT Core

  Get AWS IoT Core Endpoint URL:

  ```bash
  cd <REPOSITORY_PATH>
  export AWS_IOTENDPOINT=$(aws iot describe-endpoint --endpoint-type iot:Data-ATS --query endpointAddress --output text)
  ```

  Send MQTT messages:

  ```bash
  cd <REPOSITORY_PATH>

  python generic/main.py \
    --host $AWS_IOTENDPOINT \
    --port 8883 \
    --topic performance/mqtt \
    --cafile certs/AmazonRootCA1.pem \
    --cert certs/<THING-CERTIFICATE-FILE> \
    --key certs/<THING-PRIVATEKEY-FILE> \
    --total-count <NUMBER_OF_MESSAGES_TO_SEND> \
    --frequency <SLEEP_TIME_BETWEEN_MESSAGES> \
    --client-id <IOT_THING_NAME>
  ```

### 6. Run the Glue Crawler

Once some messages have been published and data has been collected in the S3 Bucket, manually run the Glue Crawler to update the Athena table. The Glue crawler does not have a default schedule configured and needs to be triggered manually whenever data in the S3 bucket should be indexed. Please note, published messaged will not be stored on the S3 Bucket instantly but are cached by Kinesis and delivered in batches.

### 7. Create Views in Amazon Athena

Use the pre-defined Queries in the created Athena Workgroup (e.g. "MQTT_Load_Test_Workgroup") to create the views to analyse Message Latency and Message Loss.
Queries need to be run in the following order due to dependencies:

1. End2End_IoT_Latency
2. End2End_IoT_MessageLoss

### 8. Analyse Data in Amazon Athena

Use the Views created in the previous step to analyse Latency and Message Loss.

## Solution Cleanup

### 1. Delete the Cloudformation Stack

```bash
aws cloudformation delete-stack --stack-name <STACK_NAME>
```

### 2. Manually remove S3 Buckets

The three S3 Buckets created by the Cloudformation Stack (Bucket for the IoT Messages, Bucket for Athena Query results & Logging Bucket) will be retained after Stack deletion. Empty & delete them either using the AWS console or CLI:

```bash
aws s3 rb s3://<S3_BUCKET_NAME> --force
```

### 3. Manually remove IoT Thing

If the IoT thing that was used for the solution is no longer required, remove it including IoT Policy & Certificate using the AWS Console or CLI.
If you followed the optional steps in chapter "Optional - Create AWS IoT Thing" you can use the following commands to remove the resources.

```bash
export IOT_THING_NAME=<THING_NAME>
export IOT_POLICY_NAME=<IOT_POLICY_NAME_TO_CREATE>

# Get IoT Certificate ARN
IOT_CERTIFICATE_ARN=$(aws iot list-thing-principals \
  --thing-name $IOT_THING_NAME \
  --query principals[0] --output text)

# Detach IoT Policy
aws iot detach-policy \
  --policy-name $IOT_POLICY_NAME \
  --target $IOT_CERTIFICATE_ARN

# Delete IoT Policy
aws iot delete-policy \
  --policy-name $IOT_POLICY_NAME

# Detach IoT Certificate
aws iot detach-thing-principal \
  --thing-name $IOT_THING_NAME \
  --principal $IOT_CERTIFICATE_ARN

# Delete IoT Thing
aws iot delete-thing \
  --thing-name $IOT_THING_NAME
```


### 4. Manually remove local Certificates

IoT Thing certificates and Amazon Root CA files have been downloaded to the `certs` directory. Since the IoT Thing was deleted, the local certificates can also be deleted:

```bash
cd <REPOSITORY_PATH>

rm -r certs/
```

### 5. Manually remove Athena Workgroup

The Athena Workgroup created by the Cloudformation Stack will be retained after Stack deletion, please delete it manually using the AWS Console or CLI once you are done with data analyses.

```bash
aws athena delete-work-group \
  --work-group MQTT_Load_Test_Workgroup
```


## General Notes

### Publishing messages larger than qos 0

Notice that when you try to use this MQTT client to publish messages with qos>0, you might experience that only a maximum of 20 messages are received at the end of the MQTT broker. If so, please update the "max inflight message" configuration on the broker side, if applicable, such as [mosquitto max_inflight_messages](http://mosquitto.org/man/mosquitto-conf-5.html); so that more messages can pass through from the MQTT test client.
