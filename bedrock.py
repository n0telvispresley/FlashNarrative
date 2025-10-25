# bedrock.py
import boto3
import json
import os
import streamlit as st

# --- Bedrock Client Setup ---
@st.cache_resource
def get_bedrock_client():
    """Initializes and returns the Bedrock runtime client, caching the resource."""
    try:
        aws_region = os.getenv("AWS_REGION", "us-east-1") # Default region
        if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_KEY"):
            st.error("AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_KEY) not found. Please set them in your .env file.")
            return None

        bedrock_client = boto3.client(
            service_name="bedrock-runtime",
            region_name=aws_region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_KEY")
        )
        print(f"Bedrock client initialized successfully for region {aws_region}.")
        return bedrock_client
    except Exception as e:
        st.error(f"Error initializing Bedrock client: {e}")
        return None

# --- Model Configuration ---
# Define the models to try, in order of preference. Excludes Image models.
PREFERRED_TEXT_MODELS = [
    "anthropic.claude-3-opus-20240229-v1:0",    # Highest Quality (Expensive)
    # --- ADDED THE NEW MODEL ID HERE (CAVEAT: LIKELY INVALID) ---
    "global.anthropic.claude-sonnet-4-20250514-v1:0",
    # --- END ADDITION ---
    "anthropic.claude-3-sonnet-20240229-v1:0",   # Balanced
    "meta.llama3-70b-instruct-v1:0",           # Llama 3 70B
    "cohere.command-r-plus-v1:0",              # Cohere R+
    "mistral.mistral-large-2402-v1:0",         # Mistral Large
    "amazon.titan-text-express-v1",            # Titan Express (Faster Titan)
    "anthropic.claude-3-haiku-20240307-v1:0",    # Fastest Claude (Cheapest)
    "amazon.titan-text-lite-v1",               # Titan Lite (Fastest Titan)
]

# --- Helper Functions for Different Model Payloads ---

def _build_anthropic_body(prompt, max_tokens=10, temperature=0.1):
    """Builds the JSON body for Anthropic Claude models."""
    return json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        "temperature": temperature,
    })

def _parse_anthropic_response(response_body_json):
    """Parses the response from Anthropic Claude models."""
    content = response_body_json.get('content', [])
    if content and isinstance(content, list) and len(content) > 0:
        return content[0].get('text', '').strip()
    return None

def _build_meta_llama_body(prompt, max_tokens=10, temperature=0.1):
    """Builds the JSON body for Meta Llama models."""
    # Add instruction formatting for Llama 3 Instruct
    # Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-meta.html
    # Basic prompt might work, but this is more robust
    formatted_prompt = f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    return json.dumps({
        "prompt": formatted_prompt,
        "max_gen_len": max_tokens,
        "temperature": temperature,
    })

def _parse_meta_llama_response(response_body_json):
    """Parses the response from Meta Llama models."""
    return response_body_json.get('generation', '').strip()

def _build_amazon_titan_body(prompt, max_tokens=10, temperature=0.1):
    """Builds the JSON body for Amazon Titan Text models."""
    return json.dumps({
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": max_tokens,
            "temperature": temperature,
            "stopSequences": [],
        }
    })

def _parse_amazon_titan_response(response_body_json):
    """Parses the response from Amazon Titan Text models."""
    results = response_body_json.get('results', [])
    if results and isinstance(results, list) and len(results) > 0:
        return results[0].get('outputText', '').strip()
    return None

def _build_cohere_body(prompt, max_tokens=10, temperature=0.1):
    """Builds the JSON body for Cohere Command models."""
    # Command R+ uses a chat format
    # Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-cohere-command-r.html
    # Keep simple prompt for now, may need adjustment for complex tasks
    return json.dumps({
        "prompt": prompt, # Or use "message": prompt for newer versions? Check docs.
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stop_sequences": []
    })

def _parse_cohere_response(response_body_json):
    """Parses the response from Cohere Command models."""
    # Command R+ response structure
    if response_body_json.get('text'):
        return response_body_json.get('text','').strip()
    # Fallback for older Cohere format
    generations = response_body_json.get('generations', [])
    if generations and isinstance(generations, list) and len(generations) > 0:
        return generations[0].get('text', '').strip()
    return None

def _build_mistral_body(prompt, max_tokens=10, temperature=0.1):
    """Builds the JSON body for Mistral models."""
    # Mistral Large instruct format
    # Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-mistral.html
    formatted_prompt = f"<s>[INST] {prompt} [/INST]"
    return json.dumps({
        "prompt": formatted_prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
    })

def _parse_mistral_response(response_body_json):
    """Parses the response from Mistral models."""
    outputs = response_body_json.get('outputs', [])
    if outputs and isinstance(outputs, list) and len(outputs) > 0:
        # Mistral wraps text slightly differently
        return outputs[0].get('text', '').strip()
    return None

# --- Main API Call Function with Fallback ---

def invoke_model_sequentially(prompt, model_list, max_tokens, temperature):
    """
    Tries to invoke models from the list sequentially until one succeeds.
    Returns the successful model's output or None if all fail.
    """
    bedrock_client = get_bedrock_client()
    if not bedrock_client:
        print("Bedrock client not available.")
        return None

    last_error = "No models attempted or all skipped."

    for model_id in model_list:
        print(f"Attempting model: {model_id}")
        body = None
        parse_func = None

        try:
            # Build body based on model family
            if "anthropic.claude" in model_id or "global.anthropic" in model_id: # Handle both Claude ID types
                body = _build_anthropic_body(prompt, max_tokens, temperature)
                parse_func = _parse_anthropic_response
            elif "meta.llama" in model_id:
                body = _build_meta_llama_body(prompt, max_tokens, temperature)
                parse_func = _parse_meta_llama_response
            elif "amazon.titan" in model_id:
                if "text" in model_id: # Only use text models
                     body = _build_amazon_titan_body(prompt, max_tokens, temperature)
                     parse_func = _parse_amazon_titan_response
                else:
                     print(f"Skipping non-text Titan model: {model_id}")
                     continue
            elif "cohere.command" in model_id:
                body = _build_cohere_body(prompt, max_tokens, temperature)
                parse_func = _parse_cohere_response
            elif "mistral." in model_id:
                body = _build_mistral_body(prompt, max_tokens, temperature)
                parse_func = _parse_mistral_response
            else:
                print(f"Model family not recognized or unsupported for: {model_id}")
                last_error = f"Unsupported model ID format: {model_id}"
                continue # Skip unknown models

            # Make the API Call
            response = bedrock_client.invoke_model(
                body=body,
                modelId=model_id,
                accept='application/json',
                contentType='application/json'
            )
            response_body = json.loads(response.get('body').read())

            # Parse the Response
            result_text = parse_func(response_body) if parse_func else None

            if result_text is not None and result_text != "":
                print(f"Success with model: {model_id}")
                return result_text # Return the first successful result
            else:
                print(f"Model {model_id} returned empty or failed to parse response: {response_body}")
                last_error = f"Model {model_id} returned invalid data."

        except Exception as e:
            last_error = f"Error invoking {model_id}: {e}"
            print(last_error)
            if "AccessDeniedException" in str(e):
                # Only show warning in Streamlit UI for access denied
                st.warning(f"AWS Error: Model access for {model_id} may not be enabled. Check the Bedrock console.")
            # Continue to the next model for other errors
            continue

    # If loop finishes without success
    print(f"All models failed. Last error: {last_error}")
    # Show a generic error in Streamlit if all failed
    st.error(f"AI models failed. Last error: {last_error}. Using keyword fallback.")
    return None # Indicate failure


# --- Updated Sentiment Function ---

def get_llm_sentiment(text_chunk):
    """
    Analyzes sentiment using Bedrock with model fallback.
    Returns sentiment string or None if all models fail.
    """
    text_chunk = (text_chunk or "")[:500]

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
    result_text = invoke_model_sequentially(
        prompt=prompt,
        model_list=PREFERRED_TEXT_MODELS,
        max_tokens=10,
        temperature=0.1
    )

    if result_text:
        sentiment = result_text.lower().strip().replace(".", "")
        valid_sentiments = ['positive', 'negative', 'neutral', 'mixed', 'anger', 'appreciation']
        if sentiment in valid_sentiments:
            return sentiment
        else:
            # Attempt basic mapping
            if "positive" in sentiment: return "positive"
            if "negative" in sentiment: return "negative"
            if "neutral" in sentiment: return "neutral"
            print(f"Model returned unexpected sentiment text: '{sentiment}'. Treating as failure.")
            return None # Fallback if result is not a valid sentiment word
    else:
        return None # Trigger keyword fallback

# --- Updated Report Summary Function ---

def generate_llm_report_summary(kpis, top_keywords, articles, brand):
    """
    Generates a summary/recommendations using Bedrock with model fallback.
    Returns report text or error message.
    """
    data_summary = f"""
    Brand: {brand}
    Sentiment Ratio: {kpis.get('sentiment_ratio', {})}
    Top Keywords: {', '.join([k[0] for k in top_keywords])}

    Major Headlines (Positive/Appreciation):
    {[a['text'][:150] for a in articles if a.get('sentiment') in ['positive', 'appreciation']][:3]}

    Major Headlines (Negative/Anger):
    {[a['text'][:150] for a in articles if a.get('sentiment') in ['negative', 'anger']][:3]}
    """

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
    result_text = invoke_model_sequentially(
        prompt=prompt,
        model_list=PREFERRED_TEXT_MODELS,
        max_tokens=500,
        temperature=0.7
    )

    if result_text:
        if "**Summary:**" not in result_text or "**Recommendations:**" not in result_text:
            print(f"Model report format unexpected: {result_text[:100]}...")
        return result_text
    else:
        return ("**Error:** Could not generate AI summary using available models.\n"
                "Please check Bedrock model access permissions in the AWS console "
                "for the models listed in `bedrock.py` and ensure AWS credentials are correct.")
