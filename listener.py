from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Callback received! Check console. You can close this window.")

        query_components = parse_qs(urlparse(self.path).query)
        state = query_components.get("user_id_validation_state", [""])[0]
        print(f"Captured user_id_validation_state: {state}")

if __name__ == "__main__":
    server_address = ('', 8080)
    httpd = HTTPServer(server_address, RequestHandler)
    print("Listening on port 8080...")
    httpd.serve_forever()