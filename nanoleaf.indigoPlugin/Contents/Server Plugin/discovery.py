#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# nanoleaf Controller - Main © Autolog 2017-2020
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
from nanoleaf.nanoleaf import *
from nanoleaf.discover_nanoleaf import *

class ThreadDiscovery(threading.Thread):

    # This class controls the discovery of nanoleaf devices.

    def __init__(self, globals):

        threading.Thread.__init__(self)

        self.globals = globals[0]

        self.discoveryMonitorLogger = logging.getLogger("Plugin.MonitorDiscovery")
        self.discoveryMonitorLogger.setLevel(self.globals['debug']['monitorDiscovery'])

        self.discoveryDebugLogger = logging.getLogger("Plugin.DebugDiscovery")
        self.discoveryDebugLogger.setLevel(self.globals['debug']['debugDiscovery'])

        self.methodTracer = logging.getLogger("Plugin.method")  
        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

        self.discoveryDebugLogger.debug(u"Initialising nanoleaf Discovery Thread")  

    def run(self):
        self.methodTracer.threaddebug(u"ThreadDiscovery")
 
        try:
            self.discoveryDebugLogger.debug(u"nanoleaf Discovery Thread initialised.")    

            while True:

                try:
                    nanoleafQueuedPriorityCommandData = self.globals['queues']['discovery'].get(True,5)

                    self.discoveryDebugLogger.debug(u'NANOLEAF QUEUED PRIORITY COMMAND DATA: {}'.format(nanoleafQueuedPriorityCommandData))    
                    nanoleafQueuePriority, nanoleafCommand, nanoleafCommandParameters = nanoleafQueuedPriorityCommandData

                    # Check if monitoring / debug options have changed and if so set accordingly
                    if self.globals['debug']['previousMonitorDiscovery'] != self.globals['debug']['monitorDiscovery']:
                        self.globals['debug']['previousMonitorDiscovery'] = self.globals['debug']['monitorDiscovery']
                        self.discoveryMonitorLogger.setLevel(self.globals['debug']['monitorDiscovery'])
                    if self.globals['debug']['previousDebugDiscovery'] != self.globals['debug']['debugDiscovery']:
                        self.globals['debug']['previousDebugDiscovery'] = self.globals['debug']['debugDiscovery']
                        self.discoveryDebugLogger.setLevel(self.globals['debug']['debugDiscovery'])
                    if self.globals['debug']['previousDebugMethodTrace'] !=self.globals['debug']['debugMethodTrace']:
                        self.globals['debug']['previousDebugMethodTrace'] = self.globals['debug']['debugMethodTrace']
                        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

                    self.discoveryDebugLogger.debug(u'Dequeued Discovery Message to process [NANOLEAFCOMMAND]: {}'.format(nanoleafCommand))

                    if nanoleafCommand == 'STOPTHREAD':
                        break  # Exit While loop and quit thread


                    if nanoleafCommand == 'DISCOVERY':
                        self.discoveryMonitorLogger.info(u'Discovering nanoleaf aurora and canvas devices on network - this should take ~{} seconds . . .'.format(self.globals['discovery']['period']))

                        self.globals['discovery']['discoveredUnmatchedDevices'] = {}
                        self.globals['discovery']['discoveredAuroras'] = {}                        
                        self.globals['discovery']['discoveredCanvases'] = {}                        
                        self.globals['discovery']['discoveredDevices'] = {}

                        rc_aurora, statusMessage, self.globals['discovery']['discoveredAuroras'] = discover_nanoleafs(self.globals['overriddenHostIpAddress'], self.globals['discovery']['period'], 'aurora')  # discover nanoleaf Auroras on network
                        self.discoveryMonitorLogger.debug(u'nanoleaf aurora Discovery result: {}, {} = {}'.format(rc_aurora, statusMessage, self.globals['discovery']['discoveredAuroras']))
                        if not rc_aurora:  # Return code = False = NOT OK
                            self.discoveryMonitorLogger.error(u'Discovering nanoleaf aurora devices failed: {}'.format(statusMessage))
                            continue

                        rc_canvas, statusMessage, self.globals['discovery']['discoveredCanvases'] = discover_nanoleafs(self.globals['overriddenHostIpAddress'], self.globals['discovery']['period'], 'canvas')  # discover nanoleaf Canvases on network
                        self.discoveryMonitorLogger.debug(u'nanoleaf canvas Discovery result: {}, {} = {}'.format(rc_canvas, statusMessage, self.globals['discovery']['discoveredCanvases']))
                        if not rc_canvas:  # Return code = False = NOT OK
                            self.discoveryMonitorLogger.error(u'Discovering nanoleaf canvas devices failed: {}'.format(statusMessage))
                            continue

                        self.globals['discovery']['discoveredDevices'] = self.globals['discovery']['discoveredAuroras']
                        self.globals['discovery']['discoveredDevices'].update(self.globals['discovery']['discoveredCanvases'])

                        self.discoveryMonitorLogger.debug(u'nanoleaf Discovered Devices: {}'.format(self.globals['discovery']['discoveredDevices']))
                        self.discoveryMonitorLogger.debug(u'NANOLEAF DISCOVERY: {}'.format(self.globals['discovery']['discoveredDevices']))

                        if len(self.globals['discovery']['discoveredDevices']) > 0:
                            for nlDeviceid, nlInfo in self.globals['discovery']['discoveredDevices'].iteritems():
                                nlDeviceid = '{}'.format(nlDeviceid)
                                nlIpAddress = '{}'.format(nlInfo[0])
                                nlMacAddress = '{}'.format(nlInfo[1])

                                if nlMacAddress[1:2] == u':':
                                    nlMacAddress = '0{}'.format(nlMacAddress)
                                nlDeviceName = '{}'.format(nlInfo[2])
                                if 'aurora' in nlDeviceName.lower():
                                    nlDeviceName = 'Aurora'
                                elif 'canvas' in nlDeviceName.lower():
                                    nlDeviceName = 'Canvas'
                                nanoleafDeviceMatchedtoIndigoDevice = False
                                for devId in self.globals['nl']:
                                    if self.globals['nl'][devId]['nlDeviceid'] != '':
                                        if nlDeviceid == self.globals['nl'][devId]['nlDeviceid']:
                                            nanoleafDeviceMatchedtoIndigoDevice = True
                                            break
                                if not nanoleafDeviceMatchedtoIndigoDevice:
                                    self.globals['discovery']['discoveredUnmatchedDevices'][nlDeviceid] = (nlIpAddress, nlMacAddress, nlDeviceName)
                                    self.discoveryMonitorLogger.info(u'New nanoleaf {} with device Id \'{}\' and Mac Address \'{}\' discovered at IP Address: {} and not yet assigned to an Indigo device'.format(nlDeviceName, nlDeviceid, nlMacAddress, nlIpAddress))
                                else:
                                    dev = indigo.devices[devId]
                                    devName = dev.name
                                    self.discoveryMonitorLogger.info(u'Known nanoleaf {} with device Id \'{}\' and Mac Address \'{}\' discovered at address: {} and already assigned to Indigo device \'{}\''.format(nlDeviceName, nlDeviceid, nlMacAddress, nlIpAddress, devName))
                                    devIpAddress = indigo.devices[devId].states['ipAddress']
                                    if devIpAddress != nlIpAddress:
                                        self.discoveryDebugLogger.error(u'WARNING: IP Address changed for Nanoleaf \'{}\', it was \'{}\' and is now \'{}\' - Edit Device and Update IP Address.'.format(devName, devIpAddress, nlIpAddress))
                                        dev.updateStateOnServer(key='connected', value=False)
                                        dev.setErrorStateOnServer(u"ip mismatch")
                        else:
                            self.discoveryMonitorLogger.error(u"Discovering nanoleaf aurora / canvas devices failed to find any. Make sure nanoleaf device is switched on, has been connected to network and is accessible from nanoleaf App")
                        continue

                except Queue.Empty:
                    pass
                except StandardError, e:
                    self.discoveryDebugLogger.error(u"StandardError detected communicating with NANOLEAF lamp:") 
                    errorLines = traceback.format_exc().splitlines()
                    for errorLine in errorLines:
                        self.discoveryDebugLogger.error(u'{}'.format(errorLine))   

        except StandardError, e:
            self.discoveryDebugLogger.error(u'StandardError detected in NANOLEAF Send Receive Message Thread. Line \'{}\' has error=\'{}\''.format(sys.exc_traceback.tb_lineno, e))   

        self.discoveryDebugLogger.debug(u'NANOLEAF Send Receive Message Thread ended.')   