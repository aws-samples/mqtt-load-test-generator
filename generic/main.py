"""
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
 * OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

import string
import time
import json 
import math 
import ssl
import argparse
import logging
import socks
from datetime import datetime, timezone
from paho.mqtt import client as mqtt

# Setup logging
logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
streamHandler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

# Parse Arguments
parser = argparse.ArgumentParser()
parser.add_argument("--host", dest="host", required=True, help="IoT broker host address (e.g. AWS IoT Core Endpoint)")
parser.add_argument("--port", dest="port", default=8883, type=int, help="IoT broker port (e.g. AWS IoT Core Endpoint port)")
parser.add_argument("--qos", dest="qos", default=1, type=int, help="Broker publishing QoS [Default: 1]")
parser.add_argument("--topic", dest="topic", default="performance/mqtt", help="IoT topic to subscribe/publish to")
parser.add_argument("--username", dest="username", help="IoT broker username")
parser.add_argument("--password", dest="password", help="IoT broker password")
parser.add_argument("--cafile", dest="cafile", help="IoT broker CA certificate file path")
parser.add_argument("--cert", dest="cert", help="Client device certificate file path")
parser.add_argument("--key", dest="key", help="Client private key file path")
parser.add_argument("--frequency", dest="frequency", type=float, default=1, help="Delay between published messages in seconds [Default: 1]")
parser.add_argument("--not-add-timestamp", dest="not_add_timestamp", action='store_true', help="Do not add timestamp to published messages")
parser.add_argument("--total-count", dest="total", type=int, default=math.inf, help="Number of messages to publish [Default: infinite]")
parser.add_argument("--message", dest="message", type=str, default="{}", help="JSON Payload to include in published message (e.g. '{ \"AdditionalAttribute\": \"Value\" }') [Default: {}]")
parser.add_argument("--client-id", required=True, dest="client_id", help="Client ID for MQTT client (IoT Thing Name)")
<<<<<<< HEAD
parser.add_argument("--proxy-host", dest="proxy_host", default=None, help="Client id for MQTT client")
parser.add_argument("--proxy-port", dest="proxy_port", default=None, help="Client id for MQTT client")
=======
parser.add_argument("--proxy-host", dest="proxy_host", type=str, help="Proxy Host to use for MQTT connection")
parser.add_argument("--proxy-port", dest="proxy_port", type=str, help="Proxy Port to use for MQTT connection")
>>>>>>> main

args = parser.parse_args()

messageCount = 0

logger.info(f"Publishing to: {args.host}:{args.port}")

# The callback for when the client receives a CONNACK response from the server.
def on_connect(mqttc, userdata, flags, rc):
    logger.info("Connected with result code: "+str(rc))

def on_message(mqttc, obj, msg):
    logger.info(msg.topic + " " + str(msg.qos) + " " + str(msg.payload))

def on_publish(mqttc, obj, mid):
    logger.info("mid: " + str(mid))

def on_log(mqttc, obj, level, string):
    logger.info(string)

paho_client = mqtt.Client(client_id=args.client_id)
paho_client.enable_logger(logger)
paho_client.on_message = on_message
paho_client.on_connect = on_connect
paho_client.on_publish = on_publish
paho_client.on_log = on_log



if (args.proxy_host and args.proxy_port):
    logger.info(f"[INFO]: Found proxy configuration")
    paho_client.proxy_set(proxy_type=socks.HTTP, proxy_addr=args.proxy_host, proxy_port=args.proxy_port)

if (args.cafile and args.cafile != "None"):
    logger.info(f"[INFO]: Configuring broker with CA certificate file: {args.cafile}")
    if (args.cert != "None" and args.key != "None"):
        logger.info(f"[INFO]: Found certificate and key in the configuration, setting up client with certificate in {args.cert} and private key in {args.key}")
        paho_client.tls_set(ca_certs=args.cafile, certfile=args.cert, keyfile=args.key, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2)
    else:
        paho_client.tls_set(ca_certs=args.cafile)

    paho_client.tls_insecure_set(True)


if (args.username and args.password and args.password != "None"):
    logger.info(f"[INFO]: Configuring broker with password and username")
    paho_client.username_pw_set(args.username, args.password)

# Connect Paho Client
paho_client.connect(
    args.host,
    port=args.port,
    keepalive=60
)



# Publish messages
while (messageCount < args.total):
    # Create timestamp
    ts = datetime.now(tz=timezone.utc)
    timestamp = ts.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]+'Z'
    timestamp_unix = int(ts.timestamp() * 1000)
        
    # Try parsing provided message as JSON
    try:
        msg_dict = json.loads(args.message)
        msg_dict['Id'] = messageCount

        # Do not add timestamp if parameter was set accordingly
        if (not args.not_add_timestamp):
            msg_dict['SourceTimestamp'] = timestamp
            msg_dict['SourceTimestampUNIX'] = timestamp_unix

        message = json.dumps(msg_dict)

    except json.decoder.JSONDecodeError:
        # Fallback to CSV if not valid JSON
        logger.info("Cannot interpret message as JSON, falling back to CSV")
        message = f"{args.message};{messageCount};{timestamp};{timestamp_unix}"

    # Publish message
    logger.info(f"Publishing to: {args.topic}")
    paho_client.publish(
        topic=args.topic,
        payload=message,
        qos=args.qos
    )

    # Sleep before next message is published
    time.sleep(args.frequency)

    # Increment message counter
    messageCount += 1
