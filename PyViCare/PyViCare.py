import logging
from datetime import datetime

from PyViCare.PyViCareAbstractOAuthManager import AbstractViCareOAuthManager
from PyViCare.PyViCareBrowserOAuthManager import ViCareBrowserOAuthManager
from PyViCare.PyViCareCachedService import ViCareCachedService
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareOAuthManager import ViCareOAuthManager
from PyViCare.PyViCareService import ViCareDeviceAccessor, ViCareService
from PyViCare.PyViCareUtils import PyViCareInvalidDataError

logger = logging.getLogger('ViCare')
logger.addHandler(logging.NullHandler())

""""Viessmann ViCare API Python tools"""


class PyViCare:
    def __init__(self) -> None:
        self.cacheDuration = 60

    def setCacheDuration(self, cache_duration):
        self.cacheDuration = int(cache_duration)

    def initWithCredentials(self, username: str, password: str, client_id: str, token_file: str):
        self.initWithExternalOAuth(ViCareOAuthManager(
            username, password, client_id, token_file))

    def initWithExternalOAuth(self, oauth_manager: AbstractViCareOAuthManager) -> None:
        self.oauth_manager = oauth_manager
        self.__loadInstallations()

    def initWithBrowserOAuth(self, client_id: str, token_file: str) -> None:
        self.initWithExternalOAuth(ViCareBrowserOAuthManager(client_id, token_file))

    def __buildService(self, accessor, roles):
        if self.cacheDuration > 0:
            return ViCareCachedService(self.oauth_manager, accessor, roles, self.cacheDuration)
        else:
            return ViCareService(self.oauth_manager, accessor, roles)

    def __loadInstallations(self):
        installations = self.oauth_manager.get(
            "/equipment/installations?includeGateways=true")
        if "data" not in installations:
            logger.error("Missing 'data' property when fetching installations")
            raise PyViCareInvalidDataError(installations)

        data = installations['data']
        self.installations = Wrap(data)
        self.devices = list(self.__extract_devices())

    def __extract_devices(self):
        for installation in self.installations:
            for gateway in installation.gateways:
                for device in gateway.devices:
                    if device.deviceType != "heating":
                        continue  # we are only interested in heating, photovoltaic, electricityStorage, hems and ventilation devices

                    if device.id == "gateway" and device.deviceType == "vitoconnect":
                        device.id = "0"  # vitoconnect has no device id, so we use 0

                    if device.id == "gateway" and device.deviceType == "tcu":
                        device.id = "0"  # tcu has no device id, so we use 0

                    if device.id == "HEMS" and device.deviceType == "hems":
                        device.id = "0"  # hems has no device id, so we use 0

                    if device.id == "EEBUS" and device.deviceType == "EEBus":
                        device.id = "0" # EEBus has no device id,

                    accessor = ViCareDeviceAccessor(
                        installation.id, gateway.serial, device.id)
                    service = self.__buildService(accessor, device.roles)

                    logger.info(f"Device found: {device.modelId}")

                    yield PyViCareDeviceConfig(service, device.id, device.modelId, device.status)


class DictWrap(object):
    def __init__(self, d):
        for k, v in d.items():
            setattr(self, k, Wrap(v))


def Wrap(v):
    if isinstance(v, list):
        return [Wrap(x) for x in v]
    if isinstance(v, dict):
        return DictWrap(v)
    if isinstance(v, str) and len(v) == 24 and v[23] == 'Z' and v[10] == 'T':
        return datetime.strptime(v, '%Y-%m-%dT%H:%M:%S.%f%z')
    else:
        return v
