from memory.episodic_memory import EpisodicMemory


class MemoryRouter:
    def __init__(self):
        self.episodic = EpisodicMemory()

        self.keywords = {
            "prefer": "User Preference",
            "preference": "User Preference",
            "remember": "Long-term Memory",
            "always": "Long-term Memory",
            "important": "Important Information",
            "email": "Communication Preference",
            "phone": "Communication Preference",
            "refund": "Business Policy",
            "policy": "Business Policy",
            "bug": "Bug Report",
            "feature": "Feature Request",
            "ticket": "Ticket Information",
            "customer": "Customer Information"
        }

    def evaluate(self, text):

        text_lower = text.lower()

        for keyword, reason in self.keywords.items():

            if keyword in text_lower:

                return {
                    "action": "promote",
                    "reason": reason,
                    "importance": 0.9
                }

        return {
            "action": "forget",
            "reason": "Temporary conversation",
            "importance": 0.2
        }

    def route(self, text):

        decision = self.evaluate(text)

        if decision["action"] == "promote":

            self.episodic.add_episode(
                content=text,
                reason=decision["reason"],
                importance=decision["importance"]
            )

        return decision