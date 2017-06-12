import requests
import socket
import select
import time

def discover_auroras(seek_time=30.0):
    # Returns a dict containing deyails of each Aurora found on the network.
    # A dict entry contains: nl-deviceid: IP Address

    SSDP_IP = "239.255.255.250"
    SSDP_PORT = 1900
    SSDP_MX = 3
    SSDP_ST = "nanoleaf_aurora:light"

    req = ['M-SEARCH * HTTP/1.1',
           'HOST: ' + SSDP_IP + ':' + str(SSDP_PORT),
           'MAN: "ssdp:discover"',
           'ST: ' + SSDP_ST,
           'MX: ' + str(SSDP_MX)]
    req = '\r\n'.join(req).encode('utf-8')

    def check_for_aurora(r):
        if SSDP_ST not in r:
            return
        nlDeviceid = ''
        ipAddress = ''
        for line in r.split("\n"):
            if "Location:" in line:
                ipAddress = line.replace("Location:", "").strip() \
                                  .replace("http://", "") \
                                  .replace(":16021", "")
            if "nl-deviceid:" in line:
                nlDeviceid = line.replace("nl-deviceid:", "").strip()

        if nlDeviceid != '' and ipAddress != '':
            auroras[nlDeviceid] = ipAddress
        return auroras       

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, SSDP_MX)
    sock.bind((socket.gethostname(), 9090))
    sock.sendto(req, (SSDP_IP, SSDP_PORT))
    sock.setblocking(False)

    success = True
    statusMessage = 'OK'
    auroras = {}

    timeout = time.time() + seek_time
    while time.time() < timeout:
        try:
            ready = select.select([sock], [], [], 5)
            if ready[0]:
                response = sock.recv(1024).decode("utf-8")
                check_for_aurora(response)
        except socket.error as err:
            success = False
            statusMessage = "Socket error while discovering nanoleaf devices!: " + err
            sock.close()
            break

    return (success, statusMessage, auroras)


def generate_auth_token(ip_address):
    """
    Generates an auth token for the Aurora at the given IP address. 
    
    You must first press and hold the power button on the Aurora for about 5-7 seconds, 
    until the white LED flashes briefly.
    """
    success = False
    statusMessage = 'Unknown problem encountered'
    authToken = ''

    url = "http://" + ip_address + ":16021/api/v1/new"
    r = requests.post(url)
    if r.status_code == 200:
        success = True
        statusMessage = 'OK'
        authToken = r.json()['auth_token']
    elif r.status_code == 401:
        success = False
        statusMessage = "Not Authorized!"
    elif r.status_code == 403:
        success = False
        statusMessage = "Access Forbidden to nanoleaf device! Press and hold the power button for 5-7 seconds first! (Light will begin flashing)"
    elif r.status_code == 422:
        success = False
        statusMessage = "Unprocessable Entity! Network problem?"
    return (success, statusMessage, authToken)









