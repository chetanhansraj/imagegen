# imagegen
make images
# AI Image Generator

A Flask-based AI image generator using Stability AI API with fallback to local placeholder generation.

## Features
- Text-to-image generation using Stability AI
- Multiple aspect ratios and formats
- Image gallery
- Download and copy functionality
- Responsive web interface

## Environment Variables
- `STABILITY_API_KEY`: Your Stability AI API key (optional)
- `PORT`: Port for the application (Railway sets this automatically)

## Deployment
This app is configured for Railway deployment.

## Local Development
1. Install dependencies: `pip install -r requirements.txt`
2. Run: `python app.py`
3. Open: http://localhost:8000
