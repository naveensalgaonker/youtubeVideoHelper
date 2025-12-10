"""
AI handler module for generating summaries and categories using OpenAI or Google Gemini.
Includes retry logic and error handling for API calls.
"""

import logging
import os
from typing import Dict, Any, Tuple, Optional
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
import openai
import google.generativeai as genai

logger = logging.getLogger(__name__)


class AIHandler:
    """Handles AI-powered summarization and categorization using OpenAI or Gemini."""
    
    def __init__(self, provider: str = "openai", model: str = None):
        """
        Initialize AI handler with specified provider.
        
        Args:
            provider: 'openai' or 'gemini'
            model: Model name (optional, uses defaults from env)
        """
        self.provider = provider.lower()
        
        if self.provider == "openai":
            self.api_key = os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables")
            openai.api_key = self.api_key
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
            logger.info(f"Initialized OpenAI handler with model: {self.model}")
            
        elif self.provider == "gemini":
            self.api_key = os.getenv("GEMINI_API_KEY")
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY not found in environment variables")
            genai.configure(api_key=self.api_key)
            self.model = model or os.getenv("GEMINI_MODEL", "gemini-pro")
            self.gemini_model = genai.GenerativeModel(self.model)
            logger.info(f"Initialized Gemini handler with model: {self.model}")
            
        else:
            raise ValueError(f"Unsupported AI provider: {provider}. Use 'openai' or 'gemini'")
    
    def generate_summary_and_category(self, transcription: str, 
                                      video_title: str) -> Tuple[str, str]:
        """
        Generate summary and category for a video transcription.
        
        Args:
            transcription: Full video transcription text
            video_title: Video title for context
        
        Returns:
            Tuple of (summary, category)
        """
        if self.provider == "openai":
            return self._generate_with_openai(transcription, video_title)
        elif self.provider == "gemini":
            return self._generate_with_gemini(transcription, video_title)
    
    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIError)),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(3)
    )
    def _generate_with_openai(self, transcription: str, 
                             video_title: str) -> Tuple[str, str]:
        """
        Generate summary and category using OpenAI API.
        
        Args:
            transcription: Video transcription
            video_title: Video title
        
        Returns:
            Tuple of (summary, category)
        """
        # Truncate transcription if too long (to manage token limits)
        max_chars = 12000  # Roughly 3000 tokens
        truncated_transcription = transcription[:max_chars]
        if len(transcription) > max_chars:
            truncated_transcription += "... [truncated]"
            logger.warning(f"Transcription truncated from {len(transcription)} to {max_chars} characters")
        
        prompt = self._create_prompt(truncated_transcription, video_title)
        
        try:
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes and categorizes video content."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            result = response.choices[0].message.content.strip()
            summary, category = self._parse_response(result)
            
            logger.info(f"Generated summary with OpenAI - Category: {category}")
            return summary, category
            
        except openai.RateLimitError as e:
            logger.error(f"OpenAI rate limit exceeded: {str(e)}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error with OpenAI: {str(e)}")
            raise
    
    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(3)
    )
    def _generate_with_gemini(self, transcription: str, 
                             video_title: str) -> Tuple[str, str]:
        """
        Generate summary and category using Google Gemini API.
        
        Args:
            transcription: Video transcription
            video_title: Video title
        
        Returns:
            Tuple of (summary, category)
        """
        # Truncate transcription if too long
        max_chars = 15000  # Gemini has higher limits
        truncated_transcription = transcription[:max_chars]
        if len(transcription) > max_chars:
            truncated_transcription += "... [truncated]"
            logger.warning(f"Transcription truncated from {len(transcription)} to {max_chars} characters")
        
        prompt = self._create_prompt(truncated_transcription, video_title)
        
        try:
            response = self.gemini_model.generate_content(prompt)
            result = response.text.strip()
            summary, category = self._parse_response(result)
            
            logger.info(f"Generated summary with Gemini - Category: {category}")
            return summary, category
            
        except Exception as e:
            logger.error(f"Error with Gemini API: {str(e)}")
            raise
    
    def _create_prompt(self, transcription: str, video_title: str) -> str:
        """
        Create prompt for AI model.
        
        Args:
            transcription: Video transcription
            video_title: Video title
        
        Returns:
            Formatted prompt string
        """
        return f"""Analyze this YouTube video and provide a summary and category.

Video Title: {video_title}

Transcription:
{transcription}

Please provide:
1. A concise summary (2-3 sentences) of the main points and key takeaways
2. A category from this list: Education, Technology, Entertainment, Tutorial, News, Review, Gaming, Music, Science, Business, Health, Sports, Lifestyle, Comedy, Documentary, Other

Format your response EXACTLY as follows:
SUMMARY: [Your summary here]
CATEGORY: [Category name]"""
    
    def _parse_response(self, response: str) -> Tuple[str, str]:
        """
        Parse AI response to extract summary and category.
        
        Args:
            response: Raw AI response
        
        Returns:
            Tuple of (summary, category)
        """
        summary = ""
        category = "Other"
        
        lines = response.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith("SUMMARY:"):
                summary = line.replace("SUMMARY:", "").strip()
            elif line.startswith("CATEGORY:"):
                category = line.replace("CATEGORY:", "").strip()
        
        # Fallback if parsing fails
        if not summary:
            # Try to extract first few sentences as summary
            summary = '. '.join(response.split('.')[:3]).strip()
            if not summary.endswith('.'):
                summary += '.'
        
        # Validate category
        valid_categories = [
            "Education", "Technology", "Entertainment", "Tutorial", "News", 
            "Review", "Gaming", "Music", "Science", "Business", "Health", 
            "Sports", "Lifestyle", "Comedy", "Documentary", "Other"
        ]
        
        if category not in valid_categories:
            # Try to find a valid category in the response
            for valid_cat in valid_categories:
                if valid_cat.lower() in response.lower():
                    category = valid_cat
                    break
            else:
                category = "Other"
        
        return summary, category
    
    def estimate_cost(self, transcription: str) -> Dict[str, Any]:
        """
        Estimate API cost for processing a transcription.
        
        Args:
            transcription: Transcription text
        
        Returns:
            Dictionary with cost estimate information
        """
        # Rough token estimation (1 token ≈ 4 characters)
        estimated_tokens = len(transcription) // 4 + 200  # +200 for prompt and response
        
        if self.provider == "openai":
            # Pricing as of Dec 2025 (approximate)
            if "gpt-4" in self.model:
                input_cost = (estimated_tokens / 1000) * 0.03  # $0.03 per 1K tokens
                output_cost = (500 / 1000) * 0.06  # $0.06 per 1K tokens
            else:  # gpt-3.5-turbo
                input_cost = (estimated_tokens / 1000) * 0.0015  # $0.0015 per 1K tokens
                output_cost = (500 / 1000) * 0.002  # $0.002 per 1K tokens
            
            total_cost = input_cost + output_cost
            
            return {
                "provider": "OpenAI",
                "model": self.model,
                "estimated_tokens": estimated_tokens,
                "estimated_cost_usd": round(total_cost, 4)
            }
        
        elif self.provider == "gemini":
            # Gemini has free tier and lower costs
            return {
                "provider": "Google Gemini",
                "model": self.model,
                "estimated_tokens": estimated_tokens,
                "estimated_cost_usd": 0.0,  # Free tier
                "note": "Free tier available for Gemini"
            }
