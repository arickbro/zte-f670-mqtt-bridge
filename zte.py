import requests
import hashlib
import re
import json
import logging
import xmltodict
from pathlib import Path
from re import sub

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)

class zte_f670l:
    def __init__(self,  url , username, password, cookie_file):
        self.ZTE_USERNAME = username
        self.ZTE_PASSWORD = password
        self.ZTE_BASE_URL =url
        self.ZTE_HEADERS = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': self.ZTE_BASE_URL,
        'Referer': self.ZTE_BASE_URL
        }
        self.COOKIE_FILE = cookie_file

        self.session = requests.session()
        logging.info("load cookie from : {0}".format(self.COOKIE_FILE) )
        self.session.cookies.update(self.load_cookie())

    def load_cookie(self):
        cookies = json.loads(Path(self.COOKIE_FILE).read_text()) 
        return requests.utils.cookiejar_from_dict(cookies) 

    def zte_internet(self):
        output = {}
        #need to open the page to be able to retrieve the data
        self.session.get(self.ZTE_BASE_URL+'?_type=menuView&_tag=ponopticalinfo&Menu3Location=0')

        html = self.session.get(self.ZTE_BASE_URL+'?_type=menuData&_tag=optical_info_lua.lua').text
        main_object = xmltodict.parse(html)
        output['optical_info'] = self.translate(main_object,'OBJ_PON_OPTICALPARA_ID', 0) 
        output['optical_power_on_time'] = self.translate(main_object,'OBJ_PON_POWERONTIME_ID', 0) 
        
        self.session.get(self.ZTE_BASE_URL+'?_type=menuView&_tag=ethWanStatus&Menu3Location=0')
        html = self.session.get(self.ZTE_BASE_URL+'?_type=menuData&_tag=wan_internetstatus_lua.lua&TypeUplink=2&pageType=1').text
        main_object = xmltodict.parse(html)
        output['wan_internetstatus'] = self.translate(main_object,'ID_WAN_COMFIG', 0)
        return output

    def zte_local_net_status(self):
        output = {}
        self.session.get(self.ZTE_BASE_URL+'?_type=menuView&_tag=localNetStatus&Menu3Location=0')

        html = self.session.get(self.ZTE_BASE_URL+'?_type=menuData&_tag=status_lan_info_lua.lua').text
        main_object = xmltodict.parse(html)
        output['status_lan_info'] = self.translate(main_object,'OBJ_PON_PORT_BASIC_STATUS_ID', 0) 

        html = self.session.get(self.ZTE_BASE_URL+'?_type=menuData&_tag=wlan_wlanstatus_lua.lua&TypeUplink=2&pageType=1').text
        main_object = xmltodict.parse(html)
        output['wlan_wlanstatus'] = self.translate(main_object,'OBJ_WLANAP_ID', 0) 
        output['wlan_client_configdrv_id'] = self.translate(main_object,'OBJ_WLANCONFIGDRV_ID', 0) 

        html = self.session.get(self.ZTE_BASE_URL+'?_type=menuData&_tag=wlan_client_stat_lua.lua&TypeUplink=2&pageType=1').text
        main_object = xmltodict.parse(html)
        output['wlan_client_stat'] = self.translate(main_object,'OBJ_WLAN_AD_ID', 0) 
        output['wlan_client_stat_id'] = self.translate(main_object,'OBJ_WLANAP_ID', 0) 
        
        
        return output


    def check_login(self):
        output = self.session.get(self.ZTE_BASE_URL).text
        if output.find('Please login.') != -1:
            logging.error('need login')
            self.post_login()
            self.session.cookies.update(self.load_cookie())

    def generate_login_token(self, token):
        m = hashlib.sha256()
        m.update((self.ZTE_PASSWORD+token).encode('utf-8'))
        return m.hexdigest()

    def login_entry(self):
        #{"lockingTime":0,"loginErrMsg":"","promptMsg":"","sess_token":"WIdv0cVB6zaTGAGR1aIfhluU"}
        html = self.session.get(self.ZTE_BASE_URL+'?_type=loginData&_tag=login_entry', headers=self.ZTE_HEADERS)
        return html.json()


    def login_token(self):
        #<ajax_response_xml_root>40891370</ajax_response_xml_root>
        html = self.session.get(self.ZTE_BASE_URL+'?_type=loginData&_tag=login_token', headers=self.ZTE_HEADERS)
        matches = re.findall(r"(\d+)", html.text)
        return matches[0]
    
    def translate(self,main_object,parent, key):
        try:
            object = main_object['ajax_response_xml_root'][parent]
            output = {}
            if isinstance(object['Instance'], list):
                Instance = object['Instance']
            else:
                Instance = [object['Instance']]
            for i in Instance:
                object_key = i['ParaValue'][key]
                output[object_key] = {}
                for index, object_param in enumerate(i['ParaName']):
                    output[object_key][object_param] = i['ParaValue'][index]
      
            return output
        except Exception as e:
            logging.error("key translation error")
            logging.error(str(e))


    def post_login(self):
        self.session = requests.session()
        entry= self.login_entry()
        logging.info("session token: {0}".format(entry['sess_token']) )

        token= self.login_token()
        logging.info("login token: {0}".format(token) )

        #Telkomdso12340891370 -> sha256  -> eeb48656668ff79445c24f1267fc393a2221561b52baf781743a4380fbe9c031

        login_form ={
            'action' :'login',
            'Username':self.ZTE_USERNAME,
            'Password' :self.generate_login_token(token),
            '_sessionTOKEN': str(entry['sess_token']) 
        }
        logging.info("attempt to login" )
        html =self.session.post(self.ZTE_BASE_URL+'?_type=loginData&_tag=login_entry', data=login_form, headers=self.ZTE_HEADERS)
        output = html.text

        logging.info("saving cookie" )
        cookies = requests.utils.dict_from_cookiejar(self.session.cookies)  # turn cookiejar into dict
        Path(self.COOKIE_FILE).write_text(json.dumps(cookies)) 

        logging.info("refresh base url" )
        output = self.session.get(self.ZTE_BASE_URL).text

        if output.find('Please login.') != -1:
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
            
                    txt  = "{4}\n{0}_{2} {{device={1}}} {3}\n".format(
                        main_stat,
                        device.lower(),
                        clean_stat,
                        value,
                        type
                        )
                    f.write(txt)
        f.close()