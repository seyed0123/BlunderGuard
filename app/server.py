from flask import Flask, jsonify, request,send_from_directory
from flask_cors import CORS
from dataset.expert import expert_struct_output
from app.chat import single_method,chain_method
import os

REACT_BUILD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "chess-frontend", "build"))

if not os.path.exists(os.path.join(REACT_BUILD_DIR, "index.html")):
    raise RuntimeError(f"React build not found in {REACT_BUILD_DIR}. Run 'bun run build' first.")

app = Flask(__name__,static_folder=None)
CORS(app, resources={r"/*": {"origins": ['*']}})

def analyze(before_fen,after_fen,analyze_method):
    stockfish_output = expert_struct_output(before_fen,after_fen)
    return analyze_method(stockfish_output)

@app.route('/chain',methods=['POST'])
def chain():
    try:
        after_fen = request.json.get('after')
        before_fen = request.json.get('before')
    except Exception as e:
        return jsonify({'error':'unexpected input format'}), 400
    llm_output = analyze(before_fen,after_fen,chain_method)
    return jsonify({'text':llm_output}), 200

@app.route('/single',methods=['POST'])
def single():
    try:
        after_fen = request.json.get('after')
        before_fen = request.json.get('before')
    except Exception as e:
        return jsonify({'error':'unexpected input format'}), 400
    llm_output = analyze(before_fen,after_fen,single_method)
    return jsonify({'text':llm_output}), 200
    
@app.route('/health',methods=['GET'])
def home():
    return jsonify({'text':'this is the blunder guard server'}), 200

# Serve index.html for root
@app.route('/')
def serve_index():
    return send_from_directory(REACT_BUILD_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_public_assets(filename):
    # Only allow known safe public files to avoid security risk
    allowed = {'favicon.ico', 'favicon.png', 'manifest.json', 'robots.txt', 'logo192.png', 'logo512.png'}
    if filename in allowed:
        full_path = os.path.join(REACT_BUILD_DIR, filename)
        if os.path.exists(full_path):
            return send_from_directory(REACT_BUILD_DIR, filename)
    return "Not found", 404

@app.route('/static/<path:filename>')
def serve_static(filename):
    static_folder = os.path.join(REACT_BUILD_DIR, "static")
    full_path = os.path.join(static_folder, filename)
    
    if not os.path.exists(full_path):
        return "File not found", 404
    
    return send_from_directory(static_folder, filename)