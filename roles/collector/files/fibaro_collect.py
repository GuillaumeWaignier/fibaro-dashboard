from flask import Flask
from datetime import datetime
import requests
import configparser
from elasticapm.contrib.flask import ElasticAPM
from elasticsearch import Elasticsearch


app = Flask(__name__)

# Load configuration from file
config = configparser.ConfigParser()
config.read("config.ini")

# Access configuration values
FIBARO_LOGIN = config.get('App', 'FIBARO_LOGIN')
FIBARO_PASSWORD = config.get('App', 'FIBARO_PASSWORD')
FIBARO_URL = config.get('App', 'FIBARO_URL')
ELASTICSEARCH_LOGIN = config.get('App', 'ELASTICSEARCH_LOGIN')
ELASTICSEARCH_PASSWORD = config.get('App', 'ELASTICSEARCH_PASSWORD')
ELASTICSEARCH_URL = config.get('App', 'ELASTICSEARCH_URL')
APM_URL = config.get('App', 'APM_URL')
EVENTS_INDEX = config.get('App', 'EVENTS_INDEX')
CLIMATE_INDEX = config.get('App', 'CLIMATE_INDEX')
POWER_INDEX = config.get('App', 'POWER_INDEX')
RESOURCES_INDEX = config.get('App', 'RESOURCES_INDEX')
THERMOSTAT_INDEX = config.get('App', 'THERMOSTAT_INDEX')

# APM
app.config['ELASTIC_APM'] = {
  'SERVICE_NAME': 'fibaro-collector',
  'SERVER_URL': APM_URL,
}
apm = ElasticAPM(app)



# Define the device type mapping
device_type_mapping = {
    "com.fibaro.humiditySensor": "humiditySensor",
    "com.fibaro.temperatureSensor": "temperatureSensor",
    "com.fibaro.windSensor": "windSensor",
    "com.fibaro.philipsHueLight": "philipsHueLight",
    "com.fibaro.lightSensor": "lightSensor",
    "com.fibaro.FGWP102": "wallPlug",
    "com.fibaro.binarySensor": "binarySensor",
    "com.fibaro.motionSensor": "motionSensor",
    "com.fibaro.FGMS001v2": "motionSensor",
    "com.fibaro.binarySwitch": "binarySwitch",
    "com.fibaro.FGWDS221": "binarySwitch",
    "com.fibaro.FGDW002": "doorSensor",
    "com.fibaro.FGKF601": "keyFob",
    "com.fibaro.multilevelSensor": "multilevelSensor",
    "com.fibaro.FGWR111": "blind",
    "com.fibaro.FGR223": "blind",
    "com.fibaro.hvacSystemHeat": "hvacSystemHeat",
    "com.fibaro.windowSensor": "windowSensor",
    "com.fibaro.electricMeter": "electricMeter",
    "com.fibaro.powerMeter": "powerMeter",
    "com.fibaro.energyMeter": "energyMeter",
    "com.fibaro.FGCD001": "coSensor",
    "com.fibaro.FGSS001": "smokeSensor",
    "com.fibaro.FGWD111": "walliDimmer",
    "com.fibaro.floodSensor": "floodSensor",
    "com.fibaro.heatDetector": "heatDetector"
}

iot_type_mapping = {
  "com.fibaro.temperatureSensor": "temperature",
  "com.fibaro.humiditySensor": "humidity",
  "com.fibaro.lightSensor": "light",
  "com.fibaro.windSensor": "wind",
  "uv": "uv"
}

cached_devices = []
cached_scenes = []
LAST_DATE = None


es = Elasticsearch([ELASTICSEARCH_URL], basic_auth=(ELASTICSEARCH_LOGIN, ELASTICSEARCH_PASSWORD))

## ROOM
def get_all_rooms():
    global rooms
    rooms = requests.get(f'{FIBARO_URL}/api/rooms', auth=(FIBARO_LOGIN, FIBARO_PASSWORD), headers={'Accept': 'application/json'}, verify=False).json()

####################################
#                                  #
#          Event                   #
#                                  #
####################################

def cache_all_device():
    print("Cache all devices")
    get_all_rooms()
    devices = requests.get(f'{FIBARO_URL}/api/devices', auth=(FIBARO_LOGIN, FIBARO_PASSWORD), verify=False).json()
    device_number = len(devices)
    cached_devices.clear()
    for i in range(device_number):
        device = devices[i]
        id = device['id']
        name = device['name'].replace(' ', '_')  # workaround: space produce crash during ES ation (pb of charset ?)
        roomID = device['roomID']
        type = device['type']
        type = device_type_mapping.get(type, type)
        room = next((r['name'] for r in rooms if r['id'] == roomID), None)
        cached_devices.append({"id": id, "name": name, "room": room, "type": type})
    return device_number

def cache_all_scene():
    print("Cache all scenes")
    scenes = requests.get(f'{FIBARO_URL}/api/scenes', auth=(FIBARO_LOGIN, FIBARO_PASSWORD), verify=False).json()
    scene_number = len(scenes)
    cached_scenes.clear()
    for i in range(scene_number):
        scene = scenes[i]
        id = scene['id']
        name = scene['name'].replace(' ', '_')  # workaround: space produce crash during ES indexation (pb of charset ?)
        cached_scenes.append({"id": id, "name": name})
    return scene_number

def enrich_event(event):
    global events
    event_type = event['objects'][0]['type']
    if event_type == 'device':
        id = event['data']['id']
        metainfo = next((device for device in cached_devices if device['id'] == id), None)
        if metainfo:
            event['name'] = metainfo['name']
            event['room'] = metainfo['room']
            event['deviceType'] = metainfo['type']
    elif event_type == 'scene':
        id = event['data']['id']
        metainfo = next((scene for scene in cached_scenes if scene['id'] == id), None)
        if metainfo:
            event['name'] = metainfo['name']

    sourceType = event.get('sourceType')
    if sourceType == 'device':
        id = event['sourceId']
        metainfo = next((device for device in cached_devices if device['id'] == id), None)
        if metainfo:
            event['sourceName'] = metainfo['name']
            event['room'] = metainfo['room']
            event['deviceType'] = metainfo['type']

def iterate_over_all_events():
    global events
    if LAST_DATE:
        events = requests.get(f'{FIBARO_URL}/api/events/history?from={LAST_DATE}&numberOfRecords=500', auth=(FIBARO_LOGIN, FIBARO_PASSWORD), verify=False).json()
    else:
        events = requests.get(f'{FIBARO_URL}/api/events/history?numberOfRecords=500', auth=(FIBARO_LOGIN, FIBARO_PASSWORD), verify=False).json()

    events_number = len(events)
    for i in range(events_number):
        event = events[i]
        enrich_event(event)
        es.index(index=f'{EVENTS_INDEX}-alias', document=event)
    return events_number


def get_last_event_id():
    global LAST_DATE
    body = {"size":1, "sort":[{"timestamp": {"order": "desc"}}], "_source": "timestamp"}
    res = es.search(index=f'{EVENTS_INDEX}-alias', body=body)
    hits = res['hits']['hits']
    hits_number = len(hits)
    for i in range(hits_number):
        hit = hits[i]
        LAST_DATE = hit['_source']['timestamp']
        LAST_DATE += 1


cache_all_device()
cache_all_scene()


####################################
#                                  #
#          IOT info                #
#                                  #
####################################

def iterate_over_all_devices():
    global rooms
    now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    devices = requests.get(f"{FIBARO_URL}/api/devices", auth=(FIBARO_LOGIN, FIBARO_PASSWORD), verify=False).json()
    deviceNumber = len(devices)

    for i in range(deviceNumber):
        device = devices[i]
        visible = device.get('visible')

        if visible:
            collect_climate(device, now)
            collect_power(device, now)
            collect_thermostat(device, now)
    return deviceNumber


def collect_climate(device, now):
    global rooms

    type = device.get('type')
    type = iot_type_mapping.get(type, None)
    name = device.get('name')

    if type is None and name == "uv":
        type = "uv"

    if type is None:
        return

    roomID = device.get('roomID')
    room = next((room['name'] for room in rooms if room['id'] == roomID), None)
    body = {
        "@timestamp": now,
        "id": device.get('id'),
        "name": name,
        "value": device.get('properties', {}).get('value'),
        "roomID": roomID,
        "room": room,
        "type" : type
    }
    es.index(index=f'{CLIMATE_INDEX}-alias', document=body)



def collect_power(device, now):
    global rooms

    power = device.get('properties', {}).get('power')
    type = device.get('type')
    roomID = device.get('roomID')
    room = next((room['name'] for room in rooms if room['id'] == roomID), None)

    if power is not None:
        body = {
            "@timestamp": now,
            "id": device.get('id'),
            "name": device.get('name'),
            "power": power,
            "energy": device.get('properties', {}).get('energy'),
            "roomID": roomID,
            "room": room
        }
        es.index(index=f'{POWER_INDEX}-alias', document=body)
    elif type == "com.fibaro.powerMeter":
        body = {
            "@timestamp": now,
            "id": device.get('id'),
            "name": device.get('name'),
            "power": device.get('properties', {}).get('value'),
            "roomID": roomID,
            "room": room
        }
        es.index(index=f'{POWER_INDEX}-alias', document=body)
    elif type == "com.fibaro.energyMeter":
        body = {
            "@timestamp": now,
            "id": device.get('id'),
            "name": device.get('name'),
            "energy": device.get('properties', {}).get('value'),
            "roomID": roomID,
            "room": room
        }
        es.index(index=f'{POWER_INDEX}-alias', document=body)



def collect_thermostat(device, now):
    global rooms

    baseType = device.get('baseType')
    if baseType == "com.fibaro.hvacSystem":
        roomID = device.get('roomID')
        room = next((room['name'] for room in rooms if room['id'] == roomID), None)
        body = {
            "@timestamp": now,
            "id": device.get('id'),
            "name": device.get('name'),
            "status": device.get('properties', {}).get('log'),
            "mode": device.get('properties', {}).get('thermostatMode'),
            "temperature": device.get('properties', {}).get('heatingThermostatSetpoint'),
            "roomID": roomID,
            "room": room
        }
        es.index(index=f'{THERMOSTAT_INDEX}-alias', document=body)




####################################
#                                  #
#          Resources               #
#                                  #
####################################

def collect_hc3_resources():
    now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    resources_data = requests.get(f"{FIBARO_URL}/api/diagnostics", auth=(FIBARO_LOGIN, FIBARO_PASSWORD), verify=False).json()

    memory_body = {
        "@timestamp": now,
        "memory": {
            "free": resources_data.get('memory', {}).get('free'),
            "cache": resources_data.get('memory', {}).get('cache'),
            "buffer": resources_data.get('memory', {}).get('buffers'),
            "used": resources_data.get('memory', {}).get('used')
        },
        "storage": resources_data.get('storage', {}).get('internal', [{}])[0].get('used')
    }
    es.index(index=f'{RESOURCES_INDEX}-alias', document=memory_body)

    cpus = resources_data.get('cpuLoad', [])
    for cpu in cpus:
        cpu_body = {
            "@timestamp": now,
            "cpuName": cpu.get('name'),
            "user": cpu.get('user'),
            "nice": cpu.get('nice'),
            "system": cpu.get('system'),
            "idle": cpu.get('idle')
        }
        es.index(index=f'{RESOURCES_INDEX}-alias', document=cpu_body)



####################################
#                                  #
#          REST API                #
#                                  #
####################################

@app.route("/index/event")
def index_event():
    get_last_event_id()
    events_number = iterate_over_all_events()
    date_string = datetime.fromtimestamp(LAST_DATE).strftime("%Y-%m-%d %H:%M:%S")
    return f'Indexed {events_number} events from {date_string}'

@app.route("/index/iot")
def index_iot():
    deviceNumber = iterate_over_all_devices()
    return f'Indexed {deviceNumber} iot data devices'

@app.route("/index/resource")
def index_resource():
    collect_hc3_resources()
    return f'Indexed resources'

@app.route("/cache/device")
def cache_device():
    device_number = cache_all_device()
    return f'Cached {device_number} devices'


@app.route("/cache/scene")
def cache_scene():
    scene_number = cache_all_scene()
    return f'Cached {scene_number} scenes'


if __name__ == "__main__":
    app.run()
