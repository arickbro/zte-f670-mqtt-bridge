import paho.mqtt.publish as publish
import json
from zte import zte_f670l

MQTT_IP= '192.168.1.8'
MQTT_PORT=1883

ic = zte_f670l(
    cookie_file='/home/pi/zte-f670-mqtt-bridge/cookies.json', 
    url='http://192.168.1.1/',
    username='admin',
    password='Telkomdso123'
    )
ic.check_login()
zte_local_net_status = ic.zte_local_net_status()
publish.single("zte/gpon/f670l/local_net_status", json.dumps(zte_local_net_status), hostname=MQTT_IP, port=MQTT_PORT)
ic.to_node_exporter('', zte_local_net_status)

#zte_internet = ic.zte_internet()
#publish.single("zte/gpon/f670l/internet", json.dumps(zte_internet), hostname=MQTT_IP, port=MQTT_PORT)
