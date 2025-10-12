import asyncio
import json
import logging
import ssl
import websockets
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# List of all OCPP 1.6 test messages
TEST_MESSAGES = [
    # Authorize
    [
        2,
        "12345",
        "Authorize",
        {
            "idTag": "TAG123"
        }
    ],
    # BootNotification
    [
        2,
        "12346",
        "BootNotification",
        {
            "chargePointModel": "ModelX",
            "chargePointVendor": "VendorY",
            "firmwareVersion": "1.2.3"
        }
    ],
    # CancelReservation
    [
        2,
        "12347",
        "CancelReservation",
        {
            "reservationId": 1001
        }
    ],
    # ChangeAvailability
    [
        2,
        "12348",
        "ChangeAvailability",
        {
            "connectorId": 1,
            "type": "Operative"
        }
    ],
    # ChangeConfiguration
    [
        2,
        "12349",
        "ChangeConfiguration",
        {
            "key": "HeartbeatInterval",
            "value": "300"
        }
    ],
    # ClearCache
    [
        2,
        "12350",
        "ClearCache",
        {}
    ],
    # ClearChargingProfile
    [
        2,
        "12351",
        "ClearChargingProfile",
        {
            "id": 1,
            "connectorId": 1,
            "chargingProfilePurpose": "TxProfile",
            "stackLevel": 0
        }
    ],
    # DataTransfer
    [
        2,
        "12352",
        "DataTransfer",
        {
            "vendorId": "VendorX",
            "messageId": "CustomMessage",
            "data": "CustomData"
        }
    ],
    # DiagnosticsStatusNotification
    [
        2,
        "12353",
        "DiagnosticsStatusNotification",
        {
            "status": "Uploaded"
        }
    ],
    # FirmwareStatusNotification
    [
        2,
        "12354",
        "FirmwareStatusNotification",
        {
            "status": "Downloaded"
        }
    ],
    # GetCompositeSchedule
    [
        2,
        "12372",
        "GetCompositeSchedule",
        {
            "connectorId": 1,
            "duration": 3600,
            "chargingRateUnit": "W"
        }
    ],
    # GetConfiguration
    [
        2,
        "12355",
        "GetConfiguration",
        {
            "key": ["HeartbeatInterval"]
        }
    ],
    # GetDiagnostics
    [
        2,
        "12356",
        "GetDiagnostics",
        {
            "location": "ftp://example.com/diagnostics",
            "startTime": "2025-10-12T10:00:00Z",
            "stopTime": "2025-10-12T11:00:00Z",
            "retries": 3,
            "retryInterval": 60
        }
    ],
    # GetLocalListVersion
    [
        2,
        "12357",
        "GetLocalListVersion",
        {}
    ],
    # Heartbeat
    [
        2,
        "12358",
        "Heartbeat",
        {}
    ],
    # MeterValues
    [
        2,
        "12359",
        "MeterValues",
        {
            "connectorId": 1,
            "transactionId": 100,
            "meterValue": [
                {
                    "timestamp": "2025-10-12T11:00:00Z",
                    "sampledValue": [
                        {
                            "value": "500",
                            "context": "Sample.Periodic",
                            "measurand": "Energy.Active.Import.Register",
                            "unit": "Wh"
                        }
                    ]
                }
            ]
        }
    ],
    # RemoteStartTransaction
    [
        2,
        "12360",
        "RemoteStartTransaction",
        {
            "idTag": "TAG123",
            "connectorId": 1
        }
    ],
    # RemoteStopTransaction
    [
        2,
        "12361",
        "RemoteStopTransaction",
        {
            "transactionId": 100
        }
    ],
    # ReserveNow
    [
        2,
        "12362",
        "ReserveNow",
        {
            "connectorId": 1,
            "expiryDate": "2025-10-12T12:00:00Z",
            "idTag": "TAG123",
            "reservationId": 1001,
            "parentIdTag": "PARENT_TAG"
        }
    ],
    # Reset
    [
        2,
        "12363",
        "Reset",
        {
            "type": "Hard"
        }
    ],
    # SendLocalList
    [
        2,
        "12364",
        "SendLocalList",
        {
            "listVersion": 1,
            "updateType": "Full",
            "localAuthorizationList": [
                {
                    "idTag": "TAG123",
                    "idTagInfo": {
                        "status": "Accepted"
                    }
                }
            ]
        }
    ],
    # SetChargingProfile
    [
        2,
        "12365",
        "SetChargingProfile",
        {
            "connectorId": 1,
            "csChargingProfiles": {
                "chargingProfileId": 1,
                "stackLevel": 0,
                "chargingProfilePurpose": "TxProfile",
                "chargingProfileKind": "Absolute",
                "chargingSchedule": {
                    "chargingRateUnit": "W",
                    "chargingSchedulePeriod": [
                        {
                            "startPeriod": 0,
                            "limit": 10000
                        }
                    ]
                }
            }
        }
    ],
    # StartTransaction
    [
        2,
        "12366",
        "StartTransaction",
        {
            "connectorId": 1,
            "idTag": "TAG123",
            "meterStart": 1000,
            "timestamp": "2025-10-12T11:00:00Z"
        }
    ],
    # StatusNotification
    [
        2,
        "12367",
        "StatusNotification",
        {
            "connectorId": 1,
            "errorCode": "NoError",
            "status": "Available"
        }
    ],
    # StopTransaction
    [
        2,
        "12368",
        "StopTransaction",
        {
            "transactionId": 100,
            "idTag": "TAG123",
            "meterStop": 1500,
            "timestamp": "2025-10-12T11:30:00Z"
        }
    ],
    # TriggerMessage
    [
        2,
        "12369",
        "TriggerMessage",
        {
            "requestedMessage": "StatusNotification",
            "connectorId": 1
        }
    ],
    # UnlockConnector
    [
        2,
        "12370",
        "UnlockConnector",
        {
            "connectorId": 1
        }
    ],
    # UpdateFirmware
    [
        2,
        "12371",
        "UpdateFirmware",
        {
            "location": "ftp://example.com/firmware",
            "retrieveDate": "2025-10-12T12:00:00Z",
            "retries": 3,
            "retryInterval": 60
        }
    ]
]

async def test_ocpp_server():
    # Configure SSL context (disable for ws:// testing)
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE  # Ignore certificate verification for testing

    uri = "wss://localhost:9000/CP_1"  # Use ws://localhost:9000/CP_1 for non-SSL testing

    try:
        async with websockets.connect(
            uri,
            subprotocols=["ocpp1.6"],
            ssl=ssl_context
        ) as websocket:
            logging.info("Connected to OCPP server")

            for message in TEST_MESSAGES:
                # Send test message
                message_json = json.dumps(message)
                logging.info(f"Sending message: {message_json}")
                await websocket.send(message_json)

                # Receive and log response
                response = await websocket.recv()
                logging.info(f"Received response: {response}")

                # Optional: Add response validation here
                response_data = json.loads(response)
                if response_data[0] != 3 or response_data[1] != message[1]:
                    logging.error(f"Invalid response for message {message[2]}: {response}")
                else:
                    logging.info(f"Valid response for {message[2]}")

                # Small delay to ensure server processes each message
                await asyncio.sleep(0.5)

    except Exception as e:
        logging.error(f"Client error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ocpp_server())
