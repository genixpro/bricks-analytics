from wsgiref.simple_server import make_server
from server import main


if __name__ == '__main__':
    server = make_server('0.0.0.0', 1806, main(None))
    print("Serving on port 1806: http://localhost:1806/")
    server.serve_forever()

