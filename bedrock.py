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
    "global.anthropic.claude-sonnet-4-20250514-v1:0", # Added (Likely Invalid)
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
    return json.dumps({
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stop_sequences": []
    })

def _parse_cohere_response(response_body_json):
    """Parses the response from Cohere Command models."""
    if response_body_json.get('text'):
        return response_body_json.get('text','').strip()
    generations = response_body_json.get('generations', [])
    if generations and isinstance(generations, list) and len(generations) > 0:
        return generations[0].get('text', '').strip()
    return None

def _build_mistral_body(prompt, max_tokens=10, temperature=0.1):
    """Builds the JSON body for Mistral models."""
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
            if "anthropic.claude" in model_id or "global.anthropic" in model_id:
                body = _build_anthropic_body(prompt, max_tokens, temperature)
                parse_func = _parse_anthropic_response
            elif "meta.llama" in model_id:
                body = _build_meta_llama_body(prompt, max_tokens, temperature)
                parse_func = _parse_meta_llama_response
            elif "amazon.titan" in model_id:
                if "text" in model_id:
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
                continue

            # Make the API Call
            response = bedrock_client.invoke_model(
                body=body, modelId=model_id, accept='application/json', contentType='application/json'
            )
            response_body = json.loads(response.get('body').read())

            # Parse the Response
            result_text = parse_func(response_body) if parse_func else None

            if result_text is not None and result_text != "":
                print(f"Success with model: {model_id}")
                return result_text
            else:
                print(f"Model {model_id} returned empty or failed to parse response: {response_body}")
                last_error = f"Model {model_id} returned invalid data."

        except Exception as e:
            last_error = f"Error invoking {model_id}: {e}"
            print(last_error)
            if "AccessDeniedException" in str(e):
                st.warning(f"AWS Error: Model access for {model_id} may not be enabled. Check Bedrock console.")
            continue

    print(f"All models failed. Last error: {last_error}")
    st.error(f"AI models failed. Last error: {last_error}. Using keyword fallback.")
    return None


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
        prompt=prompt, model_list=PREFERRED_TEXT_MODELS, max_tokens=10, temperature=0.1
    )

    if result_text:
        sentiment = result_text.lower().strip().replace(".", "")
        valid_sentiments = ['positive', 'negative', 'neutral', 'mixed', 'anger', 'appreciation']
        if sentiment in valid_sentiments:
            return sentiment
        else:
            if "positive" in sentiment: return "positive"
            if "negative" in sentiment: return "negative"
            if "neutral" in sentiment: return "neutral"
            print(f"Model returned unexpected sentiment text: '{sentiment}'. Treating as failure.")
            return None
    else:
        return None

# --- UPDATED Report Summary Function ---
def generate_llm_report_summary(kpis, top_keywords, articles, brand, competitors): # Added competitors
    """
    Generates a more comprehensive, professional report summary and recommendations
    using Bedrock with model fallback. Includes competitive context.
    Returns report text (Markdown formatted) or error message.
    """
    bedrock_client = get_bedrock_client() # Check client availability early
    if not bedrock_client:
        print("Bedrock client not available. Cannot generate LLM report summary.")
        return ("**Error:** Could not connect to Bedrock client.\n"
                "**Recommendations:** Review data manually.")

    # --- Prepare Data Summary for Prompt ---
    sentiment_summary = ", ".join([f"{k.capitalize()}: {v:.1f}%" for k,v in kpis.get('sentiment_ratio', {}).items()])
    sov_summary = ""
    all_brands_list = kpis.get('all_brands', [brand] + (competitors or [])) # Ensure competitors is a list
    sov_values = kpis.get('sov', [])
    # Recalculate SOV mapping if needed
    if len(sov_values) != len(all_brands_list):
         brand_counts = Counter()
         for item in articles: # Use 'articles' passed to this function
              mentioned = item.get('mentioned_brands', [])
              present_brands = set()
              if isinstance(mentioned, list): present_brands.update(b for b in mentioned if b in all_brands_list)
              elif isinstance(mentioned, str) and mentioned in all_brands_list: present_brands.add(mentioned)
              for b in present_brands: brand_counts[b] += 1
         total_sov_mentions = sum(brand_counts.values())
         sov_values = [(brand_counts[b] / total_sov_mentions * 100) if total_sov_mentions > 0 else 0 for b in all_brands_list]

    if len(sov_values) == len(all_brands_list):
        sov_items = [f"{b}: {s:.1f}%" for b, s in zip(all_brands_list, sov_values)]
        sov_summary = ", ".join(sov_items)


    data_summary = f"""
    **Brand:** {brand}
    **Competitors Tracked:** {', '.join(competitors) if competitors else 'None'}
    **Key Performance Indicators (KPIs):**
    * Sentiment Ratio: {sentiment_summary if sentiment_summary else 'N/A'}
    * Share of Voice (SOV): {sov_summary if sov_summary else 'N/A'}
    * Media Impact Score (MIS): {kpis.get('mis', 0):.0f}
    * Message Penetration Index (MPI): {kpis.get('mpi', 0):.1f}%
    * Avg. Social Engagement: {kpis.get('engagement_rate', 0):.1f}
    * Total Reach: {kpis.get('reach', 0):,}

    **Top Keywords/Phrases Mentioned:** {', '.join([k[0] for k in top_keywords]) if top_keywords else 'None identified'}

    **Recent Positive/Appreciative Headlines for {brand}:**
    {[a['text'][:150] for a in articles if brand.lower() in (mb.lower() for mb in a.get('mentioned_brands',[])) and a.get('sentiment') in ['positive', 'appreciation']][:3]}

    **Recent Negative/Angry Headlines for {brand}:**
    {[a['text'][:150] for a in articles if brand.lower() in (mb.lower() for mb in a.get('mentioned_brands',[])) and a.get('sentiment') in ['negative', 'anger']][:3]}

    **Notable Competitor Headlines:**
    {[a['text'][:150] for a in articles if any(c.lower() in (mb.lower() for mb in a.get('mentioned_brands',[])) for c in competitors)][:3]}
    """

    # --- Define the Enhanced Prompt ---
    prompt = f"""
Human: You are a senior Public Relations analyst creating a concise report for the client, '{brand}'.
Analyze the provided data summary, focusing on brand sentiment, market visibility (SOV compared to competitors: {', '.join(competitors)}), key discussion themes, and overall media impact.

Based *only* on the data below, generate a report with these Markdown sections:

**1. Executive Summary:** (2-3 bullet points)
    * Overview of '{brand}'s online reputation (sentiment ratio, MIS).
    * '{brand}'s visibility vs. competitors (SOV).
    * Critical emerging themes (positive/negative keywords or headlines).

**2. Key Findings:** (3-4 bullet points)
    * Dominant sentiment drivers (positive/negative percentages if significant).
    * Share of Voice analysis: Is '{brand}' leading/lagging?
    * Message Penetration (MPI): Are campaign messages resonating? ({kpis.get('mpi', 0):.1f}% detected).
    * Significant positive/negative headlines for '{brand}'.
    * Brief note on any major competitor activity observed in headlines.

**3. PR Recommendations:** (3-4 actionable bullet points)
    * Concrete actions based on findings.
    * Examples: Amplify positive themes (keywords/headlines), address negative feedback, adjust messaging based on MPI, counter competitor narratives (SOV/headlines), leverage high-impact (MIS) coverage.
    * Link recommendations directly to data (sentiment, SOV, MPI, keywords, headlines).

**Do NOT add greetings or sentences outside these sections.** Use professional language.

<data_summary>
{data_summary}
</data_summary>

Assistant:
"""

    # --- Call the Sequential Invoker ---
    result_text = invoke_model_sequentially(
        prompt=prompt,
        model_list=PREFERRED_TEXT_MODELS,
        max_tokens=1000, # Increased max tokens
        temperature=0.6 # Slightly lower temp
    )

    if result_text:
        if "**Executive Summary:**" not in result_text or "**Key Findings:**" not in result_text or "**PR Recommendations:**" not in result_text:
            print(f"Model report format unexpected (missing sections): {result_text[:150]}...")
        return result_text
    else:
        return ("**Error:** Could not generate AI Report Summary using available models.\n"
                "Please check Bedrock model access permissions in the AWS console "
                "for the models listed in `bedrock.py` and ensure AWS credentials are correct.\n\n"
                "**Recommendations:** Review raw data and KPIs manually.")
