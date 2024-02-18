import requests
import base64 
import re
import json
import logging
from pathlib import Path
from re import sub

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)

class huwei_hg8245h:
    def __init__(self,  url , username, password, cookie_file):
        self.HUAWEI_USERNAME = username
        self.HUAWEI_PASSWORD = password
        self.HUAWEI_BASE_URL =url
        self.HUAWEI_HEADERS = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': self.HUAWEI_BASE_URL,
        'Referer': self.HUAWEI_BASE_URL,
        'Cookie': 'Cookie=body:Language:english:id=-1'
        }
        self.COOKIE_FILE = cookie_file

        self.session = requests.session()
        logging.info("load cookie from : {0}".format(self.COOKIE_FILE) )
        self.session.cookies.update(self.load_cookie())

    def load_cookie(self):
        cookies = json.loads(Path(self.COOKIE_FILE).read_text()) 
        return requests.utils.cookiejar_from_dict(cookies) 

    def lan_info(self):
        html = self.session.get(self.HUAWEI_BASE_URL+'html/amp/ethinfo/ethinfo.asp').text

        regex = r"LANStats\(\"(\S+)\",\"(\S+)\",\"(\S+)\",\"(\S+)\",\"(\S+)\"\)"
        matches = re.findall(regex, html)
        return self.translate(matches, "eth_info")
    
    def wlan_associated_device(self):
        html = self.session.get(self.HUAWEI_BASE_URL+'html/amp/wlaninfo/getassociateddeviceinfo.asp').text

        regex = r"stAssociatedDevice\(\"(\S+)\",(\S+)\",\"(\d+)\",\"(\d+)\",\"(\d+)\",\"(\S+)\",\"(\S+)\",\"(\d+)\",\"(\d+)\",\"(\S+)\",\"(\d+)\",\"(\d+)\""
        matches = re.findall(regex, html)
        return self.translate(matches, "wlan_associated_device")
    
    def wlan_statistic(self):
        html = self.session.get(self.HUAWEI_BASE_URL+'html/amp/wlaninfo/wlaninfo.asp').text

        regex = r"stPacketInfo\(\"(\S+)\",\"(\d+)\",\"(\d+)\",\"(\d+)\",\"(\d+)"
        matches = re.findall(regex, html)
        output = {}
        output["wlan_packet"] = self.translate(matches, "wlan_packet")
        
        regex = r"stStats\(\"(\S+)\",\"(\d+)\",\"(\d+)\",\"(\d+)\",\"(\d+)"
        matches = re.findall(regex, html)

        output["wlan_stats"] =self.translate(matches, "wlan_stats")
        return output
    

    
    def check_login(self):
        output = self.session.get(self.HUAWEI_BASE_URL)
        if output.text.find("txt_Username") != -1 or output.status_code == 404:
            logging.error('need login')
            self.post_login()
            self.session.cookies.update(self.load_cookie())

    def login_token(self):
        html = self.session.post(self.HUAWEI_BASE_URL+'asp/GetRandCount.asp')
        return html.text.replace('ï»¿','')
    
    def translate(self,main_object, key):
        map = {
            "wlan_stats":{"prefix":"WLAN", "fields":["out_error","in_error","out_discard","in_discard"]},
            "wlan_packet":{"prefix":"WLAN", "fields":["total_bytes_sent","total_packets_sent","total_bytes_received","total_packets_received"]},
            "wlan_associated_device":{"prefix":"DEV", "fields":["mac","uptime","rx_rate","hw_txrate","hw_rssi","hw_noise","hw_snr","hw_singalquality","hw_workingmode","hw_wmmstatus","hw_psmode"]},
            "eth_info":{"prefix":"LAN", "fields":["total_bytes_received","total_packets_received","total_bytes_sent","total_packets_sent"]}
        }
        try:
            output = {}
            config = map[key]
            for index1, record in enumerate(main_object):
                if  key == "eth_info":
                    regex = r"LANPort.(\d+).Statistics" 
                    matches = re.findall(regex, record[0])
                    object_key = config["prefix"]+matches[0]
                elif key == "wlan_associated_device":
                    object_key = str(record[1]).replace("\\x3a",":").replace('"','')
                else:
                    object_key = config["prefix"]+str(index1)

                output[object_key] = {}
                for index, field_name in enumerate(config["fields"]):
                    if field_name == "hw_rssi":
                        value = str(record[index+1]).replace("\\x2d","-")
                    else:
                        value = record[index+1]
                    output[object_key][field_name] = value
                
            return output
        except Exception as e:
            logging.error("key translation error")
            logging.error(str(e))


    def post_login(self):
        self.session = requests.session()
        token= self.login_token()
        logging.info("login token: {0}".format(token) )

        byte_data = self.HUAWEI_PASSWORD.encode('utf-8')
        encoded_data = base64.b64encode(byte_data)

        login_form ={
            'UserName':self.HUAWEI_USERNAME,
            'PassWord' :'dGhld29ybGRpbnlvdXJoYW5k',
            'x.X_HW_Token': str(token) 
        }
        print(login_form)
        logging.info("attempt to login" )
        html =self.session.post(self.HUAWEI_BASE_URL+'login.cgi', data=login_form, headers=self.HUAWEI_HEADERS)
        output = html.text
        logging.info("saving cookie" )
        cookies = requests.utils.dict_from_cookiejar(self.session.cookies)  # turn cookiejar into dict
        Path(self.COOKIE_FILE).write_text(json.dumps(cookies)) 


        if output.find("txt_Username") != -1:
            logging.error('login failed')
            return False
        else:
            return True
    def snake_case(self,s):
        # Replace hyphens with spaces, then apply regular expression substitutions for title case conversion
        # and add an underscore between words, finally convert the result to lowercase
        return '_'.join(
            sub('([A-Z][a-z]+)', r' \1',
            sub('([A-Z]+)', r' \1',
            s.replace('-', ' '))).split()).lower()
    
    def to_node_exporter(self,object, filename):
        f = open(filename, "w")
        counter = ['total_bytes_sent','total_packets_sent','total_packets_received','total_bytes_received'
                'in_discard','in_error','out_multicas','in_bytes','out_pkts','out_discard',
                'in_unicast','out_unicast','in_multicast','out_error','out_bytes','in_pkts']
        for main_stat in object:
            for device in object[main_stat]:
                for stat in object[main_stat][device]:
                    clean_stat = self.snake_case(stat)
                    value = object[main_stat][device][stat]
                    if clean_stat in counter:
                        type ='#TYPE  counter'
                    else:
                        type ='#TYPE  gauge'
                    try:
                        int(value)
                    except ValueError:
                        continue
                        
                    txt  = "{4}\n{0}_{2} {{device=\"{1}\"}} {3}\n".format(
                        main_stat,
                        str(device).lower(),
                        clean_stat,
                        value,
                        type
                        )
                    f.write(txt)
        f.close()