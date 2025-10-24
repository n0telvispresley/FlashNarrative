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
            return None # Return None if creds missing

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
            return None # Return None if client init fails
        return bedrock_client
    except Exception as e:
        st.error(f"Error initializing Bedrock client: {e}")
        return None # Return None if client fails to init

# Use the most powerful model
MODEL_ID = "anthropic.claude-3-opus-20240229-v1:0"

def get_llm_sentiment(text_chunk):
    """
    Analyzes sentiment using Bedrock. Returns None if the API call fails or gives invalid output.
    """
    bedrock_client = get_bedrock_client()
    # --- CHANGE: Check client init failure ---
    if not bedrock_client:
        print("Bedrock client not available. Cannot perform LLM sentiment analysis.")
        return None # Return None if client isn't available

    text_chunk = (text_chunk or "")[:500] # Truncate

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
            # --- CHANGE: Return None on unexpected format ---
            return None

        valid_sentiments = ['positive', 'negative', 'neutral', 'mixed', 'anger', 'appreciation']
        if sentiment in valid_sentiments:
            return sentiment
        else:
            # If the model didn't give a valid word, try to map common alternatives
            if "positive" in sentiment: return "positive"
            if "negative" in sentiment: return "negative"
            if "neutral" in sentiment: return "neutral"
            print(f"Bedrock returned unexpected sentiment: '{sentiment}'. Treating as failure.")
            # --- CHANGE: Return None on unexpected word ---
            return None

    except Exception as e:
        error_msg = f"Bedrock sentiment API error: {e}"
        print(error_msg)
        # Display warning only for AccessDenied, otherwise just print
        if "AccessDeniedException" in str(e):
            st.warning("AWS Error: Model access for Claude 3 Opus is not enabled. Please enable it in the Amazon Bedrock console.")
        # --- CHANGE: Return None on any API exception ---
        return None

def generate_llm_report_summary(kpis, top_keywords, articles, brand):
    """
    Generates a summary and recommendations using Bedrock. Includes fallback text.
    """
    bedrock_client = get_bedrock_client()
    if not bedrock_client:
        print("Bedrock client not available. Cannot generate LLM report summary.")
        # Return mock summary if client failed
        return "**Mock Summary:**\n* LLM client unavailable.\n\n**Mock Recommendations:**\n* Review data manually."

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
                 # Return the text anyway, maybe partially useful
            return report_text
        else:
            print(f"Unexpected Bedrock response format for report: {response_body}")
            return "Error: Could not generate AI summary due to unexpected response."


    except Exception as e:
        error_msg = f"Bedrock report gen API error: {e}"
        print(error_msg)

        fallback_msg = f"Error generating AI recommendations: {e}"
        if "AccessDeniedException" in str(e):
            fallback_msg = "Error: Model access for Claude 3 Opus is not enabled. Please enable it in the Amazon Bedrock console."
            # Show warning in UI only if this specific error occurs
            st.warning(fallback_msg)

        # Return a generic error for other API issues
        return fallback_msg
