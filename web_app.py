from flask import Flask, render_template, request, jsonify
import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

app = Flask(__name__)

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Deep Research Agent</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
            .header { text-align: center; background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            .chat-container { background: white; border-radius: 10px; height: 500px; overflow-y: auto; padding: 20px; margin: 20px 0; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            .input-container { display: flex; gap: 10px; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            input[type="text"] { flex: 1; padding: 15px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px; }
            button { padding: 15px 30px; background: #007bff; color: white; border: none; cursor: pointer; border-radius: 5px; font-size: 16px; }
            button:hover { background: #0056b3; }
            button:disabled { background: #ccc; cursor: not-allowed; }
            .message { margin: 15px 0; padding: 15px; border-radius: 10px; }
            .user { background: #e3f2fd; border-left: 4px solid #2196f3; }
            .assistant { background: #f5f5f5; border-left: 4px solid #4caf50; }
            .loading { color: #666; font-style: italic; background: #fff3cd; border-left: 4px solid #ffc107; }
            .error { background: #f8d7da; border-left: 4px solid #dc3545; color: #721c24; }
            pre { white-space: pre-wrap; font-family: Arial, sans-serif; }
            .features { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
            .feature { background: white; padding: 15px; border-radius: 10px; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            .feature-icon { font-size: 30px; margin-bottom: 10px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔍 Deep Research Agent</h1>
            <p>Your AI-powered research assistant with enhanced source attribution</p>
        </div>
        
        <div class="features">
            <div class="feature">
                <div class="feature-icon">🔍</div>
                <h3>Deep Research</h3>
                <p>Breaks down complex questions into sub-questions</p>
            </div>
            <div class="feature">
                <div class="feature-icon">📚</div>
                <h3>Source Attribution</h3>
                <p>Provides clickable sources with titles and dates</p>
            </div>
            <div class="feature">
                <div class="feature-icon">🎯</div>
                <h3>Quality Scoring</h3>
                <p>Rates research quality and completeness</p>
            </div>
            <div class="feature">
                <div class="feature-icon">💡</div>
                <h3>Follow-up Questions</h3>
                <p>Suggests related research topics</p>
            </div>
        </div>
        
        <div class="chat-container" id="chat">
            <div class="message assistant">
                <strong>🤖 Research Assistant:</strong><br>
                Welcome! I'm your enhanced Deep Research Agent. I can help you research any topic by:
                <ul>
                    <li>Breaking down complex questions into manageable sub-questions</li>
                    <li>Conducting systematic web research using multiple sources</li>
                    <li>Providing detailed, well-sourced answers with clickable links</li>
                    <li>Offering research quality scores and follow-up suggestions</li>
                </ul>
                <strong>Try asking me about:</strong>
                <ul>
                    <li>"What is the latest large language model launch in AI industry?"</li>
                    <li>"How does climate change affect global food security?"</li>
                    <li>"What are the current trends in renewable energy technology?"</li>
                </ul>
            </div>
        </div>
        
        <div class="input-container">
            <input type="text" id="question" placeholder="Enter your research question..." />
            <button id="researchBtn" onclick="askQuestion()">🔍 Research</button>
        </div>
        
        <script>
            async function askQuestion() {
                const question = document.getElementById('question').value;
                if (!question.trim()) return;
                
                const chat = document.getElementById('chat');
                const btn = document.getElementById('researchBtn');
                
                // Disable button and show loading state
                btn.disabled = true;
                btn.innerHTML = '⏳ Researching...';
                
                // Add user message
                chat.innerHTML += `<div class="message user"><strong>You:</strong> ${question}</div>`;
                
                // Add loading message
                const loadingId = 'loading-' + Date.now();
                chat.innerHTML += `<div class="message loading" id="${loadingId}">
                    🔍 <strong>Research in Progress...</strong><br>
                    • Generating research plan<br>
                    • Searching for current information<br>
                    • Analyzing multiple sources<br>
                    • Compiling comprehensive report<br>
                    <em>This may take 1-2 minutes...</em>
                </div>`;
                
                // Clear input
                document.getElementById('question').value = '';
                
                // Scroll to bottom
                chat.scrollTop = chat.scrollHeight;
                
                try {
                    const response = await fetch('/research', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ question: question })
                    });
                    
                    const data = await response.json();
                    
                    // Remove loading message
                    document.getElementById(loadingId).remove();
                    
                    if (data.error) {
                        chat.innerHTML += `<div class="message error"><strong>❌ Error:</strong><br>${data.error}</div>`;
                    } else {
                        // Add response with better formatting
                        chat.innerHTML += `<div class="message assistant">
                            <strong>🔍 Research Results:</strong><br>
                            <pre>${data.answer}</pre>
                        </div>`;
                    }
                    
                } catch (error) {
                    document.getElementById(loadingId).remove();
                    chat.innerHTML += `<div class="message error"><strong>❌ Network Error:</strong><br>${error.message}</div>`;
                }
                
                // Re-enable button
                btn.disabled = false;
                btn.innerHTML = '🔍 Research';
                
                // Scroll to bottom
                chat.scrollTop = chat.scrollHeight;
            }
            
            // Allow Enter key to submit
            document.getElementById('question').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    askQuestion();
                }
            });
        </script>
    </body>
    </html>
    '''

@app.route('/research', methods=['POST'])
def research():
    try:
        data = request.json
        question = data.get('question', '')
        
        if not question:
            return jsonify({'error': 'No question provided'}), 400
        
        # Import and use the agent
        from agent import DeepResearchAgent
        agent = DeepResearchAgent()
        
        # Run the research
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(agent.ainvoke({"input": question}))
        
        # Extract the output
        if hasattr(result.get("agent_outcome"), "return_values"):
            output = result["agent_outcome"].return_values.get("output", "No output generated")
        else:
            output = str(result.get("agent_outcome", "No result"))
        
        return jsonify({'answer': output})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Deep Research Agent Web Interface...")
    print("📊 Enhanced with improved source attribution!")
    print("🔍 Access at: http://localhost:8080")
    app.run(debug=True, host='0.0.0.0', port=8080)
