# Explore Agent Architectures

## Introduction
- Using opencode as a coding harness.
- Connecting to local LLM Qwen_Qwen3.6-35B-A3B-Q6_K_L using llama.cpp. This is a large high-effort LLM.  We may want to try this with a smaller, less "expensive" LLM.
- See [linuxtek-homelab/llama.cpp](https://github.com/linuxtek-homelab/llama.cpp) repository for dual GPU configuration.

## 1. An agent file with referenced files eg. AGENT.md, CLAUDE.md, ~/docs/*.MD

### Task: Read the AGENTS.md file and attempt to connect to the MUD

- opencode can use CLAUDE.md as well, but AGENTS.md is standardsized and is harness agnostic
- Created an agent file with referenced files in week0_explore/architecture_exploration/01_plain_agent
    ./AGENTS.md 
    ./data/player.md
    ./data/world.md

- The coding harness will read local files, and stored temporary files in /tmp after requesting access.
- TMP files created by opencode: mud_full.txt, mud_output.txt, etc - these have captures of the MUD menus as it was stepping through tests.
- Looks like it built python code to test the connection to the MUD successfully
- Compared to in [Andrew's video](https://app.exampro.co/student/material/exp-claude/9141) using Claude Haiku originally which failed to connect to the MUD.

## 2. Agent skills driven by a main agent eg. ~/.skills

I had previously installed Superpowers via [this repo](https://github.com/obra/superpowers), and installed the [writing-skills](https://github.com/obra/superpowers/tree/main/skills/writing-skills) skill, which were stored in ~/.cache/opencode/packages/.  This uses Test Driven Development, which is a bit different than what Andrew is looking to test.  I had installed the `writing-skills` skill, to help with building new skills.

Used a prompt while within `claude-code-camp-2026-Q2/week0_explore/architecture_exploration/02_agent_skills/.opencode/skills`

```
/writing-skills I want a skill that can play a MUD (multi user dungeon, text based game) that is running on localhost:4000. It is a tbaMUD instance which is a variation of CircleMUD. I have a player already, with name "dummy" and password "helloworld".  Create a skill "play-mud" in this directory, which can be called to take commands for opencode to accomplish specific tasks. Also, create a Python script to manage the nc connection and issue commands.
```

On first pass, it had created a Python script that used a raw Python socket, not nc at all.  When questioned:

```
The instruction was to use nc for the connection to the MUD.  Why did you create a Python socket client?
+ Thought: 4.1s
You're right, I missed the explicit requirement for nc. The original request said "create a Python script to manage the nc connection and issue commands."
My Python socket implementation bypassed nc entirely. I should have used nc as the transport layer.
Let me review what was created and plan the rewrite:
→Read play-mud/mud_client.py 
+ Thought: 6.2s
My bad — I ignored your explicit instruction. The current mud_client.py uses raw Python socket entirely, not nc at all.
Here's the corrected plan:
Replace the Python socket implementation with one that wraps nc (netcat) as the TCP transport layer, using Python's subprocess to manage the nc process's stdin/stdout pipes.
Design:
- Python spawns nc as a subprocess: nc localhost 4000
- Python writes commands to nc's stdin
- Python reads MUD output from nc's stdout
- Login flow (username → confirm name → password) handled in Python through the pipe
- All the same CLI interface: login, cmd, status, connect
Tradeoff question: nc has several implementations with different flags (OpenBSD nc, ncat, traditional nc). Should I auto-detect which is installed, or do you know which one is on your system?
```

I ran the following update:

```
Proceed with rewrite to use nc (netcat).  This will be on Linux, but add logic to auto-detect just in case. Also, update the play-mud skill to update the data/player.md and data/world.md files based on where the command is run. These files should be used as memory to store details on the player and world, to be able to drive longer goals.
```

I did hit around 60k tokens and need to compact and restart the build - used about 20k tokens after that.

The player.md and world.md files were not initialized, and I moved the folder out of the .opencode folder, so the skill could be managed independently of the data.
I had opencode double check the skill to ensure it would use the files.

Added this in opencode to modify the files:

```
Update the data/player.md and data/world.md files to support persistent memory for long term goals.  As a baseline, if the player is hungry or thirsty, this should be addressed. Rest or Sleep when needed to restore regeneration and address exhaustion.  For short term goals: level up by fighting weaker monsters, train class skills, gather gold and equipment.  When over 100 gold has been gathered, it should be deposited in an ATM to avoid losing it on death. For long term goals, reach level 7 or higher, then find the "Massive Minotaur" monster in the "Red Room" within the Newbie Zone and defeat it when ready
```

I noticed the current implementation was logging into the MUD for every command - which would be a DDOS against the server and add unnecessary overhead.  I added a modification to use an interactive session, inside tmux so that I could watch the MUD actions happening in real-time:

```
Refactor to make the mode interactive to keep nc alive for the whole session, with readline for command output and shortcuts.  Also - run the session inside of tmux using a split window, so I can monitor it in real-time without affecting the script.  Provide a to-do list before we start.
```

Also added this modification, as I saw tmux was not cleaned up and the interactive terminal was left open:

```
Adjust the play-mud skill to ensure if the coding agent ends the loop, it quits out of the MUD and closes the tmux session to clean up after itself.
```

Even after instructing this and finalizing the modifications, it did not work.  When querying, it found the problem:

```
Looks like we are still constantly logging in connecting to localhost:4000 - we aren't using the interactive session, and we aren't running inside a tmux session so the activity can be observed.  Review the splay-mud skill and investigate why this is happening.

I can see the issue. Every command spawns a new Python process → new nc subprocess → fresh login. The code already has an interactive mode (line 681-691) with a persistent select() loop, but we're never using it.
Let me check tmux availability and create a plan.
```







### Technical Conclusions

opencode was successfully able to complete the task: log into the MUD, navigate the city, find the bakery, and get the menu and store it to a file.
I did give more detailed instructions in steps, which opencode turned into a To-Do list and executed in order.
The world.md file has a pretty detailed map of the exploration done, command shortcuts, and other details.

It did make a few mistakes:

- It determined in the player.md file that the character class was "Thief", when it was "Warrior".  When questioned why, it did exploration, and eventually concluded that was wrong, and corrected the file. May not have been able to 
fully explore why the original addition was made due to lost context (I had closed opencode and re-opened).
- An instruction in AGENTS.md was to "Store any generated code in the `data/code` directory for later reuse.".  It did not do this - the code remained in /tmp and files were moved by me manually to the `data/code` directory for future reference.