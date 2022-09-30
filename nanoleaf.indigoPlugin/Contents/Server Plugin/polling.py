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
import sys
import threading
import traceback

from constants import *

class ThreadPolling(threading.Thread):

    def __init__(self, globalsAndEvent):

        threading.Thread.__init__(self)

        self.globals, self.pollStop = globalsAndEvent

        self.previousPollingSeconds = self.globals[POLLING][SECONDS]

        self.globals[POLLING][THREAD_ACTIVE] = True

        self.pollingLogger = logging.getLogger("Plugin.polling")

        self.pollingLogger.info(f"Initialising to poll at {int(self.globals[POLLING][SECONDS])} second intervals")

    def exception_handler(self, exception_error_message, log_failing_statement):
        filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]
        module = filename.split('/')
        log_message = f"'{exception_error_message}' in module '{module[-1]}', method '{method}'"
        if log_failing_statement:
            log_message = log_message + f"\n   Failing statement [line {line_number}]: '{statement}'"
        else:
            log_message = log_message + f" at line {line_number}"
        self.pollingLogger.error(log_message)

    def run(self):
        try:  
            self.pollingLogger.debug("Polling thread running")

            while not self.pollStop.wait(self.globals[POLLING][SECONDS]):

                # Check if polling seconds interval has changed and if so set accordingly
                if self.globals[POLLING][SECONDS] != self.previousPollingSeconds:
                    self.pollingLogger.info(f"Changing to poll at {int(self.globals[POLLING][SECONDS])} second intervals (was {int(self.previousPollingSeconds)} seconds)")
                    self.previousPollingSeconds = self.globals[POLLING][SECONDS]

                self.pollingLogger.debug("Start of While Loop ...")
                if self.pollStop.isSet():
                    if self.globals[POLLING][FORCE_THREAD_END]:
                        break
                    else:
                        self.pollStop.clear()
                self.pollingLogger.debug("Polling at {self.globals[POLLING][SECONDS]} second intervals")

                if not self.globals[POLLING][QUIESCED]:
                    self.globals[POLLING][COUNT] += 1  # Increment polling count

                    # Check if nanoleaf devices are responding to polls
                    all_responding = True  # Assume all nanoleafs are responding 
                    for devId in self.globals[NL]:
                        if indigo.devices[devId].enabled:
                            if ((len(self.globals[DEBUG_FILTERED_IP_ADDRESSES]) == 0)
                                or ((len(self.globals[DEBUG_FILTERED_IP_ADDRESSES]) > 0)
                                    and (IP_ADDRESS in self.globals[NL][devId])
                                    and (self.globals[NL][devId][IP_ADDRESS] in self.globals['debug'][DEBUG_FILTERED_IP_ADDRESSES]))):
                                dev_poll_check = self.globals[NL][devId][LAST_RESPONSE_TO_POLL_COUNT] + self.globals[POLLING][MISSED_POLL_LIMIT]
                                self.pollingLogger.debug(f"Dev = '{indigo.devices[devId].name}', Count = {int(self.globals[POLLING][COUNT])},"
                                                         f" nanoleaf LastResponse = {int(self.globals[NL][devId][LAST_RESPONSE_TO_POLL_COUNT])},"
                                                         f" Missed Limit = {int(self.globals[POLLING][MISSED_POLL_LIMIT])}, Check = {int(dev_poll_check)}")
                                dev = indigo.devices[devId]
                                if (dev_poll_check < self.globals[POLLING][COUNT]) or (not self.globals[NL][devId][STARTED]):
                                    self.pollingLogger.debug("dev_poll_check < self.globals[POLLING][COUNT]")
                                    indigo.devices[devId].setErrorStateOnServer(u"no ack")
                                    dev.updateStateOnServer(key="connected", value="false", clearErrorState=False)
                                    all_responding = False  # At least one nanoleaf is not responding
                                elif not dev.states["connected"]:  # Previously detected as not responding
                                    all_responding = False  # At least one nanoleaf is not responding
                    if not all_responding:
                        self.globals[QUEUES][DISCOVERY].put([QUEUE_PRIORITY_LOW, 'DISCOVERY', []])  # Run Discovery to search for device (in case details have changed)

                    self.globals[QUEUES][MESSAGE_TO_SEND].put([QUEUE_PRIORITY_POLLING, STATUS_POLLING, 0])  # Poll nanoleaf devices for status updates

            self.pollingLogger.debug(u"Polling thread ending")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

        self.globals[POLLING][THREAD_ACTIVE] = False
