from flask import Flask, request, render_template, redirect, url_for, jsonify
from flask_cors import CORS
import sqlite3
import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Gemini API configuration
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')  # Loaded from .env
GEMINI_MODEL = 'gemini-2.0-flash'  # Requested model; if invalid, try 'gemini-1.5-flash-latest'
GEMINI_API_URL = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            company TEXT,
            service TEXT NOT NULL,
            budget TEXT,
            timeline TEXT,
            message TEXT NOT NULL,
            newsletter BOOLEAN DEFAULT FALSE
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName')
        email = request.form.get('email')
        phone = request.form.get('phone', '')
        company = request.form.get('company', '')
        service = request.form.get('service')
        budget = request.form.get('budget', '')
        timeline = request.form.get('timeline', '')
        message = request.form.get('message')
        newsletter = 'newsletter' in request.form

        if not all([first_name, last_name, email, service, message]):
            return jsonify({'error': 'Missing required fields'}), 400

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO contacts (first_name, last_name, email, phone, company, service, budget, timeline, message, newsletter)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (first_name, last_name, email, phone, company, service, budget, timeline, message, newsletter))
        conn.commit()
        conn.close()

        return jsonify({'message': 'Form submitted successfully'})
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    error = None
    entries = None
    show = False

    if request.method == 'POST':
        password = request.form.get('password')
        if password == 'webnifyadmin':
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute('SELECT * FROM contacts ORDER BY id DESC')
            entries = c.fetchall()
            conn.close()
            show = True
        else:
            error = 'Incorrect password'

    return render_template('admin.html', show=show, entries=entries, error=error)

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get('message')
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        # Validate API key
        if not GEMINI_API_KEY:
            return jsonify({'error': 'API key not configured'}), 500

        # System prompt with Webnify context
        system_prompt = """
        You are Sarah, a support agent for Webnify, a premium digital solutions and AI innovation company founded by Animesh Gupta in 2025. Webnify specializes in custom web development, AI and machine learning, mobile app development, cloud solutions, cybersecurity, and digital strategy. The company is ISO 27001 certified, GDPR compliant, and trusted by over 500 clients, including Fortune 500 companies like Microsoft, Google, Amazon, Tesla, and Apple. Webnify has won over 50 awards, serves 25+ countries, and maintains a 99.9% uptime SLA. Animeh Gupta, the founder, is a visionary leader passionate about leveraging technology to drive business growth and innovation. Respond as Sarah, providing helpful, professional, and accurate information about Webnify's services, values, and achievements. If asked about Animeh Gupta, highlight his role as the founder and his commitment to digital excellence. Always align responses with Webnify's brand as a leader in digital transformation.
        """

        # Call Gemini API
        headers = {
            'Content-Type': 'application/json'
        }
        payload = {
            'contents': [
                {
                    'role': 'user',
                    'parts': [{'text': system_prompt + '\n\nUser: ' + user_message}]
                }
            ],
            'generationConfig': {
                'temperature': 0.7,
                'maxOutputTokens': 500
            }
        }
        response = requests.post(
            f'{GEMINI_API_URL}?key={GEMINI_API_KEY}',
            headers=headers,
            json=payload,
            timeout=10
        )

        # Check response status and log details for debugging
        if response.status_code != 200:
            print(f"Gemini API Error Response: {response.text}")  # Log for debugging
            return jsonify({'error': f'Gemini API request failed with status {response.status_code}: {response.text}'}), 500

        response_data = response.json()
        try:
            # Extract the text from the Gemini API response
            gemini_response = response_data['candidates'][0]['content']['parts'][0]['text'].strip()
            if not gemini_response:
                return jsonify({'error': 'Empty response from Gemini API'}), 500
        except (KeyError, IndexError) as e:
            print(f"Response Data: {response_data}")  # Log for debugging
            return jsonify({'error': f'Unexpected response format from Gemini API: {str(e)}'}), 500

        return jsonify({'response': gemini_response})

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {str(e)} - Response: {response.text if 'response' in locals() else 'No response'}")  # Log for debugging
        return jsonify({'error': f'Gemini API request failed: {str(e)}'}), 500
    except requests.exceptions.RequestException as e:
        print(f"Network Error: {str(e)}")  # Log for debugging
        return jsonify({'error': f'Network error during Gemini API request: {str(e)}'}), 500
    except Exception as e:
        print(f"General Error: {str(e)}")  # Log for debugging
        return jsonify({'error': f'Server error: {str(e)}'}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True)