#!/usr/bin/env python3
"""
Environment and Configuration Test Script
Test your Deep Research Agent setup before running the main application.
"""

import os
import sys
from dotenv import load_dotenv

def test_environment():
    """Test environment configuration"""
    print("🔍 Deep Research Agent - Environment Test")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Test 1: Python version
    print(f"\n1. Python Version: {sys.version}")
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        return False
    else:
        print("✅ Python version OK")
    
    # Test 2: Environment variables
    print("\n2. Environment Variables:")
    
    google_key = os.getenv("GOOGLE_API_KEY")
    if google_key:
        print(f"✅ GOOGLE_API_KEY: Set (length: {len(google_key)})")
    else:
        print("❌ GOOGLE_API_KEY: Not set (required)")
    
    brightdata_token = os.getenv("BRIGHTDATA_API_TOKEN")
    if brightdata_token:
        print(f"✅ BRIGHTDATA_API_TOKEN: Set (length: {len(brightdata_token)})")
    else:
        print("⚠️ BRIGHTDATA_API_TOKEN: Not set (web research will be limited)")
    
    # Test 3: Dependencies
    print("\n3. Dependencies:")
    
    dependencies = [
        ("chainlit", "Chainlit UI framework"),
        ("langchain_google_genai", "Google Gemini integration"),
        ("langgraph", "LangGraph for agent workflow"),
        ("mcp", "Model Context Protocol"),
        ("langchain_mcp_adapters", "MCP adapters for LangChain"),
        ("dotenv", "Environment variable loading")
    ]
    
    missing_deps = []
    
    for dep_name, description in dependencies:
        try:
            __import__(dep_name)
            print(f"✅ {dep_name}: Available")
        except ImportError:
            print(f"❌ {dep_name}: Missing ({description})")
            missing_deps.append(dep_name)
    
    # Test 4: Google API test
    print("\n4. Google Gemini API Test:")
    if google_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            
            model = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash-exp",
                google_api_key=google_key,
                temperature=0.1
            )
            
            # Simple test
            response = model.invoke("Hello, respond with just 'API working'")
            if "API working" in response.content:
                print("✅ Google Gemini API: Working")
            else:
                print(f"⚠️ Google Gemini API: Unexpected response: {response.content}")
        except Exception as e:
            print(f"❌ Google Gemini API: Error - {str(e)}")
    else:
        print("❌ Google Gemini API: Cannot test (API key missing)")
    
    # Test 5: MCP Server test
    print("\n5. MCP Server Test:")
    if brightdata_token:
        try:
            import subprocess
            result = subprocess.run(["npx", "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("✅ NPX available for MCP server")
                
                # Test BrightData MCP
                try:
                    result = subprocess.run(
                        ["npx", "@brightdata/mcp", "--help"], 
                        capture_output=True, 
                        text=True, 
                        timeout=15,
                        env={**os.environ, "API_TOKEN": brightdata_token}
                    )
                    if result.returncode == 0:
                        print("✅ BrightData MCP: Available")
                    else:
                        print("⚠️ BrightData MCP: May need installation")
                except Exception as e:
                    print(f"⚠️ BrightData MCP: {str(e)}")
            else:
                print("❌ NPX not available (Node.js required)")
        except Exception as e:
            print(f"❌ MCP Server: Error - {str(e)}")
    else:
        print("⚠️ MCP Server: Cannot test (BrightData token missing)")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Summary:")
    
    if missing_deps:
        print(f"❌ Missing dependencies: {', '.join(missing_deps)}")
        print("   Run: pip install -r requirements.txt")
    
    if not google_key:
        print("❌ Google API key required")
        print("   Add GOOGLE_API_KEY to your .env file")
    
    if not brightdata_token:
        print("⚠️ BrightData token recommended for web research")
        print("   Add BRIGHTDATA_API_TOKEN to your .env file")
    
    # Configuration recommendations
    print("\n🔧 Configuration Steps:")
    print("1. Copy .env.example to .env")
    print("2. Add your Google API key to .env")
    print("3. Add your BrightData API token to .env (optional)")
    print("4. Install missing dependencies: pip install -r requirements.txt")
    print("5. Test again with: python test_environment.py")
    
    return len(missing_deps) == 0 and google_key is not None

if __name__ == "__main__":
    success = test_environment()
    
    if success:
        print("\n🎉 Environment test passed! You can run the Deep Research Agent.")
        print("   Start with: chainlit run app.py")
    else:
        print("\n⚠️ Environment test failed. Please fix the issues above.")
        sys.exit(1)
