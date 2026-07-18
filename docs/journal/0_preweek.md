# Preweek  Technical Documentation

## Technical Goal

The technical goal of Preweek (Explore) is to determine how well do Agent Architectures fit our business use-case.

Examples of agent architectures that scale with wffort:

* An agent file with referenced files eg. AGENT.md, @~/docs/*.MD
* Agent Skills driven by main agent eg. ~/.skills
* Filesystem Subagent driven by a coding harness or Coding Agent SDK eg. ~/subagents
* AI workflow automation platform eg. n8n
* Use a generic AI Agent SDK that leverages plug and plays generic AI packages.
* Use low level first-party LLM SDKs and write our own agentic loop
* Use REST APIs directly, write our own agentic loop
  * The agentic loop is model-driven orchestration with middleware programmatic guidance
  * The agentic loop is code-driven orchestration

Start by focusing on using self-hosted LLMs, coding harnesses, and tools. If possible, experiment with different models and evaluate efficiency.

## Technical Uncertainty
* Uncertain if open source LLMs and coding harnesses will be effective enough to complete the workload, compared to closed source applications and frontier models.
* Uncertain if coding harnesses are the correct tool for driving a MUD play session.
* Uncertain if LLMs model's thinking mode and other intelligent parameters is sufficent enough to hold memory and drive decisions for work specific use-case. Likely we will hit LLM context window limit before completing tasks.

## Technical Hypotheses

* From past experience with opencode - it takes multiple iterations to get the result you want.  I will attempt to be more specific in my design, but I have seen cases where requirements are ignored.  This may need more investigation.
* When using telnet or nc (netcat) to manage the MUD session, we will need to be intentional to build an interface that stays connected and interactive.  This is also valuable so we can observe the commands being passed into the MUD.
* I expect a coding focused agent like opencode will not be an ideal tool for driving our use-case.  We will need more data than flat file markdown to drive proper decision making and avoid wasting tokens.  We may need to be more specific in design on what information the agent should explore and retain so it can start new sessions with more relevant existing knowledge on how to navigate and play the game.

## Technical Observerations

### Experiment #1 - Plain Agent with AGENT.md

[Detailed Experimentation Notes and Screenshots](../week0_explore.md) - 1. An agent file with referenced files

Observations: 
* The agent was able to log into the MUD and explore the city, find the bakery, and provide the bakery menu successfully. With a very specific goal, it was able to learn and achieve the desired result.
* A configuration in an [AGENT.md](../../week0_explore/architecture_exploration/01_plain_agent/AGENTS.md) file was able to log into the MUD and perform simple tasks.  I created a slightly more specific file with step by step goals, as opencode tends to create a "to-do" list and work through it. 
* Opencode wrote a number of iterations of Python code to complete the goals, stored in /tmp - along with some txt files with MUD output.  I had instructed in my AGENTS.md file "Store any generated code in the `data/code` directory for later reuse" and it did not do this. Again, will need to investigate why some instructions are being ignored.  I've saved them to [this folder](../../week0_explore/architecture_exploration/01_plain_agent/data/code/) for later analysis.
* From the files generated such as [world.md](../../week0_explore/architecture_exploration/01_plain_agent/data/world.md), it is build its own knowledge map of rooms discovered, commands, and movement.  
* This iteration does not appear to understand that it is moving between rooms, and is not generating and storing a proper map of where it is, and where it has been, to make movement more efficient.
* Agent hallucinated that the character was a THIEF class, when it was a WARRIOR class.  Some of the help files include data for both, which may be why it got confused. Also, the `score` command doesn't tell you your class, only your current rank - eg. "Dummy the Swordpupil", so it was difficult to infer. When this was pointed out, it read the existing files and corrected the player.md definition.

### Experiment #2 - Agent driven by a custom generated skill

[Detailed Experimentation Notes and Screenshots](../week0_explore.md) - 2. Agent skills driven by a main agent

* Used [Obra Superpowers - writing-skills](https://github.com/obra/superpowers/tree/main/skills/writing-skills), similar to [Anthropic   skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator). These do work differently, as writing-skills is test-driven development.
* Created a custom skill [play-mud](../../week0_explore/architecture_exploration/02_agent_skills/.opencode/skills/play-mud/SKILL.md) along with a Python script to interface with the MUD.
* Despite adding in the prompt to "use a telnet or nc connection" in the Linux terminal to connect, opencode wrote its own Python TCP socket into the script to connect.  Will need to investigate why it is ignoring instructions, as this is a concern. When called on this, it admitted it had ignored the explicit instruction.
* Multiple refactors was needed to refine the skill, including to store memory in [data/player.md](../../week0_explore/architecture_exploration/02_agent_skills/data/player.md) and [data/world.md](../../week0_explore/architecture_exploration/02_agent_skills/data/world.md).
* Added capability to the Python script and skill to keep a persistent tmux session to run all MUD interactions, so I could attach and view what it was doing. This worked rather well, as it generated its own command list on where to reason, and when to pass commands into the MUD interface. Some skill refinement was needed as initially the tmux session would constantly be destroyed.
* The skill and agent ignored explicit instructions, when told to use interactive mode only and not CLI - it continued to use CLI, causing continuous disconnect/connect to the MUD for each command. Even after being called on it and "fixing" this, it continued to do it until I removed the CLI option from the script.
* The agentic loop using opencode and the Qwen_Qwen3.6-35B-A3B-Q6_K_L model had about a 60,000 token context window limit. The [Huggingface page](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) indicates "Context Length: 262,144 natively and extensible up to 1,010,000 tokens".  May need to investigate why the window is limited - may be a llama.cpp configuration issue.
* Due to the low context window, during the agentic loop, we would hit the limit, and have to compact, or it would fail to proceed. This also meant we couldn't persist a long session with the coding agent running the MUD - it would eventually hit the limit and stop.
* In one observed instance, the agent wandered around lost in the dark while hungry, thirsty, and exhausted. It did keep a priority to find food, water, and did rest briefly, but not enough to recover any significant vitality. It did not sleep. It kept checking various help commands, and despite being a WARRIOR, kept looking at spells despite not having the ability to cast any.

## Technical Conclusions

* Coding Agent (opencode) with AGENTS.md or SKILLS.md are capable of driving the MUD, however the navigation and tasks are very brittle and fail easily.
* opencode and LLM may ignore explicit instructions during building skills or code. Additional guardrails are needed to verify all instructions are obeyed, and adding tests to confirm this before completing work is recommended.
* Generating the Python code and skills was very inefficient, despite running locally successfully. The 60,000 token context window limit was hit multiple times, requiring compaction. For MUD play sessions it is also not suitable for long sessions or goals, as it will hit the limit while attempting loops to complete the long term goals.
* Consideration to avoid DOS/DDOS by the agent is needed.  Despite instructions, it did not maintain an interactive persistent session until the alternative CLI was removed. In a real world scenario, the constant connection/disconnection would likely trigger throttling or IP ban.
* We need specialized memory for map, navigation, and world data - a world.md file is not sufficient, and the pathfinding was very inefficient. The agent did not keep track of where it was, and where it had been.  It should be able to generate its own map so it doesn't get lost.
* We need specialized memory for player abilities and status, to avoid looping to attempt to use abilities the player doesn't have, updating when we learn new abilities. A player.md file is not sufficient.
* Including knowledge like a user guide for the agent or LLM would be helpful to avoid the initial experimentation (which did not persist). A RAG option to include additional resources would be helpful - however from a quick search, there does not appear to be an individual file - eg. "Players Handbook",  which means the user and agent must rely on the help commands and build their own knowledge base.

## Key Takeaway

For a specialized use-case like playing a MUD, we need specialized tooling, knowledge sources, and agentic loops; and a coding harness with skills is not sufficient.

