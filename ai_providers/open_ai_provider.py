import os
from openai import OpenAI  # pip install openai

MODEL_CLASSES = ["o1", "4o", "gpt-4.1", "gpt-5", "gpt-5-chat"]

MODELS_NOT_SUPPORTING_SYS_MSG = ["o1"]
MODELS_NOT_SUPPORTING_VERBOSITY = ["gpt-5-chat"]
USE_LEGACY_CHAT_COMPLETIONS_FOR_THESE = ["gpt-4.1", "gpt-5-chat"]

# OpenAI recommends reserving at least 25,000 tokens for reasoning and outputs
# https://platform.openai.com/docs/guides/reasoning/how-reasoning-works?reasoning-prompt-examples=research 
MODEL_SPECIFIC_LIMITS = {"o1": 30000}


def build_client():
    key = os.environ["OPENAI_API_KEY"]
    client = OpenAI(api_key=key)
    return client


def build_model_handle():
    # Default to GPT-5 if not specified
    handle = os.environ.get("OPENAI_MODEL", "gpt-5")  # e.g. "gpt-5" or Azure deployment name
    return handle


# if os.environ["AI_PROVIDER"] == "openai":
MODEL = build_model_handle()
CLIENT = build_client()
print(f"Loaded OpenAI model: {MODEL}")
print(f"Loaded OpenAI client: {CLIENT}")
# else:
#    MODEL = None
#    CLIENT = None


def identify_model_class(model):
    for model_class in MODEL_CLASSES:
        if isinstance(model, str) and model_class.lower() in model.lower():
            return model_class
    return None


def should_use_legacy_chat_completions(model_name):
    try:
        lowered = model_name.lower() if isinstance(model_name, str) else ""
        for token in sorted(USE_LEGACY_CHAT_COMPLETIONS_FOR_THESE, key=len, reverse=True):
            if token.lower() in lowered:
                return True
        return False
    except Exception:
        return False


def supports_verbosity_param(model_name):
    try:
        lowered = model_name.lower() if isinstance(model_name, str) else ""
        for token in MODELS_NOT_SUPPORTING_VERBOSITY:
            if token.lower() in lowered:
                return False
        # Only apply verbosity to GPT-5 class models
        model_class = identify_model_class(model_name)
        return (model_class or "").lower() == "gpt-5"
    except Exception:
        return False


def build_verbosity_options(model_name, use_legacy7):
    try:
        if supports_verbosity_param(model_name):
            if use_legacy7:
                return {"verbosity": "low"}
            return {"text": {"verbosity": "low"}}
        return {}
    except Exception:
        return {}


def sys_msg_conditional_removal(messages):
    # Create a new list to store modified messages
    modified_messages = []
    model_class = identify_model_class(MODEL)
    
    for message in messages:
        if model_class in MODELS_NOT_SUPPORTING_SYS_MSG and message.get("role") == "system":
            # If the model doesn't support system messages, change role to "assistant"
            modified_messages.append({"role": "assistant", "content": message.get("content", "")})
        else:
            # Otherwise, add the message as-is
            modified_messages.append(message.copy())
    
    # print(f"Messages after conditional removal: {modified_messages}")
    return modified_messages


def convert_messages_to_responses_input(messages):
    responses_input = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")

        text_type = "output_text" if role == "assistant" else "input_text"
        typed_parts = []

        if isinstance(content, str):
            typed_parts.append({"type": text_type, "text": content})
        elif isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    typed_parts.append({"type": text_type, "text": str(item)})
                    continue
                item_type = item.get("type")
                if item_type == "text":
                    typed_parts.append({"type": text_type, "text": item.get("text", "")})
                elif item_type == "image_url":
                    image_payload = item.get("image_url")
                    image_url = None
                    if isinstance(image_payload, dict):
                        image_url = image_payload.get("url") or image_payload.get("image_url")
                    elif isinstance(image_payload, str):
                        image_url = image_payload
                    if image_url:
                        typed_parts.append({"type": "input_image", "image_url": image_url})
                else:
                    typed_parts.append({"type": text_type, "text": str(item)})
        else:
            typed_parts.append({"type": text_type, "text": str(content)})

        responses_input.append({"role": role, "content": typed_parts})
    return responses_input


def extract_text_from_responses_output(response):
    try:
        # Newer SDKs expose convenient property
        text = getattr(response, "output_text", None)
        if isinstance(text, str) and len(text) > 0:
            return text
        # Fallback: traverse structured output
        output = getattr(response, "output", [])
        collected = []
        for block in output or []:
            for part in block.get("content", []):
                if part.get("type") in ("output_text", "input_text"):
                    t = part.get("text")
                    if isinstance(t, str) and len(t) > 0:
                        collected.append(t)
        return "\n".join(collected) if collected else ""
    except Exception:
        return ""


def get_max_tokens_arg_name(model_class):
    if (model_class or "").lower() == "o1":
        return "max_output_tokens"
    return "max_completion_tokens"


def ask_open_ai(messages, max_length):
    modified_messages = sys_msg_conditional_removal(messages)
    answer = ""
    try:
        model_class = identify_model_class(MODEL)
        if model_class in MODEL_SPECIFIC_LIMITS:
            max_length = MODEL_SPECIFIC_LIMITS[model_class]

        use_legacy7 = should_use_legacy_chat_completions(MODEL)
        verbosity_opts = build_verbosity_options(MODEL, use_legacy7)

        if use_legacy7:
            tokens_arg_name = get_max_tokens_arg_name(model_class)
            kwargs = {**verbosity_opts}
            if isinstance(max_length, int) and max_length > 0:
                kwargs[tokens_arg_name] = max_length
            completion = CLIENT.chat.completions.create(
                model=MODEL,
                messages=modified_messages,
                **kwargs,
            )
            answer = completion.choices[0].message.content
        else:
            responses_input = convert_messages_to_responses_input(modified_messages)
            response = CLIENT.responses.create(
                model=MODEL,
                input=responses_input,
                **verbosity_opts,
            )
            answer = extract_text_from_responses_output(response)

        print(f"OpenAI response: {answer}")
    except Exception as e:
        msg = f"Error while sending to OpenAI: {e}"
        print(msg)
        answer = msg
    return answer
