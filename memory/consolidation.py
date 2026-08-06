from memory.episodic_memory import EpisodicMemory
from memory.semantic_memory import SemanticMemory


class Consolidation:

    def __init__(self):

        self.episodic = EpisodicMemory()

        self.semantic = SemanticMemory()

    def consolidate(self):

        episodes = self.episodic.get_all()

        for episode in episodes:

            if episode["importance"] < 0.5:
                continue

            text = episode["content"]

            words = text.split()

            if len(words) < 2:
                continue

            subject = words[0]

            fact = " ".join(words[1:])

            self.semantic.add_fact(subject, fact)

        print("Memory Consolidation Finished")