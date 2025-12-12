import http.server
import socketserver
import webbrowser
import os
import sys

# Define the port
PORT = 8000

# Change directory to the script's directory to ensure we serve the right files
# This ensures that no matter where you run the script from, it serves the project root
# os.chdir(os.path.dirname(os.path.abspath(__file__)))
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
os.chdir(project_root)

Handler = http.server.SimpleHTTPRequestHandler

# Allow reuse of the address to prevent "Address already in use" errors on restart
socketserver.TCPServer.allow_reuse_address = True

try:
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}/"
        print(f"\n--------------------------------------------------")
        print(f" Servidor iniciado en: {url}")
        print(f" Presiona Ctrl+C en la terminal para detenerlo.")
        print(f"--------------------------------------------------\n")
        
        # Open the browser automatically
        webbrowser.open(url)
        
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\nServidor detenido.")
    sys.exit(0)
except OSError as e:
    print(f"\nError: No se pudo iniciar el servidor en el puerto {PORT}.")
    print(f"Detalles: {e}")
    print("Intenta cerrar otras instancias de python o usa otro puerto.")
