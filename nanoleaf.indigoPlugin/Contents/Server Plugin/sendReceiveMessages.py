#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# nanoleaf Controller - Main © Autolog 2017-2020
#

try:
    import indigo
except:
    pass
import logging
import Queue
import threading
import traceback

from constants import *
from nanoleaf.nanoleaf import *
from nanoleaf.discover_nanoleaf import *

class ThreadSendReceiveMessages(threading.Thread):

    # This class controls the sending of commands to a nanoleaf device and handles it's response.
    # It receives high level commands to send to the nanoleaf device from a queue which it waits on
    #   and queues replies for handling by the runConcurrent thread

    # It contains the logic for correctly formatting the the high level commands to be sent to the nanoleaf device
    #   into the specific formats required by the nanoleaf device.

    def __init__(self, globals):

        threading.Thread.__init__(self)

        self.globals = globals[0]

        self.sendReceiveMonitorLogger = logging.getLogger('Plugin.MonitorSendReceive')
        self.sendReceiveMonitorLogger.setLevel(self.globals['debug']['monitorSendReceive'])

        self.sendReceiveDebugLogger = logging.getLogger('Plugin.DebugSendReceive')
        self.sendReceiveDebugLogger.setLevel(self.globals['debug']['debugSendReceive'])

        self.methodTracer = logging.getLogger('Plugin.method')  
        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

        self.sendReceiveDebugLogger.debug(u'Initialising nanoleaf Send and Receive Message Thread')  

    def run(self):
        self.methodTracer.threaddebug(u'ThreadSendReceiveMessages')
 
        try:
            self.sendReceiveDebugLogger.debug(u'nanoleaf Send Receive Message Thread initialised.')    

            while True:

                try:
                    nanoleafQueuedPriorityCommandData = self.globals['queues']['messageToSend'].get(True,5)

                    self.sendReceiveDebugLogger.debug(u'NANOLEAF QUEUED PRIORITY COMMAND DATA: {}'.format(nanoleafQueuedPriorityCommandData))    
                    nanoleafQueuePriority, nanoleafCommand, nanoleafCommandParameters = nanoleafQueuedPriorityCommandData

                    # Check if monitoring / debug options have changed and if so set accordingly
                    if self.globals['debug']['previousMonitorSendReceive'] != self.globals['debug']['monitorSendReceive']:
                        self.globals['debug']['previousMonitorSendReceive'] = self.globals['debug']['monitorSendReceive']
                        self.sendReceiveMonitorLogger.setLevel(self.globals['debug']['monitorSendReceive'])
                    if self.globals['debug']['previousDebugSendReceive'] != self.globals['debug']['debugSendReceive']:
                        self.globals['debug']['previousDebugSendReceive'] = self.globals['debug']['debugSendReceive']
                        self.sendReceiveDebugLogger.setLevel(self.globals['debug']['debugSendReceive'])
                    if self.globals['debug']['previousDebugMethodTrace'] !=self.globals['debug']['debugMethodTrace']:
                        self.globals['debug']['previousDebugMethodTrace'] = self.globals['debug']['debugMethodTrace']
                        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

                    self.sendReceiveDebugLogger.debug(u'Dequeued Send Message to process [NANOLEAFCOMMAND]: {}'.format(nanoleafCommand))

                    # Handle commands to all NANOLEAF lamps

                    if nanoleafCommand == 'STOPTHREAD':
                        break  # Exit While loop and quit thread


                    if nanoleafCommand == 'STATUSPOLLING':
                        for nanoleafDevId in self.globals['nl']:
                            if self.globals['nl'][nanoleafDevId]["started"] == True:
                                self.sendReceiveDebugLogger.debug(u'Processing {} for {}'.format(nanoleafCommand, indigo.devices[nanoleafDevId].name))
                                self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_MEDIUM, 'STATUS', [nanoleafDevId]])
                                 
                        continue  

                    if nanoleafCommand == 'STATUS':
                        nanoleafDevId = nanoleafCommandParameters[0]
                        nanoleafDev   = indigo.devices[nanoleafDevId]

                        if self.globals['nl'][nanoleafDevId]["started"] == True:
                            
                            self.sendReceiveDebugLogger.debug(u'Processing {} for \'{}\''.format(nanoleafCommand, nanoleafDev.name))
                            ipAddress = self.globals['nl'][nanoleafDevId]["ipAddress"]
                            authToken = self.globals['nl'][nanoleafDevId]["authToken"]
                            self.globals['nl'][nanoleafDevId]["nanoleaf"] = Nanoleaf(ipAddress, authToken)  # May move this to discovery process?
                            self.sendReceiveDebugLogger.debug(u'STATUS DEBUG: Type = {}, Data1= {}'.format(type(self.globals['nl'][nanoleafDevId]["nanoleaf"]), self.globals['nl'][nanoleafDevId]["nanoleaf"]))

                            success, statusMsg, self.globals['nl'][nanoleafDevId]["nanoleafInfo"] = self.globals['nl'][nanoleafDevId]["nanoleaf"].info
                            self.sendReceiveDebugLogger.debug(u'STATUS DEBUG: Success = {}, StatusMsg = {}'.format(success, statusMsg))
                            self.sendReceiveDebugLogger.debug(u'STATUS DEBUG: Type = {}, Data2= {}'.format(type(self.globals['nl'][nanoleafDevId]["nanoleafInfo"]), self.globals['nl'][nanoleafDevId]["nanoleafInfo"]))

                            if success:
                                self.updateDeviceState(nanoleafDevId)
                            else:
                                self.sendReceiveDebugLogger.error(u'Problem retrieving status for device \'{}\': {}'.format(nanoleafDev.name, statusMsg))
                                self.communicationProblem(nanoleafDev) 


                        continue

                    if (nanoleafCommand == 'ON') or (nanoleafCommand == 'OFF'):
                        nanoleafDevId = nanoleafCommandParameters[0]

                        if self.globals['nl'][nanoleafDevId]["started"] == True:
                            self.sendReceiveDebugLogger.debug(u'Processing {} for \'{}\' '.format(nanoleafCommand, indigo.devices[nanoleafDevId].name))

                            if nanoleafCommand == 'ON':
                                success, statusMsg, reply = self.globals['nl'][nanoleafDevId]["nanoleaf"].set_on()
                            else:  # nanoleafCommand == 'OFF'
                                success, statusMsg, reply = self.globals['nl'][nanoleafDevId]["nanoleaf"].set_off()

                            if success:
                                self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_HIGH, 'STATUS', [nanoleafDevId]])
                            else:
                                self.sendReceiveDebugLogger.error(u'Problem turning {} the device \'{}\': {}'.format(nanoleafCommand, nanoleafDev.name, statusMsg))
                                self.communicationProblem(nanoleafDev) 

                        continue

                    if (nanoleafCommand == 'BRIGHTNESS'):
                        nanoleafDevId = nanoleafCommandParameters[0]

                        targetBrightness = nanoleafCommandParameters[1]


                        if self.globals['nl'][nanoleafDevId]["started"] == True:
                            self.sendReceiveDebugLogger.debug(u'Processing {} for \'{}\' '.format(nanoleafCommand, indigo.devices[nanoleafDevId].name))

                            success, statusMsg, reply = self.globals['nl'][nanoleafDevId]["nanoleaf"].set_brightness(targetBrightness)

                            if success:
                                self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_HIGH, 'STATUS', [nanoleafDevId]])
                            else:
                                self.sendReceiveDebugLogger.error(u'Problem setting brightness of device \'{}\': {}'.format(nanoleafDev.name, statusMsg))
                                self.communicationProblem(nanoleafDev) 
                        
                        continue

                    if nanoleafCommand == 'DIM':
                        nanoleafDevId = nanoleafCommandParameters[0]

                        targetDimBy = nanoleafCommandParameters[1]

                        if self.globals['nl'][nanoleafDevId]["started"] == True:

                            self.sendReceiveDebugLogger.debug(u'Processing {} for \'{}\' '.format(nanoleafCommand, indigo.devices[nanoleafDevId].name))

                            success, statusMsg, reply = self.globals['nl'][nanoleafDevId]["nanoleaf"].brightness_lower(targetDimBy)

                            if success:
                                self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_HIGH, 'STATUS', [nanoleafDevId]])
                            else:
                                self.sendReceiveDebugLogger.error(u'Problem dimming the device \'{}\': {}'.format(nanoleafDev.name, statusMsg))
                                self.communicationProblem(nanoleafDev) 

                        continue

                    if nanoleafCommand == 'BRIGHTEN':
                        nanoleafDevId = nanoleafCommandParameters[0]

                        targetBrightenBy = nanoleafCommandParameters[1]

                        if self.globals['nl'][nanoleafDevId]["started"] == True:

                            self.sendReceiveDebugLogger.debug(u'Processing {} for \'{}\' '.format(nanoleafCommand, indigo.devices[nanoleafDevId].name))

                            success, statusMsg, reply = self.globals['nl'][nanoleafDevId]["nanoleaf"].brightness_raise(targetBrightenBy)

                            if success:
                                self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_HIGH, 'STATUS', [nanoleafDevId]])
                            else:
                                self.sendReceiveDebugLogger.error(u'Problem brightening the device \'{}\': {}'.format(nanoleafDev.name, statusMsg))
                                self.communicationProblem(nanoleafDev) 

                        continue

                    if nanoleafCommand == 'WHITE':
                        nanoleafDevId, targetWhiteLevel, targetWhiteTemperature = nanoleafCommandParameters

                        if self.globals['nl'][nanoleafDevId]["started"] == True:
                            nanoleafDev = indigo.devices[nanoleafDevId]

                            success, statusMsg, reply = self.globals['nl'][nanoleafDevId]["nanoleaf"].set_color_temperature(int(targetWhiteTemperature))

                            if success:
                                success, statusMsg, reply = self.globals['nl'][nanoleafDevId]["nanoleaf"].set_brightness(int(targetWhiteLevel))
                                if success:
                                    self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_HIGH, 'STATUS', [nanoleafDevId]])

                                else:
                                    self.sendReceiveDebugLogger.error(u'Problem setting white level for device \'{}\': {}'.format(nanoleafDev.name, statusMsg))
                                    self.communicationProblem(nanoleafDev) 

                            else:
                                self.sendReceiveDebugLogger.error(u'Problem setting white temperature for device \'{}\': {}'.format(nanoleafDev.name, statusMsg))
                                self.communicationProblem(nanoleafDev) 

                        continue


                    if nanoleafCommand == 'COLOR':
                        nanoleafDevId, targetRedLevel, targetGreenLevel, targetBlueLevel = nanoleafCommandParameters

                        self.sendReceiveDebugLogger.debug(u'NANOLEAF COMMAND [COLOR]; Target for {}: Red={}, Green={}, Blue={}'.format(indigo.devices[nanoleafDevId].name,  targetRedLevel, targetGreenLevel, targetBlueLevel))   
                        if self.globals['nl'][nanoleafDevId]["started"] == True:
                            nanoleafDev = indigo.devices[nanoleafDevId]

                            red = int((targetRedLevel*255.0)/100.0)
                            green = int((targetGreenLevel*255.0)/100.0)
                            blue = int((targetBlueLevel*255.0)/100.0)

                            success, statusMsg, reply = self.globals['nl'][nanoleafDevId]["nanoleaf"].set_rgb([red, green, blue])

                            if success:
                                self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_HIGH, 'STATUS', [nanoleafDevId]])
                            else:
                                self.sendReceiveDebugLogger.error(u'Problem setting the color on the device \'{}\': {}'.format(nanoleafDev.name, statusMsg))
                                self.communicationProblem(nanoleafDev) 

                        continue


                    if nanoleafCommand == 'SETEFFECT':
                        nanoleafDevId = nanoleafCommandParameters[0]

                        effect = nanoleafCommandParameters[1]

                        if self.globals['nl'][nanoleafDevId]["started"] == True:

                            self.sendReceiveDebugLogger.debug(u'Processing {} for \'{}\' '.format(nanoleafCommand, indigo.devices[nanoleafDevId].name))

                            nanoleafDev = indigo.devices[nanoleafDevId]

                            success, statusMsg, reply = self.globals['nl'][nanoleafDevId]["nanoleaf"].set_effect(effect)

                            if success:
                                self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_HIGH, 'STATUS', [nanoleafDevId]])
                            else:
                                self.sendReceiveDebugLogger.error(u'Problem setting the effect on the device \'{}\': {}'.format(nanoleafDev.name, statusMsg))
                                self.communicationProblem(nanoleafDev) 

                        continue

                except Queue.Empty:
                    pass
                # except StandardError, e:
                #     self.sendReceiveDebugLogger.error(u'StandardError detected communicating with nanoleaf device. Line \'{}\' has error=\'{}\''.format(sys.exc_traceback.tb_lineno, e))   
                except StandardError, e:
                    self.sendReceiveDebugLogger.error(u'StandardError detected communicating with NANOLEAF lamp:') 
                    errorLines = traceback.format_exc().splitlines()
                    for errorLine in errorLines:
                        self.sendReceiveDebugLogger.error(u'{}'.format(errorLine))   

        except StandardError, e:
            self.sendReceiveDebugLogger.error(u'StandardError detected in NANOLEAF Send Receive Message Thread. Line \'{}\' has error=\'{}\''.format(sys.exc_traceback.tb_lineno, e))   

        self.sendReceiveDebugLogger.debug(u'NANOLEAF Send Receive Message Thread ended.')   

    def communicationProblem(self, argNanoleafDev):
        if argNanoleafDev.states['connected'] == True:
            argNanoleafDev.updateStateOnServer(key='connected', value=False)
            argNanoleafDev.setErrorStateOnServer(u'no ack')
            self.sendReceiveMonitorLogger.error(u'Communication lost with \"{}\" - status set to \'No Acknowledgment\' (no ack)'.format(argNanoleafDev.name))  

    def updateDeviceState(self, nanoleafDevId):
        self.methodTracer.threaddebug(u'ThreadHandleMessages')

        try:
            nanoleafDev = indigo.devices[nanoleafDevId]

            self.globals['nl'][nanoleafDevId]['lastResponseToPollCount'] = self.globals['polling']['count']  # Set the current poll count (for 'no ack' check)

            if str(self.globals['nl'][nanoleafDevId]["nanoleafInfo"]['state']['on']['value']) == 'True':
                onState = True
                onOffState = 'on'
            else:
                onState = False
                onOffState = 'off'

            colorMode = self.globals['nl'][nanoleafDevId]["nanoleafInfo"]['state']['colorMode']

            hue = int(self.globals['nl'][nanoleafDevId]["nanoleafInfo"]['state']['hue']['value'])
            saturation = int(self.globals['nl'][nanoleafDevId]["nanoleafInfo"]['state']['sat']['value'])
            brightness = int(self.globals['nl'][nanoleafDevId]["nanoleafInfo"]['state']['brightness']['value'])
            if not onState:
                brightnessLevel = 0
            else:
                brightnessLevel = brightness
            colorTemperature = int(self.globals['nl'][nanoleafDevId]["nanoleafInfo"]['state']['ct']['value'])

            success, statusMsg, rgb = self.globals['nl'][nanoleafDevId]["nanoleaf"].rgb
            if not success:
                self.sendReceiveMonitorLogger.error(u'Status not updated for \'{}\': RGB conversion for device update with error \'{}\''.format(nanoleafDev.name, statusMsg))
                return  

            red, green, blue = [int((rgb[0] * 100)/255), int((rgb[1] * 100)/255), int((rgb[2] * 100)/255)]

            self.globals['nl'][nanoleafDevId]['effectsList'] = self.globals['nl'][nanoleafDevId]["nanoleafInfo"]['effects']['effectsList']

            effect = self.globals['nl'][nanoleafDevId]["nanoleafInfo"]['effects']['select']

            serialNo = self.globals['nl'][nanoleafDevId]["nanoleafInfo"]['serialNo']
            model = self.globals['nl'][nanoleafDevId]["nanoleafInfo"]['model']
            manufacturer = self.globals['nl'][nanoleafDevId]["nanoleafInfo"]['manufacturer']
            name = self.globals['nl'][nanoleafDevId]["nanoleafInfo"]['name']
            firmwareVersion = self.globals['nl'][nanoleafDevId]["nanoleafInfo"]['firmwareVersion']

            keyValueList = [
                {'key': 'connected', 'value': True},
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
            if 'version' in props and str(props['version']) == firmwareVersion:
                pass
            else:
                props["version"] = str(firmwareVersion)
                nanoleafDev.replacePluginPropsOnServer(props)

            if nanoleafDev.model != model:
                nanoleafDev.model = str(model)
                nanoleafDev.replaceOnServer()

            self.globals['nl'][nanoleafDevId]['lastResponseToPollCount'] = self.globals['polling']['count']  # Set the current poll count (for 'no ack' check)
 
        except StandardError, e:
            self.sendReceiveDebugLogger.error(u'StandardError detected in \'updateDeviceState\'. Line \'{}\' has error=\'{}\''.format(sys.exc_traceback.tb_lineno, e))   

