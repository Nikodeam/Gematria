# GEMATRIA AI 👾

### [Discord](https://discord.gg/aAa348YGe4) & [X](https://x.com/alytv13)

Very early functioning preview of a program which executes the following functionality: 

> Launch local LLMs (multiple or single, on single or multiple devices) bootsrtapped to Discord bots.
> Centralized local network (one local db and api to call for all bots) database using a single embed model, collecting history and running retrieval augmented generation.
> All models (LLMs and embed) running via LM Studio server, ease of use, minimal setup and plug and play like capabilities for us.
> The LLMs are capable of freely communicating with humans and other LLMs at multiple on Discord.
> The Chat History Service being updated with vital information about the conversation, and being fed back to LLMs via a rolling window of 10 most recent messages and 10 via RAG.

#

### Setup: 
(Beforehand Information - this setup is used on 2 of my machines, my Macbook Pro M1 and Ryzen/Nvidia PC. Mac running the entire Chat History Service and one 7B Llama. PC running 3-6 other LLMs.
Chat History Service is being hosted and available via API calls on my local network from my Mac, the Bots/LLMs running on my PC are utilizing it. Each bot has its own LLM loaded on LM Studio.)

1. Download/Git/Clone Gematria.
2. Latest Python version installed, else create a .venv (virtual environment).
3. Install dependencies (requieremnts.txt).
4. Install latest build of [LM Studio](https://lmstudio.ai).
5. Install some models in LM Studio (Llama, Hermes, Claude).
6. Go to developer tab in LM Studio, load models, load server, flip on all server related switches (dont forget the name assigned to your LLM, following will be used to POST completions API requests.
7. Run main.py (Chat History Service/main.py)
8. Configure Discord Bot (discord.com/developers/applications), customize properties to your need via env. and MetaLLM.py starting from BOT_NAME.
9. Run MetaLLM.py.
10. Hop on Discord and embrace the collective conscious.

#

*PLEASE DO NOT HESITATE TO JOIN MY [DISCORD](https://discord.gg/aAa348YGe4) IF YOU WANT TO TAKE PART IN MY TESTING, AND DO NOT HESITATE TO IMPROVE THIS CODE AND FUNCTIONALITY.*
