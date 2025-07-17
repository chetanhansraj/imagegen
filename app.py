#!/usr/bin/env python3
"""
AI Image Generator for Railway Deployment
Flask backend with Stability AI integration and fallbacks
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import base64
import os
import time
import json
from datetime import datetime
import urllib3
from PIL import Image, ImageDraw, ImageFont
import io

# Disable SSL warnings for development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configuration - Railway will set environment variables
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY", "sk-OZHK53eG1CkZDS8ygr142tWJ0LDSw4P4xu8WfrlZDLMgxcSF")
STABILITY_API_URL = "https://api.stability.ai/v2beta/stable-image/generate/core"
OUTPUT_DIR = "generated_images"
PORT = int(os.getenv("PORT", 8000))  # Railway sets PORT automatically

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Alternative APIs (you can add your own keys here)
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", None)
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY", None)

def check_api_credits():
    """Check if Stability AI API has credits"""
    try:
        headers = {
            "authorization": f"Bearer {STABILITY_API_KEY}",
            "accept": "application/json"
        }
        
        response = requests.get(
            "https://api.stability.ai/v1/user/account",
            headers=headers,
            verify=False,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Credits remaining: {data.get('credits', 'Unknown')}")
            return True
        elif response.status_code == 402:
            print("❌ No credits remaining on API key")
            return False
        else:
            print(f"⚠️ API check returned: {response.status_code}")
            return True
            
    except Exception as e:
        print(f"⚠️ Could not check API credits: {e}")
        return True

def create_placeholder_image(prompt, width=512, height=512, format="webp"):
    """Create a placeholder image when APIs fail"""
    try:
        img = Image.new('RGB', (width, height), color='lightblue')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        except:
            font = None
            small_font = None
        
        # Draw gradient-like background
        for y in range(height):
            color_val = int(173 + (82 * y / height))
            draw.line([(0, y), (width, y)], fill=(color_val, color_val + 20, 255))
        
        # Draw text
        if font:
            draw.text((width//2, height//4), "🎨 AI Image", 
                     font=font, fill='white', anchor='mm')
            
            # Prompt (wrapped)
            words = prompt.split()
            lines = []
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                if len(test_line) > 30:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        lines.append(word)
                        current_line = []
                else:
                    current_line.append(word)
            
            if current_line:
                lines.append(' '.join(current_line))
            
            start_y = height//2 - (len(lines) * 20)//2
            for i, line in enumerate(lines[:4]):
                draw.text((width//2, start_y + i*25), line, 
                         font=small_font, fill='navy', anchor='mm')
            
            draw.text((width//2, height - height//4), 
                     "Generated locally", 
                     font=small_font, fill='white', anchor='mm')
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format=format.upper())
        img_bytes.seek(0)
        
        return True, img_bytes.getvalue()
        
    except Exception as e:
        print(f"Error creating placeholder: {e}")
        return False, str(e)

def generate_image_with_stability(prompt, output_format="webp", aspect_ratio="1:1"):
    """Generate image using Stability AI API"""
    
    headers = {
        "authorization": f"Bearer {STABILITY_API_KEY}",
        "accept": "image/*"
    }
    
    data = {
        "prompt": prompt,
        "output_format": output_format,
        "aspect_ratio": aspect_ratio
    }
    
    print(f"Generating image for prompt: {prompt[:50]}...")
    
    try:
        response = requests.post(
            STABILITY_API_URL,
            headers=headers,
            files={"none": ''},
            data=data,
            timeout=60
        )
    except requests.exceptions.SSLError as e:
        print(f"SSL Error: {e}. Retrying without SSL verification...")
        try:
            response = requests.post(
                STABILITY_API_URL,
                headers=headers,
                files={"none": ''},
                data=data,
                verify=False,
                timeout=60
            )
        except Exception as fallback_error:
            return False, f"Connection failed: {str(fallback_error)}"
    except Exception as e:
        return False, f"Request failed: {str(e)}"
    
    if response.status_code == 200:
        print("✅ Image generated successfully with Stability AI!")
        return True, response.content
    elif response.status_code == 402:
        return False, "PAYMENT_REQUIRED"
    else:
        try:
            error_data = response.json()
            error_message = error_data.get('message', f'HTTP {response.status_code}')
        except:
            error_message = f"HTTP {response.status_code}: {response.text[:200]}"
        
        print(f"API Error: {error_message}")
        return False, error_message

def generate_image_fallback(prompt, output_format="webp", aspect_ratio="1:1"):
    """Fallback image generation using multiple methods"""
    
    # Method 1: Try Stability AI
    print("🔄 Trying Stability AI...")
    success, result = generate_image_with_stability(prompt, output_format, aspect_ratio)
    if success:
        return True, result, "Stability AI"
    
    print(f"❌ Stability AI failed: {result}")
    
    # Method 2: Create placeholder image
    print("🔄 Creating placeholder image...")
    
    # Determine dimensions based on aspect ratio
    width, height = 512, 512
    if aspect_ratio == "16:9":
        width, height = 672, 378
    elif aspect_ratio == "9:16":
        width, height = 378, 672
    elif aspect_ratio == "4:3":
        width, height = 512, 384
    elif aspect_ratio == "3:4":
        width, height = 384, 512
    
    success, result = create_placeholder_image(prompt, width, height, output_format)
    if success:
        return True, result, "Local Placeholder"
    
    return False, "All generation methods failed", None

def save_image_to_file(image_data, filename=None, output_format="webp"):
    """Save image data to file"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"generated_{timestamp}.{output_format}"
    
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    try:
        with open(filepath, 'wb') as file:
            file.write(image_data)
        print(f"💾 Image saved to: {filepath}")
        return True, filepath
    except Exception as e:
        print(f"❌ Error saving image: {e}")
        return False, str(e)

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('.', 'image_generator.html')

@app.route('/generate', methods=['POST', 'OPTIONS'])
def generate_image_api():
    """API endpoint for image generation with fallbacks"""
    
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response
    
    try:
        data = request.get_json()
        if not data or 'prompt' not in data:
            return jsonify({'error': 'No prompt provided'}), 400
        
        prompt = data['prompt'].strip()
        if not prompt:
            return jsonify({'error': 'Empty prompt provided'}), 400
        
        output_format = data.get('output_format', 'webp')
        aspect_ratio = data.get('aspect_ratio', '1:1')
        save_to_file = data.get('save_to_file', True)
        
        print(f"\n=== Image Generation Request ===")
        print(f"Prompt: {prompt}")
        print(f"Format: {output_format}")
        print(f"Aspect Ratio: {aspect_ratio}")
        print(f"Save to file: {save_to_file}")
        
        # Generate image with fallback methods
        success, result, method = generate_image_fallback(prompt, output_format, aspect_ratio)
        
        if not success:
            response = jsonify({'error': result})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 500
        
        # Convert to base64 for JSON response
        image_base64 = base64.b64encode(result).decode('utf-8')
        
        response_data = {
            'success': True,
            'image_data': image_base64,
            'prompt': prompt,
            'format': output_format,
            'aspect_ratio': aspect_ratio,
            'generation_method': method
        }
        
        # Optionally save to file
        if save_to_file:
            filename = f"generated_{int(time.time())}.{output_format}"
            file_success, filepath = save_image_to_file(result, filename, output_format)
            if file_success:
                response_data['saved_file'] = filepath
        
        print(f"✅ Image generated successfully using: {method}")
        
        response = jsonify(response_data)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
        
    except Exception as e:
        print(f"❌ Error in generate_image_api: {e}")
        response = jsonify({'error': f'Internal server error: {str(e)}'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@app.route('/test', methods=['GET'])
def test_connection():
    """Test endpoint with API status check"""
    
    api_status = check_api_credits()
    
    response_data = {
        'status': 'ok',
        'message': 'Image generator server is running on Railway!',
        'timestamp': datetime.now().isoformat(),
        'stability_api_available': api_status,
        'fallback_available': True,
        'environment': 'Railway Production' if os.getenv('RAILWAY_ENVIRONMENT') else 'Local Development'
    }
    
    response = jsonify(response_data)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response



@app.route('/list-images', methods=['GET'])
def list_images():
    """List all generated images"""
    try:
        files = os.listdir(OUTPUT_DIR)
        image_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
        
        response = jsonify({
            'images': sorted(image_files, reverse=True),
            'count': len(image_files)
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    except Exception as e:
        response = jsonify({'error': str(e)})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@app.route('/health')
def health_check():
    """Health check endpoint for Railway"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/gallery', methods=['GET'])
def gallery():
    """Return list of generated images"""
    try:
        # Ensure directory exists
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            return jsonify({'images': [], 'count': 0})
        
        # Get all image files
        files = os.listdir(OUTPUT_DIR)
        image_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
        
        # Format for frontend
        images = []
        for filename in sorted(image_files, reverse=True):
            prompt = filename.replace('.webp', '').replace('.png', '').replace('.jpg', '').replace('_', ' ')
            if len(prompt) > 50:
                prompt = prompt[:50] + "..."
            
            images.append({
                'filename': filename,
                'prompt': prompt
            })
        
        print(f"Gallery found {len(images)} images")
        
        response = jsonify({
            'images': images,
            'count': len(images)
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
        
    except Exception as e:
        print(f"Gallery error: {e}")
        response = jsonify({'error': str(e), 'images': [], 'count': 0})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@app.route('/images/<filename>')
def serve_image(filename):
    """Serve individual images"""
    try:
        response = send_from_directory('generated_images', filename)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
    except Exception as e:
        return jsonify({'error': 'Image not found'}), 404

if __name__ == '__main__':
    print("🎨 Starting AI Image Generator for Railway...")
    print(f"📁 Images will be saved to: {os.path.abspath(OUTPUT_DIR)}")
    print(f"🌐 Server will run on port: {PORT}")
    print("🔧 Available generation methods:")
    print("   1. ✨ Stability AI (if credits available)")
    print("   2. 🎭 Local Placeholder (always available)")
    print("\n" + "="*50)
    
    # Check API status on startup
    check_api_credits()
    
    # Railway deployment configuration
    app.run(host='0.0.0.0', port=PORT, debug=False)
