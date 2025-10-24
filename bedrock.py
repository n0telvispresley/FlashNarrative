# bedrock.py
import boto3
import json
import os
import streamlit as st

# --- Bedrock Client Setup ---
# Use st.cache_resource to initialize the client once
@st.cache_resource
def get_bedrock_client():
    try:
        aws_region = os.getenv("AWS_REGION", "us-east-1")
        if not os.getenv("AWS_ACCESS_KEY_ID"):
            st.error("AWS credentials not found. Please set AWS_ACCESS_KEY_ID, AWS_SECRET_KEY, and AWS_REGION in your .env file.")
            return None
            
        bedrock_client = boto3.client(
            service_name="bedrock-runtime",
            region_name=aws_region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_KEY")
        )
        return bedrock_client
    except Exception as e:
        st.error(f"Error initializing Bedrock client: {e}")
        return None

# Define the model ID
# Haiku is fast and cheap, perfect for a hackathon.
MODEL_ID = "anthropic.claude-3-opus-20240229-v1:0"

def get_llm_sentiment(text_chunk):
    """
    Analyzes a chunk of text (e.g., a single article) for sentiment using Bedrock.
    """
    bedrock_client = get_bedrock_client()
    if not bedrock_client:
        return "neutral" # Fallback

    # Clean text for the prompt
    text_chunk = (text_chunk or "")[:500] # Truncate to save tokens

    prompt = f"""
    Human: Analyze the sentiment of the following news headline or social media post.
    Respond with only a single word: 'positive', 'negative', 'neutral', 'mixed', 'anger', or 'appreciation'.
    
    <text>
    {text_chunk}
    </text>

    Assistant:
    """

    try:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 10,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}]
                }
            ]
        })

        response = bedrock_client.invoke_model(
            body=body,
            modelId=MODEL_ID,
            accept='application/json',
            contentType='application/json'
        )
        
        response_body = json.loads(response.get('body').read())
        sentiment = response_body.get('content')[0].get('text').lower().strip().replace(".", "")
        
        valid_sentiments = ['positive', 'negative', 'neutral', 'mixed', 'anger', 'appreciation']
        if sentiment in valid_sentiments:
            return sentiment
        else:
            return "neutral" # Default if LLM gives a weird response

    except Exception as e:
        # --- IMPROVED ERROR ---
        error_msg = f"Bedrock sentiment error: {e}"
        print(error_msg)
        if "AccessDeniedException" in str(e):
            st.warning("AWS Error: Model access for Claude 3 Haiku is not enabled. Please enable it in the Amazon Bedrock console.")
        return "neutral" # Fallback

def generate_llm_report_summary(kpis, top_keywords, articles, brand):
    """
    Generates a summary and recommendations using Bedrock.
    """
    bedrock_client = get_bedrock_client()
    if not bedrock_client:
        return "**Mock Summary:**\n* Sentiment is mixed.\n\n**Mock Recommendations:**\n* Monitor keywords."

    # Create a summary of the data for the LLM
    data_summary = f"""
    Brand: {brand}
    Sentiment Ratio: {kpis.get('sentiment_ratio', {})}
    Top Keywords: {', '.join([k[0] for k in top_keywords])}
    
    Major Headlines (Positive):
    {[a['text'] for a in articles if a.get('sentiment') == 'positive'][:3]}
    
    Major Headlines (Negative/Anger):
    {[a['text'] for a in articles if a.get('sentiment') in ['negative', 'anger']][:3]}
    """

    prompt = f"""
    Human: You are a professional PR crisis manager. Based on the following data summary for the brand '{brand}',
    write a 2-bullet point summary of the situation and 2-3 actionable recommendations.
    Format your response *exactly* like this, using markdown:
    
    **Summary:**
    * [Your summary bullet point 1]
    * [Your summary bullet point 2]
    
    **Recommendations:**
    * [Your recommendation bullet point 1]
    * [Your recommendation bullet point 2]

    <data>
    {data_summary}
    </data>

    Assistant:
    """
    
    try:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}]
                }
            ]
        })

        response = bedrock_client.invoke_model(
            body=body,
            modelId=MODEL_ID,
            accept='application/json',
            contentType='application/json'
        )
        
        response_body = json.loads(response.get('body').read())
        report_text = response_body.get('content')[0].get('text')
        return report_text

    except Exception as e:
        # --- IMPROVED ERROR ---
        error_msg = f"Bedrock report gen error: {e}"
        print(error_msg)
        
        fallback_msg = f"Error generating AI recommendations: {e}"
        if "AccessDeniedException" in str(e):
            fallback_msg = "Error: Model access for Claude 3 Haiku is not enabled. Please enable it in the Amazon Bedrock console."
            st.warning(fallback_msg) # Show in UI
        
        return fallback_msg
