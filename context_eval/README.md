# Context Evaluation Module

This module evaluates different context management strategies for the Coderift Support MCP Agent.

The goal is to compare different approaches for handling long conversations, reducing context size, and maintaining response accuracy.

---

# Evaluated Strategies

## 1. Sliding Window

Sliding Window keeps only the most recent messages from the conversation history while removing older messages.

### Advantages:
- Simple implementation
- Low token usage
- Fast execution

### Disadvantages:
- May lose important historical information
- Older context can be removed


---

## 2. Observation & Tool Output Masking

This strategy reduces the size of MCP tool outputs by hiding unnecessary details and keeping only important information.

### Advantages:
- Reduces token consumption
- Suitable for MCP tool responses
- Keeps important observations

### Disadvantages:
- Some details may be removed
- Requires proper masking rules


---

## 3. Recursive Summarization

Recursive Summarization compresses previous conversations into summaries while keeping recent messages unchanged.

### Advantages:
- Preserves long-term information
- Good balance between accuracy and context size
- Suitable for long conversations

### Disadvantages:
- Requires additional processing
- Summaries may lose some details


---

## 4. Zone-Based Pruning

Zone-Based Pruning divides the conversation context into different zones:

- Old Zone: Removed
- Middle Zone: Compressed
- Recent Zone: Fully preserved

### Advantages:
- Efficient for very long conversations
- Maintains recent important information
- Reduces context size significantly


---

# Evaluation Metrics

## Accuracy

Accuracy measures whether the agent can correctly answer questions after applying each context strategy.

Formula:

```
Accuracy = Correct Responses / Total Tests
```

---

## Token Usage

Token Usage measures the approximate number of tokens required after applying each context reduction strategy.

Lower token usage provides:

- Lower model cost
- Faster processing
- Better scalability

---

## Latency

Latency measures the processing time required by each strategy.

Lower latency indicates faster context processing.


---

# Running Evaluation

Run the evaluation script from the project root:

```bash
cd context_eval

python evaluation.py
```

The generated evaluation results are saved automatically in:

```text
results.csv
```

---

# Comparison Results

The evaluation was performed on the four context management strategies.

| Strategy | Accuracy | Average Tokens | Average Latency |
|----------|----------|----------------|-----------------|
| Sliding Window | 100.0% | 18.5 | 0.0 |
| Observation Masking | 100.0% | 18.5 | 0.0 |
| Recursive Summarization | 100.0% | 20.5 | 0.0 |
| Zone Based Pruning | 100.0% | 19.5 | 0.0 |

---

# Best Strategy Selection

The best strategy is selected based on:

- Highest accuracy
- Lowest token usage
- Acceptable latency


Based on the evaluation results:

- All strategies achieved 100% accuracy.
- Sliding Window achieved the lowest token usage with 18.5 tokens.
- Observation Masking achieved the same token efficiency.
- Recursive Summarization used slightly more tokens because it preserves compressed historical context.
- Zone-Based Pruning provided a balance between keeping recent information and reducing context size.


## Selected Strategy

**Sliding Window** was selected as the best strategy because it achieved:

- Highest Accuracy: 100%
- Lowest Token Usage: 18.5 tokens
- Lowest Latency: 0.0


Observation Masking is also a suitable alternative when working with large MCP tool outputs.

---

# Project Structure

```
context_eval/
│
├── strategies.py
├── evaluation.py
├── test_cases.json
├── results.csv
└── README.md
```

---

# Conclusion

This evaluation module helps identify the most effective context management strategy for the Coderift Support MCP Agent.

The selected strategy improves long-context handling by reducing unnecessary information while maintaining accurate responses and efficient token usage.