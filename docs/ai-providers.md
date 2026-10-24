# AI providers

Radio Show Builder separates the editorial workflow from the provider. It needs text generation, not a particular vendor.

## Connection formats

- **OpenAI Responses:** instructions and brief sent to /responses.
- **OpenAI-compatible Chat:** system and user messages sent to /chat/completions.
- **Anthropic Messages:** system instructions and a user message sent to /messages using the API-key header.

Every response becomes the same validated rundown format. A service must support one of these formats; an API key alone cannot make an unrelated API compatible.

Requests avoid mandatory tools, provider-specific web search and strict structured-output extensions. The model is asked for JSON and the app validates it. Smaller models may fail to follow the structure.

## Configuration

Select a preset, enter your key, then choose **Load models**. The catalogue can contain embedding or audio models; select a text-generation model. Manual model IDs are always supported.

Advanced settings expose the base URL, API format, output-token limit and request timeout. Use a base URL, not a complete generation endpoint. Do not put credentials in the URL. Remote services require HTTPS; HTTP is limited to local servers.

Changing providers clears the key and model fields. Keys are not persisted across reloads.

## Local inference

Start the local API server and load a model separately.

- Ollama: http://localhost:11434/v1
- LM Studio: http://localhost:1234/v1

Provide a local-server key only if you have enabled authentication there. Local inference does not require a cloud account; the model must fit the computer's memory.

Local presets allow up to 30 minutes for a draft by default. Remote presets use five minutes. Adjust the request timeout, up to two hours, for slower models.

## Compatibility boundaries

Catalogue discovery calls /models. Some services do not support it, paginate it or expose only part of the catalogue. Enter IDs manually when necessary.

This release supports standard bearer authentication and Anthropic x-api-key authentication. AWS signing, Azure-specific API-key headers, Google service-account credentials and other proprietary authentication are not implemented.

Some models require different token-limit fields or message roles. Use a compatible gateway or add an adapter. Being listed in the catalogue does not guarantee suitability for a long JSON draft.

Provider tests use local mock servers. No paid account is silently used in testing. Validate a new service with a short draft using your own account.

## Research

This release does not browse automatically. Add reliable source notes before generation. The prompt asks the model to flag uncertainty and never invent source links or claim verification.

Review dates, names, quotations, connections, track versions and durations before recording.

## Official references

- [OpenAI text generation](https://developers.openai.com/api/docs/guides/text)
- [Anthropic Messages](https://platform.claude.com/docs/en/api/messages)
- [Gemini compatibility](https://ai.google.dev/gemini-api/docs/openai)
- [OpenRouter API](https://openrouter.ai/docs/api/reference/overview)
- [Mistral API](https://docs.mistral.ai/api/)
- [DeepSeek API](https://api-docs.deepseek.com/)
- [Groq compatibility](https://console.groq.com/docs/openai)
- [Together compatibility](https://docs.together.ai/docs/openai-api-compatibility)
- [Ollama compatibility](https://docs.ollama.com/api/openai-compatibility)
- [LM Studio compatibility](https://lmstudio.ai/docs/developer/openai-compat)
