from collections import deque


class ShortTermMemory:
    def __init__(self, max_size=10):
        self.buffer = deque(maxlen=max_size)

    def add(self, role, content):
        self.buffer.append({
            "role": role,
            "content": content
        })

    def get_memory(self):
        return list(self.buffer)

    def clear(self):
        self.buffer.clear()

    def is_full(self):
        return len(self.buffer) == self.buffer.maxlen

    def size(self):
        return len(self.buffer)