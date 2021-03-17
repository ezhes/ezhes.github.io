#!/usr/bin/env python

from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess
# HTTPRequestHandler class
class testHTTPServer_RequestHandler(BaseHTTPRequestHandler):

       	# GET
       	def do_GET(self):
       				# Send response status code
       				self.send_response(200)

       				# Send headers
       				self.send_header('Content-type','text/html')
       				self.send_header("Cache-Control", "no-cache")
       				self.end_headers()

       				# Send message back to client
       				page = ""

       				if self.path == "/":
       					page = """
       					<html>
       					<head>
       					<meta name="apple-mobile-web-app-capable" content="yes">
       					<meta name="viewport" content="width=device-width">
       					<meta name="viewport" content="initial-scale=1.0">


       					<title>AirConPi</title>

       					<script>
       					function sendControl(forName) {
       					var r = new XMLHttpRequest();
       					r.open("GET","/" + forName);
       					r.setRequestHeader('Cache-Control', 'no-cache');
       					r.send();
       					}

       					</script>

       					</head>
       					<body bgcolor="#FFFFFF">
       					<h1>Control</h1>
       					<br/>
       					<input style=\"width:100%\" type='button' onclick='sendControl(\"POWER_OFF\")' value='Stop, clean' />
       					<br/>
       					<input style=\"width:100%\" type='button' onclick='sendControl(\"ON_COOL_F1_70\"); sendControl(\"POWER_OFF\")' value='Stop now' />
       					<br/>
       					<br/>
       					<h1>Cooling</h1>
       					<input style=\"width:100%\" type='button' onclick='sendControl(\"ON_COOL_F1_70_CLEAN\")' value='F1, 70'/>
       					<br/>
       					<input style=\"width:100%\" type='button' onclick='sendControl(\"ON_COOL_F2_70_CLEAN\")' value='F2, 70' />
       					<br/>
       					<input style=\"width:100%\" type='button' onclick='sendControl(\"ON_COOL_F3_70_CLEAN\")' value='F3, 70' />
       					<br/>
       					<input style=\"width:100%\" type='button' onclick='sendControl(\"ON_COOL_F3_65_CLEAN\")' value='F3, 65' />
       					<br/>
       					<br/>
       					<h1>Heating</h1>
       					<br/>
       					<input style=\"width:100%\" type='button' onclick='sendControl(\"ON_HEAT_F1_74_CLEAN\")' value='F1, 74' />
       					<br/>
       					<input style=\"width:100%\" type='button' onclick='sendControl(\"ON_HEAT_F2_74_CLEAN\")' value='F2, 74' />
       					<br/>
       					<input style=\"width:100%\" type='button' onclick='sendControl(\"ON_HEAT_F3_74_CLEAN\")' value='F2, 74' />
       					</body></html>
       					"""
       				else:
       					#We have a command, supposedly
       					print("executing " + str(["irsend", "SEND_ONCE","LG_AC",self.path.split("/")[1]]))
       					subprocess.run(["irsend", "SEND_ONCE","LG_AC",self.path.split("/")[1]])
       					page = "OK"
       				# Write content as utf-8 data
       				self.wfile.write(bytes(page, "utf8"))
       				return

def run():
       	print('starting server...')

       	# Server settings
       	# Choose port 8080, for port 80, which is normally used for a http server, you need root access
       	server_address = ('0.0.0.0', 8081)
       	httpd = HTTPServer(server_address, testHTTPServer_RequestHandler)
       	print('running server...')
       	httpd.serve_forever()


run()
