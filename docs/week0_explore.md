## Notes and Observations

- Using opencode as a coding harness.
- Connecting to local LLM Qwen_Qwen3.6-35B-A3B-Q6_K_L using llama.cpp.
- See [linuxtek-homelab/llama.cpp](https://github.com/linuxtek-homelab/llama.cpp) repository for dual GPU configuration.

### Task: Read the AGENTS.md file and attempt to connect to the MUD

- Can use CLAUDE.md as well but AGENTS.md is agnostic

- An agent file with referenced files in week0_explore/architecture_exploration/01_plain_agent
    ./AGENTS.md 
    ./data/player.md
    ./data/world.md

- The coding harness will read local files, and stored temporary files in /tmp after requesting access.
- TMP files created by opencode: mud_full.txt, mud_output.txt, etc - these have captures of the MUD menus as it was stepping through tests.
- Looks like it built python code to test the connection to the MUD successfully
- Compared to in [Andrew's video](https://app.exampro.co/student/material/exp-claude/9141) using Claude Haiku originally which failed to connect.