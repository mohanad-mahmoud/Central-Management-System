import asyncio
import logging
from datetime import datetime

import websockets
from ocpp.routing import on
from ocpp.v16 import ChargePoint as cp
from ocpp.v16 import call_result
from ocpp.v16.enums import Action, RegistrationStatus, AuthorizationStatus

logging.basicConfig(level=logging.DEBUG)  # Set to DEBUG for detailed logging

class CentralSystem(cp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logging.debug("CentralSystem initialized with route_map: %s", self.route_map)

    @on(Action.boot_notification)
    async def on_boot_notification(self, charge_point_model, charge_point_vendor, firmware_version, **kwargs):
        try:
            logging.info(f"Received BootNotification from {charge_point_model}, {charge_point_vendor}, firmware: {firmware_version}")
            return call_result.BootNotification(
                current_time=datetime.utcnow().isoformat(),
                interval=60,
                status=RegistrationStatus.accepted
            )
        except Exception as e:
            logging.error(f"Error in on_boot_notification: {e}")
            raise

    @on(Action.heartbeat)
    async def on_heartbeat(self, **kwargs):
        try:
            logging.info("Received Heartbeat")
            return call_result.Heartbeat(
                current_time=datetime.utcnow().isoformat()
            )
        except Exception as e:
            logging.error(f"Error in on_heartbeat: {e}")
            raise

    @on(Action.status_notification)
    async def on_status_notification(self, connector_id, error_code, status, **kwargs):
        try:
            logging.info(f"Received StatusNotification: connector {connector_id}, status {status}, error {error_code}")
            return call_result.StatusNotification()
        except Exception as e:
            logging.error(f"Error in on_status_notification: {e}")
            raise

    @on(Action.start_transaction)
    async def on_start_transaction(self, connector_id, id_tag, meter_start, timestamp, **kwargs):
        try:
            logging.info(f"Received StartTransaction: connector {connector_id}, id_tag {id_tag}")
            return call_result.StartTransaction(
                transaction_id=1,
                id_tag_info={'status': AuthorizationStatus.accepted}
            )
        except Exception as e:
            logging.error(f"Error in on_start_transaction: {e}")
            raise

    @on(Action.meter_values)
    async def on_meter_values(self, connector_id, transaction_id, meter_value, **kwargs):
        try:
            logging.info(f"Received MeterValues: connector {connector_id}, transaction {transaction_id}")
            return call_result.MeterValues()
        except Exception as e:
            logging.error(f"Error in on_meter_values: {e}")
            raise

    @on(Action.stop_transaction)
    async def on_stop_transaction(self, transaction_id, id_tag, meter_stop, timestamp, **kwargs):
        try:
            logging.info(f"Received StopTransaction: transaction {transaction_id}, id_tag {id_tag}")
            return call_result.StopTransaction(
                id_tag_info={'status': AuthorizationStatus.accepted}
            )
        except Exception as e:
            logging.error(f"Error in on_stop_transaction: {e}")
            raise

async def main():
    try:
        async with websockets.serve(
            lambda ws, path: CentralSystem(path.split('/')[-1], ws).start(),
            "localhost",
            9000,
            subprotocols=["ocpp1.6"]
        ):
            logging.info("OCPP 1.6 server running on ws://localhost:9000")
            await asyncio.Future()  # Run forever
    except Exception as e:
        logging.error(f"Server failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
