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
import sys
import threading

from constants import *

class ThreadPolling(threading.Thread):

    def __init__(self, globalsAndEvent):

        threading.Thread.__init__(self)

        self.globals, self.pollStop = globalsAndEvent

        self.previousPollingSeconds = self.globals['polling']['seconds']

        self.globals['polling']['threadActive'] = True

        self.pollingLogger = logging.getLogger("Plugin.polling")
        self.pollingLogger.setLevel(self.globals['debug']['debugPolling'])

        self.methodTracer = logging.getLogger("Plugin.method")  
        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

        self.pollingLogger.info(u'Initialising to poll at {} second intervals'.format(int(self.globals['polling']['seconds'])))  
        self.pollingLogger.debug('debugPolling = {} [{}], debugMethodTrace = {} [{}]'.format(self.globals['debug']['debugPolling'], 
            type(self.globals['debug']['debugPolling']), 
            self.globals['debug']['debugMethodTrace'], 
            type(self.globals['debug']['debugMethodTrace'])))  

    def run(self):
        try:  
            self.methodTracer.threaddebug(u"ThreadPolling")

            self.pollingLogger.debug(u"Polling thread running")  

            while not self.pollStop.wait(self.globals['polling']['seconds']):

                # Check if monitoring / debug options have changed and if so set accordingly
                if self.globals['debug']['previousDebugPolling'] != self.globals['debug']['debugPolling']:
                    self.globals['debug']['previousDebugPolling'] = self.globals['debug']['debugPolling']
                    self.pollingLogger.setLevel(self.globals['debug']['debugPolling'])
                if self.globals['debug']['previousDebugMethodTrace'] !=self.globals['debug']['debugMethodTrace']:
                    self.globals['debug']['previousDebugMethodTrace'] = self.globals['debug']['debugMethodTrace']
                    self.pollingLogger.setLevel(self.globals['debug']['debugMethodTrace'])

                # Check if polling seconds interval has changed and if so set accordingly
                if self.globals['polling']['seconds'] != self.previousPollingSeconds:
                    self.pollingLogger.info(u'Changing to poll at {} second intervals (was {} seconds)'.format(int(self.globals['polling']['seconds']), int(self.previousPollingSeconds)))
                    self.previousPollingSeconds = self.globals['polling']['seconds']

                self.pollingLogger.debug(u"Start of While Loop ...")
                if self.pollStop.isSet():
                    if self.globals['polling']['forceThreadEnd'] == True:
                        break
                    else:
                        self.pollStop.clear()
                self.pollingLogger.debug(u'Polling at {} second intervals'.format(self.globals['polling']['seconds']))
                if self.globals['polling']['quiesced'] == False:

                    self.globals['polling']['count'] += 1  # Increment polling count

                    # Check if nanoleaf devices are responding to polls
                    allResponding = True  # Assume all nanoleafs are responding 
                    for devId in self.globals['nl']:
                        if indigo.devices[devId].enabled:
                            if ((len(self.globals['debug']['debugFilteredIpAddresses']) == 0) 
                                or ((len(self.globals['debug']['debugFilteredIpAddresses']) > 0) 
                                    and ('ipAddress' in self.globals['nl'][devId]) 
                                    and (self.globals['nl'][devId]['ipAddress'] in self.globals['debug']['debugFilteredIpAddresses']))):
                                dev_poll_check = self.globals['nl'][devId]['lastResponseToPollCount'] + self.globals['polling']['missedPollLimit']
                                self.pollingLogger.debug(u'Dev = \'{}\', Count = {}, nanoleaf LastResponse = {}, Missed Limit = {}, Check = {}'.format(indigo.devices[devId].name, int(self.globals['polling']['count']), int(self.globals['nl'][devId]['lastResponseToPollCount']), int(self.globals['polling']['missedPollLimit']), int(dev_poll_check)))
                                dev = indigo.devices[devId]
                                if (dev_poll_check < self.globals['polling']['count']) or (not self.globals['nl'][devId]['started']):
                                    self.pollingLogger.debug(u"dev_poll_check < self.globals['polling']['count']")
                                    indigo.devices[devId].setErrorStateOnServer(u"no ack")
                                    dev.updateStateOnServer(key='connected', value='false', clearErrorState=False)
                                    allResponding = False  # At least one nanoleaf is not responding
                                elif not dev.states['connected']:  # Previously detected as not responding
                                    allResponding = False  # At least one nanoleaf is not responding
                    if not allResponding:
                        self.globals['queues']['discovery'].put([QUEUE_PRIORITY_LOW, 'DISCOVERY', []])  # Run Discovery to search for device (in case details have changed)

                    self.globals['queues']['messageToSend'].put([QUEUE_PRIORITY_POLLING, 'STATUSPOLLING', 0])  # Poll nanoleaf devices for status updates

            self.pollingLogger.debug(u'Polling thread ending')

        except StandardError, e:
            self.pollingLogger.error(u'StandardError detected during Polling. Line \'{}\' has error = \'{}\''.format(sys.exc_traceback.tb_lineno, e))

        self.globals['polling']['threadActive'] = False
