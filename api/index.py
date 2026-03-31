from app import app

# Vercel serverless handler
def handler(request):
    return app(request)
