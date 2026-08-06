import json
# ==========================================
# 1. Sliding Window Strategy
# ==========================================

def sliding_window(messages, window_size=6):

    """
    Keep only the most recent messages.
    """

    if len(messages) <= window_size:
        return messages

    return messages[-window_size:]



# ==========================================
# 2. Observation & Tool Output Masking
# ==========================================

def observation_masking(messages):

    """
    Remove large tool outputs and keep only a short summary.
    """

    masked = []

    for msg in messages:

        if msg["role"] == "tool":

            content = msg["content"]

            # Replace huge tool outputs
            if len(content) > 200:

                masked.append({

                    "role": "tool",

                    "content":
                    "Tool executed successfully. "
                    "Detailed output hidden to save context."

                })

            else:

                masked.append(msg)

        else:

            masked.append(msg)


    return masked




# ==========================================
# 3. Recursive Summarization
# ==========================================

def recursive_summarization(messages, keep_recent=4):

    """
    Compress old conversation into a summary.
    """

    if len(messages) <= keep_recent:

        return messages



    old_messages = messages[:-keep_recent]

    recent_messages = messages[-keep_recent:]



    summary_text = summarize_messages(old_messages)



    summarized_context = [

        {
            "role": "system",

            "content":
            f"Conversation Summary:\n{summary_text}"
        }

    ]



    summarized_context.extend(recent_messages)


    return summarized_context




def summarize_messages(messages):

    """
    Simple rule-based summarizer.
    """

    summary = []


    for msg in messages:

        if msg["role"] == "user":

            summary.append(
                f"User asked: {msg['content']}"
            )


        elif msg["role"] == "assistant":

            summary.append(
                "Assistant provided a response."
            )


        elif msg["role"] == "tool":

            summary.append(
                "A tool was used and returned information."
            )


    return " | ".join(summary)






# ==========================================
# 4. Zone Based Pruning
# ==========================================

def zone_based_pruning(
        messages,
        recent_zone=4,
        middle_zone=4
):

    """
    Divide context into zones:

    Old:
    Removed

    Middle:
    Compressed

    Recent:
    Kept
    """

    length = len(messages)



    if length <= recent_zone:

        return messages



    recent = messages[-recent_zone:]



    middle_start = max(
        0,
        length - recent_zone - middle_zone
    )


    middle = messages[middle_start:length-recent_zone]



    compressed_middle = {

        "role": "system",

        "content":
        f"Previous context contained {len(middle)} messages."

    }



    return [

        compressed_middle

    ] + recent