import os
from dotenv import load_dotenv
from app import create_app

# Load environment variables from .env file
load_dotenv()

app = create_app()

if __name__ == '__main__':
    # Running in debug mode during local development
    port = int(os.environ.get('PORT', 5000))
    app.run(host='127.0.0.1', port=port, debug=True)
