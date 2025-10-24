# bedrock.py
import boto3
import json
import os
import streamlit as st

# --- Bedrock Client Setup ---
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
        # Add a check to ensure the client was created
        if bedrock_client:
            print(f"Bedrock client initialized successfully for region {aws_region}.")
        else:
            print("Failed to initialize Bedrock client.")
        return bedrock_client
    except Exception as e:
        st.error(f"Error initializing Bedrock client: {e}")
        return None

# Use the most powerful model
MODEL_ID = "anthropic.claude-3-opus-20240229-v1:0"

def get_llm_sentiment(text_chunk):
    """
    Analyzes a chunk of text (e.g., a single article) for sentiment using Bedrock.
    """
    bedrock_client = get_bedrock_client()
    if not bedrock_client:
        return "neutral" # Fallback

    text_chunk = (text_chunk or "")[:500] # Truncate

    # --- THIS IS THE IMPROVED PROMPT ---
    prompt = f"""
Human: Carefully analyze the sentiment expressed in the following text. Consider the overall tone and context.
Respond with only ONE of the following words: positive, negative, neutral, mixed, anger, appreciation.
If the text is purely informational or objective with no clear emotion, classify it as neutral.
Do not provide explanations, just the single word classification.

<text>
{text_chunk}
</text>

Assistant:
"""
    # --- END OF IMPROVED PROMPT ---

    try:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 10, # Needs very few tokens for a single word
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}]
                }
            ],
            "temperature": 0.1 # Lower temperature for more deterministic classification
        })

        response = bedrock_client.invoke_model(
            body=body,
            modelId=MODEL_ID,
            accept='application/json',
            contentType='application/json'
        )
        
        response_body = json.loads(response.get('body').read())
        # Add error checking for response structure
        if response_body.get('content') and isinstance(response_body['content'], list) and len(response_body['content']) > 0:
            sentiment = response_body['content'][0].get('text', '').lower().strip().replace(".", "")
        else:
            print(f"Unexpected Bedrock response format: {response_body}")
            return "neutral" # Fallback if response format is weird

        valid_sentiments = ['positive', 'negative', 'neutral', 'mixed', 'anger', 'appreciation']
        if sentiment in valid_sentiments:
            return sentiment
        else:
            # If the model didn't give a valid word, try to map common alternatives
            if "positive" in sentiment: return "positive"
            if "negative" in sentiment: return "negative"
            if "neutral" in sentiment: return "neutral"
            print(f"Bedrock returned unexpected sentiment: '{sentiment}'. Defaulting to neutral.")
            return "neutral" 

    except Exception as e:
        error_msg = f"Bedrock sentiment error: {e}"
        print(error_msg)
        if "AccessDeniedException" in str(e):
            st.warning("AWS Error: Model access for Claude 3 Opus is not enabled. Please enable it in the Amazon Bedrock console.")
        # Add more specific error handling if needed
        elif "ValidationException" in str(e) and "max_tokens" in str(e):
             st.warning("AWS Error: Check max_tokens setting for Bedrock.")
        
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
    
    Major Headlines (Positive/Appreciation):
    {[a['text'][:150] for a in articles if a.get('sentiment') in ['positive', 'appreciation']][:3]} 
    
    Major Headlines (Negative/Anger):
    {[a['text'][:150] for a in articles if a.get('sentiment') in ['negative', 'anger']][:3]}
    """ # Truncate headlines

    prompt = f"""
    Human: You are a professional PR crisis manager analyzing recent online mentions for the brand '{brand}'.
    Based *only* on the provided data summary below, write a concise report with:
    1.  A '**Summary:**' section (2 bullet points MAX) highlighting the key sentiment trends or themes.
    2.  A '**Recommendations:**' section (2-3 actionable bullet points) for the PR team.
    
    Keep the language professional and direct. Do not add any introductory or concluding sentences.
    Format your response *exactly* like this example:

    **Summary:**
    * Overall sentiment appears [positive/negative/mixed], driven by [mention key theme or keywords].
    * [Mention another key observation, e.g., competitor performance, specific sentiment spike].

    **Recommendations:**
    * [Actionable step 1, e.g., Amplify positive mentions about X on social media].
    * [Actionable step 2, e.g., Investigate negative feedback regarding Y and prepare a response].
    * [Optional Actionable step 3].

    <data>
    {data_summary}
    </data>

    Assistant:
    """
    
    try:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500, # Allow enough space for the report
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}]
                }
            ],
            "temperature": 0.7 # Allow for some creativity in recommendations
        })

        response = bedrock_client.invoke_model(
            body=body,
            modelId=MODEL_ID,
            accept='application/json',
            contentType='application/json'
        )
        
        response_body = json.loads(response.get('body').read())
        # Add error checking
        if response_body.get('content') and isinstance(response_body['content'], list) and len(response_body['content']) > 0:
            report_text = response_body['content'][0].get('text', '')
            # Basic check to see if it follows the format
            if "**Summary:**" not in report_text or "**Recommendations:**" not in report_text:
                 print(f"Bedrock report format unexpected: {report_text[:100]}...")
                 # You could add logic here to try and re-format or just return as-is
            return report_text
        else:
            print(f"Unexpected Bedrock response format for report: {response_body}")
            return "Error: Could not generate AI summary due to unexpected response."


    except Exception as e:
        error_msg = f"Bedrock report gen error: {e}"
        print(error_msg)
        
        fallback_msg = f"Error generating AI recommendations: {e}"
        if "AccessDeniedException" in str(e):
            fallback_msg = "Error: Model access for Claude 3 Opus is not enabled. Please enable it in the Amazon Bedrock console."
            st.warning(fallback_msg) # Show in UI
        
        return fallback_msg
