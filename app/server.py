from flask import Flask, jsonify, request
from flask_cors import CORS
from dataset.expert import expert_struct_output
from app.chat import single_method,chain_method

app = Flask(__name__)
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
    
@app.route('/',methods=['GET'])
def home():
    return jsonify({'text':'this is the blunder guard server'}), 200