#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# nanoleaf Controller - Main © Autolog 2017-2021
#

try:
    import indigo
except:
    pass

import logging
import queue
import sys
import threading
import traceback

from constants import *
from nanoleafapi.discover_nanoleaf import *


class ThreadDiscovery(threading.Thread):

    # This class controls the discovery of nanoleaf devices.

    def __init__(self, plugin_globals):

        threading.Thread.__init__(self)

        self.globals = plugin_globals[0]

        self.discoveryLogger = logging.getLogger("Plugin.Discovery")

    def exception_handler(self, exception_error_message, log_failing_statement):
        filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]
        module = filename.split("/")
        log_message = f"'{exception_error_message}' in module '{module[-1]}', method '{method}'"
        if log_failing_statement:
            log_message = log_message + f"\n   Failing statement [line {line_number}]: '{statement}'"
        else:
            log_message = log_message + f" at line {line_number}"
        self.discoveryLogger.error(log_message)

    def run(self):
        try:
            self.discoveryLogger.debug(u"nanoleaf Discovery Thread initialised.")    

            while True:

                try:
                    nanoleafQueuedPriorityCommandData = self.globals[QUEUES][DISCOVERY].get(True,5)

                    self.discoveryLogger.debug(f"NANOLEAF QUEUED PRIORITY COMMAND DATA: {nanoleafQueuedPriorityCommandData}")
                    nanoleafQueuePriority, nanoleafCommand, nanoleafCommandParameters = nanoleafQueuedPriorityCommandData

                    self.discoveryLogger.debug(f"Dequeued Discovery Message to process [NANOLEAFCOMMAND]: {nanoleafCommand}")

                    if nanoleafCommand == "STOPTHREAD":
                        break  # Exit While loop and quit thread

                    if nanoleafCommand == COMMAND_DISCOVERY:
                        self.discoveryLogger.info(f"Discovering nanoleaf aurora, canvas and shape devices on network - this should take ~{self.globals[DISCOVERY][PERIOD]} seconds . . .")

                        self.globals[DISCOVERY][DISCOVERED_UNMATCHED_DEVICES] = {}
                        # self.globals[DISCOVERY][DISCOVERED_AURORAS] = {}
                        # self.globals[DISCOVERY][DISCOVERED_CANVASES] = {}
                        # self.globals[DISCOVERY][DISCOVERED_SHAPES] = {}
                        # self.globals[DISCOVERY][DISCOVERED_ELEMENTS] = {}
                        # self.globals[DISCOVERY][DISCOVERED_LINES] = {}
                        self.globals[DISCOVERY][DISCOVERED_DEVICES] = {}

                        result, status_message, discovered_nanoleafs = discover_nanoleafs(self.globals[OVERRIDDEN_HOST_IP_ADDRESS], self.globals[DISCOVERY][PERIOD])

                        if not result:
                            self.discoveryLogger.error(f"Discovering nanoleaf devices failed: {status_message}")
                            continue

                        self.globals[DISCOVERY][DISCOVERED_DEVICES] = dict()
                        for nanoleaf_device_id in discovered_nanoleafs.keys():

                            nanoleaf_type = discovered_nanoleafs[nanoleaf_device_id]["NANOLEAF_TYPE"]
                            nanoleaf_ip_address = discovered_nanoleafs[nanoleaf_device_id]["NANOLEAF_IP_ADDRESS"]
                            nanoleaf_mac = discovered_nanoleafs[nanoleaf_device_id]["NANOLEAF_MAC"]
                            # nanoleaf_device_name = discovered_nanoleafs[discovered_nanoleafs]["NANOLEAF_DEVICE_NAME"]


                            device_type = "Unknown Nanoleaf"
                            if nanoleaf_type == "nanoleaf_aurora:light":  # Aurora [nl22]
                                device_type = "Aurora"
                            elif nanoleaf_type == "nanoleaf:nl29":  # Canvas [NL29]
                                device_type = "Canvas"
                            elif nanoleaf_type == "nanoleaf:nl42":  # Shape [NL42]
                                device_type = "Shape"
                            elif nanoleaf_type == "nanoleaf:nl52":  # Element [NL52]
                                device_type = "Element"
                            elif nanoleaf_type == "nanoleaf:nl59":  # Line [NL59]
                                device_type = "Line"
                            else:
                                continue

                            self.globals[DISCOVERY][DISCOVERED_DEVICES][nanoleaf_device_id] = (nanoleaf_ip_address, nanoleaf_mac, device_type)

                        # self.globals[DISCOVERY][DISCOVERED_DEVICES] = self.globals[DISCOVERY][DISCOVERED_AURORAS]
                        # self.globals[DISCOVERY][DISCOVERED_DEVICES].update(self.globals[DISCOVERY][DISCOVERED_CANVASES])
                        # self.globals[DISCOVERY][DISCOVERED_DEVICES].update(self.globals[DISCOVERY][DISCOVERED_SHAPES])
                        # self.globals[DISCOVERY][DISCOVERED_DEVICES].update(self.globals[DISCOVERY][DISCOVERED_ELEMENTS])
                        # self.globals[DISCOVERY][DISCOVERED_DEVICES].update(self.globals[DISCOVERY][DISCOVERED_LINES])
                        #
                        # self.discoveryLogger.warning(f"NANOLEAF DISCOVERY: {self.globals[DISCOVERY][DISCOVERED_DEVICES]}")

                        if len(self.globals[DISCOVERY][DISCOVERED_DEVICES]) > 0:
                            for nlDeviceid, nlInfo in self.globals[DISCOVERY][DISCOVERED_DEVICES].items():
                                nlDeviceid = f"{nlDeviceid}"
                                nlIpAddress = f"{nlInfo[0]}"
                                nlMacAddress = f"{nlInfo[1]}"

                                if nlMacAddress[1:2] == ":":
                                    nlMacAddress = f"0{nlMacAddress}"
                                nlDeviceName = f"{nlInfo[2]}"
                                nanoleafDeviceMatchedtoIndigoDevice = False
                                for devId in self.globals[NL]:
                                    if NL_DEVICE_PSEUDO_ADDRESS in self.globals[NL][devId] and self.globals[NL][devId][NL_DEVICE_PSEUDO_ADDRESS] != "":
                                        if nlDeviceid == self.globals[NL][devId][NL_DEVICE_PSEUDO_ADDRESS]:
                                            nanoleafDeviceMatchedtoIndigoDevice = True
                                            break
                                if not nanoleafDeviceMatchedtoIndigoDevice:
                                    self.globals[DISCOVERY][DISCOVERED_UNMATCHED_DEVICES][nlDeviceid] = (nlIpAddress, nlMacAddress, nlDeviceName)
                                    self.discoveryLogger.info(f"New nanoleaf {nlDeviceName} with device Id '{nlDeviceid}' and Mac Address '{nlMacAddress}' discovered at IP Address: {nlIpAddress} and not yet assigned to an Indigo device")
                                else:
                                    dev = indigo.devices[devId]  # noqa - devId will always be set due to check of nanoleafDeviceMatchedtoIndigoDevice
                                    devName = dev.name
                                    self.discoveryLogger.info(f"Known nanoleaf {nlDeviceName} with device Id '{nlDeviceid}' and Mac Address '{nlMacAddress}' discovered at address: {nlIpAddress} and already assigned to Indigo device '{devName}'")
                                    devIpAddress = indigo.devices[devId].states["ipAddress"]
                                    if devIpAddress != nlIpAddress:
                                        self.discoveryLogger.error(f"WARNING: IP Address changed for Nanoleaf '{devName}', it was '{devIpAddress}' and is now '{nlIpAddress}' - Edit Device and Update IP Address.")
                                        dev.updateStateOnServer(key="connected", value=False)
                                        dev.setErrorStateOnServer("ip mismatch")
                        else:
                            self.discoveryLogger.error("Discovering nanoleaf aurora / canvas devices failed to find any. Make sure nanoleaf device is switched on, has been connected to network and is accessible from nanoleaf App")
                        continue

                except queue.Empty:
                    pass
                except Exception as exception_error:
                    self.exception_handler(exception_error, True)  # Log error and display failing statement

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

        self.discoveryLogger.debug("NANOLEAF Send Receive Message Thread ended.")
