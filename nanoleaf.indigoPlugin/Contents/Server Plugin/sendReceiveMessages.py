#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# nanoleaf Controller - Main © Autolog 2017
#

import colorsys
try:
    import indigo
except:
    pass
import locale
import logging
import Queue
import socket
import struct
import sys
import threading
from time import time, sleep
import traceback

from constants import *
from nanoleaf.aurora import *
from nanoleaf.discover import *

class ThreadSendReceiveMessages(threading.Thread):

    # This class controls the sending of commands to a nanoleaf device and handles it's response.
    # It receives high level commands to send to the nanoleaf device from a queue which it waits on
    #   and queues replies for handling by the runConcurrent thread

    # It contains the logic for correctly formatting the the high level commands to be sent to the nanoleaf device
    #   into the specific formats required by the nanoleaf device.

    def __init__(self, globals):

        threading.Thread.__init__(self)

        self.globals = globals[0]

        self.sendReceiveMonitorLogger = logging.getLogger("Plugin.MonitorSendReceive")
        self.sendReceiveMonitorLogger.setLevel(self.globals['debug']['monitorSendReceive'])

        self.sendReceiveDebugLogger = logging.getLogger("Plugin.DebugSendReceive")
        self.sendReceiveDebugLogger.setLevel(self.globals['debug']['debugSendReceive'])

        self.methodTracer = logging.getLogger("Plugin.method")  
        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

        self.sendReceiveDebugLogger.debug(u"Initialising nanoleaf Send and Receive Message Thread")  

    def run(self):
        self.methodTracer.threaddebug(u"ThreadSendReceiveMessages")
 
        try:
            self.sendReceiveDebugLogger.debug(u"nanoleaf Send Receive Message Thread initialised.")    

            while True:

                try:
                    nanoleafQueuedPriorityCommandData = self.globals['queues']['messageToSend'].get(True,5)

                    self.sendReceiveDebugLogger.debug(u"NANOLEAF QUEUED PRIORITY COMMAND DATA: %s" % nanoleafQueuedPriorityCommandData)    
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

                    self.sendReceiveDebugLogger.debug(u"Dequeued Send Message to process [NANOLEAFCOMMAND]: %s" % (nanoleafCommand))

                    # Handle commands to all NANOLEAF lamps

                    if nanoleafCommand == 'STOPTHREAD':
                        break  # Exit While loop and quit thread


                    if nanoleafCommand == 'STATUSPOLLING':
                        for nanoleafDevId in self.globals['nl']:
                            if self.globals['nl'][nanoleafDevId]["started"] == True:
                                self.sendReceiveDebugLogger.debug(u"Processing %s for %s" % (nanoleafCommand, indigo.devices[nanoleafDevId].name))
                                self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_MEDIUM, 'STATUS', [nanoleafDevId]])
                                self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_LOW, 'GETWIFIINFO', [nanoleafDevId]])
                                 
                        continue  

                    if nanoleafCommand == 'STATUS':
                        nanoleafDevId = nanoleafCommandParameters[0]

                        if self.globals['nl'][nanoleafDevId]["started"] == True:
                            self.sendReceiveDebugLogger.debug(u"Processing %s for '%s'" % (nanoleafCommand, indigo.devices[nanoleafDevId].name))
                            nanoleafDev = indigo.devices[nanoleafDevId]
                            ipAddress = self.globals['nl'][nanoleafDevId]["ipAddress"]
                            authToken = self.globals['nl'][nanoleafDevId]["authToken"]
                            self.globals['nl'][nanoleafDevId]["aurora"] = Aurora(ipAddress, authToken)  # May move this to discovery process?
                            self.globals['nl'][nanoleafDevId]["auroraInfo"] = self.globals['nl'][nanoleafDevId]["aurora"].info

                            self.updateDeviceState(nanoleafDevId)

                        continue

                    if (nanoleafCommand == 'ON') or (nanoleafCommand == 'OFF'):
                        nanoleafDevId = nanoleafCommandParameters[0]

                        if self.globals['nl'][nanoleafDevId]["started"] == True:
                            self.sendReceiveDebugLogger.debug(u"Processing %s for '%s' " % (nanoleafCommand, indigo.devices[nanoleafDevId].name))

                            if nanoleafCommand == 'ON':
                                self.globals['nl'][nanoleafDevId]["aurora"].on = True
                            elif nanoleafCommand == 'OFF':
                                self.globals['nl'][nanoleafDevId]["aurora"].off = True

                            self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_HIGH, 'STATUS', [nanoleafDevId]])
                        
                        continue


                    if nanoleafCommand == 'DISCOVERY_DELAYED':
                        if 'DISCOVERY' in self.globals['discovery']['timer']:
                            self.globals['discovery']['timer']['DISCOVERY'].cancel()

                        self.globals['discovery']['timer']['DISCOVERY'] = threading.Timer(30.0, self.handleTimerDiscoveryCommand,[])
                        self.globals['discovery']['timer']['DISCOVERY'].start()


                    if nanoleafCommand == 'DISCOVERY':
                        self.sendReceiveMonitorLogger.info(u"Discovering nanoleaf devices on network - this should take ~%s seconds . . ." % self.globals['discovery']['period'])

                        self.globals['discovery']['discoveredUnmatchedDevices'] = {}                        
                        self.globals['discovery']['discoveredDevices'] = {}                        
                        rc, statusMessage, self.globals['discovery']['discoveredDevices'] = discover_auroras(self.globals['discovery']['period'])  # discover nanoleaf Auroras on network
                        self.sendReceiveMonitorLogger.debug(u"nanoleaf Discovery result: %s, %s = %s" % (rc, statusMessage, self.globals['discovery']['discoveredDevices']))

                        if rc:  # Return code = True = OK
                            if len(self.globals['discovery']['discoveredDevices']) > 0:
                                for nlDeviceid, nlIpAddress in self.globals['discovery']['discoveredDevices'].iteritems():
                                    nlDeviceid = str(nlDeviceid)
                                    nlIpAddress = str(nlIpAddress)
                                    nanoleafDeviceMatchedtoIndigoDevice = False
                                    for devId in self.globals['nl']:
                                        if self.globals['nl'][devId]['nlDeviceid'] != '':
                                            if nlDeviceid == self.globals['nl'][devId]['nlDeviceid']:
                                                nanoleafDeviceMatchedtoIndigoDevice = True
                                                break
                                    if not nanoleafDeviceMatchedtoIndigoDevice:
                                        self.globals['discovery']['discoveredUnmatchedDevices'][nlDeviceid] = nlIpAddress
                                        self.sendReceiveMonitorLogger.info(u'new nanoleaf device [%s] discovered at address: %s and not yet assigned to Indigo device' % (nlDeviceid, nlIpAddress))
                                    else:
                                        self.sendReceiveMonitorLogger.info(u"known nanoleaf device [%s] discovered at address: %s and already assigned to Indigo device '%s'" % (nlDeviceid, nlIpAddress, indigo.devices[devId].name))
                            else:
                                self.sendReceiveMonitorLogger.error(u"Discovering nanoleaf devices failed to find any nanoleaf devices. Make sure nanoleaf is switched on, has been connected to network and is accessible from nanoleaf App")
                        else:
                            self.sendReceiveMonitorLogger.error(u"Discovering nanoleaf devices failed: %s" % statusMessage)

                        continue


                    if (nanoleafCommand == 'BRIGHTNESS'):
                        nanoleafDevId = nanoleafCommandParameters[0]

                        targetBrightness = nanoleafCommandParameters[1]


                        if self.globals['nl'][nanoleafDevId]["started"] == True:
                            self.sendReceiveDebugLogger.debug(u"Processing %s for '%s' " % (nanoleafCommand, indigo.devices[nanoleafDevId].name))

                            self.globals['nl'][nanoleafDevId]["aurora"].brightness = targetBrightness

                            self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_HIGH, 'STATUS', [nanoleafDevId]])
                        
                        continue

                    if nanoleafCommand == 'DIM':
                        nanoleafDevId = nanoleafCommandParameters[0]

                        targetDimBy = nanoleafCommandParameters[1]

                        if self.globals['nl'][nanoleafDevId]["started"] == True:

                            self.sendReceiveDebugLogger.debug(u"Processing %s for '%s' " % (nanoleafCommand, indigo.devices[nanoleafDevId].name))

                            self.globals['nl'][nanoleafDevId]["aurora"].brightness_lower(targetDimBy)

                            self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_HIGH, 'STATUS', [nanoleafDevId]])

                        continue

                    if nanoleafCommand == 'BRIGHTEN':
                        nanoleafDevId = nanoleafCommandParameters[0]

                        targetBrightenBy = nanoleafCommandParameters[1]

                        if self.globals['nl'][nanoleafDevId]["started"] == True:

                            self.sendReceiveDebugLogger.debug(u"Processing %s for '%s' " % (nanoleafCommand, indigo.devices[nanoleafDevId].name))

                            self.globals['nl'][nanoleafDevId]["aurora"].brightness_raise(targetBrightenBy)

                            self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_HIGH, 'STATUS', [nanoleafDevId]])

                        continue

                    if nanoleafCommand == 'WHITE':
                        nanoleafDevId, targetWhiteLevel, targetWhiteTemperature = nanoleafCommandParameters

                        if self.globals['nl'][nanoleafDevId]["started"] == True:
                            nanoleafDev = indigo.devices[nanoleafDevId]

                            self.globals['nl'][nanoleafDevId]["aurora"].color_temperature =  int(targetWhiteTemperature)
                            self.globals['nl'][nanoleafDevId]["aurora"].brightness =  int(targetWhiteLevel)

                            self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_HIGH, 'STATUS', [nanoleafDevId]])

                        continue


                    if nanoleafCommand == 'COLOR':
                        nanoleafDevId, targetRedLevel, targetGreenLevel, targetBlueLevel = nanoleafCommandParameters

                        self.sendReceiveDebugLogger.debug(u'NANOLEAF COMMAND [COLOR]; Target for %s: Red=%s, Green=%s, Blue=%s' % (indigo.devices[nanoleafDevId].name,  targetRedLevel, targetGreenLevel, targetBlueLevel))   
                        if self.globals['nl'][nanoleafDevId]["started"] == True:
                            nanoleafDev = indigo.devices[nanoleafDevId]

                            red = int((targetRedLevel*255.0)/100.0)
                            green = int((targetGreenLevel*255.0)/100.0)
                            blue = int((targetBlueLevel*255.0)/100.0)

                            self.globals['nl'][nanoleafDevId]["aurora"].rgb =  [red, green, blue]
                            #self.globals['nl'][nanoleafDevId]["aurora"].saturation =  int(targetSaturation)
                            #self.globals['nl'][nanoleafDevId]["aurora"].brightness =  int(targetBrightness)

                            self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_HIGH, 'STATUS', [nanoleafDevId]])

                        continue


                    if nanoleafCommand == 'SETEFFECT':
                        nanoleafDevId = nanoleafCommandParameters[0]

                        effect = nanoleafCommandParameters[1]

                        if self.globals['nl'][nanoleafDevId]["started"] == True:

                            self.sendReceiveDebugLogger.debug(u"Processing %s for '%s' " % (nanoleafCommand, indigo.devices[nanoleafDevId].name))

                            nanoleafDev = indigo.devices[nanoleafDevId]

                            self.globals['nl'][nanoleafDevId]["aurora"].effect = effect

                            self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_HIGH, 'STATUS', [nanoleafDevId]])

                        continue



                except Queue.Empty:
                    pass
                # except StandardError, e:
                #     self.sendReceiveDebugLogger.error(u"StandardError detected communicating with nanoleaf device. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))   
                except StandardError, e:
                    self.sendReceiveDebugLogger.error(u"StandardError detected communicating with NANOLEAF lamp:") 
                    errorLines = traceback.format_exc().splitlines()
                    for errorLine in errorLines:
                        self.sendReceiveDebugLogger.error(u"%s" % errorLine)   

        except StandardError, e:
            self.sendReceiveDebugLogger.error(u"StandardError detected in NANOLEAF Send Receive Message Thread. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))   

        self.sendReceiveDebugLogger.debug(u"NANOLEAF Send Receive Message Thread ended.")   

    def clearStatusTimer(self, dev):
        self.methodTracer.threaddebug(u"CLASS: ThreadSendReceiveMessages")

        if 'STATUS' in self.globals['deviceTimers'][dev.id]:
            self.globals['deviceTimers'][dev.id]['STATUS'].cancel()

    def handleTimerRepeatingQueuedStatusCommand(self, dev, seconds):
        self.methodTracer.threaddebug(u"CLASS: ThreadSendReceiveMessages")

        try: 
            self.sendReceiveDebugLogger.debug(u'Timer for %s [%s] invoked for repeating queued message STATUS - %s seconds left' % (dev.name, dev.address, seconds))

            try:
                del self.globals['deviceTimers'][dev.id]['STATUS']
            except:
                pass

            self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_HIGH, 'STATUS', [dev.id]])

            if seconds > 0:
                seconds -= 1
                self.globals['deviceTimers'][dev.id]['STATUS'] = threading.Timer(1.0, self.handleTimerRepeatingQueuedStatusCommand, [dev, seconds])
                self.globals['deviceTimers'][dev.id]['STATUS'].start()

        except StandardError, e:
            self.sendReceiveDebugLogger.error(u"handleTimerRepeatingQueuedStatusCommand error detected. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))   

    def handleTimerDiscoveryCommand(self):
        self.methodTracer.threaddebug(u"CLASS: ThreadSendReceiveMessages")

        try:
            self.sendReceiveDebugLogger.debug(u'Timer for Discovery invoked to discover NANOLEAF devices)')

            try:
                del self.globals['discoveryTimer']['DISCOVERY']
            except:
                pass

            self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_LOW, 'DISCOVERY', []])


        except StandardError, e:
            self.sendReceiveDebugLogger.error(u"handleTimerDiscoveryCommand error detected. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))   


    def clearWaveformOffTimer(self, dev):
        self.methodTracer.threaddebug(u"CLASS: ThreadSendReceiveMessages")

        if 'WAVEFORM_OFF' in self.globals['deviceTimers'][dev.id]:
            self.globals['deviceTimers'][dev.id]['WAVEFORM_OFF'].cancel()

    def handleTimerWaveformOffCommand(self, dev):
        self.methodTracer.threaddebug(u"CLASS: ThreadSendReceiveMessages")

        try: 
            self.sendReceiveDebugLogger.debug(u'Timer for %s [%s] invoked to turn off NANOLEAF device (Used by Waveform)' % (dev.name, dev.address))

            try:
                del self.globals['deviceTimers'][dev.id]['WAVEFORM_OFF']
            except:
                pass

            self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_HIGH, 'WAVEFORM_OFF', [dev.id]])

        except StandardError, e:
            self.sendReceiveDebugLogger.error(u"handleTimerRepeatingQueuedStatusCommand error detected. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))   

    def communicationLost(self, argNanoleafDev):
        if argNanoleafDev.states['connected'] == True:
            argNanoleafDev.updateStateOnServer(key='connected', value=False)
            argNanoleafDev.setErrorStateOnServer(u"no ack")
            self.sendReceiveMonitorLogger.error(u"Communication lost with \"%s\" - status set to 'No Acknowledgment' (no ack)" % argNanoleafDev.name)  

    def updateDeviceState(self, nanoleafDevId):
        self.methodTracer.threaddebug(u"ThreadHandleMessages")

        try:
            nanoleafDev = indigo.devices[nanoleafDevId]

            if str(self.globals['nl'][nanoleafDevId]["auroraInfo"]['state']['on']['value']) == 'True':
                onState = True
                onOffState = 'on'
            else:
                onState = False
                onOffState = 'off'

            colorMode = self.globals['nl'][nanoleafDevId]["auroraInfo"]['state']['colorMode']

            hue = int(self.globals['nl'][nanoleafDevId]["auroraInfo"]['state']['hue']['value'])
            saturation = int(self.globals['nl'][nanoleafDevId]["auroraInfo"]['state']['sat']['value'])
            brightness = int(self.globals['nl'][nanoleafDevId]["auroraInfo"]['state']['brightness']['value'])
            if not onState:
                brightnessLevel = 0
            else:
                brightnessLevel = brightness
            colorTemperature = int(self.globals['nl'][nanoleafDevId]["auroraInfo"]['state']['ct']['value'])

            rgb = self.globals['nl'][nanoleafDevId]["aurora"].rgb
            red, green, blue = [int((rgb[0] * 100)/255), int((rgb[1] * 100)/255), int((rgb[2] * 100)/255)]

            self.globals['nl'][nanoleafDevId]['effectsList'] = self.globals['nl'][nanoleafDevId]["auroraInfo"]['effects']['effectsList']

            effect = self.globals['nl'][nanoleafDevId]["auroraInfo"]['effects']['select']

            serialNo = self.globals['nl'][nanoleafDevId]["auroraInfo"]['serialNo']
            model = self.globals['nl'][nanoleafDevId]["auroraInfo"]['model']
            manufacturer = self.globals['nl'][nanoleafDevId]["auroraInfo"]['manufacturer']
            name = self.globals['nl'][nanoleafDevId]["auroraInfo"]['name']
            firmwareVersion = self.globals['nl'][nanoleafDevId]["auroraInfo"]['firmwareVersion']

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
 
        except StandardError, e:
            self.sendReceiveDebugLogger.error(u"StandardError detected in 'handleNanoleafLampMessage'. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))   

