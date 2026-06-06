import chainlit as cl
from langchain_ollama import ChatOllama

# Configuração do modelo (pode mudar depois)
llm = ChatOllama(
    model="qwen3:14b",   # ou gemma4:e4b quando baixar
    temperature=0.7,
    num_ctx=8192
)

@cl.on_chat_start
async def start():
    await cl.Message(content="""
# 👋 Bem-vindo ao **FounderAI** (MVP)

Estou rodando localmente com Qwen3-14B.

**Teste enviando uma missão, por exemplo:**

"Quero criar um Uber para supermercados"
""").send()

@cl.on_message
async def main(message: cl.Message):
    msg = cl.Message(content="⏳ Pensando...")
    await msg.send()

    try:
        response = await llm.ainvoke(message.content)
        await msg.update(content=response.content)
    except Exception as e:
        await msg.update(content=f"Erro: {str(e)}")