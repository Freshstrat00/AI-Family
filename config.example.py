NAME             = "Terra"    # or Sol, Gaster etc
MODEL            = "llama3.1:8b-instruct-q4_K_M"
OLLAMA_URL       = "http://localhost:11434/api/chat"
TEMPERATURE      = 0.7
MAX_TOKENS       = 300
MEMORY_LIMIT     = 20
CONTEXT_LENGTH   = 2048

HOST             = "0.0.0.0"
PORT             = 5000       # 5001 for Sol etc
DEBUG            = False

LIBRARY_URL      = "http://192.168.1.121:6000/terra" #if running within dedicated server

KNOWLEDGE_DIR        = "knowledge/"
INTERESTS_FILE       = KNOWLEDGE_DIR + "interests.txt"
MEMORIES_FILE        = KNOWLEDGE_DIR + "memories.txt"
LEARNING_FILE        = KNOWLEDGE_DIR + "learning.txt"

MEMORY_BRAIN_DIR     = KNOWLEDGE_DIR + "memory_brain/"
TIER_1_FILE          = MEMORY_BRAIN_DIR + "short_term.json"
TIER_2_FILE          = MEMORY_BRAIN_DIR + "long_term_recent.json"
TIER_3_FILE          = MEMORY_BRAIN_DIR + "long_term_distant.json"
INTENTIONAL_FILE     = KNOWLEDGE_DIR + "intentional_memories.json"
SESSION_FILE         = KNOWLEDGE_DIR + "current_session.json"
SESSION_LOG_FILE     = KNOWLEDGE_DIR + "session_log.json"
