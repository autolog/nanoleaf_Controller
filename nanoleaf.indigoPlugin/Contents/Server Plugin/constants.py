#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# nanoleaf Controller © Autolog 2017-2022
#

import logging

# ============================== Custom Imports ===============================
try:
    import indigo  # noqa
except ImportError:
    pass

number = -1

debug_show_constants = False


def constant_id(constant_label) -> int:  # Auto increment constant id
    global number
    if debug_show_constants and number == -1:
        indigo.server.log("nanoleaf Plugin internal Constant Name mapping ...", level=logging.DEBUG)
    number += 1
    if debug_show_constants:
        indigo.server.log(f"{number}: {constant_label}", level=logging.DEBUG)
    return number

# plugin Constants


try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass

# noinspection Duplicates
PLUGIN_TITLE = "Autolog 'Nanoleaf Controller'"
CONNECTION_RETRY_LIMIT = 12

API_VERSION = constant_id("API_VERSION")
AUTH_TOKEN = constant_id("AUTH_TOKEN")
COMMAND_BRIGHTEN = constant_id("COMMAND_BRIGHTEN")
COMMAND_BRIGHTNESS = constant_id("COMMAND_BRIGHTNESS")
COMMAND_COLOR = constant_id("COMMAND_COLOR")
COMMAND_DIM = constant_id("COMMAND_DIM")
COMMAND_DISCOVERY = constant_id("COMMAND_DISCOVERY")
COMMAND_IMMEDIATE_ON = constant_id("COMMAND_IMMEDIATE_ON")
COMMAND_OFF = constant_id("COMMAND_OFF")
COMMAND_ON = constant_id("COMMAND_ON")
COMMAND_SET_EFFECT = constant_id("COMMAND_SET_EFFECT")
COMMAND_STATUS = constant_id("COMMAND_STATUS")
COMMAND_STOP_THREAD = constant_id("COMMAND_STOP_THREAD")
COMMAND_WHITE = constant_id("COMMAND_WHITE")
CONNECTION_RETRIES = constant_id("CONNECTION_RETRIES")
COUNT = constant_id("COUNT")
DATE_TIME_STARTED = constant_id("DATE_TIME_STARTED")
DEBUG_FILTERED_IP_ADDRESSES = constant_id("DEBUG_FILTERED_IP_ADDRESSES")
# DISCOVERED_AURORAS = constant_id("DISCOVERED_AURORAS")
# DISCOVERED_CANVASES = constant_id("DISCOVERED_CANVASES")
DISCOVERED_DEVICES = constant_id("DISCOVERED_DEVICES")
# DISCOVERED_SHAPES = constant_id("DISCOVERED_SHAPES")
# DISCOVERED_ELEMENTS = constant_id("DISCOVERED_ELEMENTS")
# DISCOVERED_LINES = constant_id("DISCOVERED_LINES")
DISCOVERED_UNMATCHED_DEVICES = constant_id("DISCOVERED_UNMATCHED_DEVICES")
DISCOVERY = constant_id("DISCOVERY")
DISCOVERY_DEVICES = constant_id("DISCOVERY_DEVICES")
EFFECTS_LIST = constant_id("EFFECTS_LIST")
EVENT = constant_id("EVENT")
FORCE_THREAD_END = constant_id("FORCE_THREAD_END")
INDIGO_SERVER_ADDRESS = constant_id("INDIGO_SERVER_ADDRESS")
INITIALISED = constant_id("INITIALISED")
INITIALISED_FROM_DEVICE = constant_id("INITIALISED_FROM_DEVICE")
IP_ADDRESS = constant_id("IP_ADDRESS")
LAST_RESPONSE_TO_POLL_COUNT = constant_id("LAST_RESPONSE_TO_POLL_COUNT")
MAC_ADDRESS = constant_id("MAC_ADDRESS")
MESSAGE_TO_SEND = constant_id("MESSAGE_TO_SEND")
MISSED_POLL_LIMIT = constant_id("MISSED_POLL_LIMIT")
NANOLEAF = constant_id("NANOLEAF")
NANOLEAF_DEVICE_NAME = constant_id("NANOLEAF_DEVICE_NAME")
NANOLEAF_INFO = constant_id("NANOLEAF_INFO")
NANOLEAF_IP_ADDRESS = constant_id("NANOLEAF_IP_ADDRESS")
NANOLEAF_MAC = constant_id("NANOLEAF_MAC")
NANOLEAF_OBJECT = constant_id("NANOLEAF_OBJECT")
NL = constant_id("NL")
NL_DEVICE_PSEUDO_ADDRESS = constant_id("NL_DEVICE_PSEUDO_ADDRESS")
ONOFFSTATE = constant_id("ONOFFSTATE")
ONSTATE = constant_id("ONSTATE")
OVERRIDDEN_HOST_IP_ADDRESS = constant_id("OVERRIDDEN_HOST_IP_ADDRESS")
PATH = constant_id("PATH")
PERIOD = constant_id("PERIOD")
PLUGIN_DISPLAY_NAME = constant_id("PLUGIN_DISPLAY_NAME")
PLUGIN_ID = constant_id("PLUGIN_ID")
PLUGIN_INFO = constant_id("PLUGIN_INFO")
PLUGIN_PREFS_FOLDER = constant_id("PLUGIN_PREFS_FOLDER")
PLUGIN_VERSION = constant_id("PLUGIN_VERSION")
POLLING = constant_id("POLLING")
QUEUES = constant_id("QUEUES")
QUIESCED = constant_id("QUIESCED")
RETURNED_RESPONSE = constant_id("RETURNED_RESPONSE")
SECONDS = constant_id("SECONDS")
SEND_RECEIVE_MESSAGES = constant_id("SEND_RECEIVE_MESSAGES")
STARTED = constant_id("STARTED")
STARTUP_COMPLETED = constant_id("STARTUP_COMPLETED")
STATE = constant_id("STATE")
STATUS = constant_id("STATUS")
STATUS_POLLING = constant_id("STATUS_POLLING")
STOP_THREAD = constant_id("STOP_THREAD")
THREAD = constant_id("THREAD")
THREADS = constant_id("THREADS")
THREAD_ACTIVE = constant_id("THREAD_ACTIVE")
TRIGGER = constant_id("TRIGGER")

LOG_LEVEL_NOT_SET = 0
LOG_LEVEL_DEBUGGING = 10
LOG_LEVEL_TOPIC = 15
LOG_LEVEL_INFO = 20
LOG_LEVEL_WARNING = 30
LOG_LEVEL_ERROR = 40
LOG_LEVEL_CRITICAL = 50

LOG_LEVEL_TRANSLATION = dict()
LOG_LEVEL_TRANSLATION[LOG_LEVEL_NOT_SET] = "Not Set"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_DEBUGGING] = "Debugging"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_TOPIC] = "Topic Logging"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_INFO] = "Info"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_WARNING] = "Warning"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_ERROR] = "Error"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_CRITICAL] = "Critical"

# QUEUE Priorities
QUEUE_PRIORITY_STOP_THREAD   = 0
QUEUE_PRIORITY_WAVEFORM      = 100
QUEUE_PRIORITY_COMMAND       = 200
QUEUE_PRIORITY_STATUS_HIGH   = 300
QUEUE_PRIORITY_STATUS_MEDIUM = 400
QUEUE_PRIORITY_DISCOVERY     = 500
QUEUE_PRIORITY_POLLING       = 600
QUEUE_PRIORITY_LOW           = 700
