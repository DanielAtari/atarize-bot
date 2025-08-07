# Critical Files Backup Inventory
## Backup Created: 2025-08-06 22:12:04
## Backup Location: ../atarize_bot_backup_20250806_221204/ (3.2GB)

### CORE BOT LOGIC (CRITICAL - DO NOT DELETE)
- `app.py` - Main Flask application and route handlers
- `services/chat_service.py` - Primary bot logic (1692 lines)
- `services/email_service.py` - Lead notification system
- `services/intent_service.py` - Intent detection
- `services/response_variation_service.py` - Response diversity
- `services/advanced_cache_service.py` - Performance caching
- `services/context_manager.py` - Context awareness
- `services/streaming_chat_service.py` - Streaming responses

### CONFIGURATION (CRITICAL)
- `config/settings.py` - Application configuration
- `config/logging_config.py` - Logging setup
- `core/database.py` - Database management
- `core/optimized_openai_client.py` - OpenAI client
- `data/system_prompt_atarize.txt` - Bot personality and instructions
- `data/intents_config.json` - Intent definitions
- `data/Atarize_bot_full_knowledge.json` - Knowledge base

### UTILITIES (IMPORTANT)
- `utils/text_utils.py` - Language detection and text processing
- `utils/validation_utils.py` - Lead detection and validation
- `utils/lead_parser.py` - Lead information parsing
- `utils/token_utils.py` - Token counting and usage tracking

### FRONTEND (CRITICAL)
- `static/` directory - React frontend components
- `templates/chat.html` - Chat interface template
- `package.json`, `vite.config.js`, `tailwind.config.js` - Build configuration

### ENVIRONMENT & DEPLOYMENT
- `.env` - Environment variables (contains sensitive data)
- `requirements.txt` - Python dependencies
- `deploy.sh`, `deploy_production.sh` - Deployment scripts

### SAFE TO DELETE AFTER BACKUP
#### Duplicate Directory (198MB)
- `atarize-bot/` - Complete duplicate of main project

#### Backup/Experimental Services
- `services/chat_service_WORKING_BACKUP_20250804_134139.py`
- `services/optimized_chat_service.py`
- `services/parallel_chat_service.py` 
- `services/async_chat_service.py`
- `services/cache_service.py`
- `services/fast_response_service.py`

#### Implementation Documentation (32 MD files - most can be archived)
- Various completion reports and analysis documents
- QA session reports (keep most recent only)
- Phase completion summaries

#### Log Files (can be cleaned)
- `logs/` directory - retain recent logs only
- Various simulation result JSON files

### BACKUP VERIFICATION
✅ Complete backup created at: ../atarize_bot_backup_20250806_221204/
✅ Backup size: 3.2GB (includes all duplicates and documentation)
✅ All critical files preserved in backup
✅ Ready for safe cleanup of unnecessary files

### RECOVERY INSTRUCTIONS
If anything goes wrong during cleanup:
1. Navigate to: /Users/danielatari/Desktop/Programming/atarize_bot_backup_20250806_221204/
2. Copy needed files back to main project
3. Full restore: `cp -r ../atarize_bot_backup_20250806_221204/* .`