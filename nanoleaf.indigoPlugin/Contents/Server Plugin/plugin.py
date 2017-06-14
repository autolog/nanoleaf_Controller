#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# nanoleaf Controller - Main © Autolog 2017
#

import colorsys
from datetime import datetime
try:
    import indigo
except:
    pass
import locale
import logging
import os
import Queue
import re
import sys
import threading
import time
#from time import localtime, time, sleep, strftime

from constants import *
from ghpu import GitHubPluginUpdater
from nanoleaf.aurora import *
from nanoleaf.discover import *
from polling import ThreadPolling
from sendReceiveMessages import ThreadSendReceiveMessages
from discovery import ThreadDiscovery



class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        # Initialise dictionary to store plugin Globals
        self.globals = {}

        # Used to prevent runConcurrentThread from running until startup is complete
        self.globals['startupCompleted'] = False

        # Initialise dictionary for debug in plugin Globals
        self.globals['debug'] = {}
        self.globals['debug']['monitorDebugEnabled']        = False  # if False it indicates no debugging is active else it indicates that at least one type of debug is active
        self.globals['debug']['debugFilteredIpAddresses']   = []  # Set to nanoleaf IP Address(es) to limit processing for debug purposes
        self.globals['debug']['debugFilteredIpAddressesUI'] = ''  # Set to nanoleaf IP Address(es) to limit processing for debug purposes (UI version)
        self.globals['debug']['debugGeneral']               = logging.INFO  # For general debugging of the main thread
        self.globals['debug']['monitorSendReceive']         = logging.INFO  # For monitoring messages sent to nanoleaf devices
        self.globals['debug']['debugSendReceive']           = logging.INFO  # For debugging messages sent to nanoleaf devices
        self.globals['debug']['monitorDiscovery']           = logging.INFO  # For monitoring discovery of nanoleaf devices
        self.globals['debug']['debugDiscovery']             = logging.INFO  # For debugging discovery of nanoleaf devices
        self.globals['debug']['debugMethodTrace']           = logging.INFO  # For displaying method invocations i.e. trace method
        self.globals['debug']['debugPolling']               = logging.INFO  # For polling debugging
        self.globals['debug']['previousDebugGeneral']       = logging.INFO  # For general debugging of the main thread
        self.globals['debug']['previousMonitorSendReceive'] = logging.INFO  # For monitoring messages sent to nanoleaf devices 
        self.globals['debug']['previousDebugSendReceive']   = logging.INFO  # For debugging messages sent to nanoleaf devices
        self.globals['debug']['previousMonitorDiscovery']   = logging.INFO  # For monitoring discovery of nanoleaf devices 
        self.globals['debug']['previousDebugDiscovery']     = logging.INFO  # For debugging  discovery of  nanoleaf devices
        self.globals['debug']['previousDebugMethodTrace']   = logging.INFO  # For displaying method invocations i.e. trace method
        self.globals['debug']['previousDebugPolling']       = logging.INFO  # For polling debugging

        # Setup Logging
        logformat = logging.Formatter('%(asctime)s.%(msecs)03d\t%(levelname)-12s\t%(name)s.%(funcName)-25s %(msg)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(logformat)
        self.plugin_file_handler.setLevel(logging.INFO)  # Master Logging Level for Plugin Log file
        self.indigo_log_handler.setLevel(logging.INFO)   # Logging level for Indigo Event Log
        self.generalLogger = logging.getLogger("Plugin.general")
        self.generalLogger.setLevel(self.globals['debug']['debugGeneral'])
        self.methodTracer = logging.getLogger("Plugin.method")  
        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

        # Now logging is set-up, output Initialising Message
        self.generalLogger.info(u"%s initializing . . ." % PLUGIN_TITLE)

        
        
        # Initialise dictionary to store internal details about nanoleaf devices
        self.globals['nl'] = {} 

        self.globals['threads'] = {}
        self.globals['threads']['sendReceiveMessages'] = {}
        self.globals['threads']['polling'] = {}

        # Initialise discovery dictionary to store discovered devices, discovery period
        self.globals['discovery'] = {}
        self.globals['discovery']['discoveredDevices'] = {}  # dict of nanoleaf device ids (psuedo mac) and IP Addresses
        self.globals['discovery']['discoveredUnmatchedDevices'] = {}  # dict of unmatched (no Indigo device) nanoleaf device ids (psuedo mac) and IP Addresses
        self.globals['discovery']['period'] = 30  # period of each active discovery
        self.globals['discovery']['count'] = 0  # count of number of discoveries performed

        # Initialise dictionary to store message queues
        self.globals['queues'] = {}
        self.globals['queues']['messageToSend'] = ''  # Set-up in plugin start (used to process commands to be sent to the nanoleaf device)
        self.globals['queues']['discovery'] = ''  # Set-up in plugin start (used to process command to invoke nanoleaf device discovery)
        self.globals['queues']['returnedResponse'] = '' # Set-up in plugin start (a common returned response queue)
        self.globals['queues']['initialised'] = False

        # Initialise dictionary for polling thread
        self.globals['polling'] = {}
        self.globals['polling']['threadActive'] = False        
        self.globals['polling']['status'] = False
        self.globals['polling']['seconds'] = float(300.0)  # 5 minutes
        self.globals['polling']['forceThreadEnd'] = False
        self.globals['polling']['quiesced'] = False
        self.globals['polling']['missedLimit'] = int(2)  # i.e. 10 minutes in 'seconds' = 300 (5 mins)
        self.globals['polling']['count'] = int(0)
        self.globals['polling']['trigger'] = int(0)

        # Initialise dictionary for constants
        self.globals['constant'] = {}
        self.globals['constant']['defaultDatetime'] = datetime.strptime("2000-01-01","%Y-%m-%d")

        # Initialise dictionary for update checking
        self.globals['update'] = {}

        self.validatePrefsConfigUi(pluginPrefs)  # Validate the Plugin Config
        
        self.setDebuggingLevels(pluginPrefs)  # Check monitoring / debug / filtered IP address options

    def __del__(self):

        indigo.PluginBase.__del__(self)

    def updatePlugin(self):
        self.globals['update']['updater'].update()

    def checkForUpdates(self):
        self.globals['update']['updater'].checkForUpdate()

    def forceUpdate(self):
        self.globals['update']['updater'].update(currentVersion='0.0.0')

    def checkRateLimit(self):
        limiter = self.globals['update']['updater'].getRateLimit()
        self.generalLogger.info('RateLimit {limit:%d remaining:%d resetAt:%d}' % limiter)

    def startup(self):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        # Set-up update checker
        self.globals['update']['updater'] = GitHubPluginUpdater(self)
        self.globals['update']['nextCheckTime'] = time.time()

        indigo.devices.subscribeToChanges()

        # nanoleaf device internal storage initialisation

        for dev in indigo.devices.iter("self"):
            self.generalLogger.debug(u'nanoleaf Indigo Device: %s [%s = %s]' % (dev.name, dev.states['ipAddress'], dev.address))
            self.globals['nl'][dev.id] = {}
            self.globals['nl'][dev.id]['started']                 = False
            self.globals['nl'][dev.id]['initialisedFromdevice']   = False
            self.globals['nl'][dev.id]['nlDeviceid']              = dev.address  # eg. 'd0:73:d5:0a:bc:de' (psuedo mac address)
            self.globals['nl'][dev.id]['authToken']               = ''
            self.globals['nl'][dev.id]['nanoleafObject']          = None
            self.globals['nl'][dev.id]['ipAddress']               = str(dev.pluginProps.get('ipAddress', ''))
            self.globals['nl'][dev.id]['lastResponseToPollCount'] = 0
            self.globals['nl'][dev.id]['effectsList']             = []
            dev.setErrorStateOnServer(u"no ack")  # Default to 'no ack' status i.e. communication still to be established

        # Create process queues
        self.globals['queues']['messageToSend'] = Queue.PriorityQueue()  # Used to queue commands to be sent to nanoleaf devices
        self.globals['queues']['discovery'] = Queue.PriorityQueue()  # Used to queue command for nanoleaf device discovery
        self.globals['queues']['initialised'] = True

        # define and start threads that will send messages to & receive messages from the nanoleaf devices and handle discovery
        self.globals['threads']['sendReceiveMessages'] = ThreadSendReceiveMessages([self.globals])
        self.globals['threads']['sendReceiveMessages'].start()
        self.globals['threads']['discovery'] = ThreadDiscovery([self.globals])
        self.globals['threads']['discovery'].start()

        if self.globals['polling']['status'] == True and self.globals['polling']['threadActive'] == False:
            self.globals['threads']['polling']['event']  = threading.Event()
            self.globals['threads']['polling']['thread'] = ThreadPolling([self.globals, self.globals['threads']['polling']['event']])
            self.globals['threads']['polling']['thread'].start()

        self.globals['discovery']['period'] = float(self.pluginPrefs.get("defaultDiscoveryPeriod", 30))

        self.globals['queues']['discovery'].put([QUEUE_PRIORITY_LOW, 'DISCOVERY', []])
 
        self.globals['startupCompleted'] = True  # Enable runConcurrentThread to commence processing

        self.generalLogger.info(u"%s initialization complete" % PLUGIN_TITLE)
        
    def shutdown(self):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        if self.globals['polling']['threadActive'] == True:
            self.globals['polling']['forceThreadEnd'] = True
            self.globals['threads']['polling']['event'].set()  # Stop the Polling Thread

        self.generalLogger.info(u"%s  Plugin shutdown complete" % PLUGIN_TITLE)


    def validatePrefsConfigUi(self, valuesDict):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try: 

            if "updateCheck" in valuesDict:
                self.globals['update']['check'] = bool(valuesDict["updateCheck"])
            else:
                self.globals['update']['check'] = False

            # No need to validate this as value can only be selected from a pull down list?
            if "checkFrequency" in valuesDict:
                self.globals['update']['checkFrequency'] = valuesDict.get("checkFrequency", 'DAILY')

            if "statusPolling" in valuesDict:
                self.globals['polling']['status'] = bool(valuesDict["statusPolling"])
            else:
                self.globals['polling']['status'] = False

            # No need to validate this as value can only be selected from a pull down list?
            if "pollingSeconds" in valuesDict:
                self.globals['polling']['seconds'] = float(valuesDict["pollingSeconds"])
            else:
                self.globals['polling']['seconds'] = float(300.0)  # Default to 5 minutes

            if "missedPollLimit" in valuesDict:
                try:
                    self.globals['polling']['missedPollLimit'] = int(valuesDict["missedPollLimit"])
                except:
                    errorDict = indigo.Dict()
                    errorDict["missedPollLimit"] = "Invalid number for missed polls limit"
                    errorDict["showAlertText"] = "The number of missed polls limit must be specified as an integer e.g 2, 5 etc."
                    return (False, valuesDict, errorDict)
            else:
                self.globals['polling']['missedPollLimit'] = int(360)  # Default to 6 minutes

            if "defaultDiscoveryPeriod" in valuesDict:
                try:
                    self.pluginConfigDefaultDurationDimBrighten = int(valuesDict["defaultDiscoveryPeriod"])
                except:
                    errorDict = indigo.Dict()
                    errorDict["defaultDiscoveryPeriod"] = "Invalid number for seconds"
                    errorDict["showAlertText"] = "The number of seconds must be specified as an integer e.g. 10, 20 etc."
                    return (False, valuesDict, errorDict)
            else:
                self.globals['discovery']['period'] = float(30.0)  # Default to 30 seconds  

            return True

        except StandardError, e:
            self.generalLogger.error(u"validatePrefsConfigUi error detected. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))   
            return True


    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.generalLogger.debug(u"'closePrefsConfigUi' called with userCancelled = %s" % (str(userCancelled)))  

        if userCancelled == True:
            return

        if self.globals['update']['check']:
            if self.globals['update']['checkFrequency'] == 'WEEKLY':
                self.globals['update']['checkTimeIncrement'] = (7 * 24 * 60 * 60)  # In seconds
            else:
                # DAILY 
                self.globals['update']['checkTimeIncrement'] = (24 * 60 * 60)  # In seconds


        # Check monitoring / debug / filered IP address options  
        self.setDebuggingLevels(valuesDict)

        # Following logic checks whether polling is required.
        # If it isn't required, then it checks if a polling thread exists and if it does it ends it
        # If it is required, then it checks if a pollling thread exists and 
        #   if a polling thread doesn't exist it will create one as long as the start logic has completed and created a nanoleaf Command Queue.
        #   In the case where a nanoleaf command queue hasn't been created then it means 'Start' is yet to run and so 
        #   'Start' will create the polling thread. So this bit of logic is mainly used where polling has been turned off
        #   after starting and then turned on again
        # If polling is required and a polling thread exists, then the logic 'sets' an event to cause the polling thread to awaken and
        #   update the polling interval

        if self.globals['polling']['status'] == False:
            if self.globals['polling']['threadActive'] == True:
                self.globals['polling']['forceThreadEnd'] = True
                self.globals['threads']['polling']['event'].set()  # Stop the Polling Thread
                self.globals['threads']['polling']['thread'].join(5.0)  # Wait for up t0 5 seconds for it to end
                del self.globals['threads']['polling']['thread']  # Delete thread so that it can be recreated if polling is turned on again
        else:
            if self.globals['polling']['threadActive'] == False:
                if self.globals['queues']['initialised'] == True:
                    self.globals['polling']['forceThreadEnd'] = False
                    self.globals['threads']['polling']['event'] = threading.Event()
                    self.globals['threads']['polling']['thread'] = ThreadPolling([self.globals, self.globals['threads']['polling']['event']])
                    self.globals['threads']['polling']['thread'].start()
            else:
                self.globals['polling']['forceThreadEnd'] = False
                self.globals['threads']['polling']['event'].set()  # cause the Polling Thread to update immediately with potentially new polling seconds value


    def setDebuggingLevels(self, valuesDict):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        # set filered IP address

        self.globals['debug']['debugFilteredIpAddressesUI'] = ''
        if valuesDict.get("debugFilteredIpAddresses", '') != '':
            self.globals['debug']['debugFilteredIpAddresses'] = valuesDict.get("debugFilteredIpAddresses", '').replace(' ', '').split(',')  # Create List of IP Addresses to filter on

        if self.globals['debug']['debugFilteredIpAddresses']:  # Evaluates to True if list contains entries
            for ipAddress in self.globals['debug']['debugFilteredIpAddresses']:
                if self.globals['debug']['debugFilteredIpAddressesUI'] == '':
                    self.globals['debug']['debugFilteredIpAddressesUI'] += ipAddress
                else:
                    self.globals['debug']['debugFilteredIpAddressesUI'] += ', ' + ipAddress
                    
            if len(self.globals['debug']['debugFilteredIpAddresses']) == 1:    
                self.generalLogger.warning(u"Filtering on nanoleaf Device with IP Address: %s" % (self.globals['debug']['debugFilteredIpAddressesUI']))
            else:  
                self.generalLogger.warning(u"Filtering on nanoleaf Devices with IP Addresses: %s" % (self.globals['debug']['debugFilteredIpAddressesUI']))  

        self.globals['debug']['monitorDebugEnabled'] = bool(valuesDict.get("monitorDebugEnabled", False))

        self.globals['debug']['debugGeneral']       = logging.INFO  # For general debugging of the main thread
        self.globals['debug']['monitorSendReceive'] = logging.INFO  # For logging messages sent & Received to/from nanoleaf devices
        self.globals['debug']['debugSendReceive']   = logging.INFO  # For debugging messages sent & Received to/from nanoleaf devices
        self.globals['debug']['monitorDiscovery']   = logging.INFO  # For logging discovery of nanoleaf devices
        self.globals['debug']['debugDiscovery']     = logging.INFO  # For debugging discovery of nanoleaf devices
        self.globals['debug']['debugMethodTrace']   = logging.INFO  # For displaying method invocations i.e. trace method
        self.globals['debug']['debugPolling']       = logging.INFO  # For polling debugging

        if self.globals['debug']['monitorDebugEnabled'] == False:
            self.plugin_file_handler.setLevel(logging.INFO)
        else:
            self.plugin_file_handler.setLevel(logging.THREADDEBUG)

        debugGeneral           = bool(valuesDict.get("debugGeneral", False))
        monitorSendReceive     = bool(valuesDict.get("monitorSendReceive", False))
        debugSendReceive       = bool(valuesDict.get("debugSendReceive", False))
        monitorDiscovery       = bool(valuesDict.get("monitorDiscovery", False))
        debugDiscovery         = bool(valuesDict.get("debugDiscovery", False))
        debugMethodTrace       = bool(valuesDict.get("debugMethodTrace", False))
        debugPolling           = bool(valuesDict.get("debugPolling", False))

        if debugGeneral:
            self.globals['debug']['debugGeneral'] = logging.DEBUG  # For general debugging of the main thread
            self.generalLogger.setLevel(self.globals['debug']['debugGeneral'])
        if monitorSendReceive:
            self.globals['debug']['monitorSendReceive'] = logging.DEBUG  # For logging messages sent to nanoleaf devices 
        if debugSendReceive:
            self.globals['debug']['debugSendReceive'] = logging.DEBUG  # For debugging messages sent to nanoleaf devices
        if monitorDiscovery:
            self.globals['debug']['monitorDiscovery'] = logging.DEBUG  # For logging messages sent to nanoleaf devices 
        if debugDiscovery:
            self.globals['debug']['debugDiscovery'] = logging.DEBUG  # For debugging messages sent to nanoleaf devices
        if debugMethodTrace:
            self.globals['debug']['debugMethodTrace'] = logging.THREADDEBUG  # For displaying method invocations i.e. trace method
        if debugPolling:
            self.globals['debug']['debugPolling'] = logging.DEBUG  # For polling debugging

        self.globals['debug']['monitoringActive'] = monitorSendReceive

        self.globals['debug']['debugActive'] = debugGeneral or debugSendReceive or debugDiscovery or debugMethodTrace or debugPolling

        if not self.globals['debug']['monitorDebugEnabled'] or (not self.globals['debug']['monitoringActive'] and not self.globals['debug']['debugActive']):
            self.generalLogger.info(u"No monitoring or debugging requested")
        else:
            if not self.globals['debug']['monitoringActive']:
                self.generalLogger.info(u"No monitoring requested")
            else:
                monitorTypes = []
                if monitorSendReceive:
                    monitorTypes.append('Send & Receive')
                if monitorDiscovery:
                    monitorTypes.append('Discovery')
                message = self.listActive(monitorTypes)   
                self.generalLogger.warning(u"Monitoring enabled for nanoleaf device: %s" % (message))  

            if not self.globals['debug']['debugActive']:
                self.generalLogger.info(u"No debugging requested")
            else:
                debugTypes = []
                if debugGeneral:
                    debugTypes.append('General')
                if debugSendReceive:
                    debugTypes.append('Send & Receive')
                if debugDiscovery:
                    debugTypes.append('Discovery')
                if debugMethodTrace:
                    debugTypes.append('Method Trace')
                if debugPolling:
                    debugTypes.append('Polling')
                message = self.listActive(debugTypes)   
                self.generalLogger.warning(u"Debugging enabled for nanoleaf device: %s" % (message))  

    def listActive(self, monitorDebugTypes):            
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        loop = 0
        listedTypes = ''
        for monitorDebugType in monitorDebugTypes:
            if loop == 0:
                listedTypes = listedTypes + monitorDebugType
            else:
                listedTypes = listedTypes + ', ' + monitorDebugType
            loop += 1
        return listedTypes

    def runConcurrentThread(self):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        # This thread is used to detect plugin close down and check for updates
        try:
            while not self.globals['startupCompleted']:
                self.sleep(10)  # Allow startup to complete

            while True:
                if self.globals['update']['check']:
                    if time.time() > self.globals['update']['nextCheckTime']:
                        if not 'checkTimeIncrement' in self.globals['update']:
                            self.globals['update']['checkTimeIncrement'] = (24 * 60 * 60)  # One Day In seconds
                        self.globals['update']['nextCheckTime'] = time.time() + self.globals['update']['checkTimeIncrement']
                        self.generalLogger.info(u"%s checking for Plugin update" % PLUGIN_TITLE)
                        self.globals['update']['updater'].checkForUpdate()

                        nextCheckTime = time.strftime('%A, %Y-%b-%d at %H:%M', time.localtime(self.globals['update']['nextCheckTime']))
                        self.generalLogger.info(u"%s next update check scheduled for: %s" % (PLUGIN_TITLE, nextCheckTime))
                self.sleep(300) # 5 minutes in seconds

        except self.StopThread:
            self.generalLogger.info(u"%s Plugin shutdown requested" % PLUGIN_TITLE)

            self.generalLogger.debug(u"runConcurrentThread being ended . . .") 

            if 'sendReceiveMessages' in self.globals['threads']:
                self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STOP_THREAD, 'STOPTHREAD', []])

            if 'discovery' in self.globals['threads']:
                self.globals['queues']['discovery'].put([QUEUE_PRIORITY_STOP_THREAD, 'STOPTHREAD', []])

            if self.globals['polling']['threadActive'] == True:
                self.globals['polling']['forceThreadEnd'] = True
                self.globals['threads']['polling']['event'].set()  # Stop the Polling Thread
                self.globals['threads']['polling']['thread'].join(7.0)  # wait for thread to end
                self.generalLogger.debug(u"Polling thread now stopped")

            if 'sendReceiveMessages' in self.globals['threads']:
                self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STOP_THREAD, 'STOPTHREAD', []])
                self.globals['threads']['sendReceiveMessages'].join(7.0)  # wait for thread to end
                self.generalLogger.debug(u"SendReceive thread now stopped")

            if 'discovery' in self.globals['threads']:
                self.globals['queues']['discovery'].put([QUEUE_PRIORITY_STOP_THREAD, 'STOPTHREAD', []])
                self.globals['threads']['discovery'].join(7.0)  # wait for thread to end
                self.generalLogger.debug(u"Discovery thread now stopped")

        self.generalLogger.debug(u". . . runConcurrentThread now ended")   

    def deviceStartComm(self, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try:
            self.generalLogger.info(u"Starting  '%s' . . . " % (dev.name))

            if dev.deviceTypeId != "nanoleafDevice":
                self.generalLogger.error(u"Failed to start device [%s]: Device type [%s] not known by plugin." % (dev.name, dev.deviceTypeId))
                return

            dev.stateListOrDisplayStateIdChanged()  # Ensure latest devices.xml is being used

            propsRequiresUpdate = False
            props = dev.pluginProps

            if not "onBrightensToLast" in props:
                props["onBrightensToLast"] = True
                propsRequiresUpdate = True
            elif props["onBrightensToLast"] != True: 
                props["onBrightensToLast"] = True
                propsRequiresUpdate = True

            if not "SupportsColor" in props:
                props["SupportsColor"] = True
                propsRequiresUpdate = True
            elif props["SupportsColor"] != True: 
                props["SupportsColor"] = True
                propsRequiresUpdate = True

            if not "SupportsRGB" in props:
                props["SupportsRGB"] = True
                propsRequiresUpdate = True
            elif props["SupportsRGB"] != True: 
                props["SupportsRGB"] = True
                propsRequiresUpdate = True

            if not "SupportsWhite" in props:
                props["SupportsWhite"] = True
                propsRequiresUpdate = True
            elif props["SupportsWhite"] != True: 
                props["SupportsWhite"] = True
                propsRequiresUpdate = True

            if not "SupportsTwoWhiteLevels" in props:
                props["SupportsTwoWhiteLevels"] = False
                propsRequiresUpdate = True
            elif props["SupportsTwoWhiteLevels"] != False: 
                props["SupportsTwoWhiteLevels"] = False
                propsRequiresUpdate = True

            if not "SupportsWhiteTemperature" in props:
                props["SupportsWhiteTemperature"] = True
                propsRequiresUpdate = True
            elif props["SupportsWhiteTemperature"] != True: 
                props["SupportsWhiteTemperature"] = True
                propsRequiresUpdate = True

            # if not "WhiteTemperatureMin" in props:
            #     props["WhiteTemperatureMin"] = 1200
            #     propsRequiresUpdate = True
            # elif props["WhiteTemperatureMin"] != 1200: 
            #     props["WhiteTemperatureMin"] = 1200
            #     propsRequiresUpdate = True

            # if not "WhiteTemperatureMax" in props:
            #     props["WhiteTemperatureMax"] = 6500
            #     propsRequiresUpdate = True
            # elif props["WhiteTemperatureMax"] != 6500: 
            #     props["WhiteTemperatureMax"] = 6500
            #     propsRequiresUpdate = True

            if propsRequiresUpdate:
                dev.replacePluginPropsOnServer(props)
                return

            # Initialise internal to plugin nanoleaf device states to default values
            if dev.id not in self.globals['nl']:
                self.globals['nl'][dev.id] = {}
            self.globals['nl'][dev.id]['started']                 = False
            self.globals['nl'][dev.id]['datetimeStarted']         = indigo.server.getTime()
            self.globals['nl'][dev.id]['initialisedFromdevice']   = False
            self.globals['nl'][dev.id]['nlDeviceid']              = dev.address  # eg. 'd0:73:d5:0a:bc:de' (psuedo mac address)
            self.globals['nl'][dev.id]['authToken']               = str(dev.pluginProps.get('authToken', ''))
            self.globals['nl'][dev.id]['nanoleafObject']          = None
            self.globals['nl'][dev.id]['ipAddress']               = str(dev.pluginProps.get('ipAddress', ''))
            self.globals['nl'][dev.id]['lastResponseToPollCount'] = 0 
            self.globals['nl'][dev.id]['effectsList']             = []
            dev.setErrorStateOnServer(u"no ack")  # Default to 'no ack' status i.e. communication still to be established

            # Check if ip address debug filter(s) active
            if (len(self.globals['debug']['debugFilteredIpAddresses']) > 0) and (dev.states['ipAddress'] not in self.globals['debug']['debugFilteredIpAddresses']):
                self.generalLogger.info(u"Start NOT performed for  '%s' as nanoleaf device with ip address '%s' not included in start filter" % (dev.name, dev.states['ipAddress']))
                return

            self.globals['nl'][dev.id]['onState']     = False      # True or False
            self.globals['nl'][dev.id]['onOffState']  = 'off'      # 'on' or 'off'
            #self.globals['nl'][dev.id]['turnOnIfOff'] = bool(dev.pluginProps.get('turnOnIfOff', True))

            if self.globals['nl'][dev.id]['authToken'] == '':
                self.generalLogger.error(u"Unable to start '%s' as device not authorised. Edit Device settings and follow instructions on how to authorise device." % (dev.name))
            else:
                self.globals['nl'][dev.id]["started"] = True
                self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_MEDIUM, 'STATUS', [dev.id]])
                self.generalLogger.info(u". . . Started '%s' " % (dev.name))

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.generalLogger.error(u"deviceStartComm: StandardError detected for '%s' at line '%s' = %s" % (dev.name, exc_tb.tb_lineno,  e))   


    def deviceStopComm(self, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.generalLogger.info(u"Stopping '%s'" % (dev.name))

        dev.setErrorStateOnServer(u"no ack")  # Default to 'no ack' status

        if dev.id in self.globals['nl']:
            self.globals['nl'][dev.id]["started"] = False


    def deviceDeleted(self, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        nlDeviceid = ''
        nlIpAddress = ''

        if dev.deviceTypeId == "nanoleafDevice": 
            self.deviceStopComm(dev)
            if dev.id in self.globals['nl']:
                nlDeviceid = self.globals['nl'][dev.id]['nlDeviceid']
                nlIpAddress = self.globals['nl'][dev.id]['ipAddress']
                del self.globals['nl'][dev.id]  # Delete internal storage for device

        if nlDeviceid != '' and nlIpAddress != '':
            # Make device available for adding as a new device
            self.globals['discovery']['discoveredUnmatchedDevices'][nlDeviceid] = nlIpAddress            

    def getDeviceConfigUiValues(self, pluginProps, typeId, devId):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try:
            self.generalLogger.debug(u"getDeviceConfigUiValues: typeId [%s], actionId [%s], pluginProps[%s]" % (typeId, devId, pluginProps))

            nanoleafDev = indigo.devices[devId]

            errorDict = indigo.Dict()
            valuesDict = pluginProps

            valuesDict['nanoleafAvailable'] = 'true'
            valuesDict['nanoleafDevice'] = 'SELECT_AVAILABLE'
            valuesDict['ipAddress'] = nanoleafDev.pluginProps.get('ipAddress', '')
            valuesDict['authToken'] = nanoleafDev.pluginProps.get('authToken', '')
            
            return (valuesDict, errorDict)

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.generalLogger.error(u"getDeviceConfigUiValues: StandardError detected for '%s' at line '%s' = %s" % (dev.name, exc_tb.tb_lineno,  e))   

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.currentTime = indigo.server.getTime()




        nanoleafDev = indigo.devices[devId]

        keyValueList = [
            {'key': 'ipAddress', 'value': valuesDict['ipAddress']},
            {'key': 'authToken', 'value': valuesDict['authToken']}
        ]
        nanoleafDev.updateStatesOnServer(keyValueList)
     
        props = nanoleafDev.pluginProps
        props["address"]   = valuesDict['address']
        props["ipAddress"] = valuesDict['ipAddress']
        props["authToken"] = valuesDict['authToken']
        nanoleafDev.replacePluginPropsOnServer(props)

        return (True, valuesDict)

    def getActionConfigUiValues(self, pluginProps, typeId, devId):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.generalLogger.debug(u"getActionConfigUiValues: typeId [%s], devId [%s], pluginProps[%s]" % (typeId, devId, pluginProps))

        errorDict = indigo.Dict()
        valuesDict = pluginProps

        if typeId == "setEffect":
            if ('effectList' not in valuesDict) or (valuesDict["effectList"] == '') or (len(self.globals['nl'][devId]['effectsList']) == 0):
                valuesDict["effectList"] = 'SELECT_EFFECT'
        return (valuesDict, errorDict)


    def validateActionConfigUi(self, valuesDict, typeId, actionId):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        errorsDict = indigo.Dict()

        if typeId == "setEffect":
            validateResult = self.validateActionConfigUiSetEffect(valuesDict, typeId, actionId)
        else:
            self.generalLogger.debug(u"validateActionConfigUi [UNKNOWN]: typeId=[%s], actionId=[%s]" % (typeId, actionId))
            return (True, valuesDict)

        if validateResult[0] == True:
            return (True, validateResult[1])
        else:
            return (False, validateResult[1], validateResult[2])

 
    def validateActionConfigUiSetEffect(self, valuesDict, typeId, actionId):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.generalLogger.debug(u"validateActionConfigUiSpecific: typeId=[%s], actionId=[%s]" % (typeId, actionId))

        if valuesDict['effectList'] == 'SELECT_EFFECT':
            errorDict = indigo.Dict()
            errorDict["effectList"] = "No Effect selected"
            errorDict["showAlertText"] = "You must select an effect for the action to send to the nanoleaf device"
            return (False, valuesDict, errorDict)

        return (True, valuesDict)


    def openedActionConfigUi(self, valuesDict, typeId, actionId):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.generalLogger.debug(u"openedActionConfigUi intercepted")

        return valuesDict

    def getMenuActionConfigUiValues(self, menuId):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        valuesDict = indigo.Dict()
        errorMsgDict = indigo.Dict() 

        self.generalLogger.debug(u"QWERTY QWERTY = %s" % (menuId))

        # if menuId == "yourMenuItemId":
        #  valuesDict["someFieldId"] = someDefaultValue
        return (valuesDict, errorMsgDict)


    def actionControlUniversal(self, action, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        ###### STATUS REQUEST ######
        if action.deviceAction == indigo.kUniversalAction.RequestStatus:
            self._processStatus(action, dev)


    def _processStatus(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_STATUS_MEDIUM, 'STATUS', [dev.id]])
        self.generalLogger.info(u"sent \"%s\" %s" % (dev.name, "status request"))


    def actionControlDevice(self, action, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
        if dev.states['connected'] == False or self.globals['nl'][dev.id]['started'] == False:
            self.generalLogger.info(u"Unable to process  \"%s\" for \"%s\" as device not connected" % (action.deviceAction, dev.name))
            return

        ###### TURN ON ######
        if action.deviceAction ==indigo.kDeviceAction.TurnOn:
            self._processTurnOn(action, dev)

        ###### TURN OFF ######
        elif action.deviceAction ==indigo.kDeviceAction.TurnOff:
            self._processTurnOff(action, dev)

        ###### TOGGLE ######
        elif action.deviceAction ==indigo.kDeviceAction.Toggle:
            self._processTurnOnOffToggle(action, dev)

        ###### SET BRIGHTNESS ######
        elif action.deviceAction ==indigo.kDeviceAction.SetBrightness:
            newBrightness = action.actionValue  #  action.actionValue contains brightness value (0 - 100)
            self._processBrightnessSet(action, dev, newBrightness)

        ###### BRIGHTEN BY ######
        elif action.deviceAction ==indigo.kDeviceAction.BrightenBy:
            if not dev.onState:
                self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_COMMAND, 'IMMEDIATE-ON', [dev.id]])

            if dev.brightness < 100:
                brightenBy = action.actionValue #  action.actionValue contains brightness increase value
                newBrightness = dev.brightness + brightenBy
                if newBrightness > 100:
                    newBrightness = 100
                    brightenBy = 100 - dev.brightness
                self.generalLogger.info(u"Brightening %s by %s to %s" % (dev.name, brightenBy, newBrightness))
                self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_COMMAND, 'BRIGHTEN', [dev.id, brightenBy]])
            else:
                self.generalLogger.info(u"Ignoring Brighten request for %s as device is at full brightness" % (dev.name))

        ###### DIM BY ######
        elif action.deviceAction ==indigo.kDeviceAction.DimBy:
            if dev.onState and dev.brightness > 0: 
                dimBy = action.actionValue #  action.actionValue contains brightness decrease value
                newBrightness = dev.brightness - dimBy
                if newBrightness < 0:
                    newBrightness = 0
                    dimBy = dev.brightness
                self.generalLogger.info(u"Dimming %s by %s to %s" % (dev.name, dimBy, newBrightness))
                self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_COMMAND, 'DIM', [dev.id, dimBy]])
            else:
                self.generalLogger.info(u"Ignoring Dim request for %s as device is Off" % (dev.name))

        ###### SET COLOR LEVELS ######
        elif action.deviceAction ==indigo.kDeviceAction.SetColorLevels:
            self.generalLogger.debug(u"SET COLOR LEVELS = \"%s\" %s" % (dev.name, action))
            self._processSetColorLevels(action, dev)

    def _processTurnOn(self, pluginAction, dev, actionUi='on'):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.generalLogger.debug(u"nanoleaf 'processTurnOn' [%s]" % (self.globals['nl'][dev.id]['ipAddress'])) 

        self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_COMMAND, 'ON', [dev.id]])

        self.generalLogger.info(u"sent \"%s\" %s" % (dev.name, actionUi))

    def _processTurnOff(self, pluginAction, dev, actionUi='off'):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.generalLogger.debug(u"nanoleaf 'processTurnOff' [%s]" % (self.globals['nl'][dev.id]['ipAddress'])) 

        self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_COMMAND, 'OFF', [dev.id]])

        self.generalLogger.info(u"sent \"%s\" %s" % (dev.name, actionUi))

    def _processTurnOnOffToggle(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.generalLogger.debug(u"nanoleaf 'processTurnOnOffToggle' [%s]" % (self.globals['nl'][dev.id]['ipAddress'])) 

        onStateRequested = not dev.onState
        if onStateRequested == True:
            actionUi = "toggle from 'off' to 'on'"
            self._processTurnOn(pluginAction, dev, actionUi)
        else:
            actionUi = "toggle from 'on' to 'off'"
            self._processTurnOff(pluginAction, dev, actionUi)

    def _processBrightnessSet(self, pluginAction, dev, newBrightness):  # Dev is a nanoleaf device
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        if newBrightness > 0:
            if newBrightness > dev.brightness:
                actionUi = 'brighten'
            else:
                actionUi = 'dim'  
            self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_COMMAND, 'BRIGHTNESS', [dev.id, newBrightness]])
            self.generalLogger.info(u"sent \"%s\" %s to %s" % (dev.name, actionUi, newBrightness))
        else:
            self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_COMMAND, 'OFF', [dev.id]])
            self.generalLogger.info(u"sent \"%s\" %s" % (dev.name, 'dim to off'))


    def _processSetColorLevels(self, action, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        try:
            self.generalLogger.debug(u'processSetColorLevels ACTION:\n%s ' % action)

            # Determine Color / White Mode
            colorMode = False

            # First check if color is being set by the action Set RGBW levels
            if 'redLevel' in action.actionValue and 'greenLevel' in action.actionValue and 'blueLevel' in action.actionValue:
                if float(action.actionValue['redLevel']) > 0.0 or float(action.actionValue['greenLevel']) > 0.0 or float(action.actionValue['blueLevel']) > 0.0:
                    colorMode = True

            if (not colorMode) and (('whiteLevel' in action.actionValue) or ('whiteTemperature' in action.actionValue)):
                # If either of 'whiteLevel' or 'whiteTemperature' are altered - assume mode is White
                whiteLevel = float(dev.states['whiteLevel'])
                whiteTemperature =  int(dev.states['whiteTemperature'])

                if 'whiteLevel' in action.actionValue:
                    whiteLevel = float(action.actionValue['whiteLevel'])
                    
                if 'whiteTemperature' in action.actionValue:
                    whiteTemperature = int(action.actionValue['whiteTemperature'])
                    if whiteTemperature < 1200:
                        whiteTemperature = 1200
                    elif whiteTemperature > 6500:
                        whiteTemperature = 6500

                self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_COMMAND, 'WHITE', [dev.id, whiteLevel, whiteTemperature]])

                self.generalLogger.info(u"sent \"%s\" set White Level to \"%s\" and White Temperature to \"%s\"" % (dev.name, int(whiteLevel), whiteTemperature))

            else:
                # As neither of 'whiteTemperature' or 'whiteTemperature' are set - assume mode is Colour

                props = dev.pluginProps
                if ("SupportsRGB" in props) and props["SupportsRGB"]:  # Check device supports color
                    redLevel = float(dev.states['redLevel'])
                    greenLevel = float(dev.states['greenLevel'])
                    blueLevel = float(dev.states['blueLevel'])
 
                    if 'redLevel' in action.actionValue:
                        redLevel = float(action.actionValue['redLevel'])
                    if 'greenLevel' in action.actionValue:
                        greenLevel = float(action.actionValue['greenLevel'])         
                    if 'blueLevel' in action.actionValue:
                        blueLevel = float(action.actionValue['blueLevel'])

                    self.generalLogger.debug(u"Color: \"%s\" R, G, B: %s, %s, %s" % (dev.name, redLevel, greenLevel, blueLevel))

                    self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_COMMAND, 'COLOR', [dev.id, redLevel, greenLevel, blueLevel]])

                    self.generalLogger.info(u"sent \"%s\" set Color Level to red \"%s\", green \"%s\" and blue \"%s\"" % (dev.name, int(round(redLevel)), int(round(greenLevel)), int(round(blueLevel))))
                else:
                    self.generalLogger.info(u"Failed to send \"%s\" set Color Level as device does not support color." % (dev.name))


        except StandardError, e:
            self.generalLogger.error(u"StandardError detected during processSetColorLevels. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))


    def processDiscoverDevices(self, pluginAction):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
            
        self.globals['queues']['discovery'].put([QUEUE_PRIORITY_LOW, 'DISCOVERY', []])

    def processSetEffect(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        if dev.states['connected'] == False or self.globals['nl'][dev.id]['started'] == False:
            self.generalLogger.info(u"Unable to process  \"%s\" for \"%s\" as device not connected" % (action.deviceAction, dev.name))
            return

        effect = pluginAction.props.get('effectList')

        if effect in self.globals['nl'][dev.id]['effectsList']:
            self.generalLogger.info(u"sent \"%s\" Set Effect to %s" % (dev.name, effect))
            self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_LOW, 'SETEFFECT', [dev.id, effect]])
        else:
            self.generalLogger.info("Effect '%s' not available on nanoleaf device '%s'" % (effect, dev.name)) 

    def authoriseNanoleaf(self, valuesDict, typeId, devId):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.generalLogger.debug(u"actionConfigPresetUpdateButtonPressed: typeId[%s], devId[%s], valuesDict = %s" % (typeId, devId, valuesDict))

        ipAddress = valuesDict['ipAddress']

        rc, statusMessage, authToken = generate_auth_token(ipAddress)

        if rc:
            valuesDict['authToken'] = authToken
            self.generalLogger.debug(u"generate_auth_token: rc[%s], statusMessage[%s], authToken = %s" % (rc, statusMessage, authToken))
        else:
            self.generalLogger.error(u"%s" % statusMessage)

            errorDict = indigo.Dict()
            errorDict["authorise"] = "Access Forbidden to nanoleaf device!"
            errorDict["showAlertText"] = "Access Forbidden to nanoleaf device! Press and hold the power button for 5-7 seconds first! (Light will begin flashing)"
            return (valuesDict, errorDict)

        return valuesDict


    def nanoleafAvailableDeviceSelected(self, valuesDict, typeId, devId):

        try:
            self.generalLogger.debug(u"nanoleafAvailableDeviceSelected: typeId[%s], devId[%s], valuesDict = %s" % (typeId, devId, valuesDict))

            if valuesDict['nanoleafDevice'] != 'SELECT_AVAILABLE':
                address, ipAddress = valuesDict['nanoleafDevice'].split('-')
                valuesDict['address'] = address
                valuesDict['ipAddress'] = ipAddress

            return valuesDict

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.generalLogger.error(u"nanoleafAvailableDeviceSelected: StandardError detected for '%s' at line '%s' = %s" % (dev.name, exc_tb.tb_lineno,  e))   


    def _buildAvailableDevicesList(self, filter="", valuesDict=None, typeId="", targetId=0):
        self.methodTracer.debug(u"CLASS: Plugin")

        try:
            available_dict = []
            available_dict.append(("SELECT_AVAILABLE", "- Select nanoleaf device -"))

            for nlDeviceid, nlIpAddress in self.globals['discovery']['discoveredUnmatchedDevices'].iteritems():  # self.globals['discovery']['discoveredDevices']
                nanoleaf_available = (str('%s-%s' % (nlDeviceid, nlIpAddress)), str(nlIpAddress))
                available_dict.append(nanoleaf_available)
            if len(available_dict) == 1:
                available_dict = []
                available_dict.append(("SELECT_AVAILABLE", "- No available nanoleaf devices discovered -"))

            myArray = available_dict
            return myArray

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.generalLogger.error(u"_buildAvailableDevicesList: StandardError detected for '%s' at line '%s' = %s" % (dev.name, exc_tb.tb_lineno,  e))   



    def _buildAvailableEffectsList(self, filter="", valuesDict=None, typeId="", targetId=0):
        self.methodTracer.debug(u"CLASS: Plugin")

        self.generalLogger.debug("_buildAvailableEffectsList: TARGET ID = %s" % targetId)
        try:
            nanoleafDevId = targetId

            effect_dict = []
            effect_dict.append(("SELECT_EFFECT", "- Select nanoleaf effect -"))

            for effect in self.globals['nl'][nanoleafDevId]['effectsList']:
                nanoleaf_effect = (effect, effect)
                effect_dict.append(nanoleaf_effect)
            if len(effect_dict) == 1:
                effect_dict = []
                effect_dict.append(("SELECT_EFFECT", "- No available nanoleaf effects discovered -"))

            myArray = effect_dict
            return myArray

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.generalLogger.error(u"_buildAvailableEffectsList: StandardError detected for '%s' at line '%s' = %s" % (indigo.devices[nanoleafDevId].name, exc_tb.tb_lineno,  e))   
