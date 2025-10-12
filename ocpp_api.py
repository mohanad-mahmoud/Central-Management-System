from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import json
from dataclasses import asdict
from ocpp.v16 import call_result
from ocpp.v16.enums import (
    AuthorizationStatus,
    RegistrationStatus,
    RemoteStartStopStatus,
    AvailabilityStatus,
    ConfigurationStatus,
    ClearCacheStatus,
    DataTransferStatus,
    ResetStatus,
    DiagnosticsStatus,
    FirmwareStatus,
    ReservationStatus,
    GenericStatus,
    MessageTrigger,
    AvailabilityType,
    ResetType,
    UpdateType,
    ChargingRateUnitType,
    ChargingProfilePurposeType,
    ChargingProfileKindType
)
from ocpp.routing import on
from ocpp.v16 import ChargePoint as cp

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="OCPP 1.6 WebSocket Server", description="WebSocket-based OCPP 1.6 Server")

# Store all connected WebSocket clients
connected_clients = []

# Pydantic models for request validation (same as HTTP version)
class IdTagInfo(BaseModel):
    status: str = Field(..., example="Accepted")

class AuthorizeRequest(BaseModel):
    id_tag: str = Field(..., max_length=20, example="TAG123", alias="idTag")

class BootNotificationRequest(BaseModel):
    charge_point_model: str = Field(..., max_length=20, example="ModelX", alias="chargePointModel")
    charge_point_vendor: str = Field(..., max_length=50, example="VendorY", alias="chargePointVendor")
    firmware_version: Optional[str] = Field(None, max_length=50, example="1.0.0", alias="firmwareVersion")

class CancelReservationRequest(BaseModel):
    reservation_id: int = Field(..., ge=1, example=1, alias="reservationId")

class ChangeAvailabilityRequest(BaseModel):
    connector_id: int = Field(..., ge=0, example=1, alias="connectorId")
    type: AvailabilityType = Field(..., example="Operative")

class ChangeConfigurationRequest(BaseModel):
    key: str = Field(..., max_length=50, example="MaxCurrent")
    value: str = Field(..., max_length=512, example="32")

class ClearCacheRequest(BaseModel):
    pass

class ClearChargingProfileRequest(BaseModel):
    id: Optional[int] = Field(None, ge=1, example=1)
    connector_id: Optional[int] = Field(None, ge=0, example=1, alias="connectorId")
    charging_profile_purpose: Optional[ChargingProfilePurposeType] = Field(None, example="TxProfile", alias="chargingProfilePurpose")
    stack_level: Optional[int] = Field(None, ge=0, example=0, alias="stackLevel")

class DataTransferRequest(BaseModel):
    vendor_id: str = Field(..., max_length=255, example="VendorX", alias="vendorId")
    message_id: Optional[str] = Field(None, max_length=50, example="CustomMsg", alias="messageId")
    data: Optional[str] = Field(None, max_length=1000, example="SomeData")

class DiagnosticsStatusNotificationRequest(BaseModel):
    status: DiagnosticsStatus = Field(..., example="Uploaded")

class FirmwareStatusNotificationRequest(BaseModel):
    status: FirmwareStatus = Field(..., example="Downloaded")

class GetConfigurationRequest(BaseModel):
    key: Optional[List[str]] = Field(None, example=["example_key"])

class GetDiagnosticsRequest(BaseModel):
    location: str = Field(..., example="ftp://server/diagnostics.log")
    start_time: Optional[str] = Field(None, example="2025-10-08T09:30:00Z", alias="startTime")
    stop_time: Optional[str] = Field(None, example="2025-10-08T10:30:00Z", alias="stopTime")
    retries: Optional[int] = Field(None, ge=1, example=3)
    retry_interval: Optional[int] = Field(None, ge=1, example=300, alias="retryInterval")

class GetLocalListVersionRequest(BaseModel):
    pass

class HeartbeatRequest(BaseModel):
    pass

class MeterValueSample(BaseModel):
    value: str = Field(..., example="1500")
    unit: Optional[str] = Field(None, example="Wh")

class MeterValue(BaseModel):
    timestamp: str = Field(..., example="2025-10-08T12:16:00Z")
    sampled_value: List[MeterValueSample] = Field(..., example=[{"value": "1500"}], alias="sampledValue")

class MeterValuesRequest(BaseModel):
    connector_id: int = Field(..., ge=0, example=1, alias="connectorId")
    transaction_id: Optional[int] = Field(None, ge=1, example=1, alias="transactionId")
    meter_value: List[MeterValue] = Field(..., example=[{"timestamp": "2025-10-08T12:16:00Z", "sampledValue": [{"value": "1500"}]}], alias="meterValue")

class RemoteStartTransactionRequest(BaseModel):
    id_tag: str = Field(..., max_length=20, example="TAG123", alias="idTag")
    connector_id: Optional[int] = Field(None, ge=0, example=1, alias="connectorId")

class RemoteStopTransactionRequest(BaseModel):
    transaction_id: int = Field(..., ge=1, example=1, alias="transactionId")

class ReserveNowRequest(BaseModel):
    connector_id: int = Field(..., ge=0, example=1, alias="connectorId")
    expiry_date: str = Field(..., example="2025-10-08T14:00:00Z", alias="expiryDate")
    id_tag: str = Field(..., max_length=20, example="TAG123", alias="idTag")
    reservation_id: int = Field(..., ge=1, example=1, alias="reservationId")
    parent_id_tag: Optional[str] = Field(None, max_length=20, example="PARENT123", alias="parentIdTag")

class ResetRequest(BaseModel):
    type: ResetType = Field(..., example="Soft")

class AuthorizationListEntry(BaseModel):
    id_tag: str = Field(..., max_length=20, example="TAG123", alias="idTag")
    id_tag_info: Optional[IdTagInfo] = Field(None, example={"status": "Accepted"}, alias="idTagInfo")

class SendLocalListRequest(BaseModel):
    list_version: int = Field(..., ge=1, example=1, alias="listVersion")
    update_type: UpdateType = Field(..., example="Full", alias="updateType")
    local_authorization_list: Optional[List[AuthorizationListEntry]] = Field(None, example=[{"idTag": "TAG123", "idTagInfo": {"status": "Accepted"}}], alias="localAuthorizationList")

class ChargingSchedulePeriod(BaseModel):
    start_period: int = Field(..., ge=0, example=0, alias="startPeriod")
    limit: float = Field(..., example=1000.0)

class ChargingSchedule(BaseModel):
    charging_rate_unit: ChargingRateUnitType = Field(..., example="W", alias="chargingRateUnit")
    charging_schedule_period: List[ChargingSchedulePeriod] = Field(..., example=[{"startPeriod": 0, "limit": 1000.0}], alias="chargingSchedulePeriod")

class ChargingProfile(BaseModel):
    charging_profile_id: int = Field(..., ge=1, example=1, alias="chargingProfileId")
    stack_level: int = Field(..., ge=0, example=0, alias="stackLevel")
    charging_profile_purpose: ChargingProfilePurposeType = Field(..., example="TxProfile", alias="chargingProfilePurpose")
    charging_profile_kind: ChargingProfileKindType = Field(..., example="Absolute", alias="chargingProfileKind")
    charging_schedule: ChargingSchedule = Field(..., example={"chargingRateUnit": "W", "chargingSchedulePeriod": [{"startPeriod": 0, "limit": 1000.0}]})

class SetChargingProfileRequest(BaseModel):
    connector_id: int = Field(..., ge=0, example=1, alias="connectorId")
    cs_charging_profiles: ChargingProfile = Field(..., alias="csChargingProfiles")

class StartTransactionRequest(BaseModel):
    connector_id: int = Field(..., ge=0, example=1, alias="connectorId")
    id_tag: str = Field(..., max_length=20, example="TAG123", alias="idTag")
    meter_start: int = Field(..., ge=0, example=1000, alias="meterStart")
    timestamp: str = Field(..., example="2025-10-08T12:16:00Z")

class StatusNotificationRequest(BaseModel):
    connector_id: int = Field(..., ge=0, example=1, alias="connectorId")
    error_code: str = Field(..., example="NoError", alias="errorCode")
    status: str = Field(..., example="Available")

class StopTransactionRequest(BaseModel):
    transaction_id: int = Field(..., ge=1, example=1, alias="transactionId")
    id_tag: str = Field(..., max_length=20, example="TAG123", alias="idTag")
    meter_stop: int = Field(..., ge=0, example=2000, alias="meterStop")
    timestamp: str = Field(..., example="2025-10-08T12:16:00Z")

class TriggerMessageRequest(BaseModel):
    requested_message: MessageTrigger = Field(..., example="BootNotification", alias="requestedMessage")
    connector_id: Optional[int] = Field(None, ge=0, example=1, alias="connectorId")

class UpdateFirmwareRequest(BaseModel):
    location: str = Field(..., example="ftp://server/firmware.bin")
    retrieve_date: str = Field(..., example="2025-10-08T10:00:00Z", alias="retrieveDate")
    retries: Optional[int] = Field(None, ge=1, example=3)
    retry_interval: Optional[int] = Field(None, ge=1, example=300, alias="retryInterval")

class UnlockConnectorRequest(BaseModel):
    connector_id: int = Field(..., ge=1, example=1, alias="connectorId")

# Helper to serialize OCPP call_result objects
def ocpp_response(payload_obj):
    """Convert an ocpp.v16.call_result object (dataclass) to a JSON-serializable dict."""
    if payload_obj is None:
        return {}
    return asdict(payload_obj)

# OCPP Charge Point handler
class ChargePoint(cp):
    @on("Authorize")
    async def on_authorize(self, **kwargs):
        logger.info(f"Received Authorize: id_tag {kwargs.get('idTag')}")
        return call_result.Authorize(id_tag_info={'status': AuthorizationStatus.accepted})

    @on("BootNotification")
    async def on_boot_notification(self, **kwargs):
        logger.info(f"Received BootNotification from {kwargs.get('chargePointModel')}, {kwargs.get('chargePointVendor')}, firmware: {kwargs.get('firmwareVersion')}")
        return call_result.BootNotification(
            current_time=datetime.utcnow().isoformat(),
            interval=60,
            status=RegistrationStatus.accepted
        )

    @on("CancelReservation")
    async def on_cancel_reservation(self, **kwargs):
        logger.info(f"Received CancelReservation: reservation_id {kwargs.get('reservationId')}")
        return call_result.CancelReservation(status=ReservationStatus.accepted)

    @on("ChangeAvailability")
    async def on_change_availability(self, **kwargs):
        logger.info(f"Received ChangeAvailability: connector_id {kwargs.get('connectorId')}, type {kwargs.get('type')}")
        return call_result.ChangeAvailability(status=AvailabilityStatus.accepted)

    @on("ChangeConfiguration")
    async def on_change_configuration(self, **kwargs):
        logger.info(f"Received ChangeConfiguration: key {kwargs.get('key')}, value {kwargs.get('value')}")
        return call_result.ChangeConfiguration(status=ConfigurationStatus.accepted)

    @on("ClearCache")
    async def on_clear_cache(self, **kwargs):
        logger.info("Received ClearCache")
        return call_result.ClearCache(status=ClearCacheStatus.accepted)

    @on("ClearChargingProfile")
    async def on_clear_charging_profile(self, **kwargs):
        logger.info(f"Received ClearChargingProfile: id {kwargs.get('id')}, connector_id {kwargs.get('connectorId')}, purpose {kwargs.get('chargingProfilePurpose')}, stack_level {kwargs.get('stackLevel')}")
        return call_result.ClearChargingProfile(status=GenericStatus.accepted)

    @on("DataTransfer")
    async def on_data_transfer(self, **kwargs):
        logger.info(f"Received DataTransfer: vendor_id {kwargs.get('vendorId')}, message_id {kwargs.get('messageId')}, data {kwargs.get('data')}")
        return call_result.DataTransfer(status=DataTransferStatus.accepted)

    @on("DiagnosticsStatusNotification")
    async def on_diagnostics_status_notification(self, **kwargs):
        logger.info(f"Received DiagnosticsStatusNotification: status {kwargs.get('status')}")
        return call_result.DiagnosticsStatusNotification()

    @on("FirmwareStatusNotification")
    async def on_firmware_status_notification(self, **kwargs):
        logger.info(f"Received FirmwareStatusNotification: status {kwargs.get('status')}")
        return call_result.FirmwareStatusNotification()

    @on("GetConfiguration")
    async def on_get_configuration(self, **kwargs):
        logger.info(f"Received GetConfiguration: key {kwargs.get('key')}")
        configuration_key = [{"key": "example_key", "value": "example_value"}] if not kwargs.get('key') else []
        return call_result.GetConfiguration(configuration_key=configuration_key)

    @on("GetDiagnostics")
    async def on_get_diagnostics(self, **kwargs):
        logger.info(f"Received GetDiagnostics: location {kwargs.get('location')}, start_time {kwargs.get('startTime')}, stop_time {kwargs.get('stopTime')}")
        return call_result.GetDiagnostics(file_name="diagnostics.log")

    @on("GetLocalListVersion")
    async def on_get_local_list_version(self, **kwargs):
        logger.info("Received GetLocalListVersion")
        return call_result.GetLocalListVersion(list_version=1)

    @on("Heartbeat")
    async def on_heartbeat(self, **kwargs):
        logger.info("Received Heartbeat")
        return call_result.Heartbeat(current_time=datetime.utcnow().isoformat())

    @on("MeterValues")
    async def on_meter_values(self, **kwargs):
        logger.info(f"Received MeterValues: connector_id {kwargs.get('connectorId')}, transaction_id {kwargs.get('transactionId')}")
        return call_result.MeterValues()

    @on("RemoteStartTransaction")
    async def on_remote_start_transaction(self, **kwargs):
        logger.info(f"Received RemoteStartTransaction: id_tag {kwargs.get('idTag')}, connector_id {kwargs.get('connectorId')}")
        return call_result.RemoteStartTransaction(status=RemoteStartStopStatus.accepted)

    @on("RemoteStopTransaction")
    async def on_remote_stop_transaction(self, **kwargs):
        logger.info(f"Received RemoteStopTransaction: transaction_id {kwargs.get('transactionId')}")
        return call_result.RemoteStopTransaction(status=RemoteStartStopStatus.accepted)

    @on("ReserveNow")
    async def on_reserve_now(self, **kwargs):
        logger.info(f"Received ReserveNow: connector_id {kwargs.get('connectorId')}, reservation_id {kwargs.get('reservationId')}, id_tag {kwargs.get('idTag')}")
        return call_result.ReserveNow(status=ReservationStatus.accepted)

    @on("Reset")
    async def on_reset(self, **kwargs):
        logger.info(f"Received Reset: type {kwargs.get('type')}")
        return call_result.Reset(status=ResetStatus.accepted)

    @on("SendLocalList")
    async def on_send_local_list(self, **kwargs):
        logger.info(f"Received SendLocalList: list_version {kwargs.get('listVersion')}, update_type {kwargs.get('updateType')}")
        return call_result.SendLocalList(status=DataTransferStatus.accepted)

    @on("SetChargingProfile")
    async def on_set_charging_profile(self, **kwargs):
        logger.info(f"Received SetChargingProfile: connector_id {kwargs.get('connectorId')}, profiles {kwargs.get('csChargingProfiles')}")
        return call_result.SetChargingProfile(status=GenericStatus.accepted)

    @on("StartTransaction")
    async def on_start_transaction(self, **kwargs):
        logger.info(f"Received StartTransaction: connector_id {kwargs.get('connectorId')}, id_tag {kwargs.get('idTag')}")
        return call_result.StartTransaction(
            transaction_id=1,
            id_tag_info={'status': AuthorizationStatus.accepted}
        )

    @on("StatusNotification")
    async def on_status_notification(self, **kwargs):
        logger.info(f"Received StatusNotification: connector_id {kwargs.get('connectorId')}, status {kwargs.get('status')}, error_code {kwargs.get('errorCode')}")
        return call_result.StatusNotification()

    @on("StopTransaction")
    async def on_stop_transaction(self, **kwargs):
        logger.info(f"Received StopTransaction: transaction_id {kwargs.get('transactionId')}, id_tag {kwargs.get('idTag')}")
        return call_result.StopTransaction(id_tag_info={'status': AuthorizationStatus.accepted})

    @on("TriggerMessage")
    async def on_trigger_message(self, **kwargs):
        logger.info(f"Received TriggerMessage: requested_message {kwargs.get('requestedMessage')}, connector_id {kwargs.get('connectorId')}")
        return call_result.TriggerMessage(status=GenericStatus.accepted)

    @on("UnlockConnector")
    async def on_unlock_connector(self, **kwargs):
        logger.info(f"Received UnlockConnector: connector_id {kwargs.get('connectorId')}")
        return call_result.UnlockConnector(status="Unlocked")

    @on("UpdateFirmware")
    async def on_update_firmware(self, **kwargs):
        logger.info(f"Received UpdateFirmware: location {kwargs.get('location')}, retrieve_date {kwargs.get('retrieveDate')}")
        return call_result.UpdateFirmware()

# WebSocket endpoint
@app.websocket("/wss/{charge_point_id}")
async def websocket_endpoint(websocket: WebSocket, charge_point_id: str):
    await websocket.accept(subprotocol="ocpp1.6")
    connected_clients.append(websocket)
    logger.info(f"New client connected: {charge_point_id}, Total clients: {len(connected_clients)}")

    try:
        charge_point = ChargePoint(charge_point_id, websocket)
        while True:
            # Receive OCPP message (JSON format: [message_type, unique_id, action, payload])
            data = await websocket.receive_text()
            logger.info(f"Received message from {charge_point_id}: {data}")

            # Broadcast raw incoming message to all connected clients
            for client in connected_clients:
                if client != websocket:  # Skip the sender
                    try:
                        await client.send_text(data)
                        logger.info(f"Broadcast message to client: {data}")
                    except Exception as e:
                        logger.error(f"Failed to broadcast to client: {e}")

            # Parse and validate OCPP message
            try:
                message = json.loads(data)
                if not isinstance(message, list) or len(message) < 3:
                    raise ValueError("Invalid OCPP message format")

                message_type, unique_id, action, payload = message[:4]
                if message_type != 2:  # OCPP CALL message
                    raise ValueError("Only CALL messages are supported")

                # Validate payload using Pydantic
                request_model = {
                    "Authorize": AuthorizeRequest,
                    "BootNotification": BootNotificationRequest,
                    "CancelReservation": CancelReservationRequest,
                    "ChangeAvailability": ChangeAvailabilityRequest,
                    "ChangeConfiguration": ChangeConfigurationRequest,
                    "ClearCache": ClearCacheRequest,
                    "ClearChargingProfile": ClearChargingProfileRequest,
                    "DataTransfer": DataTransferRequest,
                    "DiagnosticsStatusNotification": DiagnosticsStatusNotificationRequest,
                    "FirmwareStatusNotification": FirmwareStatusNotificationRequest,
                    "GetConfiguration": GetConfigurationRequest,
                    "GetDiagnostics": GetDiagnosticsRequest,
                    "GetLocalListVersion": GetLocalListVersionRequest,
                    "Heartbeat": HeartbeatRequest,
                    "MeterValues": MeterValuesRequest,
                    "RemoteStartTransaction": RemoteStartTransactionRequest,
                    "RemoteStopTransaction": RemoteStopTransactionRequest,
                    "ReserveNow": ReserveNowRequest,
                    "Reset": ResetRequest,
                    "SendLocalList": SendLocalListRequest,
                    "SetChargingProfile": SetChargingProfileRequest,
                    "StartTransaction": StartTransactionRequest,
                    "StatusNotification": StatusNotificationRequest,
                    "StopTransaction": StopTransactionRequest,
                    "TriggerMessage": TriggerMessageRequest,
                    "UnlockConnector": UnlockConnectorRequest,
                    "UpdateFirmware": UpdateFirmwareRequest
                }.get(action)

                if not request_model:
                    raise ValueError(f"Unsupported action: {action}")

                # Validate payload
                request_model(**payload)  # Raises ValidationError if invalid

                # Process OCPP message
                response = await charge_point.route_message(data)
                response_dict = json.loads(response)

                # Broadcast response to all clients (including sender)
                for client in connected_clients:
                    try:
                        await client.send_text(response)
                        logger.info(f"Broadcast response to client: {response}")
                    except Exception as e:
                        logger.error(f"Failed to broadcast response to client: {e}")

            except Exception as e:
                logger.error(f"Error processing message from {charge_point_id}: {e}")
                error_response = [3, unique_id, "FormationViolation", {"message": str(e)}]
                await websocket.send_text(json.dumps(error_response))

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {charge_point_id}")
        connected_clients.remove(websocket)
        logger.info(f"Total clients remaining: {len(connected_clients)}")
    except Exception as e:
        logger.error(f"Error with {charge_point_id}: {e}")
        connected_clients.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
