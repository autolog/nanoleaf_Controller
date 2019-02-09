import requests
import random
import colorsys

# Primary interface for an Aurora light
# For instructions or bug reports, please visit
# https://github.com/software-2/nanoleaf


class Aurora(object):
    def __init__(self, ip_address, auth_token):
        self.baseUrl = "http://" + ip_address + ":16021/api/v1/" + auth_token + "/"
        self.ip_address = ip_address
        self.auth_token = auth_token

    def __repr__(self):
        return "<Aurora(" + self.ip_address + ")>"

    def __put(self, endpoint, data):
        url = self.baseUrl + endpoint
        try:
            r = requests.put(url, timeout=5.0, json=data)
        except requests.exceptions.Timeout:
            return (False, 'Timeout occurred processing request', None)
        except requests.exceptions.RequestException as e:
            errorMsg = e.args[0].reason.message.split('>: ')[1]
            return (False, errorMsg, None)
        return self.__check_for_errors(r)

    def __get(self, endpoint=""):
        url = self.baseUrl + endpoint
        try:
            r = requests.get(url, timeout=5.0)
        except requests.exceptions.Timeout:
            return (False, 'Timeout occurred processing request', None)
        except requests.exceptions.RequestException as e:
            errorMsg = e.args[0].reason.message.split('>: ')[1]
            return (False, errorMsg, None)
        return self.__check_for_errors(r)


    def __delete(self, endpoint=""):
        url = self.baseUrl + endpoint
        try:
            r = requests.delete(url, timeout=5.0)
        except requests.exceptions.Timeout:
            return (False, 'Timeout occurred processing request', None)
        except requests.exceptions.RequestException as e:
            errorMsg = e.args[0].reason.message.split('>: ')[1]
            return (False, errorMsg, None)
        return self.__check_for_errors(r)

    def __check_for_errors(self, r):
        if r.status_code == 200:
            if r.text == "":  # BUG: Delete User returns 200, not 204 like it should, as of firmware 1.5.0
                return (True, 'OK', '')
            return (True, 'OK', r.json())
        elif r.status_code == 204:
            return (True, 'OK', None)
        elif r.status_code == 403:
            return (False, 'HTTP Error code 403: Bad request', None)
        elif r.status_code == 401:
            return (False, 'HTTP Error code 401: Not authorized', None)
        elif r.status_code == 404:
            return (False, 'HTTP Error code 404: Resource not found', None)
        elif r.status_code == 422:
            return (False, 'HTTP Error code 422: Unprocessible Entity', None)
        elif r.status_code == 500:
            return (False, 'HTTP Error code 500: Internal Server Error', None)
        else:
            return (False, 'HTTP Error code ' + str(r.status_code) + ' unknown', None)
        return (False, '__check_for_errors Error? - unable to process', None)


    ###########################################
    # General functionality methods
    ###########################################

    @property
    def info(self):
        """Returns the full Aurora Info request. 
        
        Useful for debugging since it's just a fat dump."""
        return self.__get()

    @property
    def color_mode(self):
        """Returns the current color mode."""
        return self.__get("state/colorMode")

    def identify(self):
        """Briefly flash the panels on and off"""
        self.__put("identify", {})

    @property
    def firmware(self):
        """Returns the firmware version of the device"""
        return self.__get("firmwareVersion")

    @property
    def model(self):
        """Returns the model number of the device. (Always returns 'NL22')"""
        return self.__get("model")

    @property
    def serial_number(self):
        """Returns the serial number of the device"""
        return self.__get("serialNo")

    def delete_user(self):
        """CAUTION: Revokes your auth token from the device."""
        self.__delete()

    ###########################################
    # On / Off methods
    ###########################################

    @property
    def on(self):
        """Returns True if the device is on, False if it's off"""
        return self.__get("state/on/value")

    # @on.setter
    # def on(self, value):
    #     """Turns the device on/off. True = on, False = off"""
    #     data = {"on": value}
    #     self.__put("state", data)

    @property
    def off(self):
        """Returns True if the device is off, False if it's on"""
        success, statusMsg, onState = self.on
        if not success:
            return success, statusMsg, onState
        else:
            return success, statusMsg, onState

    # @off.setter
    # def off(self, value):
    #     """Turns the device on/off. True = off, False = on"""
    #     self.on = not value

    # def on_toggle(self):
    #     """Switches the on/off state of the device"""
    #     self.on = not self.on

    def set_off(self):
        data = {"on": False}
        return self.__put("state", data)

    def set_on(self):
        data = {"on": True}
        return self.__put("state", data)

    def toggle_on(self):
        success, statusMsg, onState = self.on
        if not success:
            return success, statusMsg, onState
        else:
            if onState:
                return self.set_off()
            else:
                return self.set_on()



    ###########################################
    # Brightness methods
    ###########################################

    @property
    def brightness(self):
        """Returns the brightness of the device (0-100)"""
        return self.__get("state/brightness/value")

    # @brightness.setter
    # def brightness(self, level):
    #     """Sets the brightness to the given level (0-100)"""
    #     data = {"brightness": {"value": level}}
    #     self.__put("state", data)

    def set_brightness(self, level):   
        """Sets the brightness to the given level (0-100)"""
        data = {"brightness": {"value": level}}
        return self.__put("state", data)


    @property
    def brightness_min(self):
        """Returns the minimum brightness possible. (This always returns 0)"""
        return self.__get("state/brightness/min")

    @property
    def brightness_max(self):
        """Returns the maximum brightness possible. (This always returns 100)"""
        return self.__get("state/brightness/max")

    def brightness_raise(self, level):
        """Raise the brightness of the device by a relative amount (negative lowers brightness)"""
        data = {"brightness": {"increment": level}}
        return self.__put("state", data)

    def brightness_lower(self, level):
        """Lower the brightness of the device by a relative amount (negative raises brightness)"""
        return self.brightness_raise(-level)

    ###########################################
    # Hue methods
    ###########################################

    @property
    def hue(self):
        """Returns the hue of the device (0-360)"""
        return self.__get("state/hue/value")

    # @hue.setter
    # def hue(self, level):
    #     """Sets the hue to the given level (0-360)"""
    #     data = {"hue": {"value": level}}
    #     self.__put("state", data)

    def set_hue(self, level):
        """Sets the hue to the given level (0-360)"""
        data = {"hue": {"value": level}}
        return self.__put("state", data)


    @property
    def hue_min(self):
        """Returns the minimum hue possible. (This always returns 0)"""
        return self.__get("state/hue/min")

    @property
    def hue_max(self):
        """Returns the maximum hue possible. (This always returns 360)"""
        return self.__get("state/hue/max")

    def hue_raise(self, level):
        """Raise the hue of the device by a relative amount (negative lowers hue)"""
        data = {"hue": {"increment": level}}
        return self.__put("state", data)

    def hue_lower(self, level):
        """Lower the hue of the device by a relative amount (negative raises hue)"""
        return self.hue_raise(-level)

    ###########################################
    # Saturation methods
    ###########################################

    @property
    def saturation(self):
        """Returns the saturation of the device (0-100)"""
        return self.__get("state/sat/value")

    @saturation.setter
    def saturation(self, level):
        """Sets the saturation to the given level (0-100)"""
        data = {"sat": {"value": level}}
        self.__put("state", data)

    def set_saturation(self, level):
        """Sets the saturation to the given level (0-100)"""
        data = {"hue": {"value": level}}
        return self.__put("state", data)

    @property
    def saturation_min(self):
        """Returns the minimum saturation possible. (This always returns 0)"""
        return self.__get("state/sat/min")

    @property
    def saturation_max(self):
        """Returns the maximum saturation possible. (This always returns 100)"""
        return self.__get("state/sat/max")

    def saturation_raise(self, level):
        """Raise the saturation of the device by a relative amount (negative lowers saturation)"""
        data = {"sat": {"increment": level}}
        return self.__put("state", data)

    def saturation_lower(self, level):
        """Lower the saturation of the device by a relative amount (negative raises saturation)"""
        return self.saturation_raise(-level)

    ###########################################
    # Color Temperature methods
    ###########################################

    @property
    def color_temperature(self):
        """Returns the color temperature of the device (0-100)"""
        return self.__get("state/ct/value")

    @color_temperature.setter
    def color_temperature(self, level):
        """Sets the color temperature to the given level (0-100)"""
        data = {"ct": {"value": level}}
        self.__put("state", data)

    def set_color_temperature(self, level):
        """Sets the color temperature to the given level (0-100)"""
        data = {"ct": {"value": level}}
        return self.__put("state", data)

    @property
    def color_temperature_min(self):
        """Returns the minimum color temperature possible. (This always returns 1200)"""
        # return self.__get("state/ct/min")
        # BUG: Firmware 1.5.0 returns the wrong value.
        return 1200

    @property
    def color_temperature_max(self):
        """Returns the maximum color temperature possible. (This always returns 6500)"""
        # return self.__get("state/ct/max")
        # BUG: Firmware 1.5.0 returns the wrong value.
        return 6500

    def color_temperature_raise(self, level):
        """Raise the color temperature of the device by a relative amount (negative lowers color temperature)"""
        data = {"ct": {"increment": level}}
        return self.__put("state", data)

    def color_temperature_lower(self, level):
        """Lower the color temperature of the device by a relative amount (negative raises color temperature)"""
        return self.color_temperature_raise(-level)

    ###########################################
    # Color RGB/HSB methods
    ###########################################

    # TODO: Shame on all these magic numbers. SHAME.

    @property
    def rgb(self):
        """The color of the device, as represented by 0-255 RGB values"""
        success, statusMsg, hue = self.hue
        success, statusMsg, saturation = self.saturation
        success, statusMsg, brightness = self.brightness
        if hue is None or saturation is None or brightness is None:
            return False, "One or more of Hue/Saturation/Brightness is missing", None
        rgb = colorsys.hsv_to_rgb(hue / 360.0, saturation / 100.0, brightness / 100.0)
        return True, 'OK', [int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255)]

    @rgb.setter
    def rgb(self, color):
        """Set the color of the device, as represented by a list of 0-255 RGB values"""
        try:
            red, green, blue = color
        except ValueError:
            print("Error: Color must have three values.")
            return
        hsv = colorsys.rgb_to_hsv(red / 255.0, green / 255.0, blue / 255.0)
        hue = int(hsv[0] * 360)
        saturation = int(hsv[1] * 100)
        brightness = int(hsv[2] * 100)
        data = {"hue": {"value": hue}, "sat": {"value": saturation}, "brightness": {"value": brightness}}
        self.__put("state", data)


    def set_rgb(self, color):
        """Set the color of the device, as represented by a list of 0-255 RGB values"""
        try:
            red, green, blue = color
        except ValueError:
            return False, "Color must have three values", None
        hsv = colorsys.rgb_to_hsv(red / 255.0, green / 255.0, blue / 255.0)
        hue = int(hsv[0] * 360)
        saturation = int(hsv[1] * 100)
        brightness = int(hsv[2] * 100)
        data = {"hue": {"value": hue}, "sat": {"value": saturation}, "brightness": {"value": brightness}}
        return self.__put("state", data)

    ###########################################
    # Layout methods
    ###########################################

    @property
    def orientation(self):
        """Returns the orientation of the device (0-360)"""
        return self.__get("panelLayout/globalOrientation/value")

    @property
    def orientation_min(self):
        """Returns the minimum orientation possible. (This always returns 0)"""
        return self.__get("panelLayout/globalOrientation/min")

    @property
    def orientation_max(self):
        """Returns the maximum orientation possible. (This always returns 360)"""
        return self.__get("panelLayout/globalOrientation/max")

    @property
    def panel_count(self):
        """Returns the number of panels connected to the device"""
        return self.__get("panelLayout/layout/numPanels")

    @property
    def panel_length(self):
        """Returns the length of a single panel. (This always returns 150)"""
        return self.__get("panelLayout/layout/sideLength")

    @property
    def panel_positions(self):
        """Returns a list of all panels with their attributes represented in a dict.
        
        panelId - Unique identifier for this panel
        x - X-coordinate
        y - Y-coordinate
        o - Rotational orientation
        """
        return self.__get("panelLayout/layout/positionData")

    ###########################################
    # Effect methods
    ###########################################

    _reserved_effect_names = ["*Static*", "*Dynamic*", "*Solid*"]

    @property
    def effect(self):
        """Returns the active effect"""
        return self.__get("effects/select")

    @effect.setter
    def effect(self, effect_name):
        """Sets the active effect to the name specified"""
        data = {"select": effect_name}
        self.__put("effects", data)

    def set_effect(self, effect_name):
        """Sets the active effect to the name specified"""
        data = {"select": effect_name}
        return self.__put("effects", data)

    @property
    def effects_list(self):
        """Returns a list of all effects stored on the device"""
        return self.__get("effects/effectsList")

    # def effect_random(self):
    #     """Sets the active effect to a new random effect stored on the device.
        
    #     Returns the name of the new effect."""
    #     effect_list = self.effects_list
    #     active_effect = self.effect
    #     if active_effect not in self._reserved_effect_names:
    #         effect_list.remove(self.effect)
    #     new_effect = random.choice(effect_list)
    #     self.effect = new_effect
    #     return new_effect

    # def effect_set_raw(self, effect_data):
    #     """Sends a raw dict containing effect data to the device.

    #     The dict given must match the json structure specified in the API docs."""
    #     data = {"write": effect_data}
    #     self.__put("effects", data)

    # def effect_details(self, name):
    #     """Returns the dict containing details for the effect specified"""
    #     data = {"write": {"command": "request",
    #                       "animName": name}}
    #     return self.__put("effects", data)

    # def effect_details_all(self):
    #     """Returns a dict containing details for all effects on the device"""
    #     data = {"write": {"command": "requestAll"}}
    #     return self.__put("effects", data)

    # def effect_delete(self, name):
    #     """Removed the specified effect from the device"""
    #     data = {"write": {"command": "delete",
    #                       "animName": name}}
    #     self.__put("effects", data)

    # def effect_rename(self, old_name, new_name):
    #     """Renames the specified effect saved on the device to a new name"""
    #     data = {"write": {"command": "rename",
    #                       "animName": old_name,
    #                       "newName": new_name}}
    #     self.__put("effects", data)
