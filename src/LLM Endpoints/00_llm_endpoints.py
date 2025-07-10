def prompt_ollama(prompt:str, model="codellama:7b"):
    """A prompt helper function that sends a prompt to 
    ollama and returns only the text response."""
    import openai
    # setup connection to the LLM server
    client = openai.OpenAI(
        base_url = "http://localhost:11434/v1",
        api_key = "none" # not required by ollama
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # extract answer
    return response.choices[0].message.content

def prompt_blablador(prompt:str, model="alias-llama3-huge"):
    """A prompt helper function that sends a prompt to Blablador (FZ Jülich)
    and returns only the text response.
    """
    import os
    
    # setup connection to the LLM-server
    client = openai.OpenAI(
        base_url = "https://helmholtz-blablador.fz-juelich.de:8000/v1",
        api_key = os.environ.get('BLABLADOR_API_KEY')
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # extract answer
    return response.choices[0].message.content

def prompt_kisski(prompt:str, model="meta-llama-3.1-70b-instruct"):
    """A prompt helper function that sends a message to KISSKI Chat AI API
    and returns only the text response.
    """
    # setup connection to the LLM-server
    client = openai.OpenAI(
        base_url="https://chat-ai.academiccloud.de/v1",
        api_key=os.environ.get('KISSKI_API_KEY')
    )
    
    response = client.chat.completions.create(
        model=model,
        messages= [{"role": "user", "content": prompt}]
    )
    
    # extract answer
    return response.choices[0].message.content

def prompt_scadsai_llm(message:str, model="meta-llama/Llama-3.3-70B-Instruct"):
    """A prompt helper function that sends a message to ScaDS.AI LLM server at 
    ZIH TU Dresden and returns only the text response.
    """
    import os
    
    # convert message in the right format if necessary
    if isinstance(message, str):
        message = [{"role": "user", "content": message}]
    
    # setup connection to the LLM
    client = openai.OpenAI(base_url="https://llm.scads.ai/v1",
                           api_key=os.environ.get('SCADSAI_API_KEY')
    )
    response = client.chat.completions.create(
        model=model,
        messages=message
    )
    
    # extract answer
    return response.choices[0].message.content