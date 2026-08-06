from memory.short_term import ShortTermMemory
from memory.scratchpad import Scratchpad
from memory.router import MemoryRouter
from memory.episodic_memory import EpisodicMemory
from memory.semantic_memory import SemanticMemory
from memory.consolidation import Consolidation


class MemoryManager:

    def __init__(self, buffer_size=10):

        self.short_term = ShortTermMemory(max_size=buffer_size)

        self.scratchpad = Scratchpad()

        self.router = MemoryRouter()

        self.episodic = EpisodicMemory()

        self.semantic = SemanticMemory()

        self.consolidation = Consolidation()


    def remember(self, role, content):

        self.short_term.add(role, content)

        if self.short_term.is_full():

            for message in self.short_term.get_memory():

                self.router.route(message["content"])

            self.short_term.clear()


    def consolidate(self):

        self.consolidation.consolidate()


    def get_short_memory(self):

        return self.short_term.get_memory()


    def get_episodic_memory(self):

        return self.episodic.get_all()


    def get_semantic_memory(self):

        return self.semantic.get_all()


    def build_context(self):

        context = {
            "short_term": self.get_short_memory(),
            "episodic": self.get_episodic_memory(),
            "semantic": self.get_semantic_memory()
        }

        return str(context)