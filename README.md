# Overview

The Autolog nanoleaf Controller is a plugin for version 7+ of the [Indigo Home Automation system][1]. It enables you to control [nanoleaf][2] devices directly from Indigo. It enables local LAN control of nanoleaf Devices without having to use an internet connection.

The Version 1 series of the plugin is implemented using Indigo Dimmer Devices to control the nanoleaf devices and fully supporting the new built-in RGBW controls in Indigo 7. In addition to the standard controls, the plugin provides a mechanism to discover nanoleaf devices and to set effects already defined on the nanoleaf device.

The plugin makes extensive use of the code base (modified) of the [nanoleaf library by Software-2][3] for which much thanks are due :)

It is **strongly recommended** to read this documentation to familiarise yourself with the how the plugin works.

[1]: https://www.indigodomo.com
[2]: https://nanoleaf.me
[3]: https://github.com/software-2/nanoleaf