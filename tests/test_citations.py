#!/usr/bin/env python3
"""
Citation Testing Script for Deep Research Agent

Tests the citation extraction and formatting functionality to ensure
proper source attribution and web research validation.
"""

import sys
import os
import re
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from utils.helpers import extract_sources_from_text, format_research_output
    from config.settings import Config
    print("✅ Successfully imported project modules")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from project root with virtual environment activated")
    sys.exit(1)

def test_citation_extraction():
    """Test citation extraction from various text formats."""
    print("\n🔍 Testing Citation Extraction")
    print("=" * 40)
    
    # Test text with URLs
    test_text = """
    According to recent research from MIT (https://web.mit.edu/research/ai-safety), 
    AI safety regulations are evolving rapidly. The Stanford report 
    (https://stanford.edu/ai/report-2024) also discusses these developments.
    
    Sources:
    1. https://example.com/article1 - "AI Safety Guidelines 2024"
    2. https://arxiv.org/abs/2024.12345 - Research Paper on Safety
    """
    
    sources = extract_sources_from_text(test_text)
    
    print(f"Extracted {len(sources)} sources:")
    for i, source in enumerate(sources, 1):
        print(f"{i}. {source}")
    
    # Validate extraction
    expected_sources = [
        "https://web.mit.edu/research/ai-safety",
        "https://stanford.edu/ai/report-2024", 
        "https://example.com/article1",
        "https://arxiv.org/abs/2024.12345"
    ]
    
    found_all = all(any(expected in source for source in sources) for expected in expected_sources)
    
    if found_all and len(sources) >= len(expected_sources):
        print("✅ Citation extraction test PASSED")
        return True
    else:
        print("❌ Citation extraction test FAILED")
        print(f"Expected at least {len(expected_sources)} sources, found {len(sources)}")
        return False

def test_research_output_formatting():
    """Test research output formatting with proper citations."""
    print("\n📝 Testing Research Output Formatting")
    print("=" * 40)
    
    # Test data
    research_content = "AI safety is a critical concern in 2024."
    sources = [
        "https://example.com/ai-safety - AI Safety Report 2024",
        "https://research.org/study - Comprehensive AI Study"
    ]
    methodology = "web_research"
    quality_score = 85
    
    formatted_output = format_research_output(
        research_content, sources, methodology, quality_score
    )
    
    print("Formatted output:")
    print("-" * 20)
    print(formatted_output)
    print("-" * 20)
    
    # Validate formatting
    required_elements = [
        "Research Methodology: Web Research",
        "Quality Score: 85",
        "Sources:",
        "https://example.com/ai-safety",
        "https://research.org/study"
    ]
    
    all_present = all(element in formatted_output for element in required_elements)
    
    if all_present:
        print("✅ Research output formatting test PASSED")
        return True
    else:
        print("❌ Research output formatting test FAILED")
        print("Missing required elements in formatted output")
        return False

def test_web_research_indicators():
    """Test web research vs knowledge-based indicators."""
    print("\n🌐 Testing Research Method Indicators")
    print("=" * 40)
    
    # Test web research format
    web_output = format_research_output(
        "Content from web search", 
        ["https://example.com"], 
        "web_research", 
        90
    )
    
    # Test knowledge-based format  
    knowledge_output = format_research_output(
        "Content from training data",
        [],
        "knowledge_based",
        75
    )
    
    # Validate indicators
    web_indicators = ["Web Research", "Sources:", "https://"]
    knowledge_indicators = ["Knowledge-Based", "training data", "No real-time"]
    
    web_valid = any(indicator in web_output for indicator in web_indicators)
    knowledge_valid = any(indicator in knowledge_output for indicator in knowledge_indicators)
    
    print(f"Web research format valid: {web_valid}")
    print(f"Knowledge-based format valid: {knowledge_valid}")
    
    if web_valid and knowledge_valid:
        print("✅ Research method indicators test PASSED")
        return True
    else:
        print("❌ Research method indicators test FAILED")
        return False

def test_url_validation():
    """Test URL validation and extraction patterns."""
    print("\n🔗 Testing URL Validation")
    print("=" * 40)
    
    test_urls = [
        "https://www.example.com/article",
        "http://research.org/paper.pdf", 
        "https://arxiv.org/abs/2024.12345",
        "not-a-url",
        "ftp://old-protocol.com",
        "https://valid-domain.co.uk/path"
    ]
    
    # URL regex pattern (simplified version of what's used in helpers)
    url_pattern = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')
    
    valid_urls = []
    for url in test_urls:
        if url_pattern.match(url):
            valid_urls.append(url)
    
    print(f"Valid URLs found: {len(valid_urls)}")
    for url in valid_urls:
        print(f"  ✓ {url}")
    
    # Should find 4 valid HTTP/HTTPS URLs
    expected_valid = 4
    if len(valid_urls) == expected_valid:
        print("✅ URL validation test PASSED")
        return True
    else:
        print(f"❌ URL validation test FAILED - Expected {expected_valid}, found {len(valid_urls)}")
        return False

def main():
    """Run all citation tests."""
    print("🧪 Deep Research Agent - Citation Testing")
    print("=" * 50)
    
    # Check configuration
    try:
        config_status = Config.validate_config()
        print(f"✅ Configuration loaded")
        print(f"Google API configured: {'Yes' if Config.GOOGLE_API_KEY else 'No'}")
        print(f"BrightData configured: {'Yes' if Config.BRIGHTDATA_API_TOKEN else 'No'}")
        if not config_status["valid"]:
            print(f"⚠️  Configuration errors: {config_status['errors']}")
    except Exception as e:
        print(f"⚠️  Configuration warning: {e}")
    
    # Run tests
    tests = [
        test_citation_extraction,
        test_research_output_formatting, 
        test_web_research_indicators,
        test_url_validation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test error: {e}")
    
    # Results
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All citation tests PASSED!")
        print("\n✅ Your citation system is working correctly!")
        print("✅ Research output formatting is proper")
        print("✅ Web research indicators are functional")
        return True
    else:
        print(f"⚠️  {total - passed} test(s) failed")
        print("\n🔧 Recommendations:")
        print("1. Check that all project modules are properly organized")
        print("2. Verify virtual environment is activated")
        print("3. Ensure utils/helpers.py contains required functions")
        print("4. Review config/settings.py for proper configuration")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
