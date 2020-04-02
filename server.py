from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver
import json
import cgi
import urllib.parse
from vk_handshake_worker import *

#Класс (json_name_workspace) - с строковыми константами для отправки/парсинга в джейсоне
class  jsnw():
    class amethod():
        handshake = ["handshake"]

    str_users = "users"
    str_method = "method"
    str_result = "result"
    str_result_description = "resultDescription"
    str_resultCode = "resultCode"

class Server(BaseHTTPRequestHandler):
	#===================================================================================================================
	#
	#													Api Methods
	#
	#===================================================================================================================

    def parse_parameters_and_run_API_amethod(self):
        parameters_string = self.path[2:]
        # Словарь с параметрами
        parameters_dict = urllib.parse.parse_qs(parameters_string)
        print(parameters_dict)
        # Проверяем не пустые ли параметры
        if parameters_string != "" :
            # Проверяем метод API, который надо запустить
            if jsnw.str_method in parameters_dict and parameters_dict[jsnw.str_method] == jsnw.amethod.handshake:
               self.make_response_for_handShakes_method(parameters_dict=parameters_dict)
            # Если параметр "method" не является одним из доступных списка API
            else :
                self.make_response_with_not_enought_params()
        # Если нет параметров
        else :
            self.wfile.write(json.dumps({
                jsnw.str_resultCode: "0",
                jsnw.str_result_description: "Success with nothing (No parameters given)." 
                }).encode())

    def make_response_for_handShakes_method(self, parameters_dict):
        # Проверяем наличие параметра "users"
        if jsnw.str_users in parameters_dict:
            users = list(parameters_dict['users'][0].split(","))
            # Проверяем что пришло 2 пользователя через запятую в параметре "users"
            if len(users) == 2:
                print("Users = " + users[0] + ", " + users[1])
                should_use_debug = False
                # Проверяем, что нужно использовать print в дебаге
                if ('shouldUseDebug' in parameters_dict) and (parameters_dict['shouldUseDebug'] == ['True']):
                    should_use_debug = True
                worker_result = VkWorker(debug=should_use_debug).get_chains(users[0],users[1])
                self.wfile.write(worker_result)
            # Если пришло не 2 пользователя через запятую в параметре "users"
            else:
                self.make_response_with_not_enought_params()
            # Если нет параметра "users"
        else:
            self.make_response_with_not_enought_params()

    def make_response_with_not_enought_params(self):
        self.wfile.write(json.dumps({
                    jsnw.str_resultCode: "-1",
                    jsnw.str_result_description: "Can not resolve request with this parameters." 
                    }).encode())

	#===================================================================================================================
	#
	#									Do not Change File under that braket
	#
	#===================================================================================================================
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_HEAD(self):
        self._set_headers()

    # GET sends back a Hello world message
    def do_GET(self):
        self._set_headers()
        self.parse_parameters_and_run_API_amethod()

    # POST echoes the message adding a JSON field
    def do_POST(self):
        ctype, pdict = cgi.parse_header(self.headers.getheader('content-type'))

        # refuse to receive non-json content
        if ctype != 'application/json':
            self.send_response(400)
            self.end_headers()
            return

        # read the message and convert it into a python dictionary
        length = int(self.headers.getheader('content-length'))
        message = json.loads(self.rfile.read(length))

        # add a property to the object, just to mess with data
        message['received'] = 'ok'

        # send the message back
        self._set_headers()
        self.wfile.write(json.dumps(message))


def run(server_class=HTTPServer, handler_class=Server, port=8088):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print('Starting httpd on port ' + str(port))
    httpd.serve_forever()


if __name__ == "__main__":
    from sys import argv

    if len(argv) == 2:
        run(port=int(argv[1]))
    else:
        run()
