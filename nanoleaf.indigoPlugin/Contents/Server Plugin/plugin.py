#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# nanoleaf Controller © Autolog 2017-2022
#

try:
    import indigo
except:
    pass
import logging
import platform

import queue
import sys
import threading
import traceback

from constants import *
from nanoleafapi.nanoleaf import *
from nanoleafapi.discover_nanoleaf import *
from polling import ThreadPolling
from sendReceiveMessages import ThreadSendReceiveMessages
from discovery import ThreadDiscovery


class Plugin(indigo.PluginBase):

    def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs):
        indigo.PluginBase.__init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs)

        # Initialise dictionary to store plugin Globals
        self.globals = dict()

        # Initialise Indigo plugin info
        self.globals[PLUGIN_INFO] = dict()
        self.globals[PLUGIN_INFO][PLUGIN_ID] = plugin_id
        self.globals[PLUGIN_INFO][PLUGIN_DISPLAY_NAME] = plugin_display_name
        self.globals[PLUGIN_INFO][PLUGIN_VERSION] = plugin_version
        self.globals[PLUGIN_INFO][PATH] = indigo.server.getInstallFolderPath()
        self.globals[PLUGIN_INFO][API_VERSION] = indigo.server.apiVersion
        self.globals[PLUGIN_INFO][INDIGO_SERVER_ADDRESS] = indigo.server.address

        self.globals[OVERRIDDEN_HOST_IP_ADDRESS] = ''  # If needed, set in Plugin config

        # Used to prevent runConcurrentThread from running until startup is complete
        self.globals[STARTUP_COMPLETED] = False

        log_format = logging.Formatter("%(asctime)s.%(msecs)03d\t%(levelname)-12s\t%(name)s.%(funcName)-25s %(msg)s", datefmt="%Y-%m-%d %H:%M:%S")
        self.plugin_file_handler.setFormatter(log_format)
        self.plugin_file_handler.setLevel(LOG_LEVEL_INFO)  # Logging Level for plugin log file
        self.indigo_log_handler.setLevel(LOG_LEVEL_INFO)   # Logging level for Indigo Event Log

        self.logger = logging.getLogger("Plugin.Hubitat")

        # Now logging is set-up, output Initialising message

        # startup_message_ui = "\n"  # Start with a line break
        # startup_message_ui += f"{' Initialising Nanoleaf Controller Plugin ':={'^'}130}\n"
        # startup_message_ui += f"{'Plugin Name:':<31} {self.globals[PLUGIN_INFO][PLUGIN_DISPLAY_NAME]}\n"
        # startup_message_ui += f"{'Plugin Version:':<31} {self.globals[PLUGIN_INFO][PLUGIN_VERSION]}\n"
        # startup_message_ui += f"{'Plugin ID:':<31} {self.globals[PLUGIN_INFO][PLUGIN_ID]}\n"
        # startup_message_ui += f"{'Indigo Version:':<31} {indigo.server.version}\n"
        # startup_message_ui += f"{'Indigo License:':<31} {indigo.server.licenseStatus}\n"
        # startup_message_ui += f"{'Indigo API Version:':<31} {indigo.server.apiVersion}\n"
        # machine = platform.machine()
        # startup_message_ui += f"{'Architecture:':<31} {machine}\n"
        # sys_version = sys.version.replace("\n", "")
        # startup_message_ui += f"{'Python Version:':<31} {sys_version}\n"
        # startup_message_ui += f"{'Mac OS Version:':<31} {platform.mac_ver()[0]}\n"
        # startup_message_ui += f"{'':={'^'}130}\n"
        # self.logger.info(startup_message_ui)

        # Initialise dictionary to store internal details about nanoleaf devices
        self.globals[NL]= dict()

        self.globals[THREADS]= dict()
        self.globals[THREADS][SEND_RECEIVE_MESSAGES]= dict()
        self.globals[THREADS][POLLING]= dict()

        # Initialise discovery dictionary to store discovered devices, discovery period
        self.globals[DISCOVERY]= dict()
        self.globals[DISCOVERY][DISCOVERED_DEVICES] = dict()  # dict of nanoleaf device ids (psuedo mac) and tuple of (IP Address and MAC Address)
        self.globals[DISCOVERY][DISCOVERED_UNMATCHED_DEVICES] = dict()  # dict of unmatched (no Indigo device) nanoleaf device ids (psuedo mac) and tuple of (IP Address and MAC Address)
        self.globals[DISCOVERY][PERIOD] = 30  # period of each active discovery
        self.globals[DISCOVERY][COUNT] = 0  # count of number of discoveries performed

        # Initialise dictionary to store message queues
        self.globals[QUEUES] = dict()
        self.globals[QUEUES][MESSAGE_TO_SEND] = ''  # Set-up in plugin start (used to process commands to be sent to the nanoleaf device)
        self.globals[QUEUES][DISCOVERY] = ''  # Set-up in plugin start (used to process command to invoke nanoleaf device discovery)
        self.globals[QUEUES][RETURNED_RESPONSE] = ''  # Set-up in plugin start (a common returned response queue)
        self.globals[QUEUES][INITIALISED] = False

        # Initialise dictionary for polling thread
        self.globals[POLLING]= dict()
        self.globals[POLLING][THREAD_ACTIVE] = False        
        self.globals[POLLING][STATUS] = False
        self.globals[POLLING][SECONDS] = float(300.0)  # 5 minutes
        self.globals[POLLING][FORCE_THREAD_END] = False
        self.globals[POLLING][QUIESCED] = False
        self.globals[POLLING][MISSED_POLL_LIMIT] = int(2)  # Default to 2 missed polls
        self.globals[POLLING][COUNT] = int(0)
        self.globals[POLLING][TRIGGER] = int(0)

        self.globals[DEBUG_FILTERED_IP_ADDRESSES] = dict()

        self.validatePrefsConfigUi(plugin_prefs)  # Validate the Plugin Config before plugin initialisation
        
        self.closedPrefsConfigUi(plugin_prefs, False)  # Set Plugin config options (as if the dialogue had been closed)

    def __del__(self):

        indigo.PluginBase.__del__(self)

    def display_plugin_information(self):
        try:
            def plugin_information_message():
                startup_message_ui = "Plugin Information:\n"
                startup_message_ui += f"{'':={'^'}80}\n"
                startup_message_ui += f"{'Plugin Name:':<30} {self.globals[PLUGIN_INFO][PLUGIN_DISPLAY_NAME]}\n"
                startup_message_ui += f"{'Plugin Version:':<30} {self.globals[PLUGIN_INFO][PLUGIN_VERSION]}\n"
                startup_message_ui += f"{'Plugin ID:':<30} {self.globals[PLUGIN_INFO][PLUGIN_ID]}\n"
                startup_message_ui += f"{'Indigo Version:':<30} {indigo.server.version}\n"
                startup_message_ui += f"{'Indigo License:':<30} {indigo.server.licenseStatus}\n"
                startup_message_ui += f"{'Indigo API Version:':<30} {indigo.server.apiVersion}\n"
                startup_message_ui += f"{'Architecture:':<30} {platform.machine()}\n"
                startup_message_ui += f"{'Python Version:':<30} {sys.version.split(' ')[0]}\n"
                startup_message_ui += f"{'Mac OS Version:':<30} {platform.mac_ver()[0]}\n"
                startup_message_ui += f"{'Plugin Process ID:':<30} {os.getpid()}\n"
                startup_message_ui += f"{'':={'^'}80}\n"
                return startup_message_ui

            self.logger.info(plugin_information_message())

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def exception_handler(self, exception_error_message, log_failing_statement):
        filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]
        module = filename.split('/')
        log_message = f"'{exception_error_message}' in module '{module[-1]}', method '{method}'"
        if log_failing_statement:
            log_message = log_message + f"\n   Failing statement [line {line_number}]: '{statement}'"
        else:
            log_message = log_message + f" at line {line_number}"
        self.logger.error(log_message)

    def startup(self):
        indigo.devices.subscribeToChanges()

        # nanoleaf device internal storage initialisation

        for dev in indigo.devices.iter("self"):
            self.logger.debug(f'nanoleaf Indigo Device: {dev.name} [{dev.states["ipAddress"]} = {dev.address}]')
            self.globals[NL][dev.id]= dict()
            self.globals[NL][dev.id][STARTED]                  = False
            self.globals[NL][dev.id][INITIALISED_FROM_DEVICE]  = False
            self.globals[NL][dev.id][NL_DEVICE_PSEUDO_ADDRESS] = dev.address  # eg. 'd0:73:d5:0a:bc:de' (psuedo mac address)
            self.globals[NL][dev.id][AUTH_TOKEN]               = ""
            self.globals[NL][dev.id][NANOLEAF_OBJECT]          = None
            self.globals[NL][dev.id][IP_ADDRESS]               = f"{dev.pluginProps.get('ipAddress', '')}"
            self.globals[NL][dev.id][LAST_RESPONSE_TO_POLL_COUNT] = 0
            self.globals[NL][dev.id][EFFECTS_LIST]             = []
            dev.setErrorStateOnServer("no ack")  # Default to 'no ack' status i.e. communication still to be established

        # Create process queues
        self.globals[QUEUES][MESSAGE_TO_SEND] = queue.PriorityQueue()  # Used to queue commands to be sent to nanoleaf devices
        self.globals[QUEUES][DISCOVERY] = queue.PriorityQueue()  # Used to queue command for nanoleaf device discovery
        self.globals[QUEUES][INITIALISED] = True

        # define and start threads that will send messages to & receive messages from the nanoleaf devices and handle discovery
        self.globals[THREADS][SEND_RECEIVE_MESSAGES] = ThreadSendReceiveMessages([self.globals])
        self.globals[THREADS][SEND_RECEIVE_MESSAGES].start()
        self.globals[THREADS][DISCOVERY] = ThreadDiscovery([self.globals])
        self.globals[THREADS][DISCOVERY].start()

        if self.globals[POLLING][STATUS] and not self.globals[POLLING][THREAD_ACTIVE]:
            self.globals[THREADS][POLLING][EVENT]  = threading.Event()
            self.globals[THREADS][POLLING][THREAD] = ThreadPolling([self.globals, self.globals[THREADS][POLLING][EVENT]])
            self.globals[THREADS][POLLING][THREAD].start()

        self.globals[DISCOVERY][PERIOD] = float(self.pluginPrefs.get("defaultDiscoveryPeriod", 30))

        self.globals[QUEUES][DISCOVERY].put([QUEUE_PRIORITY_LOW, COMMAND_DISCOVERY, []])
 
        self.globals[STARTUP_COMPLETED] = True  # Enable runConcurrentThread to commence processing

        self.logger.info(u'{} initialization complete'.format(PLUGIN_TITLE))
        
    def shutdown(self):

        if self.globals[POLLING][THREAD_ACTIVE]:
            self.globals[POLLING][FORCE_THREAD_END] = True
            self.globals[THREADS][POLLING][EVENT].set()  # Stop the Polling Thread

        self.logger.info(u'{} Plugin shutdown complete'.format(PLUGIN_TITLE))

    def validatePrefsConfigUi(self, valuesDict):
        try:
            if 'overrideHostIpAddress' in valuesDict:
                if bool(valuesDict.get('overrideHostIpAddress', False)):
                    if valuesDict.get('overriddenHostIpAddress', '') == '':
                        errorDict = indigo.Dict()
                        errorDict["overriddenHostIpAddress"] = "Host IP Address missing"
                        errorDict["showAlertText"] = "You have elected to override the Host Ip Address but haven't specified it!"
                        return (False, valuesDict, errorDict)

            if "statusPolling" in valuesDict:
                self.globals[POLLING][STATUS] = bool(valuesDict["statusPolling"])
            else:
                self.globals[POLLING][STATUS] = False

            # No need to validate this as value can only be selected from a pull down list?
            if "pollingSeconds" in valuesDict:
                self.globals[POLLING][SECONDS] = float(valuesDict["pollingSeconds"])
            else:
                self.globals[POLLING][SECONDS] = float(300.0)  # Default to 5 minutes

            if "missedPollLimit" in valuesDict:
                try:
                    self.globals[POLLING][MISSED_POLL_LIMIT] = int(valuesDict["missedPollLimit"])
                except:
                    errorDict = indigo.Dict()
                    errorDict["missedPollLimit"] = "Invalid number for missed polls limit"
                    errorDict["showAlertText"] = "The number of missed polls limit must be specified as an integer e.g 2, 5 etc."
                    return (False, valuesDict, errorDict)
            else:
                self.globals[POLLING][MISSED_POLL_LIMIT] = int(2)  # Default to 2 missed polls

            if "defaultDiscoveryPeriod" in valuesDict:
                try:
                    self.pluginConfigDefaultDurationDimBrighten = int(valuesDict["defaultDiscoveryPeriod"])
                except:
                    errorDict = indigo.Dict()
                    errorDict["defaultDiscoveryPeriod"] = "Invalid number for seconds"
                    errorDict["showAlertText"] = "The number of seconds must be specified as an integer e.g. 10, 20 etc."
                    return (False, valuesDict, errorDict)
            else:
                self.globals[DISCOVERY][PERIOD] = float(30.0)  # Default to 30 seconds  

            return True

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def closedPrefsConfigUi(self, valuesDict, userCancelled):

        self.logger.debug(f'\'closePrefsConfigUi\' called with userCancelled = {userCancelled}')

        if userCancelled:
            return

        # Get required Event Log and Plugin Log logging levels
        plugin_log_level = int(valuesDict.get("pluginLogLevel", LOG_LEVEL_INFO))
        event_log_level = int(valuesDict.get("eventLogLevel", LOG_LEVEL_INFO))

        # Ensure following logging level messages are output
        self.indigo_log_handler.setLevel(LOG_LEVEL_INFO)
        self.plugin_file_handler.setLevel(LOG_LEVEL_INFO)

        # Output required logging levels and TP Message Monitoring requirement to logs
        self.logger.info(f"Logging to Indigo Event Log at the '{LOG_LEVEL_TRANSLATION[event_log_level]}' level")
        self.logger.info(f"Logging to Plugin Event Log at the '{LOG_LEVEL_TRANSLATION[plugin_log_level]}' level")

        # Now set required logging levels
        self.indigo_log_handler.setLevel(event_log_level)
        self.plugin_file_handler.setLevel(plugin_log_level)

        # Set Host IP Address override
        if bool(valuesDict.get('overrideHostIpAddress', False)): 
            self.globals[OVERRIDDEN_HOST_IP_ADDRESS] = valuesDict.get('overriddenHostIpAddress', '')
            if self.globals[OVERRIDDEN_HOST_IP_ADDRESS] != '':
                self.logger.info(u'Host IP Address overridden and specified as: \'{}\''.format(valuesDict.get('overriddenHostIpAddress', 'INVALID ADDRESS')))

        # Following logic checks whether polling is required.
        # If it isn't required, then it checks if a polling thread exists and if it does it ends it
        # If it is required, then it checks if a pollling thread exists and 
        #   if a polling thread doesn't exist it will create one as long as the start logic has completed and created a nanoleaf Command Queue.
        #   In the case where a nanoleaf command queue hasn't been created then it means 'Start' is yet to run and so 
        #   'Start' will create the polling thread. So this bit of logic is mainly used where polling has been turned off
        #   after starting and then turned on again
        # If polling is required and a polling thread exists, then the logic 'sets' an event to cause the polling thread to awaken and
        #   update the polling interval

        if not self.globals[POLLING][STATUS]:
            if self.globals[POLLING][THREAD_ACTIVE]:
                self.globals[POLLING][FORCE_THREAD_END] = True
                self.globals[THREADS][POLLING][EVENT].set()  # Stop the Polling Thread
                self.globals[THREADS][POLLING][THREAD].join(5.0)  # Wait for up t0 5 seconds for it to end
                del self.globals[THREADS][POLLING][THREAD]  # Delete thread so that it can be recreated if polling is turned on again
        else:
            if not self.globals[POLLING][THREAD_ACTIVE]:
                if self.globals[QUEUES][INITIALISED]:
                    self.globals[POLLING][FORCE_THREAD_END] = False
                    self.globals[THREADS][POLLING][EVENT] = threading.Event()
                    self.globals[THREADS][POLLING][THREAD] = ThreadPolling([self.globals, self.globals[THREADS][POLLING][EVENT]])
                    self.globals[THREADS][POLLING][THREAD].start()
            else:
                self.globals[POLLING][FORCE_THREAD_END] = False
                self.globals[THREADS][POLLING][EVENT].set()  # cause the Polling Thread to update immediately with potentially new polling seconds value

    def setDebuggingLevels(self, valuesDict):

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
                self.logger.warning(u'Filtering on nanoleaf Device with IP Address: {}'.format(self.globals['debug']['debugFilteredIpAddressesUI']))
            else:  
                self.logger.warning(u'Filtering on nanoleaf Devices with IP Addresses: {}'.format(self.globals['debug']['debugFilteredIpAddressesUI']))  

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
            self.logger.setLevel(self.globals['debug']['debugGeneral'])
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
            self.logger.info("No monitoring or debugging requested")
        else:
            if not self.globals['debug']['monitoringActive']:
                self.logger.info("No monitoring requested")
            else:
                monitorTypes = []
                if monitorSendReceive:
                    monitorTypes.append('Send & Receive')
                if monitorDiscovery:
                    monitorTypes.append('Discovery')
                message = self.listActive(monitorTypes)   
                self.logger.warning(u'Monitoring enabled for nanoleaf device: {}'.format(message))  

            if not self.globals['debug']['debugActive']:
                self.logger.info("No debugging requested")
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
                self.logger.warning(u'Debugging enabled for nanoleaf device: {}'.format(message))  

    def listActive(self, monitorDebugTypes):            

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

        # This thread is used to detect plugin close down and check for updates
        try:
            while not self.globals[STARTUP_COMPLETED]:
                self.sleep(10)  # Allow startup to complete

            while True:
                self.sleep(300) # 5 minutes in seconds

        except self.StopThread:
            self.logger.info(u'{} Plugin shutdown requested'.format(PLUGIN_TITLE))

            self.logger.debug("runConcurrentThread being ended . . .")

            if 'sendReceiveMessages' in self.globals[THREADS]:
                self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_STOP_THREAD, COMMAND_STOP_THREAD, []])

            if 'discovery' in self.globals[THREADS]:
                self.globals[QUEUES][DISCOVERY].put([QUEUE_PRIORITY_STOP_THREAD, COMMAND_STOP_THREAD, []])

            if self.globals[POLLING][THREAD_ACTIVE] == True:
                self.globals[POLLING][FORCE_THREAD_END] = True
                self.globals[THREADS][POLLING][EVENT].set()  # Stop the Polling Thread
                self.globals[THREADS][POLLING][THREAD].join(7.0)  # wait for thread to end
                self.logger.debug("Polling thread now stopped")

            if 'sendReceiveMessages' in self.globals[THREADS]:
                self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_STOP_THREAD, COMMAND_STOP_THREAD, []])
                self.globals[THREADS][SEND_RECEIVE_MESSAGES].join(7.0)  # wait for thread to end
                self.logger.debug("SendReceive thread now stopped")

            if 'discovery' in self.globals[THREADS]:
                self.globals[QUEUES][DISCOVERY].put([QUEUE_PRIORITY_STOP_THREAD, COMMAND_STOP_THREAD, []])
                self.globals[THREADS][DISCOVERY].join(7.0)  # wait for thread to end
                self.logger.debug("Discovery thread now stopped")

        self.logger.debug(". . . runConcurrentThread now ended")

    def deviceStartComm(self, dev):

        try:
            self.logger.info(u'Starting  \'{}\' . . .'.format(dev.name))

            if dev.deviceTypeId != "nanoleafDevice":
                self.logger.error(u'Failed to start device [{}]: Device type [{}] not known by plugin.'.format(dev.name, dev.deviceTypeId))
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

            if "WhiteTemperatureMin" not in props:
                props["WhiteTemperatureMin"] = 1200
                propsRequiresUpdate = True
            elif props["WhiteTemperatureMin"] != 1200: 
                props["WhiteTemperatureMin"] = 1200
                propsRequiresUpdate = True

            if "WhiteTemperatureMax" not in props:
                props["WhiteTemperatureMax"] = 6500
                propsRequiresUpdate = True
            elif props["WhiteTemperatureMax"] != 6500: 
                props["WhiteTemperatureMax"] = 6500
                propsRequiresUpdate = True

            if propsRequiresUpdate:
                dev.replacePluginPropsOnServer(props)
                return

            # Initialise internal to plugin nanoleaf device states to default values
            if dev.id not in self.globals[NL]:
                self.globals[NL][dev.id]= dict()
            self.globals[NL][dev.id][STARTED]                  = False
            self.globals[NL][dev.id][DATE_TIME_STARTED]        = indigo.server.getTime()
            self.globals[NL][dev.id][INITIALISED_FROM_DEVICE]  = False
            self.globals[NL][dev.id][NL_DEVICE_PSEUDO_ADDRESS] = dev.address  # e.g. "d0:73:d5:0a:bc:de" (psuedo mac address)
            self.globals[NL][dev.id][AUTH_TOKEN]               = str(dev.pluginProps.get('authToken', ''))
            self.globals[NL][dev.id][NANOLEAF_OBJECT]          = None
            self.globals[NL][dev.id][IP_ADDRESS]               = str(dev.pluginProps.get('ipAddress', ''))
            self.globals[NL][dev.id][MAC_ADDRESS]              = str(dev.pluginProps.get('macAddress', ''))
            self.globals[NL][dev.id][LAST_RESPONSE_TO_POLL_COUNT] = 0 
            self.globals[NL][dev.id][EFFECTS_LIST]             = []
            self.globals[NL][dev.id][CONNECTION_RETRIES] = 0
            dev.setErrorStateOnServer("no ack")  # Default to 'no ack' status i.e. communication still to be established

            # Check if ip address debug filter(s) active
            # if (len(self.globals['debug']['debugFilteredIpAddresses']) > 0) and (dev.states[IP_ADDRESS] not in self.globals['debug']['debugFilteredIpAddresses']):
            #     self.logger.info(u'Start NOT performed for \'{}\' as nanoleaf device with ip address \'{}\' not included in start filter'.format(dev.name, dev.states[IP_ADDRESS]))
            #     return

            self.globals[NL][dev.id][ONSTATE]     = False      # True or False
            self.globals[NL][dev.id][ONOFFSTATE]  = 'off'      # 'on' or 'off'

            if self.globals[NL][dev.id][AUTH_TOKEN] == '':
                self.logger.error(u'Unable to start \'{}\' as device not authorised. Edit Device settings and follow instructions on how to authorise device.'.format(dev.name))
            else:
                self.globals[NL][dev.id][STARTED] = True
                self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_STATUS_MEDIUM, COMMAND_STATUS, [dev.id]])
                self.logger.info(u'. . . Started \'{}\''.format(dev.name))

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def deviceStopComm(self, dev):
        

        self.logger.info(u'Stopping \'{}\''.format(dev.name))

        dev.setErrorStateOnServer("no ack")  # Default to 'no ack' status

        if dev.id in self.globals[NL]:
            self.globals[NL][dev.id][STARTED] = False

    def deviceDeleted(self, dev):

        if dev.deviceTypeId == "nanoleafDevice": 
            self.deviceStopComm(dev)
            if dev.id in self.globals[NL]:
                nlDeviceid = self.globals[NL][dev.id][NL_DEVICE_PSEUDO_ADDRESS]
                nlIpAddress = self.globals[NL][dev.id][IP_ADDRESS]
                nlMacAddress = self.globals[NL][dev.id][MAC_ADDRESS]
                del self.globals[NL][dev.id]  # Delete internal storage for device

                if nlDeviceid != '':
                    # Make device available for adding as a new device
                    self.globals[DISCOVERY][DISCOVERED_UNMATCHED_DEVICES][nlDeviceid] = (nlIpAddress, nlMacAddress)            

    def getDeviceConfigUiValues(self, pluginProps, typeId, devId):

        try:
            self.logger.debug(u'getDeviceConfigUiValues: typeId [{}], actionId [{}], pluginProps[{}]'.format(typeId, devId, pluginProps))

            nanoleafDev = indigo.devices[devId]

            errorDict = indigo.Dict()
            valuesDict = pluginProps

            valuesDict["nanoleafAvailable"] = "true"
            valuesDict["nanoleafDevice"] = "SELECT_AVAILABLE"
            valuesDict["nanoleafDeviceId"] = nanoleafDev.pluginProps.get("address", '')
            valuesDict["macAddress"] = nanoleafDev.pluginProps.get("macAddress", '')
            valuesDict["ipAddress"] = nanoleafDev.pluginProps.get("ipAddress", '')
            valuesDict["authToken"] = nanoleafDev.pluginProps.get("authToken", '')
            
            return (valuesDict, errorDict)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):

        nanoleafDev = indigo.devices[devId]

        if valuesDict["nanoleafDeviceId"] in self.globals[DISCOVERY][DISCOVERED_UNMATCHED_DEVICES]:
            del self.globals[DISCOVERY][DISCOVERED_UNMATCHED_DEVICES][valuesDict["nanoleafDeviceId"]]

        keyValueList = [
            {"key": "nanoleafDeviceId", "value": valuesDict["nanoleafDeviceId"]},
            {"key": "macAddress", "value": valuesDict["macAddress"]},
            {"key": "ipAddress", "value": valuesDict["ipAddress"]},
            {"key": "authToken", "value": valuesDict["authToken"]}
        ]
        nanoleafDev.updateStatesOnServer(keyValueList)
     
        valuesDict["address"] = valuesDict["nanoleafDeviceId"]

        if valuesDict["nanoleafDeviceId"] in self.globals[DISCOVERY][DISCOVERED_UNMATCHED_DEVICES]:
            del self.globals[DISCOVERY][DISCOVERED_UNMATCHED_DEVICES][valuesDict["nanoleafDeviceId"]]

        return (True, valuesDict)

    def getActionConfigUiValues(self, pluginProps, typeId, devId):
        

        self.logger.debug(u'getActionConfigUiValues: typeId [{}], devId [{}], pluginProps[{}]'.format(typeId, devId, pluginProps))

        errorDict = indigo.Dict()
        valuesDict = pluginProps

        if typeId == "setEffect":
            if ('effectList' not in valuesDict) or (valuesDict["effectList"] == '') or (len(self.globals[NL][devId][EFFECTS_LIST]) == 0):
                valuesDict["effectList"] = 'SELECT_EFFECT'
        return (valuesDict, errorDict)


    def validateActionConfigUi(self, valuesDict, typeId, actionId):

        errorsDict = indigo.Dict()

        if typeId == "setEffect":
            validateResult = self.validateActionConfigUiSetEffect(valuesDict, typeId, actionId)
        else:
            self.logger.debug(u'validateActionConfigUi [UNKNOWN]: typeId=[{}], actionId=[{}]'.format(typeId, actionId))
            return (True, valuesDict)

        if validateResult[0] == True:
            return (True, validateResult[1])
        else:
            return (False, validateResult[1], validateResult[2])
 
    def validateActionConfigUiSetEffect(self, valuesDict, typeId, actionId):

        self.logger.debug(u'validateActionConfigUiSpecific: typeId=[{}], actionId=[{}]'.format(typeId, actionId))

        if valuesDict["effectList"] == "SELECT_EFFECT":
            errorDict = indigo.Dict()
            errorDict["effectList"] = "No Effect selected"
            errorDict["showAlertText"] = "You must select an effect for the action to send to the nanoleaf device"
            return (False, valuesDict, errorDict)

        return (True, valuesDict)

    def openedActionConfigUi(self, valuesDict, typeId, actionId):

        self.logger.debug("openedActionConfigUi intercepted")

        return valuesDict

    def getMenuActionConfigUiValues(self, menuId):

        valuesDict = indigo.Dict()
        errorMsgDict = indigo.Dict() 

        self.logger.debug(f'getMenuActionConfigUiValues: menuId = {menuId}')

        # if menuId == "yourMenuItemId":
        #  valuesDict["someFieldId"] = someDefaultValue
        return (valuesDict, errorMsgDict)

    def actionControlUniversal(self, action, dev):

        # ##### STATUS REQUEST ######
        if action.deviceAction == indigo.kUniversalAction.RequestStatus:
            self._processStatus(action, dev)

    def _processStatus(self, pluginAction, dev):

        self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_STATUS_MEDIUM, COMMAND_STATUS, [dev.id]])
        self.logger.info(u'sent \'{}\' {}'.format(dev.name, "status request"))

    def actionControlDevice(self, action, dev):
        
        if dev.states['connected'] == False or self.globals[NL][dev.id][STARTED] == False:
            self.logger.info(u'Unable to process  \'{}\' for \'{}\' as device not connected'.format(action.deviceAction, dev.name))
            return

        # ##### TURN ON ######
        if action.deviceAction ==indigo.kDeviceAction.TurnOn:
            self._processTurnOn(action, dev)

        # ##### TURN OFF ######
        elif action.deviceAction ==indigo.kDeviceAction.TurnOff:
            self._processTurnOff(action, dev)

        # ##### TOGGLE ######
        elif action.deviceAction ==indigo.kDeviceAction.Toggle:
            self._processTurnOnOffToggle(action, dev)

        # ##### SET BRIGHTNESS ######
        elif action.deviceAction ==indigo.kDeviceAction.SetBrightness:
            newBrightness = action.actionValue  #  action.actionValue contains brightness value (0 - 100)
            self._processBrightnessSet(action, dev, newBrightness)

        # ##### BRIGHTEN BY ######
        elif action.deviceAction ==indigo.kDeviceAction.BrightenBy:
            if not dev.onState:
                self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_COMMAND, COMMAND_IMMEDIATE_ON, [dev.id]])

            if dev.brightness < 100:
                brightenBy = action.actionValue #  action.actionValue contains brightness increase value
                newBrightness = dev.brightness + brightenBy
                if newBrightness > 100:
                    newBrightness = 100
                    brightenBy = 100 - dev.brightness
                self.logger.info(u'Brightening {} by {} to {}'.format(dev.name, brightenBy, newBrightness))
                self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_COMMAND, COMMAND_BRIGHTEN, [dev.id, brightenBy]])
            else:
                self.logger.info(u'Ignoring Brighten request for {}} as device is at full brightness'.format(dev.name))

        # ##### DIM BY ######
        elif action.deviceAction ==indigo.kDeviceAction.DimBy:
            if dev.onState and dev.brightness > 0: 
                dimBy = action.actionValue #  action.actionValue contains brightness decrease value
                newBrightness = dev.brightness - dimBy
                if newBrightness < 0:
                    newBrightness = 0
                    dimBy = dev.brightness
                self.logger.info(u'Dimming {} by {} to {}'.format(dev.name, dimBy, newBrightness))
                self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_COMMAND, COMMAND_DIM, [dev.id, dimBy]])
            else:
                self.logger.info(u'Ignoring Dim request for {} as device is Off'.format(dev.name))

        # ##### SET COLOR LEVELS ######
        elif action.deviceAction ==indigo.kDeviceAction.SetColorLevels:
            self.logger.debug(u'SET COLOR LEVELS = \'{}\' {}'.format(dev.name, action))
            self._processSetColorLevels(action, dev)

    def _processTurnOn(self, pluginAction, dev, actionUi='on'):
        
        self.logger.debug(u'nanoleaf \'processTurnOn\' [{}]'.format(self.globals[NL][dev.id][IP_ADDRESS])) 

        self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_COMMAND, COMMAND_ON, [dev.id]])

        self.logger.info(u'sent \'{}\' {}'.format(dev.name, actionUi))

    def _processTurnOff(self, pluginAction, dev, actionUi='off'):

        self.logger.debug(u'nanoleaf \'processTurnOff\' [{}]'.format(self.globals[NL][dev.id][IP_ADDRESS])) 

        self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_COMMAND, COMMAND_OFF, [dev.id]])

        self.logger.info(u'sent \'{}\' {}'.format(dev.name, actionUi))

    def _processTurnOnOffToggle(self, pluginAction, dev):

        self.logger.debug(u'nanoleaf \'processTurnOnOffToggle\' [{}]'.format(self.globals[NL][dev.id][IP_ADDRESS])) 

        onStateRequested = not dev.onState
        if onStateRequested == True:
            actionUi = "toggle from 'off' to 'on'"
            self._processTurnOn(pluginAction, dev, actionUi)
        else:
            actionUi = "toggle from 'on' to 'off'"
            self._processTurnOff(pluginAction, dev, actionUi)

    def _processBrightnessSet(self, pluginAction, dev, newBrightness):  # Dev is a nanoleaf device

        if newBrightness > 0:
            if newBrightness > dev.brightness:
                actionUi = 'brighten'
            else:
                actionUi = 'dim'  
            self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_COMMAND, COMMAND_BRIGHTNESS, [dev.id, newBrightness]])
            self.logger.info(u'sent \'{}\' {} to {}'.format(dev.name, actionUi, newBrightness))
        else:
            self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_COMMAND, COMMAND_OFF, [dev.id]])
            self.logger.info(u'sent \'{}\' {}'.format(dev.name, 'dim to off'))

    def _processSetColorLevels(self, action, dev):
        try:
            self.logger.debug(u'processSetColorLevels ACTION:\n{}'.format(action))

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

                self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_COMMAND, COMMAND_WHITE, [dev.id, whiteLevel, whiteTemperature]])

                self.logger.info(u'sent \'{}\' set White Level to \'{}\' and White Temperature to \'{}\''.format(dev.name, int(whiteLevel), whiteTemperature))

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

                    self.logger.debug(u'Color: \'{}\' R, G, B: {}, {}, {}'.format(dev.name, redLevel, greenLevel, blueLevel))

                    self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_COMMAND, COMMAND_COLOR, [dev.id, redLevel, greenLevel, blueLevel]])

                    self.logger.info(u'sent \'{}\' set Color Level to red \'{}\', green \'{}\' and blue \'{}\''.format(dev.name, int(round(redLevel)), int(round(greenLevel)), int(round(blueLevel))))
                else:
                    self.logger.info(u'Failed to send \'{}\' set Color Level as device does not support color.'.format(dev.name))

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def processDiscoverDevices(self, pluginAction):

        self.globals[QUEUES][DISCOVERY].put([QUEUE_PRIORITY_LOW, COMMAND_DISCOVERY, []])

    def processSetEffect(self, pluginAction, dev):
        try:      
            if dev.states['connected'] == False or self.globals[NL][dev.id][STARTED] == False:
                self.logger.info(u'Unable to process  \'{}\' for \'{}\' as device not connected'.format(pluginAction.description, dev.name))
                return
    
            effect = pluginAction.props.get('effectList')
    
            if effect in self.globals[NL][dev.id][EFFECTS_LIST]:
                self.logger.info(u'sent \'{}\' Set Effect to {}'.format(dev.name, effect))
                self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_LOW, COMMAND_SET_EFFECT, [dev.id, effect]])
            else:
                self.logger.info('Effect \'{}\' not available on nanoleaf device \'{}\''.format(effect, dev.name))
        
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def authoriseNanoleaf(self, valuesDict, typeId, devId):

        self.logger.debug(f"deviceConfigAuthoriseButtonPressed: typeId[{typeId}], devId[{devId}], valuesDict = {valuesDict}")

        ipAddress = valuesDict["ipAddress"]

        try:
            socket.inet_aton(ipAddress)
            # legal
        except socket.error:
            # Not legal
            errorDict = indigo.Dict()
            errorDict["nanoleafDevice"] = "IP Address is invalid"
            errorDict["showAlertText"] = "IP Address is invalid! Select Nanoleaf device before attempting to authorise."
            return (valuesDict, errorDict)

        try:
            self.globals[NL][devId][NANOLEAF_OBJECT] = Nanoleaf(ipAddress)
        except NanoleafRegistrationError as statusMessage:
            self.logger.error(u'{}'.format(statusMessage))
            errorDict = indigo.Dict()
            errorDict["authorise"] = 'Access Forbidden to nanoleaf device!'
            errorDict["showAlertText"] = 'Access Forbidden to nanoleaf device! Press and hold the power button for 5-7 seconds first! (Light will begin flashing)'
            return (valuesDict, errorDict)
        else:
            valuesDict["authToken"] = self.globals[NL][devId][NANOLEAF_OBJECT].auth_token  # noqa - self.globals[NL][devId][NANOLEAF_OBJECT] is a Nanoleaf object NOT a text string

        return valuesDict

    def updateIpAddress(self, valuesDict, typeId, devId):

        self.logger.debug(f'actionConfigPresetUpdateButtonPressed: typeId[{typeId}], devId[{devId}], valuesDict = {valuesDict}')

        if 'address' in valuesDict and valuesDict["address"] != '':
            nlInfo = self.globals[DISCOVERY][DISCOVERED_DEVICES][valuesDict["address"]]
            valuesDict["ipAddress"] = nlInfo[0]  # from tuple of (IP Address, MAC Address)
            return valuesDict
        else:
            errorDict = indigo.Dict()
            errorDict["updateIpAddress"] = "Unable to update IP Address!"
            errorDict["showAlertText"] = "Unable to update IP Address as nanoleaf Device ID not set"
            return (valuesDict, errorDict)

    def nanoleafAvailableDeviceSelected(self, valuesDict, typeId, devId):

        try:
            self.logger.debug(f'nanoleafAvailableDeviceSelected: typeId[{typeId}], devId[{devId}], valuesDict = {valuesDict}')

            if valuesDict["nanoleafDevice"] != "SELECT_AVAILABLE":
                nanoleafDeviceId, macAddress, ipAddress, nlName = valuesDict["nanoleafDevice"].split('*')
                valuesDict["nanoleafDeviceId"] = nanoleafDeviceId
                valuesDict["macAddress"] = macAddress
                valuesDict["ipAddress"] = ipAddress

            return valuesDict

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def _buildAvailableDevicesList(self, filter="", valuesDict=None, typeId="", targetId=0):

        self.logger.debug(u'_buildAvailableDevicesList: TARGET ID = \'{}\''.format(targetId))

        try:
            available_dict = []
            available_dict.append(("SELECT_AVAILABLE", "- Select nanoleaf device -"))

            for nlDeviceid, nlInfo in self.globals[DISCOVERY][DISCOVERED_UNMATCHED_DEVICES].items():  # self.globals[DISCOVERY][DISCOVERED_DEVICES]
                nlIpAddress = nlInfo[0]
                nlMacAddress = nlInfo[1]
                nlName = nlInfo[2]
                nanoleaf_available = ('{}*{}*{}*{}'.format(nlDeviceid, nlMacAddress, nlIpAddress, nlName), '{}: {}'.format(nlName, nlMacAddress))
                available_dict.append(nanoleaf_available)
            if len(available_dict) == 1:
                available_dict = []
                available_dict.append(("SELECT_AVAILABLE", "- No available nanoleaf devices discovered -"))

            myArray = available_dict
            return myArray

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def _buildAvailableEffectsList(self, filter="", valuesDict=None, typeId="", targetId=0):

        self.logger.debug(f'_buildAvailableEffectsList: TARGET ID = {targetId}')
        try:
            nanoleafDevId = targetId

            effect_dict = []
            effect_dict.append(("SELECT_EFFECT", "- Select nanoleaf effect -"))

            for effect in self.globals[NL][nanoleafDevId][EFFECTS_LIST]:
                nanoleaf_effect = (effect, effect)
                effect_dict.append(nanoleaf_effect)
            if len(effect_dict) == 1:
                effect_dict = []
                effect_dict.append(("SELECT_EFFECT", "- No available nanoleaf effects discovered -"))

            myArray = effect_dict
            return myArray

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def refreshEffectList(self, valuesDict, typeId, devId):

        self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_STATUS_HIGH, COMMAND_STATUS, [devId]])

        self.sleep(3)  # Allow 3 seconds for the list to be refreshed