### How to config Open-webui for this low-fi prototype

(see the README.md for how to set the environment variables to use an open-api compliant API such as open-webui's or llamma.cpp's )

1) obtain a model such Gemma3 12b or MedGemma 4B or 27B in the models library

2) set up a workspace e.g., `AgentStudyAssistant`

3) In advanced params set (as a starting point, you can make changes for experimentation):
- stream chat responts: off
- temperature: 1.0
- max_tokens: 2048
- top_k: 64
- top_p: 0.95
- min_p: 0.01

