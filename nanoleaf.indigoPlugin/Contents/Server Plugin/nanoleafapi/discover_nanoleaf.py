import re
import requests
import socket
import select
import time
from subprocess import Popen, PIPE


def discover_nanoleafs(overriddenHostIpAddress, seek_time=10.0):
    # Returns a dict containing details of each nanoleaf deviceType found on the network.
    # A dict entry contains: nl-deviceid: IP Address

    SSDP_IP = "239.255.255.250"
    SSDP_PORT = 1900
    SSDP_MX = 3
    SSDP_ST = "ssdp:all"
    SSDP_LIST = ["nanoleaf_aurora:light", "nanoleaf:nl29", "nanoleaf:nl42"]

    # req = ['M-SEARCH * HTTP/1.1',
    #        'HOST: ' + SSDP_IP + ':' + str(SSDP_PORT),
    #        'MAN: "ssdp:discover"',
    #        'ST: ' + SSDP_ST,
    #        'MX: ' + str(SSDP_MX)]

    req = ['M-SEARCH * HTTP/1.1',
           'HOST: ' + SSDP_IP + ':' + str(SSDP_PORT),
           'MAN: "ssdp:discover"',
           'MX: ' + str(SSDP_MX),
           'ST: ' + SSDP_ST,
           ' ',
           ' ']
    req = '\r\n'.join(req).encode('utf-8')

    # Start of inline definition
    def check_for_nanoleaf(r):
        # discovered_nanoleafs = dict()
        if any(nanoleaf in r for nanoleaf in SSDP_LIST):  # See http://net-informations.com/python/basics/multiple.htm
            pass
        else:
            return dict()
        # print(f"\n\n*********** Nanoleaf found in SSDP_LIST:\n{r}")
        nanoleaf_device_id = ''
        nanoleaf_ip_address = ''
        nanoleaf_device_name = ''
        nanoleaf_type = ""
        for line in r.split("\n"):
            if "ST:" in line:
                nanoleaf_type = line.replace("ST:", "").strip()
            if "Location:" in line:
                nanoleaf_ip_address = line.replace("Location:", "").strip() \
                                  .replace("http://", "") \
                                  .replace(":16021", "")
            if "nl-deviceid:" in line:
                nanoleaf_device_id = line.replace("nl-deviceid:", "").strip()
            if "nl-devicename" in line:
                nanoleaf_device_name = line.replace("nl-devicename:", "").strip()

        if nanoleaf_device_id != "" and nanoleaf_ip_address != "":
            nanoleaf_mac = ""
            try:
                pid = Popen(["/usr/sbin/arp", "-n", nanoleaf_ip_address], stdout=PIPE)
                s = pid.communicate()[0].decode("utf-8")
                # print(f"MAC ADDRESS [1-S] for {nanoleaf_device_name} at {nanoleaf_ip_address}: {s}\n")
                nanoleaf_mac = re.search(r"(([a-f\d]{1,2}\:){5}[a-f\d]{1,2})", s).groups()[0]
                # print(f"MAC ADDRESS [2-MAC] for {nanoleaf_device_name} at {nanoleaf_ip_address}: {nanoleaf_mac}\n")
            except Exception as exception_error:
                print(f"Standard error detected in MAC processing 'discover_nanoleaf': {exception_error}")

            discovered_nanoleafs[nanoleaf_device_id] = dict()
            discovered_nanoleafs[nanoleaf_device_id]["NANOLEAF_TYPE"] = nanoleaf_type
            discovered_nanoleafs[nanoleaf_device_id]["NANOLEAF_IP_ADDRESS"] = nanoleaf_ip_address
            discovered_nanoleafs[nanoleaf_device_id]["NANOLEAF_MAC"] = nanoleaf_mac
            discovered_nanoleafs[nanoleaf_device_id]["NANOLEAF_DEVICE_NAME"] = nanoleaf_device_name

            print(f"check_for_nanoleaf: {discovered_nanoleafs}")

        return discovered_nanoleafs
    # End of inline definition

    sockBindHost = "Unknown"
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, SSDP_MX)

        if overriddenHostIpAddress != '':
            sockBindHost = overriddenHostIpAddress
        else:
            sockBindHost = socket.gethostname()
        sock.bind((sockBindHost, 9090))
        sock.sendto(req, (SSDP_IP, SSDP_PORT))
        sock.setblocking(False)
    except socket.error as err:
        success = False
        statusMessage = f"Socket error while setting up host '{sockBindHost}' discovery of nanoleaf devices!: {err}"
        sock.close()
        return (success, statusMessage, {})

    success = True
    statusMessage = f"Discovery established for host '{sockBindHost}'"
    discovered_nanoleafs = dict()

    timeout = time.time() + seek_time
    while time.time() < timeout:
        try:
            ready = select.select([sock], [], [], 5)
            if ready[0]:
                response = sock.recv(1024).decode("utf-8")
                # print(u"Response:\n{0}\n------------------------".format(response))
                result = check_for_nanoleaf(response)
                if len(result) > 0:
                    print(f"=================> Discovered Nanoleaf: {result}")
                    discovered_nanoleafs.update(result)
        except socket.error as err:
            success = False
            statusMessage = f"Socket error while host '{sockBindHost}' discovering nanoleaf devices!: {err}"
            sock.close()
            break

    print(f"=================> Final list of Discovered Nanoleafs: {discovered_nanoleafs}")

    return success, statusMessage, discovered_nanoleafs


def generate_auth_token(ip_address):
    """
    Generates an auth token for the canvas at the given IP address. 
    
    You must first press and hold the power button on the canvas for about 5-7 seconds, 
    until the white LED flashes briefly.
    """
    success = False
    status_message = "Unknown problem encountered"
    auth_token = ""

    url = "http://" + ip_address + ":16021/api/v1/new"
    r = requests.post(url)
    if r.status_code == 200:
        success = True
        status_message = 'OK'
        auth_token = r.json()['auth_token']
    elif r.status_code == 401:
        success = False
        status_message = "Not Authorized!"
    elif r.status_code == 403:
        success = False
        status_message = "Access Forbidden to nanoleaf canvas device! Press and hold the power button for 5-7 seconds first! (Light will begin flashing)"
    elif r.status_code == 422:
        success = False
        status_message = "Unprocessable Entity! Network problem?"
    return (success, status_message, auth_token)









