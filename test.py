
from huawei import huwei_hg8245h

MQTT_IP= '192.168.1.8'
MQTT_PORT=1883

ic = huwei_hg8245h(
    cookie_file='cookies_huawei.json', 
    url='http://192.168.1.100/',
    username='Support',
    password='theworldinyourhand'
    )
ic.check_login()
zte_local_net_status ={}
zte_local_net_status = ic.wlan_statistic()
zte_local_net_status["lan_info"] = ic.lan_info()
zte_local_net_status["associated_device"]= ic.wlan_associated_device()

ic.to_node_exporter( zte_local_net_status,"metrics")