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

                    self.discoveryDebugLogger.debug(u"NANOLEAF QUEUED PRIORITY COMMAND DATA: %s" % nanoleafQueuedPriorityCommandData)    
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

                    self.discoveryDebugLogger.debug(u"Dequeued Discovery Message to process [NANOLEAFCOMMAND]: %s" % (nanoleafCommand))

                    if nanoleafCommand == 'STOPTHREAD':
                        break  # Exit While loop and quit thread


                    if nanoleafCommand == 'DISCOVERY':
                        self.discoveryMonitorLogger.info(u"Discovering nanoleaf devices on network - this should take ~%s seconds . . ." % self.globals['discovery']['period'])

                        self.globals['discovery']['discoveredUnmatchedDevices'] = {}                        
                        self.globals['discovery']['discoveredDevices'] = {}                        
                        rc, statusMessage, self.globals['discovery']['discoveredDevices'] = discover_auroras(self.globals['overriddenHostIpAddress'], self.globals['discovery']['period'])  # discover nanoleaf Auroras on network
                        self.discoveryMonitorLogger.debug(u"nanoleaf Discovery result: %s, %s = %s" % (rc, statusMessage, self.globals['discovery']['discoveredDevices']))

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
                                        self.discoveryMonitorLogger.info(u'new nanoleaf device [%s] discovered at address: %s and not yet assigned to Indigo device' % (nlDeviceid, nlIpAddress))
                                    else:
                                        self.discoveryMonitorLogger.info(u"known nanoleaf device [%s] discovered at address: %s and already assigned to Indigo device '%s'" % (nlDeviceid, nlIpAddress, indigo.devices[devId].name))
                            else:
                                self.discoveryMonitorLogger.error(u"Discovering nanoleaf devices failed to find any nanoleaf devices. Make sure nanoleaf is switched on, has been connected to network and is accessible from nanoleaf App")
                        else:
                            self.discoveryMonitorLogger.error(u"Discovering nanoleaf devices failed: %s" % statusMessage)

                        continue

                except Queue.Empty:
                    pass
                # except StandardError, e:
                #     self.discoveryDebugLogger.error(u"StandardError detected communicating with nanoleaf device. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))   
                except StandardError, e:
                    self.discoveryDebugLogger.error(u"StandardError detected communicating with NANOLEAF lamp:") 
                    errorLines = traceback.format_exc().splitlines()
                    for errorLine in errorLines:
                        self.discoveryDebugLogger.error(u"%s" % errorLine)   

        except StandardError, e:
            self.discoveryDebugLogger.error(u"StandardError detected in NANOLEAF Send Receive Message Thread. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))   

        self.discoveryDebugLogger.debug(u"NANOLEAF Send Receive Message Thread ended.")   