#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# nanoleaf Controller © Autolog 2017-2022
#

try:
    import indigo
except:
    pass

# import colorsys
import queue
import sys
import threading
import traceback

from constants import *
from nanoleafapi.nanoleaf import *
# from nanoleafapi.discovery import *

class ThreadSendReceiveMessages(threading.Thread):

    # This class controls the sending of commands to a nanoleaf device and handles it's response.
    # It receives high level commands to send to the nanoleaf device from a queue which it waits on
    #   and queues replies for handling by the runConcurrent thread

    # It contains the logic for correctly formatting the the high level commands to be sent to the nanoleaf device
    #   into the specific formats required by the nanoleaf device.

    def __init__(self, globals):

        threading.Thread.__init__(self)

        self.globals = globals[0]

        self.sendReceiveLogger = logging.getLogger("Plugin.SendReceive")

        self.sendReceiveLogger.debug("Initialising nanoleaf Send and Receive Message Thread")

    def exception_handler(self, exception_error_message, log_failing_statement):
        filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]
        module = filename.split('/')
        log_message = f"'{exception_error_message}' in module '{module[-1]}', method '{method}'"
        if log_failing_statement:
            log_message = log_message + f"\n   Failing statement [line {line_number}]: '{statement}'"
        else:
            log_message = log_message + f" at line {line_number}"
        self.sendReceiveLogger.error(log_message)

    def run(self):
        try:
            self.sendReceiveLogger.debug("nanoleaf Send Receive Message Thread initialised.")

            while True:

                try:
                    nanoleaf_queued_priority_command_data = self.globals[QUEUES][MESSAGE_TO_SEND].get(True,5)

                    self.sendReceiveLogger.debug(f"NANOLEAF QUEUED PRIORITY COMMAND DATA: {nanoleaf_queued_priority_command_data}")
                    nanoleaf_queue_priority, nanoleaf_command, nanoleaf_command_parameters = nanoleaf_queued_priority_command_data

                    self.sendReceiveLogger.debug(f"Dequeued Send Message to process [NANOLEAFCOMMAND]: {nanoleaf_command}")

                    # Handle commands to all NANOLEAF lamps

                    if nanoleaf_command == STOP_THREAD:
                        break  # Exit While loop and quit thread

                    if nanoleaf_command == STATUS_POLLING:
                        for nanoleafDevId in self.globals[NL]:
                            if self.globals[NL][nanoleafDevId][STARTED]:
                                self.sendReceiveLogger.debug(f"Processing {nanoleaf_command} for {indigo.devices[nanoleafDevId].name}")
                                self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_STATUS_MEDIUM, COMMAND_STATUS, [nanoleafDevId]])
                                 
                        continue  

                    if nanoleaf_command == COMMAND_STATUS:
                        nanoleafDevId = nanoleaf_command_parameters[0]
                        nanoleafDev   = indigo.devices[nanoleafDevId]

                        if self.globals[NL][nanoleafDevId][STARTED] == True:
                            
                            self.sendReceiveLogger.debug(f"Processing {nanoleaf_command} for '{nanoleafDev.name}'")
                            ip_address = self.globals[NL][nanoleafDevId][IP_ADDRESS]
                            auth_token = self.globals[NL][nanoleafDevId][AUTH_TOKEN]
                            try:
                                self.globals[NL][nanoleafDevId][CONNECTION_RETRIES] += 1
                                self.globals[NL][nanoleafDevId][NANOLEAF_OBJECT] = Nanoleaf(ip_address, auth_token)  # May move this to discovery process?
                                if self.globals[NL][nanoleafDevId][CONNECTION_RETRIES] > 1:
                                    self.sendReceiveLogger.warning(f"Connection re-established with '{nanoleafDev.name}'.")
                                self.globals[NL][nanoleafDevId][CONNECTION_RETRIES] = 0
                            except Exception as exception_error:
                                retries_so_far = self.globals[NL][nanoleafDevId][CONNECTION_RETRIES]
                                if retries_so_far < CONNECTION_RETRY_LIMIT:
                                    if retries_so_far == 1:
                                        self.sendReceiveLogger.warning(f"Problem connecting to '{nanoleafDev.name}'. Commencing retries . . .")
                                    else:
                                        self.sendReceiveLogger.warning(f"Problem connecting to '{nanoleafDev.name}'. Retry {retries_so_far} failed. Retrying . . .")
                                    self.sendReceiveLogger.debug(f"Problem connecting to '{nanoleafDev.name}': {exception_error}")
                                else:
                                    if retries_so_far == CONNECTION_RETRY_LIMIT:
                                        self.sendReceiveLogger.error(f"Problem connecting to '{nanoleafDev.name}'. Reporting Retry limit reached and so will continue retrying in the background.")
                                self.communicationProblem(nanoleafDev)
                                continue

                            self.sendReceiveLogger.debug(f"STATUS DEBUG: Type = {type(self.globals[NL][nanoleafDevId][NANOLEAF_OBJECT])}, Data1= {self.globals[NL][nanoleafDevId][NANOLEAF_OBJECT]}")

                            # self.sendReceiveLogger.warning(f"NANOLEAF GET INFO:\n {self.globals[NL][nanoleafDevId][NANOLEAF_OBJECT].get_info()}\n")  # NEW LIBRARY

                            try:
                                self.globals[NL][nanoleafDevId][NANOLEAF_INFO] = self.globals[NL][nanoleafDevId][NANOLEAF_OBJECT].get_info()  # NEW LIBRARY
                            except Exception as exception_error:
                                self.sendReceiveLogger.error(f"Problem getting status of '{nanoleafDev.name}': {exception_error}")
                                self.communicationProblem(nanoleafDev)
                                continue

                            self.updateDeviceState(nanoleafDevId)

                        continue

                    if (nanoleaf_command == COMMAND_ON) or (nanoleaf_command == COMMAND_OFF):
                        nanoleafDevId = nanoleaf_command_parameters[0]
                        nanoleafDev = indigo.devices[nanoleafDevId]

                        if self.globals[NL][nanoleafDevId][STARTED]:
                            self.sendReceiveLogger.debug(f"Processing {nanoleaf_command} for '{indigo.devices[nanoleafDevId].name}' ")

                            try:
                                if nanoleaf_command == COMMAND_ON:
                                    self.globals[NL][nanoleafDevId][NANOLEAF_OBJECT].power_on()  # NEW LIBRARY
                                else:  # nanoleafCommand == COMMAND_OFF
                                    self.globals[NL][nanoleafDevId][NANOLEAF_OBJECT].power_off()  # NEW LIBRARY
                            except Exception as exception_error:
                                self.sendReceiveLogger.error(f"Problem turning {nanoleaf_command} the device '{nanoleafDev.name}': {exception_error}")
                                self.communicationProblem(nanoleafDev)

                            self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_STATUS_HIGH, COMMAND_STATUS, [nanoleafDevId]])

                        continue

                    if nanoleaf_command == COMMAND_BRIGHTNESS:
                        nanoleafDevId = nanoleaf_command_parameters[0]
                        nanoleafDev = indigo.devices[nanoleafDevId]

                        targetBrightness = nanoleaf_command_parameters[1]

                        if self.globals[NL][nanoleafDevId][STARTED]:
                            self.sendReceiveLogger.debug(f"Processing {nanoleaf_command} for '{indigo.devices[nanoleafDevId].name}'")
                            try:
                                self.globals[NL][nanoleafDevId][NANOLEAF_OBJECT].set_brightness(targetBrightness)  # NEW LIBRARY
                            except Exception as exception_error:
                                self.sendReceiveLogger.error(f"Problem setting brightness of '{nanoleafDev.name}': {exception_error}")
                                self.communicationProblem(nanoleafDev)
                                continue

                            self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_STATUS_HIGH, COMMAND_STATUS, [nanoleafDevId]])
                        continue

                    if nanoleaf_command == COMMAND_DIM:
                        nanoleafDevId = nanoleaf_command_parameters[0]
                        nanoleafDev = indigo.devices[nanoleafDevId]

                        targetDimBy = nanoleaf_command_parameters[1]

                        if self.globals[NL][nanoleafDevId][STARTED]:
                            self.sendReceiveLogger.debug(f"Processing {nanoleaf_command} for '{indigo.devices[nanoleafDevId].name}'")
                            try:
                                self.globals[NL][nanoleafDevId][NANOLEAF_OBJECT].set_brightness(targetDimBy)  # NEW LIBRARY
                            except Exception as exception_error:
                                self.sendReceiveLogger.error(f"Problem dimming '{nanoleafDev.name}': {exception_error}")
                                self.communicationProblem(nanoleafDev)
                                continue

                            self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_STATUS_HIGH, COMMAND_STATUS, [nanoleafDevId]])
                        continue

                    if nanoleaf_command == COMMAND_BRIGHTEN:
                        nanoleafDevId = nanoleaf_command_parameters[0]
                        nanoleafDev = indigo.devices[nanoleafDevId]

                        targetBrightenBy = nanoleaf_command_parameters[1]

                        if self.globals[NL][nanoleafDevId][STARTED]:
                            self.sendReceiveLogger.debug(f"Processing {nanoleaf_command} for '{indigo.devices[nanoleafDevId].name}'")
                            try:
                                self.globals[NL][nanoleafDevId][NANOLEAF_OBJECT].set_brightness(targetBrightenBy)  # NEW LIBRARY
                            except Exception as exception_error:
                                self.sendReceiveLogger.error(f"Problem brightening '{nanoleafDev.name}': {exception_error}")
                                self.communicationProblem(nanoleafDev)
                                continue

                            self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_STATUS_HIGH, COMMAND_STATUS, [nanoleafDevId]])
                        continue

                    if nanoleaf_command == COMMAND_WHITE:
                        nanoleafDevId, targetWhiteLevel, targetWhiteTemperature = nanoleaf_command_parameters
                        nanoleafDev = indigo.devices[nanoleafDevId]

                        if self.globals[NL][nanoleafDevId][STARTED]:
                            try:
                                self.globals[NL][nanoleafDevId][NANOLEAF_OBJECT].set_color_temp(int(targetWhiteTemperature))  # NEW LIBRARY
                            except Exception as exception_error:
                                self.sendReceiveLogger.error(f"Problem setting white temperature for '{nanoleafDev.name}': {exception_error}")
                                self.communicationProblem(nanoleafDev)
                                continue

                            try:
                                self.globals[NL][nanoleafDevId][NANOLEAF_OBJECT].set_brightness(int(targetWhiteLevel))  # NEW LIBRARY
                            except Exception as exception_error:
                                self.sendReceiveLogger.error(f"Problem setting white temperature brightness for '{nanoleafDev.name}': {exception_error}")
                                self.communicationProblem(nanoleafDev)
                                continue

                            self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_STATUS_HIGH, COMMAND_STATUS, [nanoleafDevId]])

                        continue

                    if nanoleaf_command == COMMAND_COLOR:
                        nanoleafDevId, targetRedLevel, targetGreenLevel, targetBlueLevel = nanoleaf_command_parameters
                        nanoleafDev = indigo.devices[nanoleafDevId]

                        self.sendReceiveLogger.debug(f"NANOLEAF COMMAND [COLOR]; Target for {indigo.devices[nanoleafDevId].name}: Red={targetRedLevel}, Green={targetGreenLevel}, Blue={targetBlueLevel}")
                        if self.globals[NL][nanoleafDevId][STARTED]:
                            red = int((targetRedLevel*255.0)/100.0)
                            green = int((targetGreenLevel*255.0)/100.0)
                            blue = int((targetBlueLevel*255.0)/100.0)

                            try:
                                self.globals[NL][nanoleafDevId][NANOLEAF_OBJECT].set_color([red, green, blue])  # NEW LIBRARY
                            except Exception as exception_error:
                                self.sendReceiveLogger.error(f"Problem setting color for '{nanoleafDev.name}': {exception_error}")
                                self.communicationProblem(nanoleafDev)
                                continue

                            self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_STATUS_HIGH, COMMAND_STATUS, [nanoleafDevId]])

                        continue

                    if nanoleaf_command == COMMAND_SET_EFFECT:
                        nanoleafDevId = nanoleaf_command_parameters[0]
                        nanoleafDev = indigo.devices[nanoleafDevId]

                        effect = nanoleaf_command_parameters[1]

                        if self.globals[NL][nanoleafDevId][STARTED]:
                            self.sendReceiveLogger.debug(f"Processing {nanoleaf_command} for '{indigo.devices[nanoleafDevId].name}' ")

                            try:
                                self.globals[NL][nanoleafDevId][NANOLEAF_OBJECT].set_effect(effect)  # NEW LIBRARY
                            except Exception as exception_error:
                                self.sendReceiveLogger.error(f"Problem setting the effect for '{nanoleafDev.name}': {exception_error}")
                                self.communicationProblem(nanoleafDev)
                                continue

                            self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_STATUS_HIGH, COMMAND_STATUS, [nanoleafDevId]])

                        continue

                except queue.Empty:
                    pass
                except Exception as exception_error:
                    self.exception_handler(exception_error, True)  # Log error and display failing statement

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

        self.sendReceiveLogger.debug("NANOLEAF Send Receive Message Thread ended.")

    def communicationProblem(self, argNanoleafDev):
        if argNanoleafDev.states["connected"]:
            argNanoleafDev.updateStateOnServer(key="connected", value=False)
            argNanoleafDev.setErrorStateOnServer("no ack")
            self.sendReceiveLogger.error(f"Communication lost with \"{argNanoleafDev.name}\" - status set to 'No Acknowledgment' (no ack)")

    def updateDeviceState(self, nanoleafDevId):
        try:
            nanoleafDev = indigo.devices[nanoleafDevId]

            self.globals[NL][nanoleafDevId][LAST_RESPONSE_TO_POLL_COUNT] = self.globals[POLLING][COUNT]  # Set the current poll count (for 'no ack' check)

            # if str(self.globals[NL][nanoleafDevId][NANOLEAF_INFO]["state"]["on"]["value"]) == "True":  # TODO: Check this
            #     onState = True
            #     onOffState = 'on'
            # else:
            #     onState = False
            #     onOffState = 'off'

            onState = self.globals[NL][nanoleafDevId][NANOLEAF_INFO]["state"]["on"]["value"]  # TODO: Check this is OK
            onOffState = "on" if onState else "off"

            colorMode = self.globals[NL][nanoleafDevId][NANOLEAF_INFO]["state"]["colorMode"]

            hue = int(self.globals[NL][nanoleafDevId][NANOLEAF_INFO]["state"]["hue"]["value"])
            saturation = int(self.globals[NL][nanoleafDevId][NANOLEAF_INFO]["state"]["sat"]["value"])
            brightness = int(self.globals[NL][nanoleafDevId][NANOLEAF_INFO]["state"]["brightness"]["value"])

            brightnessLevel = brightness if onState else 0

            colorTemperature = int(self.globals[NL][nanoleafDevId][NANOLEAF_INFO]["state"]["ct"]["value"])

            hsv_hue = float(hue) / 360.0
            hsv_value = float(brightness) / 100.0
            hsv_saturation = float(saturation) / 100.0
            red, green, blue = colorsys.hsv_to_rgb(hsv_hue, hsv_saturation, hsv_value)

            # success, status_msg, rgb = self.globals[NL][nanoleafDevId][NANOLEAF_OBJECT].rgb
            # if not success:
            #     self.sendReceiveLogger.error(f"Status not updated for '{nanoleafDev.name}': RGB conversion for device update with error '{status_msg}'")
            #     return
            #
            # red, green, blue = [int((rgb[0] * 100)/255), int((rgb[1] * 100)/255), int((rgb[2] * 100)/255)]

            red = int(red * 100.0)
            green = int(green * 100.0)
            blue = int(blue * 100.0)

            self.globals[NL][nanoleafDevId][EFFECTS_LIST] = self.globals[NL][nanoleafDevId][NANOLEAF_INFO]["effects"]["effectsList"]

            effect = self.globals[NL][nanoleafDevId][NANOLEAF_INFO]["effects"]["select"]

            serialNo = self.globals[NL][nanoleafDevId][NANOLEAF_INFO]["serialNo"]
            model = self.globals[NL][nanoleafDevId][NANOLEAF_INFO]["model"]
            manufacturer = self.globals[NL][nanoleafDevId][NANOLEAF_INFO]["manufacturer"]
            name = self.globals[NL][nanoleafDevId][NANOLEAF_INFO]["name"]
            firmwareVersion = self.globals[NL][nanoleafDevId][NANOLEAF_INFO]["firmwareVersion"]

            keyValueList = [
                {'key': "connected", 'value': True},
                {'key': 'nanoleafOnState', 'value': onState},
                {'key': 'nanoleafOnOffState', 'value': onOffState},

                {'key': 'colorMode', 'value': colorMode},
                {'key': 'brightness', 'value': brightness},
                {'key': 'hue', 'value': hue},
                {'key': 'saturation', 'value': saturation},
                {'key': 'brightnessLevel', 'value': brightnessLevel},
                {'key': 'colorTemperature', 'value': colorTemperature},

                {'key': 'effect', 'value': effect},

                {'key': 'whiteTemperature', 'value': colorTemperature},
                {'key': 'whiteLevel', 'value': brightness},
                {'key': 'redLevel', 'value': red},
                {'key': 'greenLevel', 'value': green},
                {'key': 'blueLevel', 'value': blue},

                {'key': 'name', 'value': name},
                {'key': 'manufacturer', 'value': manufacturer},
                {'key': 'serialNo', 'value': serialNo}

            ]

            nanoleafDev.updateStatesOnServer(keyValueList)

            nanoleafDev.updateStateImageOnServer(indigo.kStateImageSel.Auto)

            props = nanoleafDev.pluginProps
            if "version" in props and str(props["version"]) == firmwareVersion:
                pass
            else:
                props["version"] = str(firmwareVersion)
                nanoleafDev.replacePluginPropsOnServer(props)

            if nanoleafDev.model != model:
                nanoleafDev.model = str(model)
                nanoleafDev.replaceOnServer()

            self.globals[NL][nanoleafDevId][LAST_RESPONSE_TO_POLL_COUNT] = self.globals[POLLING][COUNT]  # Set the current poll count (for 'no ack' check)
 
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement
