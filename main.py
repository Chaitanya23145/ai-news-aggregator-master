from app.daily_runner import run_daily_pipeline
from app.api import app  # Expose ASGI app for Vercel and serverless detection

# Ensure handler is defined for standard serverless adapters
handler = app


def main(hours: int = 24, top_n: int = 10):
    return run_daily_pipeline(hours=hours, top_n=top_n)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("web", "--web", "serve", "--serve", "ui"):
        import uvicorn
        import socket
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
        # Check if port is free, otherwise fallback to 8080 or 8001
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("0.0.0.0", port))
            sock.close()
        except OSError:
            if len(sys.argv) <= 2:
                port = 8080

        print(f"🚀 Starting AI Intelligence Hub Dashboard on http://localhost:{port}")
        uvicorn.run("app.api:app", host="0.0.0.0", port=port, reload=False)
        sys.exit(0)
    
    hours = 24
    top_n = 10
    
    args = sys.argv[1:]
    if args and args[0].lower() in ("pipeline", "--pipeline", "run", "--run"):
        args = args[1:]
    
    if len(args) > 0 and args[0].isdigit():
        hours = int(args[0])
    if len(args) > 1 and args[1].isdigit():
        top_n = int(args[1])
    
    result = main(hours=hours, top_n=top_n)
    exit(0 if result["success"] else 1)

