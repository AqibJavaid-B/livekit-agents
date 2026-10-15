from utils.constants import WAIT_PHRASES
from utils.logger import setup_logger

logger = setup_logger("stream_filter")


async def stream_filter(stream):
    buffer = []
    buffered_chunks = []
    last_content_chunk = None

    async for chunk in stream:
        # Skip invalid chunks early
        delta = getattr(chunk, "delta", None)
        if not delta:
            continue

        # pass through tool calls
        if hasattr(delta, "tool_calls") and delta.tool_calls:
            yield chunk
            continue

        content = getattr(delta, "content", None)
        if not content:
            buffered_chunks.append(chunk)
            continue

        buffer.append(content)
        last_content_chunk = chunk

        buffered_chunks.append(chunk)

    # Combine once
    full_buffer = "".join(buffer)
    lower_buffer = full_buffer.lower()


    #WAIT PHRASES (whole-output override)
    for phrase, replacement in WAIT_PHRASES.items():

        if phrase in lower_buffer:
            if last_content_chunk:
                last_delta = last_content_chunk.delta
                last_delta.content = replacement
                yield last_content_chunk

            logger.info("Suppressing remaining output due to WAIT phrase")
            return  # stop stream completely

    # Normal path — replay filtered chunks
    for chunk in buffered_chunks:
        delta = getattr(chunk, "delta", None)
        content = getattr(delta, "content", None)
        if content:
            yield chunk
