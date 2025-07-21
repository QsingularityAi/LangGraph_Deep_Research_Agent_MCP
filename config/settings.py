"""
Configuration management for Deep Research Agent
"""

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Configuration class for Deep Research Agent"""
    
    # API Configuration
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash-exp")
    BRIGHTDATA_API_TOKEN: str = os.getenv("BRIGHTDATA_API_TOKEN", "")
    BROWSER_AUTH: str = os.getenv("BROWSER_AUTH", "")
    WEB_UNLOCKER_ZONE: str = os.getenv("WEB_UNLOCKER_ZONE", "map_web_unlocker")
    
    # Agent Configuration
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    TIMEOUT: float = float(os.getenv("TIMEOUT", "90.0"))
    
    # Research Configuration
    MAX_SUB_QUESTIONS: int = int(os.getenv("MAX_SUB_QUESTIONS", "5"))
    DEFAULT_RESEARCH_TIME: int = int(os.getenv("DEFAULT_RESEARCH_TIME", "15"))
    
    # Debug Configuration
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"
    VERBOSE_LOGGING: bool = os.getenv("VERBOSE_LOGGING", "false").lower() == "true"
    
    @classmethod
    def validate_config(cls) -> Dict[str, Any]:
        """Validate configuration and return status"""
        status = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Required configurations
        if not cls.GOOGLE_API_KEY:
            status["errors"].append("GOOGLE_API_KEY is required")
            status["valid"] = False
        
        # Optional but recommended
        if not cls.BRIGHTDATA_API_TOKEN:
            status["warnings"].append("BRIGHTDATA_API_TOKEN not set - web research will be limited")
        
        return status
    
    @classmethod
    def get_mcp_server_params(cls) -> Dict[str, Any]:
        """Get MCP server parameters"""
        return {
            "command": "npx",
            "env": {
                "API_TOKEN": cls.BRIGHTDATA_API_TOKEN,
                "BROWSER_AUTH": cls.BROWSER_AUTH,
                "WEB_UNLOCKER_ZONE": cls.WEB_UNLOCKER_ZONE,
                "NODE_OPTIONS": "--max-old-space-size=4096",
            },
            "args": ["@brightdata/mcp"],
            "timeout": 30.0,
        }
    
    @classmethod
    def get_environment_status(cls) -> str:
        """Get formatted environment status"""
        status = "**🔧 Environment Status:**\n"
        
        if cls.GOOGLE_API_KEY:
            status += "✅ **Google API:** Configured\n"
        else:
            status += "❌ **Google API:** Missing (required)\n"
        
        if cls.BRIGHTDATA_API_TOKEN:
            status += "✅ **BrightData API:** Configured (Web research enabled)\n"
            research_mode = "🌐 **Research Mode:** Real-time web search + LLM synthesis"
        else:
            status += "⚠️ **BrightData API:** Missing (Knowledge-based only)\n"
            research_mode = "📚 **Research Mode:** Knowledge-based analysis"
        
        status += f"{research_mode}\n"
        return status
